"""Smoke test: the package imports and the CLI entry point runs."""

from __future__ import annotations

import clerk
from clerk.cli import main


def test_version_is_set() -> None:
    assert clerk.__version__


def test_cli_runs() -> None:
    assert main([]) == 0
    assert main(["--version"]) == 0
