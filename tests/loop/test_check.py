"""US6 / FR-006, FR-008: check mode validates via the engine dry run, writes nothing."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bailiff import runner, trust
from bailiff.errors import InvalidRunSpecError, UntrustedSourceError
from tests.conftest import TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


# ---------------------------------------------------------------------------
# Direct-import tests (001-preserved library-level guarantees)
# ---------------------------------------------------------------------------


def test_check_clean_produces_no_files(base_template: TemplateRepo, tmp_path: Path) -> None:
    trust.add_trust(base_template.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=base_template.url, dest=str(dest), answers={"project_name": "demo"}
    )
    result = runner.init(spec, today="2026-07-09", check=True)
    assert result.pretend is True
    # nothing written
    assert not (dest / "out.txt").exists()


def test_check_missing_answer_reports_and_writes_nothing(
    base_template: TemplateRepo, tmp_path: Path
) -> None:
    trust.add_trust(base_template.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(source=base_template.url, dest=str(dest), answers={})
    with pytest.raises(InvalidRunSpecError):
        runner.init(spec, today="2026-07-09", check=True)
    assert not (dest / "out.txt").exists()


def test_check_untrusted_reports_untrusted_precedence(
    base_template: TemplateRepo, tmp_path: Path
) -> None:
    # untrusted AND missing an answer → untrusted-source condition takes precedence,
    # because the engine (and bailiff's pre-check) verify trust before answers.
    dest = tmp_path / "proj"
    spec = runner.RunSpec(source=base_template.url, dest=str(dest), answers={})
    with pytest.raises(UntrustedSourceError):
        runner.init(spec, today="2026-07-09", check=True)


# ---------------------------------------------------------------------------
# T015: the bailiff CLI init --check via subprocess
# ---------------------------------------------------------------------------


def test_check_via_bailiff_script_writes_nothing(
    base_template: TemplateRepo, tmp_path: Path
) -> None:
    """the bailiff CLI init --check exits 0 and writes nothing."""
    settings_path = tmp_path / "settings.yml"
    env = {**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)}

    trust.add_trust(base_template.url)

    dest = tmp_path / "proj"
    run_spec = tmp_path / "run_spec.json"
    run_spec.write_text(
        json.dumps(
            {"source": base_template.url, "dest": str(dest), "answers": {"project_name": "demo"}}
        )
    )

    result = subprocess.run(
        [sys.executable, "-m", "bailiff", "init", "--check", "--run-spec", str(run_spec)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"bailiff.py init --check failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # --check must write nothing (FR-006 / FR-008)
    assert not dest.exists() or not (dest / "out.txt").exists()
    assert "inputs valid" in result.stdout


def test_check_via_bailiff_script_exits_1_on_missing_answer(
    base_template: TemplateRepo, tmp_path: Path
) -> None:
    """the bailiff CLI init --check exits 1 when a required answer is absent."""
    settings_path = tmp_path / "settings.yml"
    env = {**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)}

    trust.add_trust(base_template.url)

    dest = tmp_path / "proj"
    run_spec = tmp_path / "run_spec.json"
    run_spec.write_text(json.dumps({"source": base_template.url, "dest": str(dest), "answers": {}}))

    result = subprocess.run(
        [sys.executable, "-m", "bailiff", "init", "--check", "--run-spec", str(run_spec)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 1
    assert not (dest / "out.txt").exists()
