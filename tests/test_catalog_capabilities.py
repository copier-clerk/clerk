"""Unit tests for capability fields + shadow tracking in the catalog (spec 013 T006)."""

from __future__ import annotations

from pathlib import Path

import pytest

from bailiff import catalog, discovery
from bailiff.catalog import (
    CatalogListing,
    FullListing,
    TemplateRecord,
    build_listing,
    save,
)


def test_template_record_field_defaults() -> None:
    rec = TemplateRecord(
        full_id="demo/mod",
        source="https://example.com/mod.git",
        ref="v1.0.0",
        versions=["v1.0.0"],
        reproducible=True,
        has_tasks=False,
        questions=[],
    )
    assert rec.provides == []
    assert rec.exclusive is False
    assert rec.shadowed is False


def test_full_listing_to_dict_includes_capability_fields() -> None:
    rec = TemplateRecord(
        full_id="demo/mod",
        source="https://example.com/mod.git",
        ref="v1.0.0",
        versions=["v1.0.0"],
        reproducible=True,
        has_tasks=False,
        questions=["project_name"],
        provides=["python-project"],
        exclusive=True,
        shadowed=True,
    )
    listing = FullListing(catalogs=[CatalogListing(name="demo", templates=[rec], unusable=[])])
    entry = listing.to_dict()["catalogs"][0]["templates"][0]
    assert entry["provides"] == ["python-project"]
    assert entry["exclusive"] is True
    assert entry["shadowed"] is True


def _fake_discover_factory(caps: dict[str, tuple[list[str], bool]]):
    """Build a discovery.discover stub keyed by source basename."""

    def _fake_discover(source: str, ref: str | None = None) -> discovery.Discovery:
        base = source.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
        provides, exclusive = caps.get(base, ([], False))
        return discovery.Discovery(
            source=source,
            ref=ref or "v1.0.0",
            versions=["v1.0.0"],
            reproducible=True,
            has_tasks=False,
            jinja_extensions=[],
            questions=[],
            secret_questions=[],
            provides=provides,
            exclusive=exclusive,
        )

    return _fake_discover


@pytest.fixture
def two_pointer_catalog(tmp_path: Path) -> Path:
    path = tmp_path / "catalog.toml"
    model = catalog.CatalogModel(
        pointers=[
            catalog.CatalogPointer(
                name="internal",
                sources=[catalog.CatalogSource(locator="acme/bailiff-mod-python", ref=None)],
            ),
            catalog.CatalogPointer(
                name="demo",
                sources=[
                    catalog.CatalogSource(locator="bailiff-io/bailiff-mod-python", ref=None),
                    catalog.CatalogSource(locator="bailiff-io/bailiff-mod-go", ref=None),
                ],
            ),
        ]
    )
    save(path, model)
    return path


def test_build_listing_populates_capabilities_and_shadow(
    two_pointer_catalog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        catalog.discovery,
        "discover",
        _fake_discover_factory(
            {
                "bailiff-mod-python": (["python-project"], True),
                "bailiff-mod-go": (["go-project"], False),
            }
        ),
    )
    listing = build_listing(two_pointer_catalog)
    by_full_id = {t.full_id: t for cl in listing.catalogs for t in cl.templates}

    first = by_full_id["internal/bailiff-mod-python"]
    assert first.provides == ["python-project"]
    assert first.exclusive is True
    assert first.shadowed is False  # first pointer wins

    second = by_full_id["demo/bailiff-mod-python"]
    assert second.shadowed is True  # same bare name, later pointer

    go = by_full_id["demo/bailiff-mod-go"]
    assert go.provides == ["go-project"]
    assert go.exclusive is False
    assert go.shadowed is False


def test_build_listing_single_pointer_no_shadow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "catalog.toml"
    model = catalog.CatalogModel(
        pointers=[
            catalog.CatalogPointer(
                name="demo",
                sources=[catalog.CatalogSource(locator="bailiff-io/bailiff-mod-go", ref=None)],
            )
        ]
    )
    save(path, model)
    monkeypatch.setattr(catalog.discovery, "discover", _fake_discover_factory({}))
    listing = build_listing(path)
    assert all(not t.shadowed for cl in listing.catalogs for t in cl.templates)
