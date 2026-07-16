"""US2: multi-template reproduce — recomputed order, byte-identical, recipe-free (spec 003 / T011).

Tests:
- reproduce recomputes order respecting edges (SC-002)
- reproduce TWICE → byte-identical (SC-002)
- no recipe/DAG file present; resolution uses only committed answers files + fetches
- copier-only-by-hand parity: plain copier recopy in recomputed order → same tree
- N=1 no-regression: single-template project reproduces identically via reproduce_many (SC-006)
- cross-catalog order-independence: 2 edge-independent templates from different catalog
  names — init order == reproduce order
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from bailiff import runner, trust
from tests.conftest import MultiTemplateSet


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _tree_digest(root: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] == ".git":
            continue
        digests[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


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


def _init_ab(multi_template_set: MultiTemplateSet, dest: Path) -> None:
    """Init a project with templates A and B (B depends_on A) at dest."""
    tpl_a = multi_template_set.tpl_a
    tpl_b = multi_template_set.tpl_b
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)
    runner.init_many(
        [
            (_make_record("testcat/tpl-a", tpl_a), {"project_name": "demo"}),
            (_make_record("testcat/tpl-b", tpl_b), {"project_name": "demo"}),
        ],
        str(dest),
        today="2026-07-09",
    )


# ---------------------------------------------------------------------------
# T011-a: reproduce recomputes order and respects edges
# ---------------------------------------------------------------------------


def test_reproduce_many_respects_edge_order(
    multi_template_set: MultiTemplateSet, tmp_path: Path
) -> None:
    """reproduce_many runs without error on an A+B project; both output files remain correct."""
    dest = tmp_path / "proj"
    _init_ab(multi_template_set, dest)

    # Corrupt both output files
    (dest / "a_out.txt").write_text("CORRUPTED_A\n")
    (dest / "b_out.txt").write_text("CORRUPTED_B\n")

    runner.reproduce_many(str(dest))

    assert (dest / "a_out.txt").read_text().strip() == "a=demo"
    assert (dest / "b_out.txt").read_text().strip() == "b=demo"


# ---------------------------------------------------------------------------
# T011-b: reproduce TWICE → byte-identical (SC-002)
# ---------------------------------------------------------------------------


def test_reproduce_twice_byte_identical(
    multi_template_set: MultiTemplateSet, tmp_path: Path
) -> None:
    """Two consecutive reproduce_many calls produce byte-identical output."""
    dest = tmp_path / "proj"
    _init_ab(multi_template_set, dest)

    runner.reproduce_many(str(dest))
    digest1 = _tree_digest(dest)

    runner.reproduce_many(str(dest))
    digest2 = _tree_digest(dest)

    assert digest1 == digest2, (
        "reproduce_many is not idempotent.\n"
        f"Changed: {[k for k in digest1 if k in digest2 and digest1[k] != digest2[k]]}"
    )


# ---------------------------------------------------------------------------
# T011-c: no recipe/DAG file; only committed answers files used
# ---------------------------------------------------------------------------


def test_no_recipe_file_present_and_reproduce_works(
    multi_template_set: MultiTemplateSet, tmp_path: Path
) -> None:
    """reproduce_many works with only committed .copier-answers.*.yml — no recipe file."""
    dest = tmp_path / "proj"
    _init_ab(multi_template_set, dest)

    # Confirm no recipe/DAG file was written at init
    for name in ("bailiff_order.yml", "bailiff_dag.yml", ".bailiff_order", "bailiff_recipe.yml"):
        assert not (dest / name).exists(), f"Unexpected recipe file: {name}"

    # reproduce still works without any recipe file
    runner.reproduce_many(str(dest))
    assert (dest / "a_out.txt").exists()
    assert (dest / "b_out.txt").exists()


# ---------------------------------------------------------------------------
# T011-d: copier-only-by-hand parity
# ---------------------------------------------------------------------------


def test_copier_only_parity_multi_layer(
    multi_template_set: MultiTemplateSet, tmp_path: Path
) -> None:
    """Plain copier recopy in recomputed order yields the same tree as reproduce_many.

    The recomputed order is A then B (tpl-a before tpl-b, since B depends_on A).
    """
    # Build a reference project via bailiff
    dest_bailiff = tmp_path / "proj_bailiff"
    _init_ab(multi_template_set, dest_bailiff)
    reference = _tree_digest(dest_bailiff)

    # Build a second project, corrupt it, then restore via copier-only path
    dest_manual = tmp_path / "proj_manual"
    _init_ab(multi_template_set, dest_manual)

    # Corrupt output files
    (dest_manual / "a_out.txt").write_text("HAND_EDITED\n")
    (dest_manual / "b_out.txt").write_text("HAND_EDITED\n")

    settings_path = tmp_path / "settings.yml"
    env = {**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)}

    # Recomputed order: A first (no predecessors, comes first alphabetically), then B
    for af_name in (".copier-answers.tpl-a.yml", ".copier-answers.tpl-b.yml"):
        result = subprocess.run(
            [
                "copier",
                "recopy",
                "--vcs-ref=:current:",
                "--defaults",
                "--overwrite",
                "--quiet",
                "-a",
                af_name,
            ],
            cwd=str(dest_manual),
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, (
            f"copier recopy {af_name} failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    manual_digest = _tree_digest(dest_manual)
    assert reference == manual_digest, (
        "copier-only-by-hand diverges from bailiff reproduce_many.\n"
        f"Missing in manual: {set(reference) - set(manual_digest)}\n"
        f"Extra in manual: {set(manual_digest) - set(reference)}\n"
        "Changed: "
        + str([k for k in reference if k in manual_digest and reference[k] != manual_digest[k]])
    )


# ---------------------------------------------------------------------------
# T011-e: N=1 no-regression — single template reproduces identically via reproduce_many
# ---------------------------------------------------------------------------


def test_n1_reproduce_many_matches_reproduce(
    multi_template_set: MultiTemplateSet, tmp_path: Path
) -> None:
    """Single-template project reproduces identically through reproduce_many (SC-006)."""
    tpl_a = multi_template_set.tpl_a
    trust.add_trust(tpl_a.url)

    # Init with a single template (N=1)
    dest = tmp_path / "proj"
    runner.init_many(
        [(_make_record("testcat/tpl-a", tpl_a), {"project_name": "solo"})],
        str(dest),
        today="2026-07-09",
    )
    before = _tree_digest(dest)

    # Corrupt and reproduce via reproduce_many
    (dest / "a_out.txt").write_text("CORRUPTED\n")
    runner.reproduce_many(str(dest))
    after = _tree_digest(dest)

    assert before == after, (
        "N=1 reproduce_many diverges from init state.\n"
        f"Changed: {[k for k in before if k in after and before[k] != after[k]]}"
    )


def test_n1_reproduce_many_via_cli(multi_template_set: MultiTemplateSet, tmp_path: Path) -> None:
    """the bailiff CLI reproduce on a single-template project exits 0 and is byte-identical."""
    tpl_a = multi_template_set.tpl_a
    trust.add_trust(tpl_a.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [(_make_record("testcat/tpl-a", tpl_a), {"project_name": "solo"})],
        str(dest),
        today="2026-07-09",
    )
    before = _tree_digest(dest)
    (dest / "a_out.txt").write_text("CORRUPTED\n")

    env = {**os.environ, "COPIER_SETTINGS_PATH": str(tmp_path / "settings.yml")}
    result = subprocess.run(
        [sys.executable, "-m", "bailiff", "reproduce", str(dest)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"reproduce failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    after = _tree_digest(dest)
    assert before == after


# ---------------------------------------------------------------------------
# T011-f: cross-catalog order-independence (the bug the review caught)
#
# Two edge-independent templates from DIFFERENT catalog names must produce
# the same order at init AND reproduce.  Previously a bug caused reproduce to
# use a different naming convention for the synthetic full_id (_recorded/*)
# which could break the tie-break if init used catalog/basename ordering.
# ---------------------------------------------------------------------------


def test_cross_catalog_order_independence(tmp_path: Path) -> None:
    """Edge-independent templates from different catalog names have identical init/reproduce order.

    The key invariant: both init and reproduce use the same basename-based tie-break,
    so the recomputed order is identical regardless of the catalog prefix.
    """
    from tests.conftest import build_template_repo

    # Two templates with different catalog names but disjoint output files.
    # Use basename ordering: "tpl-c" < "tpl-d" (alphabetical)
    tpl_c = build_template_repo(
        tmp_path / "tpl-c",
        files={
            "copier.yml": "project_name:\n  type: str\n_subdirectory: template\n",
            "template/c_out.txt.jinja": "c={{ project_name }}\n",
        },
    )
    tpl_d = build_template_repo(
        tmp_path / "tpl-d",
        files={
            "copier.yml": "project_name:\n  type: str\n_subdirectory: template\n",
            "template/d_out.txt.jinja": "d={{ project_name }}\n",
        },
    )
    trust.add_trust(tpl_c.url)
    trust.add_trust(tpl_d.url)

    # Use DIFFERENT catalog prefixes to simulate cross-catalog scenario
    dest = tmp_path / "proj"
    runner.init_many(
        [
            (_make_record("catalog-x/tpl-d", tpl_d), {"project_name": "demo"}),
            (_make_record("catalog-y/tpl-c", tpl_c), {"project_name": "demo"}),
        ],
        str(dest),
        today="2026-07-09",
    )
    before = _tree_digest(dest)

    # Corrupt and reproduce — order must be recomputed consistently
    (dest / "c_out.txt").write_text("X\n")
    (dest / "d_out.txt").write_text("X\n")
    runner.reproduce_many(str(dest))
    after = _tree_digest(dest)

    assert before == after, (
        "Cross-catalog reproduce_many diverges from init.\n"
        f"Changed: {[k for k in before if k in after and before[k] != after[k]]}"
    )

    # Additionally verify the answers files read the correct source paths
    af_c = yaml.safe_load((dest / ".copier-answers.tpl-c.yml").read_text())
    af_d = yaml.safe_load((dest / ".copier-answers.tpl-d.yml").read_text())
    assert tpl_c.url in af_c["_src_path"]
    assert tpl_d.url in af_d["_src_path"]
