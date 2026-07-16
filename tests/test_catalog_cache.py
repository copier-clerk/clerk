"""Unit + CLI tests for the persisted listing cache (spec 013 T012)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import tomli_w

from bailiff.catalog import (
    CatalogListing,
    FullListing,
    TemplateRecord,
    UnusableRecord,
    build_and_cache_listing,
    listing_cache_path,
    load_listing_cache,
    persist_listing,
)
from tests.conftest import build_template_repo

_YML = "project_name:\n  type: str\n_subdirectory: template\n"


def _listing() -> FullListing:
    return FullListing(
        catalogs=[
            CatalogListing(
                name="demo",
                templates=[
                    TemplateRecord(
                        full_id="demo/mod-a",
                        source="https://example.com/mod-a.git",
                        ref="v1.0.0",
                        versions=["v1.0.0"],
                        reproducible=True,
                        has_tasks=True,
                        questions=["project_name"],
                        provides=["python-project"],
                        exclusive=True,
                        shadowed=True,
                    )
                ],
                unusable=[UnusableRecord(source="bad/src", reason="no tags")],
            )
        ]
    )


def test_persist_load_round_trip_all_fields(tmp_path: Path) -> None:
    cache = tmp_path / "listing.json"
    original = _listing()
    persist_listing(original, cache)
    loaded = load_listing_cache(cache)
    assert loaded is not None
    assert loaded.to_dict() == original.to_dict()
    t = loaded.catalogs[0].templates[0]
    assert t.provides == ["python-project"]
    assert t.exclusive is True
    assert t.shadowed is True


def test_load_absent_cache_returns_none(tmp_path: Path) -> None:
    assert load_listing_cache(tmp_path / "missing.json") is None


def test_load_corrupt_cache_returns_none(tmp_path: Path) -> None:
    cache = tmp_path / "listing.json"
    cache.write_text("{not json")
    assert load_listing_cache(cache) is None
    cache.write_text('{"unexpected": "shape"}')
    assert load_listing_cache(cache) is None


def test_atomic_write_no_tmp_left_behind(tmp_path: Path) -> None:
    cache = tmp_path / "nested" / "listing.json"
    persist_listing(_listing(), cache)
    assert cache.is_file()
    assert not cache.with_suffix(".json.tmp").exists()


def test_listing_cache_path_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAILIFF_LISTING_CACHE_PATH", "/tmp/custom-cache.json")
    assert listing_cache_path() == Path("/tmp/custom-cache.json")


def test_build_and_cache_listing_writes_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = build_template_repo(
        tmp_path / "tpl-x",
        files={"copier.yml": _YML, "template/x.txt.jinja": "x\n"},
    )
    cat_path = tmp_path / "catalog.toml"
    cat_path.write_bytes(
        tomli_w.dumps({"catalog": [{"name": "d", "sources": [repo.url]}]}).encode()
    )
    cache = tmp_path / "cache.json"

    listing = build_and_cache_listing(cat_path, cache)
    assert cache.is_file()
    assert load_listing_cache(cache).to_dict() == listing.to_dict()  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# CLI wiring (refresh writes; list auto-builds once; repeat lists identical)
# ---------------------------------------------------------------------------


def _bailiff(*args: str, catalog: Path, cache: Path) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "BAILIFF_CATALOG_PATH": str(catalog),
        "BAILIFF_LISTING_CACHE_PATH": str(cache),
    }
    return subprocess.run(
        [sys.executable, "-m", "bailiff", "catalog", "--catalog", str(catalog), *args],
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture
def cli_catalog(tmp_path: Path) -> tuple[Path, Path]:
    repo = build_template_repo(
        tmp_path / "tpl-cli",
        files={"copier.yml": _YML, "template/c.txt.jinja": "c\n"},
    )
    cat_path = tmp_path / "catalog.toml"
    cat_path.write_bytes(
        tomli_w.dumps({"catalog": [{"name": "d", "sources": [repo.url]}]}).encode()
    )
    return cat_path, tmp_path / "listing-cache.json"


def test_cli_list_auto_builds_cache_with_notice(cli_catalog: tuple[Path, Path]) -> None:
    cat_path, cache = cli_catalog
    assert not cache.exists()
    r = _bailiff("list", "--json", catalog=cat_path, cache=cache)
    assert r.returncode == 0
    assert "notice" in r.stderr.lower()
    assert cache.is_file()
    assert json.loads(r.stdout)["catalogs"][0]["name"] == "d"


def test_cli_refresh_writes_cache(cli_catalog: tuple[Path, Path]) -> None:
    cat_path, cache = cli_catalog
    r = _bailiff("refresh", catalog=cat_path, cache=cache)
    assert r.returncode == 0
    assert cache.is_file()
    assert "refreshed listing cache" in r.stderr


def test_cli_two_lists_after_refresh_byte_identical(cli_catalog: tuple[Path, Path]) -> None:
    cat_path, cache = cli_catalog
    assert _bailiff("refresh", catalog=cat_path, cache=cache).returncode == 0
    r1 = _bailiff("list", "--json", catalog=cat_path, cache=cache)
    r2 = _bailiff("list", "--json", catalog=cat_path, cache=cache)
    assert r1.returncode == r2.returncode == 0
    assert r1.stdout == r2.stdout
    # served from cache: no auto-build notice
    assert "notice" not in r1.stderr.lower()
