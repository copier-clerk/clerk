"""Single-source version tests (spec 013 T014)."""

from __future__ import annotations

from importlib.metadata import version as dist_version

import pytest

from bailiff import __version__
from bailiff.cli import main


def test_version_is_nonempty_string() -> None:
    assert isinstance(__version__, str) and __version__


def test_version_matches_dist_metadata() -> None:
    assert __version__ == dist_version("bailiff")


def test_cli_version_output_contains_version(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    assert __version__ in capsys.readouterr().out
