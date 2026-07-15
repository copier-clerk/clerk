#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "packaging"]
# ///
"""Generate catalog.json from templates/*/ and published split-repo tags (spec 008b / FR-008).

Enumerates templates/*/, reads each module's name + description from copier.yml,
calls discovery.list_versions() to get PEP 440 tags from the split repo, and emits
catalog.json to the monorepo root.

Modules with no published tags are omitted from output (Q-008b-a resolution) and
logged to stderr as "not yet released".

Usage:
    uv run scripts/generate_catalog.py          # write catalog.json
    uv run scripts/generate_catalog.py --dry-run # print JSON without writing
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import tomllib
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Module resolution — same dual-mode shim as scripts/bailiff.py so this script
# works both in-repo (src/bailiff/ on PYTHONPATH) and as a standalone uv script.
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent

# Add repo src/ to path so `from bailiff.discovery import list_versions` works.
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from bailiff.discovery import list_versions  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repo_path(rel: str) -> Path:
    return _REPO_ROOT / rel


def _read_copier_yml(module_path: Path) -> dict[str, object]:
    """Read and parse copier.yml from the module root. Returns {} on missing."""
    for name in ("copier.yml", "copier.yaml"):
        p = module_path / name
        if p.exists():
            raw = yaml.safe_load(p.read_text()) or {}
            return dict(raw) if isinstance(raw, dict) else {}
    return {}


def _split_repo_url(name: str) -> str:
    """Return the canonical split-repo HTTPS URL for a module name."""
    # Check catalog-sources.toml first — the authoritative declared source.
    src_path = _repo_path("catalog-sources.toml")
    if src_path.exists():
        with src_path.open("rb") as f:
            data = tomllib.load(f)
        for entry in data.get("sources", []):
            url = str(entry.get("url", ""))
            stem = url.rstrip("/").rsplit("/", 1)[-1]
            if stem.endswith(".git"):
                stem = stem[:-4]
            if stem == name:
                return url
    # Fall back to derived URL (ADR-0002 trust contract: always https://)
    return f"https://github.com/bailiff-io/{name}.git"


# ---------------------------------------------------------------------------
# Catalog generation
# ---------------------------------------------------------------------------


def generate_catalog(templates_dir: Path | None = None) -> dict[str, object]:
    """Build the catalog dict from templates/*/ and split-repo tags.

    Modules with no published tags are omitted (Q-008b-a resolution).
    """
    if templates_dir is None:
        templates_dir = _repo_path("templates")

    modules = []
    if templates_dir.exists():
        module_dirs = sorted(p for p in templates_dir.iterdir() if p.is_dir())
    else:
        module_dirs = []

    for module_path in module_dirs:
        name = module_path.name
        copier_raw = _read_copier_yml(module_path)
        description = copier_raw.get("_description") or copier_raw.get("description", "")
        # Some copier.yml files use a top-level description string value
        if not isinstance(description, str):
            description = ""
        # Use _name if present, else directory name
        module_name = copier_raw.get("_name") or name

        source_url = _split_repo_url(name)

        # Fetch published PEP 440 tags from the split repo
        try:
            tags = list_versions(source_url)
        except Exception as exc:  # noqa: BLE001
            print(
                f"generate_catalog: {name}: could not fetch tags from {source_url}: {exc}",
                file=sys.stderr,
            )
            tags = []

        if not tags:
            print(
                f"generate_catalog: {name}: no published tags — omitting from catalog",
                file=sys.stderr,
            )
            continue

        # Capability tags (spec 013 FR-009): same static YAML read; absent keys
        # normalize to empty/false. First-party well-formedness is enforced by
        # check_modules.py, so emit as-declared here.
        raw_provides = copier_raw.get("_bailiff_provides")
        provides = [str(e) for e in raw_provides] if isinstance(raw_provides, list) else []
        exclusive = bool(copier_raw.get("_bailiff_exclusive", False))

        modules.append(
            {
                "name": module_name,
                "description": description,
                "source": source_url,
                "latest_version": tags[-1],
                "tags": tags,
                "provides": provides,
                "exclusive": exclusive,
            }
        )

    return {
        "version": 1,
        "generated_at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "modules": modules,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate catalog.json from templates/*/")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON to stdout without writing catalog.json",
    )
    args = parser.parse_args(argv)

    catalog = generate_catalog()
    output = json.dumps(catalog, indent=2)

    if args.dry_run:
        print(output)
        return 0

    out_path = _repo_path("catalog.json")
    out_path.write_text(output + "\n")
    print(f"generate_catalog: wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
