"""Smoke test: the package imports and the script entry point runs."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import bailiff

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "bailiff.py"


def test_version_is_set() -> None:
    assert bailiff.__version__


def test_script_help_exits_0() -> None:
    # The bundled script's --help must exit 0 (never a bare stack trace, FR-010).
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "bailiff.py" in result.stdout


def test_script_version_flag() -> None:
    # -V / --version prints the package version and exits 0.
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert bailiff.__version__ in result.stdout
