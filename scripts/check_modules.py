#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "packaging"]
# ///
"""Module contract linter for the clerk monorepo (spec 008b / FR-006, FR-007).

Iterates templates/*/ and verifies each module satisfies the full contract:
  - Valid copier.yml with answers-file .jinja present (reproducible=True)
  - README.md and CHANGELOG.md present
  - Three-way registration parity: templates/ dirs == cog.toml packages == catalog sources
  - Published-label immutability: if any <name>-v* tag exists, choice labels match the
    latest tag's copier.yml (Constitution VI / C-06)

Exits 0 when templates/ is empty (spec 009 not yet done — graceful no-op).
Exits 1 with a named violation on any failure.

Run via `just check-modules` or directly: `uv run scripts/check_modules.py`.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo root resolution — script may be invoked from any cwd
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent  # scripts/ is one level below repo root


def _repo_path(rel: str) -> Path:
    return _REPO_ROOT / rel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ANSWERS_FILE_MARKER = "_copier_conf.answers_file"


def _ships_answers_file(module_root: Path) -> bool:
    """True if the module tree contains a {{ _copier_conf.answers_file }}.jinja file."""
    for path in module_root.rglob("*"):
        if path.is_file() and _ANSWERS_FILE_MARKER in path.name and path.name.endswith(".jinja"):
            return True
    return False


def _read_copier_yml(module_root: Path) -> dict[str, object]:
    """Read and parse copier.yml from the module root. Returns {} on missing."""
    for name in ("copier.yml", "copier.yaml"):
        p = module_root / name
        if p.exists():
            raw = yaml.safe_load(p.read_text()) or {}
            if not isinstance(raw, dict):
                return {}
            return dict(raw)
    return {}


def _choice_labels(copier_raw: dict[str, object]) -> dict[str, list[object]]:
    """Return {question_key: [label, ...]} for all questions that have choices."""
    result: dict[str, list[object]] = {}
    for key, spec in copier_raw.items():
        if key.startswith("_"):
            continue
        if isinstance(spec, dict) and spec.get("choices"):
            result[key] = list(spec["choices"])
    return result


def _git_tags_for_module(name: str) -> list[str]:
    """Return monorepo git tags matching <name>-v<digit>*, sorted newest-first."""
    proc = subprocess.run(
        ["git", "tag", "-l", f"{name}-v*"],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    if proc.returncode != 0:
        return []
    return [t for t in proc.stdout.splitlines() if t.strip()]


def _copier_yml_at_ref(name: str, ref: str) -> dict[str, object]:
    """Read copier.yml from the given git ref for templates/<name>/."""
    for filename in ("copier.yml", "copier.yaml"):
        proc = subprocess.run(
            ["git", "show", f"{ref}:templates/{name}/{filename}"],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
        )
        if proc.returncode == 0:
            try:
                raw = yaml.safe_load(proc.stdout) or {}
                return dict(raw) if isinstance(raw, dict) else {}
            except yaml.YAMLError:
                return {}
    return {}


def _read_cog_packages() -> set[str]:
    """Return the set of package names from cog.toml [monorepo.packages]."""
    cog_path = _repo_path("cog.toml")
    if not cog_path.exists():
        return set()
    with cog_path.open("rb") as f:
        data = tomllib.load(f)
    packages = data.get("monorepo", {}).get("packages", {})
    return set(packages.keys())


def _read_catalog_sources() -> set[str]:
    """Return the set of module names from catalog-sources.toml.

    Each entry in [[sources]] must have a url key ending in clerk-mod-<name>.git.
    Returns empty set if the file does not exist yet.
    """
    src_path = _repo_path("catalog-sources.toml")
    if not src_path.exists():
        return set()
    with src_path.open("rb") as f:
        data = tomllib.load(f)
    names: set[str] = set()
    for entry in data.get("sources", []):
        url = entry.get("url", "")
        # URL shape: https://github.com/copier-clerk/clerk-mod-<name>.git
        if url.endswith(".git"):
            stem = url.rstrip("/").rsplit("/", 1)[-1][:-4]  # strip trailing .git
            names.add(stem)
    return names


# ---------------------------------------------------------------------------
# Main checker
# ---------------------------------------------------------------------------


def check_modules(templates_dir: Path | None = None) -> int:
    """Run all module checks. Returns 0 on success, 1 on any violation."""
    if templates_dir is None:
        templates_dir = _repo_path("templates")

    if not templates_dir.exists():
        return 0  # no templates dir yet — graceful no-op

    module_dirs = sorted(p for p in templates_dir.iterdir() if p.is_dir())
    if not module_dirs:
        return 0  # empty templates/ — spec 009 not yet done

    violations: list[str] = []

    # -----------------------------------------------------------------------
    # Per-module checks
    # -----------------------------------------------------------------------
    for module_path in module_dirs:
        name = module_path.name

        # Check 1: answers-file .jinja present (reproducible)
        if not _ships_answers_file(module_path):
            violations.append(
                f"{name}: missing answers-file '{{{{ _copier_conf.answers_file }}}}.jinja' "
                f"— template is not reproducible (FR-016)"
            )

        # Check 2: README.md present
        if not (module_path / "README.md").exists():
            violations.append(f"{name}: missing README.md")

        # Check 3: CHANGELOG.md present
        if not (module_path / "CHANGELOG.md").exists():
            violations.append(f"{name}: missing CHANGELOG.md")

        # Check 4: published-label immutability (C-06)
        tags = _git_tags_for_module(name)
        if tags:
            # Find latest tag (sort by version suffix)
            latest_tag = sorted(tags)[-1]
            current_raw = _read_copier_yml(module_path)
            tagged_raw = _copier_yml_at_ref(name, latest_tag)
            current_labels = _choice_labels(current_raw)
            tagged_labels = _choice_labels(tagged_raw)
            for key, tagged_choices in tagged_labels.items():
                current_choices = current_labels.get(key, [])
                if current_choices != tagged_choices:
                    violations.append(
                        f"{name}: published-label mutation on question '{key}' — "
                        f"choices at {latest_tag}: {tagged_choices!r}, "
                        f"working tree: {current_choices!r} (Constitution VI / C-06)"
                    )

    # -----------------------------------------------------------------------
    # Three-way registration parity
    # -----------------------------------------------------------------------
    template_names = {p.name for p in module_dirs}
    cog_packages = _read_cog_packages()
    catalog_sources_path = _repo_path("catalog-sources.toml")

    # Only enforce three-way if catalog-sources.toml exists; otherwise two-way.
    if catalog_sources_path.exists():
        catalog_names = _read_catalog_sources()
        all_names = template_names | cog_packages | catalog_names

        for name in sorted(all_names):
            in_templates = name in template_names
            in_cog = name in cog_packages
            in_catalog = name in catalog_names
            if not (in_templates and in_cog and in_catalog):
                where = []
                if not in_templates:
                    where.append("missing from templates/")
                if not in_cog:
                    where.append("missing from cog.toml [monorepo.packages]")
                if not in_catalog:
                    where.append("missing from catalog-sources.toml")
                violations.append(f"{name}: registration parity failure — {'; '.join(where)}")
    else:
        # Two-way parity: templates/ dirs vs cog.toml packages
        all_names = template_names | cog_packages
        for name in sorted(all_names):
            in_templates = name in template_names
            in_cog = name in cog_packages
            if not (in_templates and in_cog):
                where = []
                if not in_templates:
                    where.append("missing from templates/ (ghost in cog.toml)")
                if not in_cog:
                    where.append("missing from cog.toml [monorepo.packages]")
                violations.append(f"{name}: registration parity failure — {'; '.join(where)}")

    # -----------------------------------------------------------------------
    # Report
    # -----------------------------------------------------------------------
    if violations:
        print("check-modules: FAILED", file=sys.stderr)
        for v in violations:
            print(f"  VIOLATION: {v}", file=sys.stderr)
        return 1

    print(f"check-modules: ok — {len(module_dirs)} module(s) checked")
    return 0


if __name__ == "__main__":
    sys.exit(check_modules())
