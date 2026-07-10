"""US5 / FR-016: refuse a template that cannot record its own answers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from clerk import discovery, runner, trust
from clerk.errors import NotReproducibleError
from tests.conftest import TemplateRepo

_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "clerk.py"


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


# ---------------------------------------------------------------------------
# Direct-import tests (001-preserved library-level guarantees)
# ---------------------------------------------------------------------------


def test_discovery_reports_not_reproducible(no_answers_file_template: TemplateRepo) -> None:
    assert discovery.discover(no_answers_file_template.url).reproducible is False


def test_init_refuses_non_reproducible_template(
    no_answers_file_template: TemplateRepo, tmp_path: Path
) -> None:
    trust.add_trust(no_answers_file_template.url)  # trusted, but still refused
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=no_answers_file_template.url, dest=str(dest), answers={"project_name": "x"}
    )
    with pytest.raises(NotReproducibleError):
        runner.init(spec, today="2026-07-09")
    # nothing produced
    assert not (dest / "out.txt").exists()


# ---------------------------------------------------------------------------
# T016: scripts/clerk.py discover reports reproducible:false; init exits 1
# ---------------------------------------------------------------------------


def test_clerk_script_discover_reports_not_reproducible(
    no_answers_file_template: TemplateRepo, tmp_path: Path
) -> None:
    """scripts/clerk.py discover emits reproducible:false for a template without answers-file."""
    settings_path = tmp_path / "settings.yml"
    env = {**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)}

    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "discover", no_answers_file_template.url],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"discover failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    payload = json.loads(result.stdout)
    assert payload["reproducible"] is False


def test_clerk_script_init_exits_1_for_non_reproducible_template(
    no_answers_file_template: TemplateRepo, tmp_path: Path
) -> None:
    """scripts/clerk.py init exits 1 (ClerkError) for a template that can't record answers."""
    settings_path = tmp_path / "settings.yml"
    env = {**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)}

    trust.add_trust(no_answers_file_template.url)

    dest = tmp_path / "proj"
    run_spec = tmp_path / "run_spec.json"
    run_spec.write_text(
        json.dumps(
            {
                "source": no_answers_file_template.url,
                "dest": str(dest),
                "answers": {"project_name": "x"},
            }
        )
    )

    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "init", "--run-spec", str(run_spec)],
        capture_output=True,
        text=True,
        env=env,
    )
    # NotReproducibleError → ClerkError → exit 1
    assert result.returncode == 1
    assert not (dest / "out.txt").exists()
