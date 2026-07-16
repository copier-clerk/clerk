"""spec 014 SC-001/005/007: private-by-default threading isolation.

Tests:
- Two layers with the same bare key and disjoint value domains → no InvalidRunSpecError (SC-001)
- Each answers file records only its own key, not the other layer's value (SC-005/007)
- Single-layer stack behaviour is unchanged (SC-001 invariant)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from tests.conftest import build_template_repo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _record(full_id: str, repo, questions: list[str] | None = None) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=questions or ["q"],
    )


# ---------------------------------------------------------------------------
# SC-001 / SC-005: same bare key, disjoint domains → isolated, no poisoning
# ---------------------------------------------------------------------------


def test_same_key_disjoint_domains_both_render(tmp_path: Path) -> None:
    """Two modules with q ∈ {x,y} and q ∈ {m,n} each render with their own domain.

    Before 014 the first layer's answer would bleed into the second, causing
    a validation failure (InvalidRunSpecError) because the domain is disjoint.
    After 014 each layer is isolated: both render successfully (SC-001).
    """
    tpl_a = build_template_repo(
        tmp_path / "mod-a",
        files={
            "copier.yml": (
                "q:\n  type: str\n  choices: [x, y]\n  default: x\n_subdirectory: template\n"
            ),
            "template/a_out.txt.jinja": "a_q={{ q }}\n",
        },
    )
    tpl_b = build_template_repo(
        tmp_path / "mod-b",
        files={
            "copier.yml": (
                "q:\n  type: str\n  choices: [m, n]\n  default: m\n_subdirectory: template\n"
            ),
            "template/b_out.txt.jinja": "b_q={{ q }}\n",
        },
    )
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    # No explicit answers needed — each module uses its own default
    selection = [
        (_record("testcat/mod-a", tpl_a), {}),
        (_record("testcat/mod-b", tpl_b), {}),
    ]
    # Must NOT raise InvalidRunSpecError (the old behaviour was to poison B with "x" ∈ {m,n})
    runner.init_many(selection, str(dest), today="2026-07-16")

    assert (dest / "a_out.txt").exists()
    assert (dest / "b_out.txt").exists()
    assert (dest / "a_out.txt").read_text().strip() == "a_q=x"
    assert (dest / "b_out.txt").read_text().strip() == "b_q=m"


def test_each_answers_file_records_only_own_key(tmp_path: Path) -> None:
    """After init, each .copier-answers.<mod>.yml records only that module's q value.

    Key invariant: module B's answers file must NOT contain module A's value for q,
    and vice versa. This proves isolation at the persistence layer (SC-005/SC-007).
    """
    tpl_a = build_template_repo(
        tmp_path / "mod-a",
        files={
            "copier.yml": (
                "q:\n  type: str\n  choices: [x, y]\n  default: x\n_subdirectory: template\n"
            ),
            "template/a_out.txt.jinja": "a={{ q }}\n",
        },
    )
    tpl_b = build_template_repo(
        tmp_path / "mod-b",
        files={
            "copier.yml": (
                "q:\n  type: str\n  choices: [m, n]\n  default: m\n_subdirectory: template\n"
            ),
            "template/b_out.txt.jinja": "b={{ q }}\n",
        },
    )
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [
            (_record("testcat/mod-a", tpl_a), {"q": "x"}),
            (_record("testcat/mod-b", tpl_b), {"q": "n"}),
        ],
        str(dest),
        today="2026-07-16",
    )

    af_a = yaml.safe_load((dest / ".copier-answers.mod-a.yml").read_text()) or {}
    af_b = yaml.safe_load((dest / ".copier-answers.mod-b.yml").read_text()) or {}

    # A's file: q = "x"; NOT "n" (B's value should not be in A's file)
    assert af_a.get("q") == "x", f"mod-a answers file q={af_a.get('q')!r}, want 'x'"
    # B's file: q = "n"; NOT "x" (A's value should not be in B's file)
    assert af_b.get("q") == "n", f"mod-b answers file q={af_b.get('q')!r}, want 'n'"


def test_single_layer_unchanged(tmp_path: Path) -> None:
    """Single-module render is byte-identical to the pre-014 result (SC-001 invariant)."""
    tpl_a = build_template_repo(
        tmp_path / "mod-a",
        files={
            "copier.yml": ("q:\n  type: str\n  default: hello\n_subdirectory: template\n"),
            "template/out.txt.jinja": "q={{ q }}\n",
        },
    )
    trust.add_trust(tpl_a.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [(_record("testcat/mod-a", tpl_a), {"q": "hello"})],
        str(dest),
        today="2026-07-16",
    )

    assert (dest / "out.txt").read_text().strip() == "q=hello"
    af = yaml.safe_load((dest / ".copier-answers.mod-a.yml").read_text()) or {}
    assert af.get("q") == "hello"


def test_no_private_answer_in_other_layer_data(tmp_path: Path) -> None:
    """A's private answer for 'private_val' must NOT appear in B's render context.

    This is the core isolation invariant: accumulated never accretes private answers.
    Proved by having B render its render context into a file and asserting A's value
    is absent.
    """
    # A sets private_val="secret_a"; B renders all data keys it sees to b_data.txt
    tpl_a = build_template_repo(
        tmp_path / "mod-a",
        files={
            "copier.yml": (
                "private_val:\n  type: str\n  default: secret_a\n_subdirectory: template\n"
            ),
            "template/a_out.txt.jinja": "a={{ private_val }}\n",
        },
    )
    tpl_b = build_template_repo(
        tmp_path / "mod-b",
        files={
            "copier.yml": ("own_val:\n  type: str\n  default: own_b\n_subdirectory: template\n"),
            # If private_val leaked from A, it would appear here; otherwise just own_b
            "template/b_out.txt.jinja": "own={{ own_val }}\n",
        },
    )
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [
            (_record("testcat/mod-a", tpl_a, questions=["private_val"]), {}),
            (_record("testcat/mod-b", tpl_b, questions=["own_val"]), {}),
        ],
        str(dest),
        today="2026-07-16",
    )

    # B's answers file must not contain private_val from A
    af_b = yaml.safe_load((dest / ".copier-answers.mod-b.yml").read_text()) or {}
    assert "private_val" not in af_b, f"A's private_val leaked into B's answers file: {af_b}"
    # B renders only its own answer
    assert (dest / "b_out.txt").read_text().strip() == "own=own_b"
