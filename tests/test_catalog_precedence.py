"""Unit tests for multi-catalog first-listed-wins precedence (spec 013 T011)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
import tomli_w

from bailiff.catalog import build_listing, validate_selection
from tests.conftest import build_template_repo

_YML = "project_name:\n  type: str\n_subdirectory: template\n"


@pytest.fixture
def shadow_catalog(tmp_path: Path) -> Path:
    """Two pointers each carrying a module with the same bare name, plus one
    unshadowed module in the second pointer."""
    repo_first = build_template_repo(
        tmp_path / "internal" / "tpl-shared",
        files={"copier.yml": _YML, "template/first.txt.jinja": "first\n"},
    )
    repo_second = build_template_repo(
        tmp_path / "public" / "tpl-shared",
        files={"copier.yml": _YML, "template/second.txt.jinja": "second\n"},
    )
    repo_other = build_template_repo(
        tmp_path / "public" / "tpl-other",
        files={"copier.yml": _YML, "template/other.txt.jinja": "other\n"},
    )
    data = {
        "catalog": [
            {"name": "internal", "sources": [repo_first.url]},
            {"name": "public", "sources": [repo_second.url, repo_other.url]},
        ]
    }
    path = tmp_path / "catalog.toml"
    path.write_bytes(tomli_w.dumps(data).encode())
    return path


def test_bare_name_resolves_to_first_pointer(shadow_catalog: Path) -> None:
    with pytest.warns(UserWarning, match="SHADOW WARNING"):
        records = validate_selection(shadow_catalog, ["tpl-shared"])
    assert records[0].full_id == "internal/tpl-shared"


def test_shadow_warning_names_winner_and_shadowed(shadow_catalog: Path) -> None:
    with pytest.warns(UserWarning) as record:
        validate_selection(shadow_catalog, ["tpl-shared"])
    messages = [str(w.message) for w in record if "SHADOW WARNING" in str(w.message)]
    assert messages, "no shadow warning emitted"
    assert "internal/tpl-shared" in messages[0]
    assert "public/tpl-shared" in messages[0]


def test_full_id_of_shadowed_entry_resolves_without_warning(shadow_catalog: Path) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        records = validate_selection(shadow_catalog, ["public/tpl-shared"])
    assert records[0].full_id == "public/tpl-shared"


def test_listing_shows_both_with_second_shadowed(shadow_catalog: Path) -> None:
    listing = build_listing(shadow_catalog)
    by_full_id = {t.full_id: t for cl in listing.catalogs for t in cl.templates}
    assert by_full_id["internal/tpl-shared"].shadowed is False
    assert by_full_id["public/tpl-shared"].shadowed is True
    assert by_full_id["public/tpl-other"].shadowed is False


def test_single_pointer_unchanged(tmp_path: Path) -> None:
    repo = build_template_repo(
        tmp_path / "solo" / "tpl-solo",
        files={"copier.yml": _YML, "template/solo.txt.jinja": "solo\n"},
    )
    data = {"catalog": [{"name": "solo", "sources": [repo.url]}]}
    path = tmp_path / "catalog.toml"
    path.write_bytes(tomli_w.dumps(data).encode())

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        records = validate_selection(path, ["tpl-solo"])
    assert records[0].full_id == "solo/tpl-solo"
    listing = build_listing(path)
    assert all(not t.shadowed for cl in listing.catalogs for t in cl.templates)
