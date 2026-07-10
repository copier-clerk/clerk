"""T019 / US4 / FR-001 / SC-003: no console-script; bundled script is the entry point."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib  # stdlib ≥3.11
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_SCRIPT = _REPO_ROOT / "scripts" / "clerk.py"


def test_no_project_scripts_entry() -> None:
    """pyproject.toml must declare NO `[project.scripts] clerk` entry (FR-001)."""
    data = tomllib.loads(_PYPROJECT.read_text())
    scripts = data.get("project", {}).get("scripts", {})
    assert "clerk" not in scripts, (
        f"[project.scripts] still declares 'clerk'; found keys: {list(scripts)}"
    )


def test_script_exists_and_is_executable() -> None:
    """scripts/clerk.py must exist and carry the executable bit."""
    assert _SCRIPT.exists(), f"scripts/clerk.py not found at {_SCRIPT}"
    assert os.access(_SCRIPT, os.X_OK), "scripts/clerk.py is not executable"


def test_script_help_via_uv_run() -> None:
    """`uv run python scripts/clerk.py --help` must exit 0."""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "clerk.py" in result.stdout
