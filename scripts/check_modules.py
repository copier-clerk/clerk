#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "packaging"]
# ///
"""Module contract linter for the bailiff monorepo (spec 008b / FR-006, FR-007).

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

import re
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml

# Capability names are kebab-case (spec 013 FR-007). First-party modules must
# declare them well-formed; discovery merely warns for third-party sources.
_CAPABILITY_RE = re.compile(r"^[a-z][a-z0-9-]*$")

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

    Each entry in [[sources]] must have a url key ending in bailiff-mod-<name>.git.
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
        # URL shape: https://github.com/bailiff-io/bailiff-mod-<name>.git
        if url.endswith(".git"):
            stem = url.rstrip("/").rsplit("/", 1)[-1][:-4]  # strip trailing .git
            names.add(stem)
    return names


def _check_capability_declarations(name: str, copier_raw: dict[str, object]) -> list[str]:
    """First-party well-formedness lint for capability keys (spec 013 FR-010).

    ``_bailiff_provides`` must be a list of kebab-case strings; ``_bailiff_exclusive``
    must be a boolean. Absence of either key is never an error.
    """
    violations: list[str] = []
    raw_provides = copier_raw.get("_bailiff_provides")
    if raw_provides is not None:
        if not isinstance(raw_provides, list):
            violations.append(
                f"{name}: _bailiff_provides must be a list of kebab-case strings, "
                f"got {raw_provides!r}"
            )
        else:
            for entry in raw_provides:
                if not isinstance(entry, str) or not _CAPABILITY_RE.match(entry):
                    violations.append(
                        f"{name}: _bailiff_provides entry {entry!r} is not a "
                        f"kebab-case string (^[a-z][a-z0-9-]*$)"
                    )
    raw_exclusive = copier_raw.get("_bailiff_exclusive")
    if raw_exclusive is not None and not isinstance(raw_exclusive, bool):
        violations.append(f"{name}: _bailiff_exclusive must be a boolean, got {raw_exclusive!r}")
    return violations


def _check_requires_declarations(name: str, copier_raw: dict[str, object]) -> list[str]:
    """First-party well-formedness lint for _bailiff_requires (spec 016 FR-001/008).

    Must be a list; each entry a non-empty tool-name string OR a mapping with a
    string ``tool`` (non-empty) and an optional string ``when``, no other keys.
    Absence is never an error. Mirrors the discovery parser's validation so a
    malformed declaration is caught at author time, not only at init.
    """
    violations: list[str] = []
    raw = copier_raw.get("_bailiff_requires")
    if raw is None:
        return violations
    if not isinstance(raw, list):
        violations.append(f"{name}: _bailiff_requires must be a list, got {raw!r}")
        return violations
    for entry in raw:
        if isinstance(entry, str):
            if not entry:
                violations.append(f"{name}: _bailiff_requires has an empty tool name")
            continue
        if not isinstance(entry, dict):
            violations.append(
                f"{name}: _bailiff_requires entry must be a string or a mapping, got {entry!r}"
            )
            continue
        unknown = set(entry) - {"tool", "when"}
        if unknown:
            violations.append(
                f"{name}: _bailiff_requires entry has unknown key(s) {sorted(unknown)}"
            )
        tool = entry.get("tool")
        if not isinstance(tool, str) or not tool:
            violations.append(f"{name}: _bailiff_requires entry needs a string 'tool': {entry!r}")
        when = entry.get("when")
        if when is not None and not isinstance(when, str):
            violations.append(f"{name}: _bailiff_requires 'when' must be a string, got {when!r}")
    return violations


def _check_mixed_exclusivity(module_caps: dict[str, tuple[list[str], bool]]) -> list[str]:
    """Mixed-exclusivity lint (spec 013 FR-010): all siblings of a pick-one
    capability family must declare ``_bailiff_exclusive`` consistently.

    ``module_caps`` maps module name → (provides, exclusive). A capability with
    N≥2 first-party providers where only a strict subset declares exclusive is a
    hard author-time error.
    """
    providers: dict[str, list[tuple[str, bool]]] = {}
    for name, (provides, exclusive) in module_caps.items():
        for cap in provides:
            providers.setdefault(cap, []).append((name, exclusive))

    violations: list[str] = []
    for cap, members in sorted(providers.items()):
        if len(members) < 2:
            continue
        exclusive_members = [n for n, e in members if e]
        if exclusive_members and len(exclusive_members) < len(members):
            member_list = ", ".join(
                f"{n} (exclusive={'true' if e else 'false'})" for n, e in sorted(members)
            )
            violations.append(
                f"capability {cap!r}: mixed exclusivity across first-party group — "
                f"{member_list}. All siblings of a pick-one family must declare "
                f"_bailiff_exclusive consistently."
            )
    return violations


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
    # module → (provides, exclusive) for the cross-module mixed-exclusivity lint.
    module_caps: dict[str, tuple[list[str], bool]] = {}

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

        # Check 3: CHANGELOG.md present AND contains cog's insertion separator.
        # `cog bump` fails with "cannot find default separator '- - -'" if the
        # module CHANGELOG lacks the `- - -` marker it prepends released sections
        # above (spec 008b). A module can otherwise lint clean yet break the
        # release pipeline, so gate on the separator here.
        changelog = module_path / "CHANGELOG.md"
        if not changelog.exists():
            violations.append(f"{name}: missing CHANGELOG.md")
        elif not any(line.strip() == "- - -" for line in changelog.read_text().splitlines()):
            violations.append(
                f"{name}: CHANGELOG.md missing the cocogitto '- - -' separator "
                f"(cog bump would fail to find its insertion point)"
            )

        # Check 4: capability declarations well-formed (spec 013 FR-010) and
        # collected for the cross-module mixed-exclusivity check below.
        copier_raw = _read_copier_yml(module_path)
        cap_violations = _check_capability_declarations(name, copier_raw)
        violations.extend(cap_violations)
        violations.extend(_check_requires_declarations(name, copier_raw))
        if not cap_violations:
            raw_provides = copier_raw.get("_bailiff_provides")
            provides = [str(e) for e in raw_provides] if isinstance(raw_provides, list) else []
            module_caps[name] = (provides, bool(copier_raw.get("_bailiff_exclusive", False)))

        # Check 5: published-label immutability (C-06)
        tags = _git_tags_for_module(name)
        if tags:
            # Find latest tag (sort by version suffix)
            latest_tag = sorted(tags)[-1]
            current_raw = copier_raw
            tagged_raw = _copier_yml_at_ref(name, latest_tag)
            current_labels = _choice_labels(current_raw)
            tagged_labels = _choice_labels(tagged_raw)
            for key, tagged_choices in tagged_labels.items():
                # C-06 forbids mutating the labels of a still-published question.
                # A key absent from the working tree is a rename/removal — a
                # breaking change governed by semver + a `feat!:` CHANGELOG
                # entry, not a silent label mutation — so it is out of scope here.
                if key not in current_labels:
                    continue
                current_choices = current_labels[key]
                if current_choices != tagged_choices:
                    violations.append(
                        f"{name}: published-label mutation on question '{key}' — "
                        f"choices at {latest_tag}: {tagged_choices!r}, "
                        f"working tree: {current_choices!r} (Constitution VI / C-06)"
                    )

    # -----------------------------------------------------------------------
    # Mixed exclusivity across first-party capability groups (spec 013 FR-010)
    # -----------------------------------------------------------------------
    violations.extend(_check_mixed_exclusivity(module_caps))

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
