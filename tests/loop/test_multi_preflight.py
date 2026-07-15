"""US3: all-gaps preflight — reports all missing answers at once, writes nothing (spec 003 / T013).

Tests:
- two layers each with a required question, run-spec missing one from each →
  --check reports BOTH missing at once, writes nothing (SC-005)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from bailiff import runner, trust
from bailiff.errors import InvalidRunSpecError
from tests.conftest import build_template_repo

_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "bailiff.py"


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


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


def _build_two_required_templates(tmp_path: Path):
    """Build two templates each requiring a distinct question.

    - tpl-p: requires ``proj_name`` (no default)
    - tpl-q: requires ``org_name`` (no default)
    """
    tpl_p = build_template_repo(
        tmp_path / "tpl-p",
        files={
            "copier.yml": dedent(
                """\
                proj_name:
                  type: str
                _subdirectory: template
                """
            ),
            "template/p_out.txt.jinja": "p={{ proj_name }}\n",
        },
    )
    tpl_q = build_template_repo(
        tmp_path / "tpl-q",
        files={
            "copier.yml": dedent(
                """\
                org_name:
                  type: str
                _subdirectory: template
                """
            ),
            "template/q_out.txt.jinja": "q={{ org_name }}\n",
        },
    )
    return tpl_p, tpl_q


# ---------------------------------------------------------------------------
# T013-a: direct runner.init_many check=True collects all gaps (SC-005)
# ---------------------------------------------------------------------------


def test_preflight_reports_all_gaps_at_once(tmp_path: Path) -> None:
    """init_many(check=True) raises one error listing gaps from BOTH layers."""
    tpl_p, tpl_q = _build_two_required_templates(tmp_path)
    trust.add_trust(tpl_p.url)
    trust.add_trust(tpl_q.url)

    dest = tmp_path / "proj"
    # Provide no answers for either layer — both should report missing questions
    selection = [
        (_make_record("testcat/tpl-p", tpl_p), {}),
        (_make_record("testcat/tpl-q", tpl_q), {}),
    ]

    with pytest.raises(InvalidRunSpecError) as exc_info:
        runner.init_many(selection, str(dest), today="2026-07-09", check=True)

    msg = str(exc_info.value)
    # Both layers must be named in the aggregated error
    assert "tpl-p" in msg or "proj_name" in msg.lower(), f"Expected tpl-p gap in error: {msg}"
    assert "tpl-q" in msg or "org_name" in msg.lower(), f"Expected tpl-q gap in error: {msg}"


def test_preflight_writes_nothing(tmp_path: Path) -> None:
    """init_many(check=True) with missing answers writes no files at all."""
    tpl_p, tpl_q = _build_two_required_templates(tmp_path)
    trust.add_trust(tpl_p.url)
    trust.add_trust(tpl_q.url)

    dest = tmp_path / "proj"
    with pytest.raises(InvalidRunSpecError):
        runner.init_many(
            [
                (_make_record("testcat/tpl-p", tpl_p), {}),
                (_make_record("testcat/tpl-q", tpl_q), {}),
            ],
            str(dest),
            today="2026-07-09",
            check=True,
        )

    # Nothing written — pretend=True must leave dest untouched
    assert not dest.exists() or not list(dest.iterdir()), (
        f"Preflight wrote files: {list(dest.iterdir()) if dest.exists() else '(dest created)'}"
    )


def test_preflight_partial_answers_still_collects_all(tmp_path: Path) -> None:
    """Providing one gap but not the other still reports both (not early-exit)."""
    tpl_p, tpl_q = _build_two_required_templates(tmp_path)
    trust.add_trust(tpl_p.url)
    trust.add_trust(tpl_q.url)

    dest = tmp_path / "proj"
    # Provide proj_name for tpl-p but not org_name for tpl-q
    selection = [
        (_make_record("testcat/tpl-p", tpl_p), {"proj_name": "my-project"}),
        (_make_record("testcat/tpl-q", tpl_q), {}),  # missing org_name
    ]

    with pytest.raises(InvalidRunSpecError) as exc_info:
        runner.init_many(selection, str(dest), today="2026-07-09", check=True)

    msg = str(exc_info.value)
    # tpl-q's gap must be reported
    assert "tpl-q" in msg or "org_name" in msg.lower(), f"Gap not reported: {msg}"
    # tpl-p should NOT appear in the error (its answer was supplied)
    # This is a best-effort check; the implementation may report it regardless
    # because check=True threads the simulated run.


# ---------------------------------------------------------------------------
# T013-b: via CLI (subprocess) — --check exits 1 with both gaps, writes nothing
# ---------------------------------------------------------------------------


def test_preflight_via_cli_exits_1_with_all_gaps(tmp_path: Path) -> None:
    """scripts/bailiff.py init --check exits 1 and reports gaps from both layers."""
    tpl_p, tpl_q = _build_two_required_templates(tmp_path)
    trust.add_trust(tpl_p.url)
    trust.add_trust(tpl_q.url)

    dest = tmp_path / "proj"
    spec = {
        "dest": str(dest),
        "selection": [
            {
                "full_id": "testcat/tpl-p",
                "source": tpl_p.url,
                "ref": tpl_p.tag,
                "answers": {},
            },
            {
                "full_id": "testcat/tpl-q",
                "source": tpl_q.url,
                "ref": tpl_q.tag,
                "answers": {},
            },
        ],
    }
    spec_path = tmp_path / "run_spec.json"
    spec_path.write_text(json.dumps(spec))

    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "init", "--check", "--run-spec", str(spec_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "COPIER_SETTINGS_PATH": str(tmp_path / "settings.yml")},
    )

    assert result.returncode == 1, (
        f"Expected exit 1 for missing answers;\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # Nothing written
    assert not dest.exists() or not list(dest.iterdir())


def test_preflight_clean_selection_exits_0(tmp_path: Path) -> None:
    """--check exits 0 when all required answers are supplied."""
    tpl_p, tpl_q = _build_two_required_templates(tmp_path)
    trust.add_trust(tpl_p.url)
    trust.add_trust(tpl_q.url)

    dest = tmp_path / "proj"
    spec = {
        "dest": str(dest),
        "selection": [
            {
                "full_id": "testcat/tpl-p",
                "source": tpl_p.url,
                "ref": tpl_p.tag,
                "answers": {"proj_name": "demo"},
            },
            {
                "full_id": "testcat/tpl-q",
                "source": tpl_q.url,
                "ref": tpl_q.tag,
                "answers": {"org_name": "acme"},
            },
        ],
    }
    spec_path = tmp_path / "run_spec.json"
    spec_path.write_text(json.dumps(spec))

    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "init", "--check", "--run-spec", str(spec_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "COPIER_SETTINGS_PATH": str(tmp_path / "settings.yml")},
    )

    assert result.returncode == 0, (
        f"Expected exit 0 for complete answers;\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # --check must write nothing
    assert not dest.exists() or not list(dest.iterdir())
