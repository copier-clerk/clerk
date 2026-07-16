"""US1: multi-template init — ordered apply, threaded answers, order-independence (spec 003 / T009).

Tests:
- B depends_on A, selection mis-ordered [B, A] → A applies before B (SC-001)
- each layer commits its own .copier-answers.<name>.yml
- a threaded answer from A is visible as B's default (SC-001)
- order-independence: init [C, D] and [D, C] → byte-identical trees (SC-003)
- no bailiff recipe/order file present in dest (SC-002 partial)
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from bailiff import runner, trust
from tests.conftest import MultiTemplateSet, make_multi_run_spec


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _tree_digest(root: Path) -> dict[str, str]:
    """SHA-256 digest of every non-.git file, keyed by relative path."""
    digests: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] == ".git":
            continue
        digests[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


# ---------------------------------------------------------------------------
# T009-a: B depends_on A, mis-ordered selection → A applies before B
# ---------------------------------------------------------------------------


def test_init_many_b_depends_on_a_applied_in_order(
    multi_template_set: MultiTemplateSet, tmp_path: Path
) -> None:
    """Selection [B, A] must apply A first because B depends_on A."""
    tpl_a = multi_template_set.tpl_a
    tpl_b = multi_template_set.tpl_b
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    # Selection deliberately given in wrong order (B before A)
    selection = [
        (_make_record("testcat/tpl-b", tpl_b), {"project_name": "demo"}),
        (_make_record("testcat/tpl-a", tpl_a), {"project_name": "demo"}),
    ]
    runner.init_many(selection, str(dest), today="2026-07-09")

    # Both output files must exist
    assert (dest / "a_out.txt").exists(), "A's output file missing"
    assert (dest / "b_out.txt").exists(), "B's output file missing"
    # Both answers files must be committed
    assert (dest / ".copier-answers.tpl-a.yml").exists()
    assert (dest / ".copier-answers.tpl-b.yml").exists()


def test_init_many_per_layer_answers_files(
    multi_template_set: MultiTemplateSet, tmp_path: Path
) -> None:
    """Each layer writes its own .copier-answers.<basename>.yml."""
    tpl_a = multi_template_set.tpl_a
    tpl_b = multi_template_set.tpl_b
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    selection = [
        (_make_record("testcat/tpl-a", tpl_a), {"project_name": "demo"}),
        (_make_record("testcat/tpl-b", tpl_b), {"project_name": "demo"}),
    ]
    runner.init_many(selection, str(dest), today="2026-07-09")

    af_a = yaml.safe_load((dest / ".copier-answers.tpl-a.yml").read_text())
    af_b = yaml.safe_load((dest / ".copier-answers.tpl-b.yml").read_text())

    # Each records its own source
    assert tpl_a.url in af_a["_src_path"]
    assert tpl_b.url in af_b["_src_path"]


# ---------------------------------------------------------------------------
# T009-b: threaded answers — A's answer visible in B's context
# ---------------------------------------------------------------------------


def _make_threading_templates(tmp_path: Path):
    """Build A (sets project_name) and B (depends_on A, references project_name as default)."""
    from tests.conftest import build_template_repo

    # A: sets project_name, writes it to a_out.txt
    tpl_a = build_template_repo(
        tmp_path / "tpl-a",
        files={
            "copier.yml": ("project_name:\n  type: str\n_subdirectory: template\n"),
            "template/a_out.txt.jinja": "a={{ project_name }}\n",
        },
    )
    # B: depends_on A; uses project_name from threading (no explicit answer given),
    # writes it to b_out.txt to verify the threaded value arrived.
    tpl_b = build_template_repo(
        tmp_path / "tpl-b",
        files={
            "copier.yml": (
                "project_name:\n"
                "  type: str\n"
                "  default: ''\n"
                "depends_on:\n"
                "  type: yaml\n"
                '  default: ["tpl-a"]\n'
                "  when: false\n"
                "_subdirectory: template\n"
            ),
            "template/b_out.txt.jinja": "b={{ project_name }}\n",
        },
    )
    return tpl_a, tpl_b


def test_threaded_answer_from_a_visible_in_b(tmp_path: Path) -> None:
    """A's project_name answer threads into B — no explicit project_name needed for B."""
    tpl_a, tpl_b = _make_threading_templates(tmp_path)
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    # Only supply project_name to A; B should inherit it via threading
    selection = [
        (_make_record("testcat/tpl-b", tpl_b), {}),  # no explicit answer
        (_make_record("testcat/tpl-a", tpl_a), {"project_name": "threaded-value"}),
    ]
    runner.init_many(selection, str(dest), today="2026-07-09")

    b_out = (dest / "b_out.txt").read_text().strip()
    assert b_out == "b=threaded-value", (
        f"Expected B to receive threaded project_name, got: {b_out!r}"
    )


# ---------------------------------------------------------------------------
# T009-c: order-independence — [C, D] and [D, C] → byte-identical trees (SC-003)
# ---------------------------------------------------------------------------


def test_order_independence_c_and_d(multi_template_set: MultiTemplateSet, tmp_path: Path) -> None:
    """Edge-independent C and D produce byte-identical trees regardless of selection order."""
    tpl_c = multi_template_set.tpl_c
    tpl_d = multi_template_set.tpl_d
    trust.add_trust(tpl_c.url)
    trust.add_trust(tpl_d.url)

    dest_cd = tmp_path / "proj_cd"
    dest_dc = tmp_path / "proj_dc"

    # init [C, D]
    runner.init_many(
        [
            (_make_record("testcat/tpl-c", tpl_c), {"project_name": "demo"}),
            (_make_record("testcat/tpl-d", tpl_d), {"project_name": "demo"}),
        ],
        str(dest_cd),
        today="2026-07-09",
    )
    # init [D, C] — reversed
    runner.init_many(
        [
            (_make_record("testcat/tpl-d", tpl_d), {"project_name": "demo"}),
            (_make_record("testcat/tpl-c", tpl_c), {"project_name": "demo"}),
        ],
        str(dest_dc),
        today="2026-07-09",
    )

    digest_cd = _tree_digest(dest_cd)
    digest_dc = _tree_digest(dest_dc)

    assert digest_cd == digest_dc, (
        "Order-independent [C,D] vs [D,C] produced different trees.\n"
        f"Only in CD: {set(digest_cd) - set(digest_dc)}\n"
        f"Only in DC: {set(digest_dc) - set(digest_cd)}\n"
        f"Differing: {[k for k in digest_cd if k in digest_dc and digest_cd[k] != digest_dc[k]]}"
    )


# ---------------------------------------------------------------------------
# T009-d: no bailiff recipe/order file in dest (SC-002 partial)
# ---------------------------------------------------------------------------


def test_no_bailiff_order_file_in_dest(
    multi_template_set: MultiTemplateSet, tmp_path: Path
) -> None:
    """After multi-template init, dest contains no bailiff-authored order/recipe file."""
    tpl_a = multi_template_set.tpl_a
    tpl_b = multi_template_set.tpl_b
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [
            (_make_record("testcat/tpl-a", tpl_a), {"project_name": "demo"}),
            (_make_record("testcat/tpl-b", tpl_b), {"project_name": "demo"}),
        ],
        str(dest),
        today="2026-07-09",
    )

    # No bailiff recipe or order file
    for name in (
        "bailiff_order.yml",
        "bailiff_order.yaml",
        "bailiff_dag.yml",
        ".bailiff_order",
        "justfile",
        "Justfile",
    ):
        assert not (dest / name).exists(), f"Unexpected bailiff file: {name}"

    # Only .copier-answers.* files are committed metadata
    order_files = list(dest.glob("*order*")) + list(dest.glob("*recipe*"))
    assert not order_files, f"Unexpected order/recipe files: {order_files}"


# ---------------------------------------------------------------------------
# T009-e: via CLI (subprocess) — multi run-spec, mis-ordered selection
# ---------------------------------------------------------------------------


def test_init_many_via_cli_mis_ordered(
    multi_template_set: MultiTemplateSet, tmp_path: Path
) -> None:
    """the bailiff CLI init with multi run-spec (B before A) applies in correct order."""
    tpl_a = multi_template_set.tpl_a
    tpl_b = multi_template_set.tpl_b
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    # Selection deliberately mis-ordered [B, A]
    spec = make_multi_run_spec(
        dest,
        [
            ("testcat/tpl-b", tpl_b, {"project_name": "demo"}),
            ("testcat/tpl-a", tpl_a, {"project_name": "demo"}),
        ],
    )
    spec_path = tmp_path / "run_spec.json"
    spec_path.write_text(json.dumps(spec))

    result = subprocess.run(
        [sys.executable, "-m", "bailiff", "init", "--run-spec", str(spec_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "COPIER_SETTINGS_PATH": str(tmp_path / "settings.yml")},
    )
    assert result.returncode == 0, (
        f"multi init failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert (dest / "a_out.txt").exists()
    assert (dest / "b_out.txt").exists()


# ---------------------------------------------------------------------------
# Helper (defined here, also exported for other test modules)
# ---------------------------------------------------------------------------


def _make_record(full_id: str, repo):
    from bailiff.catalog import TemplateRecord

    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=["project_name"],
    )
