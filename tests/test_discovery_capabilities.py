"""Unit tests for static capability parsing in discovery (spec 013 T005).

Exercises ``_describe`` directly on an on-disk fixture tree — no clones, no
network — so parsing stays in the same safety class as _tasks/_migrations reads.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
import yaml

from bailiff.discovery import _describe


def _describe_fixture(tmp_path: Path, config: dict[str, object]):
    (tmp_path / "copier.yml").write_text(yaml.safe_dump(config))
    return _describe("mem://fixture", "v1.0.0", ["v1.0.0"], tmp_path)


def test_well_formed_provides_and_exclusive(tmp_path: Path) -> None:
    desc = _describe_fixture(
        tmp_path,
        {
            "_bailiff_provides": ["python-project", "ci"],
            "_bailiff_exclusive": True,
            "project_name": {"type": "str", "default": "x"},
        },
    )
    assert desc.provides == ["python-project", "ci"]
    assert desc.exclusive is True


@pytest.mark.parametrize("config", [{}, {"_bailiff_provides": []}])
def test_absent_or_empty_provides(tmp_path: Path, config: dict[str, object]) -> None:
    desc = _describe_fixture(tmp_path, config)
    assert desc.provides == []
    assert desc.exclusive is False


def test_malformed_non_list_provides_warns_and_treated_absent(tmp_path: Path) -> None:
    with pytest.warns(UserWarning, match="_bailiff_provides"):
        desc = _describe_fixture(tmp_path, {"_bailiff_provides": "python-project"})
    assert desc.provides == []


def test_non_kebab_case_entry_warned_and_dropped(tmp_path: Path) -> None:
    with pytest.warns(UserWarning, match="kebab-case"):
        desc = _describe_fixture(
            tmp_path, {"_bailiff_provides": ["Python_Project", "valid-cap", 42]}
        )
    # only the well-formed entry survives
    assert desc.provides == ["valid-cap"]


def test_exclusive_false_and_absent_equivalent(tmp_path: Path) -> None:
    desc_false = _describe_fixture(tmp_path, {"_bailiff_exclusive": False})
    assert desc_false.exclusive is False


def test_malformed_exclusive_warns_and_treated_absent(tmp_path: Path) -> None:
    with pytest.warns(UserWarning, match="_bailiff_exclusive"):
        desc = _describe_fixture(tmp_path, {"_bailiff_exclusive": "yes please"})
    assert desc.exclusive is False


def test_to_dict_includes_capability_fields(tmp_path: Path) -> None:
    desc = _describe_fixture(
        tmp_path, {"_bailiff_provides": ["quality"], "_bailiff_exclusive": True}
    )
    d = desc.to_dict()
    assert d["provides"] == ["quality"]
    assert d["exclusive"] is True


def test_no_warning_on_well_formed_declarations(tmp_path: Path) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        desc = _describe_fixture(tmp_path, {"_bailiff_provides": ["a-cap"]})
    assert desc.provides == ["a-cap"]
