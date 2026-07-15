"""Unit tests for scripts/generate_catalog.py (spec 008b / T010).

All offline — monkeypatches discovery.list_versions so no git ls-remote calls occur.
Asserts JSON shape matches contracts/fanout.md; modules with no tags are omitted;
generated_at is present; source URLs are fully-expanded https://.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest


def _load_generate_catalog():
    spec = importlib.util.spec_from_file_location(
        "generate_catalog",
        Path(__file__).parent.parent.parent / "scripts" / "generate_catalog.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_gc = _load_generate_catalog()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COPIER_YML_WITH_DESC = """\
_description: "Base project scaffold"
project_name:
  type: str
  default: myproject
"""

_COPIER_YML_NO_DESC = """\
project_name:
  type: str
  default: myproject
"""


def _make_templates(root: Path, modules: dict[str, str]) -> Path:
    """Create templates/<name>/copier.yml for each name->yml_content mapping."""
    tpl = root / "templates"
    tpl.mkdir(parents=True, exist_ok=True)
    for name, yml in modules.items():
        mod_dir = tpl / name
        mod_dir.mkdir()
        (mod_dir / "copier.yml").write_text(yml)
    return tpl


def _make_catalog_sources(root: Path, names: list[str]) -> None:
    lines = []
    for name in names:
        lines.append("[[sources]]")
        lines.append(f'url = "https://github.com/bailiff-io/{name}.git"')
        lines.append("")
    (root / "catalog-sources.toml").write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mono(tmp_path: Path) -> Path:
    """Minimal monorepo root with templates/ and no catalog-sources.toml."""
    return tmp_path


# ---------------------------------------------------------------------------
# JSON shape matches contracts/fanout.md
# ---------------------------------------------------------------------------


def test_catalog_shape_matches_contract(mono: Path) -> None:
    _make_templates(mono, {"bailiff-mod-base": _COPIER_YML_WITH_DESC})
    _make_catalog_sources(mono, ["bailiff-mod-base"])

    with (
        patch.object(_gc, "_REPO_ROOT", mono),
        patch.object(
            _gc,
            "list_versions",
            return_value=["v1.0.0", "v1.1.0", "v1.2.0"],
        ),
    ):
        catalog = _gc.generate_catalog(mono / "templates")

    assert catalog["version"] == 1
    assert "generated_at" in catalog
    assert len(catalog["modules"]) == 1
    mod = catalog["modules"][0]
    assert mod["name"] == "bailiff-mod-base"
    assert mod["description"] == "Base project scaffold"
    assert mod["source"] == "https://github.com/bailiff-io/bailiff-mod-base.git"
    assert mod["latest_version"] == "v1.2.0"
    assert mod["tags"] == ["v1.0.0", "v1.1.0", "v1.2.0"]


# ---------------------------------------------------------------------------
# Modules with no tags are omitted
# ---------------------------------------------------------------------------


def test_module_with_no_tags_omitted(mono: Path, capsys) -> None:
    _make_templates(
        mono,
        {
            "bailiff-mod-released": _COPIER_YML_WITH_DESC,
            "bailiff-mod-unreleased": _COPIER_YML_NO_DESC,
        },
    )

    def mock_list_versions(url: str) -> list[str]:
        if "bailiff-mod-released" in url:
            return ["v1.0.0"]
        return []  # unreleased module

    with (
        patch.object(_gc, "_REPO_ROOT", mono),
        patch.object(_gc, "list_versions", side_effect=mock_list_versions),
    ):
        catalog = _gc.generate_catalog(mono / "templates")

    names = [m["name"] for m in catalog["modules"]]
    assert "bailiff-mod-released" in names
    assert "bailiff-mod-unreleased" not in names
    captured = capsys.readouterr()
    assert "bailiff-mod-unreleased" in captured.err
    assert "omitting" in captured.err


# ---------------------------------------------------------------------------
# generated_at is present and ISO-8601 UTC
# ---------------------------------------------------------------------------


def test_generated_at_present_and_utc(mono: Path) -> None:
    _make_templates(mono, {"bailiff-mod-x": _COPIER_YML_NO_DESC})

    with (
        patch.object(_gc, "_REPO_ROOT", mono),
        patch.object(_gc, "list_versions", return_value=["v0.1.0"]),
    ):
        catalog = _gc.generate_catalog(mono / "templates")

    assert "generated_at" in catalog
    ga = catalog["generated_at"]
    # Must end with Z (UTC) per contract
    assert ga.endswith("Z"), f"generated_at must end with Z: {ga!r}"
    # Must be parseable as ISO-8601
    from datetime import datetime

    datetime.strptime(ga, "%Y-%m-%dT%H:%M:%SZ")  # raises ValueError if wrong format


# ---------------------------------------------------------------------------
# Source URLs are fully-expanded https://
# ---------------------------------------------------------------------------


def test_source_urls_are_https(mono: Path) -> None:
    _make_templates(
        mono,
        {
            "bailiff-mod-a": _COPIER_YML_NO_DESC,
            "bailiff-mod-b": _COPIER_YML_NO_DESC,
        },
    )
    _make_catalog_sources(mono, ["bailiff-mod-a", "bailiff-mod-b"])

    with (
        patch.object(_gc, "_REPO_ROOT", mono),
        patch.object(_gc, "list_versions", return_value=["v1.0.0"]),
    ):
        catalog = _gc.generate_catalog(mono / "templates")

    for mod in catalog["modules"]:
        assert mod["source"].startswith("https://"), (
            f"source URL must be https://: {mod['source']!r}"
        )


# ---------------------------------------------------------------------------
# Empty templates/ → empty modules list
# ---------------------------------------------------------------------------


def test_empty_templates_produces_empty_catalog(mono: Path) -> None:
    (mono / "templates").mkdir()

    with patch.object(_gc, "_REPO_ROOT", mono):
        catalog = _gc.generate_catalog(mono / "templates")

    assert catalog["modules"] == []
    assert catalog["version"] == 1


# ---------------------------------------------------------------------------
# --dry-run flag prints JSON without writing catalog.json
# ---------------------------------------------------------------------------


def test_dry_run_does_not_write_file(mono: Path, capsys) -> None:
    _make_templates(mono, {"bailiff-mod-dry": _COPIER_YML_NO_DESC})

    with (
        patch.object(_gc, "_REPO_ROOT", mono),
        patch.object(_gc, "list_versions", return_value=["v1.0.0"]),
    ):
        rc = _gc.main(["--dry-run"])

    assert rc == 0
    assert not (mono / "catalog.json").exists()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "modules" in data


# ---------------------------------------------------------------------------
# Tags from catalog-sources.toml used as source URL
# ---------------------------------------------------------------------------


def test_catalog_sources_toml_url_used(mono: Path) -> None:
    _make_templates(mono, {"bailiff-mod-z": _COPIER_YML_NO_DESC})
    _make_catalog_sources(mono, ["bailiff-mod-z"])

    captured_urls: list[str] = []

    def mock_list_versions(url: str) -> list[str]:
        captured_urls.append(url)
        return ["v2.0.0"]

    with (
        patch.object(_gc, "_REPO_ROOT", mono),
        patch.object(_gc, "list_versions", side_effect=mock_list_versions),
    ):
        catalog = _gc.generate_catalog(mono / "templates")

    assert captured_urls == ["https://github.com/bailiff-io/bailiff-mod-z.git"]
    assert catalog["modules"][0]["source"] == "https://github.com/bailiff-io/bailiff-mod-z.git"
