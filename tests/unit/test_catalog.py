"""Unit tests for bailiff.catalog — CRUD, listing, and validation gate (T007, T010, T012)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
import tomli_w

from bailiff.catalog import (
    CatalogModel,
    CatalogPointer,
    CatalogSource,
    add_source,
    build_listing,
    init_catalog,
    load,
    pointer_name,
    remove_source,
    save,
    validate_selection,
)
from bailiff.errors import CatalogError
from tests.conftest import _SIMPLE_COPIER_YML, MultiSourceCatalog, build_template_repo

# ---------------------------------------------------------------------------
# CRUD — T007
# ---------------------------------------------------------------------------


def test_load_missing_file_returns_empty_model(tmp_path: Path) -> None:
    model = load(tmp_path / "nonexistent.toml")
    assert model.pointers == []


def test_load_malformed_toml_raises_catalog_error(tmp_path: Path) -> None:
    bad = tmp_path / "catalog.toml"
    bad.write_text("[[catalog\n")  # unterminated table header
    with pytest.raises(CatalogError, match="not valid TOML"):
        load(bad)


def test_save_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "catalog.toml"
    model = CatalogModel(
        pointers=[
            CatalogPointer(
                name="demo",
                sources=[
                    CatalogSource(locator="user/repo-a", ref=None),
                    CatalogSource(locator="user/repo-b", ref="v2.1.0"),
                ],
            )
        ]
    )
    save(path, model)
    loaded = load(path)

    assert len(loaded.pointers) == 1
    ptr = loaded.pointers[0]
    assert ptr.name == "demo"
    assert len(ptr.sources) == 2
    assert ptr.sources[0].locator == "user/repo-a"
    assert ptr.sources[0].ref is None
    assert ptr.sources[1].locator == "user/repo-b"
    assert ptr.sources[1].ref == "v2.1.0"


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c" / "catalog.toml"
    save(nested, CatalogModel())
    assert nested.is_file()


def test_add_source_creates_file_if_absent(tmp_path: Path) -> None:
    path = tmp_path / "catalog.toml"
    assert not path.exists()
    added = add_source(path, "user/new-repo", name="myptr")
    assert added is True
    assert path.is_file()
    model = load(path)
    assert model.pointers[0].name == "myptr"
    assert model.pointers[0].sources[0].locator == "user/new-repo"


def test_add_source_idempotent_returns_false(tmp_path: Path) -> None:
    path = tmp_path / "catalog.toml"
    add_source(path, "user/repo", name="p")
    result = add_source(path, "user/repo", name="p")
    assert result is False
    # Exactly one entry after two identical adds.
    assert len(load(path).pointers[0].sources) == 1


def test_add_source_no_duplicate_in_toml(tmp_path: Path) -> None:
    path = tmp_path / "catalog.toml"
    add_source(path, "user/repo", name="p")
    add_source(path, "user/repo", name="p")
    raw = tomllib.loads(path.read_text())
    assert raw["catalog"][0]["sources"].count("user/repo") == 1


def test_add_source_preserves_other_pointers(tmp_path: Path) -> None:
    path = tmp_path / "catalog.toml"
    # Write two existing pointers.
    save(
        path,
        CatalogModel(
            pointers=[
                CatalogPointer(name="alpha", sources=[CatalogSource("u/a", None)]),
                CatalogPointer(name="beta", sources=[CatalogSource("u/b", None)]),
            ]
        ),
    )
    add_source(path, "u/c", name="alpha")
    model = load(path)
    names = [p.name for p in model.pointers]
    assert "alpha" in names
    assert "beta" in names
    alpha = next(p for p in model.pointers if p.name == "alpha")
    assert len(alpha.sources) == 2
    beta = next(p for p in model.pointers if p.name == "beta")
    assert len(beta.sources) == 1


def test_remove_source_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "catalog.toml"
    add_source(path, "user/repo", name="p")
    assert remove_source(path, "user/repo", name="p") is True
    assert remove_source(path, "user/repo", name="p") is False  # already gone


def test_remove_source_preserves_other_sources(tmp_path: Path) -> None:
    path = tmp_path / "catalog.toml"
    save(
        path,
        CatalogModel(
            pointers=[
                CatalogPointer(
                    name="p",
                    sources=[CatalogSource("u/a", None), CatalogSource("u/b", None)],
                )
            ]
        ),
    )
    remove_source(path, "u/a", name="p")
    model = load(path)
    sources = [s.locator for s in model.pointers[0].sources]
    assert sources == ["u/b"]


def test_remove_source_preserves_other_pointers(tmp_path: Path) -> None:
    path = tmp_path / "catalog.toml"
    save(
        path,
        CatalogModel(
            pointers=[
                CatalogPointer(name="alpha", sources=[CatalogSource("u/a", None)]),
                CatalogPointer(name="beta", sources=[CatalogSource("u/b", None)]),
            ]
        ),
    )
    remove_source(path, "u/a", name="alpha")
    model = load(path)
    beta = next(p for p in model.pointers if p.name == "beta")
    assert len(beta.sources) == 1


def test_add_source_ref_parsed_and_retained(tmp_path: Path) -> None:
    """@ref in source string is parsed and written back — display-only, not a pin."""
    path = tmp_path / "catalog.toml"
    add_source(path, "user/repo@v2.0.0", name="p")
    model = load(path)
    src = model.pointers[0].sources[0]
    assert src.locator == "user/repo"
    assert src.ref == "v2.0.0"
    # It round-trips through save/load.
    raw = tomllib.loads(path.read_text())
    assert raw["catalog"][0]["sources"] == ["user/repo@v2.0.0"]


def test_pointer_name_explicit_wins() -> None:
    assert pointer_name("myname", "user/repo") == "myname"


def test_pointer_name_sanitized_basename() -> None:
    assert pointer_name(None, "user/My Template Repo") == "my-template-repo"
    assert pointer_name(None, "user/bailiff-mod-base") == "bailiff-mod-base"


def test_init_catalog_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "catalog.toml"
    assert init_catalog(path, name="myptr") is True
    assert path.is_file()
    model = load(path)
    assert model.pointers[0].name == "myptr"
    assert model.pointers[0].sources == []


def test_init_catalog_idempotent_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "catalog.toml"
    init_catalog(path, name="first")
    assert init_catalog(path, name="second") is False
    # File contents unchanged.
    assert load(path).pointers[0].name == "first"


# ---------------------------------------------------------------------------
# Listing — T010
# ---------------------------------------------------------------------------


def test_build_listing_two_usable_one_unusable(
    multi_source_catalog: MultiSourceCatalog,
) -> None:
    listing = build_listing(multi_source_catalog.catalog_path)
    assert len(listing.catalogs) == 1
    cl = listing.catalogs[0]
    assert cl.name == "mycat"

    usable_ids = {t.full_id for t in cl.templates}
    assert "mycat/tpl-alpha" in usable_ids
    assert "mycat/tpl-beta" in usable_ids

    assert len(cl.unusable) == 1
    assert "tpl-broken" in cl.unusable[0].source


def test_build_listing_usable_metadata(multi_source_catalog: MultiSourceCatalog) -> None:
    listing = build_listing(multi_source_catalog.catalog_path)
    cl = listing.catalogs[0]
    alpha = next(t for t in cl.templates if t.full_id == "mycat/tpl-alpha")
    assert alpha.reproducible is True
    assert alpha.versions == ["v1.0.0"]
    assert "project_name" in alpha.questions


def test_build_listing_unusable_has_reason(multi_source_catalog: MultiSourceCatalog) -> None:
    listing = build_listing(multi_source_catalog.catalog_path)
    cl = listing.catalogs[0]
    assert cl.unusable[0].reason  # non-empty reason string


def test_build_listing_deterministic(multi_source_catalog: MultiSourceCatalog) -> None:
    """Two calls produce identical dicts (SC-002)."""
    d1 = build_listing(multi_source_catalog.catalog_path).to_dict()
    d2 = build_listing(multi_source_catalog.catalog_path).to_dict()
    assert d1 == d2


def test_build_listing_full_id_namespacing_basename_default(tmp_path: Path) -> None:
    """Without an explicit name the pointer name is the sanitized basename."""
    repo = build_template_repo(
        tmp_path / "my-cool-template",
        files={
            "copier.yml": _SIMPLE_COPIER_YML,
            "template/out.txt.jinja": "x\n",
        },
    )
    # Write a catalog where the pointer name is explicit.
    data = {"catalog": [{"name": "explicit", "sources": [repo.url]}]}
    cat_path = tmp_path / "catalog.toml"
    cat_path.write_bytes(tomli_w.dumps(data).encode())
    listing = build_listing(cat_path)
    cl = listing.catalogs[0]
    assert cl.name == "explicit"
    # full_id = pointer-name / repo-basename
    full_id = cl.templates[0].full_id
    assert full_id == "explicit/my-cool-template"


def test_to_dict_shape(multi_source_catalog: MultiSourceCatalog) -> None:
    """to_dict() output matches the contract shape."""
    d = build_listing(multi_source_catalog.catalog_path).to_dict()
    assert "catalogs" in d
    cat = d["catalogs"][0]
    assert "name" in cat
    assert "templates" in cat
    assert "unusable" in cat
    tmpl = cat["templates"][0]
    for key in ("full_id", "source", "ref", "versions", "reproducible", "has_tasks", "questions"):
        assert key in tmpl, f"missing key {key!r} in template record"
    unusable = cat["unusable"][0]
    assert "source" in unusable
    assert "reason" in unusable


# ---------------------------------------------------------------------------
# validate_selection — T012
# ---------------------------------------------------------------------------


def test_validate_selection_valid_full_id(multi_source_catalog: MultiSourceCatalog) -> None:
    records = validate_selection(multi_source_catalog.catalog_path, ["mycat/tpl-alpha"])
    assert len(records) == 1
    assert records[0].full_id == "mycat/tpl-alpha"


def test_validate_selection_multiple_valid(multi_source_catalog: MultiSourceCatalog) -> None:
    records = validate_selection(
        multi_source_catalog.catalog_path, ["mycat/tpl-alpha", "mycat/tpl-beta"]
    )
    assert {r.full_id for r in records} == {"mycat/tpl-alpha", "mycat/tpl-beta"}


def test_validate_selection_unknown_id_raises(multi_source_catalog: MultiSourceCatalog) -> None:
    with pytest.raises(CatalogError, match="unknown template id") as exc_info:
        validate_selection(multi_source_catalog.catalog_path, ["mycat/nonexistent"])
    # Error message names valid ids.
    msg = str(exc_info.value)
    assert "mycat/tpl-alpha" in msg or "mycat/tpl-beta" in msg


def test_validate_selection_unknown_id_message_lists_valid_ids(
    multi_source_catalog: MultiSourceCatalog,
) -> None:
    with pytest.raises(CatalogError) as exc_info:
        validate_selection(multi_source_catalog.catalog_path, ["mycat/ghost"])
    msg = str(exc_info.value)
    assert "mycat/tpl-alpha" in msg
    assert "mycat/tpl-beta" in msg


def test_validate_selection_bare_name_unambiguous_accepted(
    multi_source_catalog: MultiSourceCatalog,
) -> None:
    """Bare name matching exactly one usable template → accepted (convenience)."""
    records = validate_selection(multi_source_catalog.catalog_path, ["tpl-alpha"])
    assert records[0].full_id == "mycat/tpl-alpha"


def test_validate_selection_bare_name_ambiguous_refused(tmp_path: Path) -> None:
    """Bare name matching two different catalog pointers → CatalogError.

    Both repos share the same directory basename ("tpl-shared") so the short name
    "tpl-shared" is ambiguous across the two pointer namespaces.
    """
    # Same basename under different parent dirs → same short template name.
    repo_a = build_template_repo(
        tmp_path / "group-a" / "tpl-shared",
        files={"copier.yml": _SIMPLE_COPIER_YML, "template/out.txt.jinja": "x\n"},
        tag="v1.0.0",
    )
    repo_b = build_template_repo(
        tmp_path / "group-b" / "tpl-shared",
        files={"copier.yml": _SIMPLE_COPIER_YML, "template/out.txt.jinja": "x\n"},
        tag="v1.0.0",
    )
    data = {
        "catalog": [
            {"name": "cat1", "sources": [repo_a.url]},
            {"name": "cat2", "sources": [repo_b.url]},
        ]
    }
    cat_path = tmp_path / "catalog.toml"
    cat_path.write_bytes(tomli_w.dumps(data).encode())

    with pytest.raises(CatalogError, match="ambiguous"):
        validate_selection(cat_path, ["tpl-shared"])


def test_validate_selection_unusable_id_refused(
    multi_source_catalog: MultiSourceCatalog,
) -> None:
    """Requesting a known-but-unusable full-id raises a specific error."""
    with pytest.raises(CatalogError, match="not usable"):
        validate_selection(multi_source_catalog.catalog_path, ["mycat/tpl-broken"])
