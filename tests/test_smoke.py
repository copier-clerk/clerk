"""Smoke test: the package imports and the CLI entry point runs."""

from __future__ import annotations

import subprocess
import sys

import bailiff


def test_version_is_set() -> None:
    assert bailiff.__version__


def test_cli_help_exits_0() -> None:
    # The CLI's --help must exit 0 (never a bare stack trace, FR-010).
    result = subprocess.run(
        [sys.executable, "-m", "bailiff", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "bailiff" in result.stdout


def test_cli_version_flag() -> None:
    # -V / --version prints the package version and exits 0.
    result = subprocess.run(
        [sys.executable, "-m", "bailiff", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert bailiff.__version__ in result.stdout
