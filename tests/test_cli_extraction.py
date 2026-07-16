"""Tests for the extracted CLI module (spec 013 T013)."""

from __future__ import annotations

import pytest

from bailiff.cli import main


def test_version_flag_exits_zero(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "bailiff" in out


def test_doctor_exits_zero_in_dev_env() -> None:
    assert main(["doctor"]) == 0


def test_catalog_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["catalog", "--help"])
    assert exc_info.value.code == 0


def test_no_command_prints_help(capsys) -> None:
    assert main([]) == 0
    assert "usage: bailiff" in capsys.readouterr().out


def test_unknown_verb_exits_two() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["frobnicate"])
    assert exc_info.value.code == 2


def test_prog_name_is_bailiff(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    assert "usage: bailiff" in capsys.readouterr().out
