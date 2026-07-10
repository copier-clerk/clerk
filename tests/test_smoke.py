"""Smoke test: the package imports and the CLI entry point runs."""

from __future__ import annotations

import pytest

import clerk
from clerk.cli import main


def test_version_is_set() -> None:
    assert clerk.__version__


def test_cli_no_args_prints_help() -> None:
    # No subcommand: print help and exit 0 (never a bare stack trace, FR-010).
    assert main([]) == 0


def test_cli_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    # argparse's version action prints and raises SystemExit(0).
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert clerk.__version__ in capsys.readouterr().out
