"""Stdlib-only preflight: check third-party deps are present and version-compatible.

Runs BEFORE any third-party imports, so it must import nothing outside stdlib.
Scope: macOS/Linux + WSL on Windows (no native-Windows PATH/py-launcher handling).
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import shutil
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Dependency declarations
# ---------------------------------------------------------------------------

# Each entry is (import_name, install_name, version_spec_or_None).
# [project.dependencies] in pyproject.toml and the install commands generated
# below must stay in sync with this list; an equality test in tests/ enforces that.
#
# version_spec format: ">=X.Y,<Z" (a PEP 440 specifier; None means any version).
# We hand-parse simple ">=" / "<" pairs rather than importing `packaging`
# (which is itself a checked dep and may not be installed yet).


class _DepSpec(NamedTuple):
    import_name: str  # name used in `import` / `find_spec`
    install_name: str  # name used in pip/uv install commands
    version_spec: str | None  # None → any installed version is fine
    brew_formula: str | None  # brew formula name, or None if not brew-installable


REQUIRED_DEPS: list[_DepSpec] = [
    _DepSpec("copier", "copier", ">=9.16,<10", "copier"),
    _DepSpec("yaml", "pyyaml", None, None),
    _DepSpec("packaging", "packaging", None, None),
    _DepSpec("tomli_w", "tomli-w", None, None),
]

# ---------------------------------------------------------------------------
# Version-spec parsing (no `packaging` dep)
# ---------------------------------------------------------------------------


def _satisfies_spec(version: str, spec: str) -> bool:
    """Return True iff *version* satisfies a simple ">=A,<B" / ">=A" / "<B" spec.

    Only handles the exact forms used in REQUIRED_DEPS above — no full PEP 440
    parser. Inputs are normalised dot-tuples for comparison, so pre-release
    qualifiers are stripped (conservative: "9.16.0rc1" → (9, 16, 0)).
    """

    def _to_tuple(v: str) -> tuple[int, ...]:
        # Strip any pre/post-release suffix after the numeric portion.
        import re

        numeric = re.match(r"[\d.]+", v)
        parts = numeric.group(0).rstrip(".").split(".") if numeric else ["0"]
        return tuple(int(p) for p in parts if p.isdigit())

    ver_t = _to_tuple(version)
    for clause in spec.split(","):
        clause = clause.strip()
        if clause.startswith(">="):
            bound = _to_tuple(clause[2:])
            if not (ver_t >= bound):
                return False
        elif clause.startswith("<="):
            bound = _to_tuple(clause[2:])
            if not (ver_t <= bound):
                return False
        elif clause.startswith(">"):
            bound = _to_tuple(clause[1:])
            if not (ver_t > bound):
                return False
        elif clause.startswith("<"):
            bound = _to_tuple(clause[1:])
            if not (ver_t < bound):
                return False
        elif clause.startswith("=="):
            bound = _to_tuple(clause[2:])
            if ver_t != bound:
                return False
        elif clause.startswith("!="):
            bound = _to_tuple(clause[2:])
            if ver_t == bound:
                return False
    return True


# ---------------------------------------------------------------------------
# Per-dep check
# ---------------------------------------------------------------------------


class DepIssue(NamedTuple):
    dep: _DepSpec
    kind: str  # "missing" | "incompatible"
    installed_version: str | None  # set for "incompatible"


def missing_or_incompatible() -> list[DepIssue]:
    """Return a list of deps that are absent or whose installed version fails the pin.

    Returns an empty list iff all deps are present and version-compatible.
    """
    issues: list[DepIssue] = []
    for dep in REQUIRED_DEPS:
        spec = importlib.util.find_spec(dep.import_name)
        if spec is None:
            issues.append(DepIssue(dep=dep, kind="missing", installed_version=None))
            continue
        if dep.version_spec is None:
            continue  # any version is fine
        # Resolve the installed version via importlib.metadata using the *install* name.
        try:
            installed = importlib.metadata.version(dep.install_name)
        except importlib.metadata.PackageNotFoundError:
            # Module exists but metadata is missing (editable/unusual install).
            # Be conservative: treat as incompatible so the user is alerted.
            issues.append(DepIssue(dep=dep, kind="incompatible", installed_version="unknown"))
            continue
        if not _satisfies_spec(installed, dep.version_spec):
            issues.append(DepIssue(dep=dep, kind="incompatible", installed_version=installed))
    return issues


# ---------------------------------------------------------------------------
# Package-manager detection
# ---------------------------------------------------------------------------


def detect_manager() -> str | None:
    """Return the first package manager found on PATH, or None.

    Detection order: uv → pipx → pip → pip3.
    brew is NOT returned here; it is offered only for copier (see install_suggestion).
    """
    for mgr in ("uv", "pipx", "pip", "pip3"):
        if shutil.which(mgr):
            return mgr
    return None


# ---------------------------------------------------------------------------
# Install suggestion builder
# ---------------------------------------------------------------------------


def install_suggestion(issues: list[DepIssue]) -> str:
    """Return a human-readable, environment-aware install suggestion for *issues*.

    Detects the package manager in the same call (for testability via monkeypatching).
    brew is offered only for packages with a brew_formula; all other pkgs use
    uv/pipx/pip. Falls back to generic `pip install` if nothing is on PATH.
    """
    if not issues:
        return ""

    mgr = detect_manager()

    # Separate brew-installable (copier only) from pip-installable deps.
    brew_deps = [i for i in issues if i.dep.brew_formula is not None]

    lines: list[str] = []

    if mgr == "uv":
        all_install_names = [i.dep.install_name for i in issues]
        # uv tool install for tool-like packages when using pipx workflow is less
        # common; prefer `uv pip install` (works in both venv and project contexts).
        lines.append(f"  uv pip install {' '.join(all_install_names)}")
        lines.append("  # or, in a uv project: uv add " + " ".join(all_install_names))
    elif mgr == "pipx":
        # pipx is for isolated tool installs; for library deps, suggest pip fallback.
        pip_names = [i.dep.install_name for i in issues]
        lines.append(f"  pip install {' '.join(pip_names)}")
        lines.append("  # (pipx is for tools; use pip/uv for library deps)")
    elif mgr in ("pip", "pip3"):
        pip_names = [i.dep.install_name for i in issues]
        lines.append(f"  {mgr} install {' '.join(pip_names)}")
    else:
        # Nothing on PATH — generic fallback.
        pip_names = [i.dep.install_name for i in issues]
        lines.append(f"  pip install {' '.join(pip_names)}")
        lines.append(
            "  # Tip: install uv (https://docs.astral.sh/uv/) for frictionless dep management."
        )

    # Offer brew for the brew-installable subset regardless of pip manager.
    if brew_deps:
        brew_formulae = [i.dep.brew_formula for i in brew_deps if i.dep.brew_formula]
        lines.append("  # macOS alternative for copier: brew install " + " ".join(brew_formulae))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def report(issues: list[DepIssue]) -> str:
    """Format a human-readable preflight report for the given issues.

    Returns an empty string when *issues* is empty (all deps satisfied).
    """
    if not issues:
        return ""

    parts: list[str] = ["bailiff: missing or incompatible dependencies detected."]
    for issue in issues:
        dep = issue.dep
        if issue.kind == "missing":
            parts.append(f"  - {dep.install_name}: not installed")
        else:
            spec_note = f" (requires {dep.version_spec})" if dep.version_spec else ""
            parts.append(
                f"  - {dep.install_name}: installed {issue.installed_version}{spec_note}"
                " — version incompatible"
            )
    parts.append("")
    parts.append("Install suggestion:")
    parts.append(install_suggestion(issues))
    return "\n".join(parts)
