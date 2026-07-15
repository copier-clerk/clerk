"""Unit tests for src/bailiff/_preflight.py (spec 008, T004).

Hermetic / stdlib-only: monkeypatches importlib.util.find_spec,
importlib.metadata.version, and shutil.which to simulate dep presence,
absence, and version mismatches without actually touching the environment.

Also validates that the PEP 723 header in scripts/bailiff.py matches
_preflight.REQUIRED_DEPS / PEP723_DEPS (FR-005 equality test).
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest import mock

from bailiff._preflight import (
    PEP723_DEPS,
    REQUIRED_DEPS,
    DepIssue,
    _satisfies_spec,
    detect_manager,
    install_suggestion,
    missing_or_incompatible,
    report,
)

SCRIPTS_BAILIFF = Path(__file__).resolve().parents[2] / "scripts" / "bailiff.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_find_spec(missing: set[str]):
    """Return a find_spec replacement that returns None for names in *missing*."""
    _real = importlib.util.find_spec

    def _find_spec(name: str, *args: Any, **kwargs: Any):
        if name in missing:
            return None
        return _real(name, *args, **kwargs)

    return _find_spec


def _mock_version(overrides: dict[str, str]):
    """Return an importlib.metadata.version replacement with version overrides."""
    _real = importlib.metadata.version

    def _version(pkg: str) -> str:
        if pkg in overrides:
            return overrides[pkg]
        return _real(pkg)

    return _version


def _mock_which(available: set[str] | None):
    """Return a shutil.which replacement that finds only tools in *available*."""

    def _which(name: str, *args: Any, **kwargs: Any) -> str | None:
        if available is None:
            return None
        return name if name in available else None

    return _which


# ---------------------------------------------------------------------------
# _satisfies_spec
# ---------------------------------------------------------------------------


class TestSatisfiesSpec:
    def test_passes_within_range(self) -> None:
        assert _satisfies_spec("9.16.0", ">=9.16,<10")
        assert _satisfies_spec("9.20.3", ">=9.16,<10")

    def test_fails_below_lower_bound(self) -> None:
        assert not _satisfies_spec("9.15.0", ">=9.16,<10")

    def test_fails_at_or_above_upper_bound(self) -> None:
        assert not _satisfies_spec("10.0.0", ">=9.16,<10")
        assert not _satisfies_spec("10.1.0", ">=9.16,<10")

    def test_exact_lower_bound_passes(self) -> None:
        assert _satisfies_spec("9.16", ">=9.16,<10")

    def test_single_lower_clause(self) -> None:
        assert _satisfies_spec("1.0", ">=1.0")
        assert not _satisfies_spec("0.9", ">=1.0")

    def test_single_upper_clause(self) -> None:
        assert _satisfies_spec("0.9", "<1.0")
        assert not _satisfies_spec("1.0", "<1.0")


# ---------------------------------------------------------------------------
# missing_or_incompatible — presence
# ---------------------------------------------------------------------------


class TestMissingOrIncompatible:
    def test_all_present_no_issues(self) -> None:
        # Real environment has all deps installed (dev venv).
        issues = missing_or_incompatible()
        assert issues == [], f"Unexpected issues in dev venv: {issues}"

    def test_missing_one_dep(self) -> None:
        with mock.patch.object(importlib.util, "find_spec", _mock_find_spec({"yaml"})):
            issues = missing_or_incompatible()
        names = {i.dep.import_name for i in issues}
        assert "yaml" in names
        kinds = {i.kind for i in issues}
        assert "missing" in kinds

    def test_missing_multiple_deps(self) -> None:
        with mock.patch.object(importlib.util, "find_spec", _mock_find_spec({"yaml", "packaging"})):
            issues = missing_or_incompatible()
        names = {i.dep.import_name for i in issues}
        assert {"yaml", "packaging"} <= names

    def test_missing_copier(self) -> None:
        with mock.patch.object(importlib.util, "find_spec", _mock_find_spec({"copier"})):
            issues = missing_or_incompatible()
        assert any(i.dep.import_name == "copier" for i in issues)

    def test_only_missing_reported(self) -> None:
        """Partial: only the missing dep appears in the result."""
        with mock.patch.object(importlib.util, "find_spec", _mock_find_spec({"tomli_w"})):
            issues = missing_or_incompatible()
        names = {i.dep.import_name for i in issues}
        assert "tomli_w" in names
        # Others should be fine (present in dev venv).
        assert "yaml" not in names
        assert "packaging" not in names


# ---------------------------------------------------------------------------
# missing_or_incompatible — version pinning
# ---------------------------------------------------------------------------


class TestVersionPin:
    def test_compatible_copier_passes(self) -> None:
        with mock.patch("importlib.metadata.version", _mock_version({"copier": "9.18.0"})):
            issues = missing_or_incompatible()
        assert not any(i.dep.import_name == "copier" for i in issues)

    def test_too_old_copier_is_incompatible(self) -> None:
        with mock.patch("importlib.metadata.version", _mock_version({"copier": "9.10.0"})):
            issues = missing_or_incompatible()
        copier_issues = [i for i in issues if i.dep.import_name == "copier"]
        assert len(copier_issues) == 1
        assert copier_issues[0].kind == "incompatible"
        assert copier_issues[0].installed_version == "9.10.0"

    def test_copier_10_is_incompatible(self) -> None:
        with mock.patch("importlib.metadata.version", _mock_version({"copier": "10.0.0"})):
            issues = missing_or_incompatible()
        copier_issues = [i for i in issues if i.dep.import_name == "copier"]
        assert len(copier_issues) == 1
        assert copier_issues[0].kind == "incompatible"

    def test_pyyaml_any_version_passes(self) -> None:
        """pyyaml has no version pin — any installed version is fine."""
        with mock.patch("importlib.metadata.version", _mock_version({"pyyaml": "1.0.0"})):
            issues = missing_or_incompatible()
        assert not any(i.dep.import_name == "yaml" for i in issues)

    def test_missing_metadata_treated_as_incompatible(self) -> None:
        """When module is found but metadata is absent, report incompatible."""

        def _no_meta(pkg: str) -> str:
            if pkg == "copier":
                raise importlib.metadata.PackageNotFoundError(pkg)
            return importlib.metadata.version(pkg)

        with mock.patch("importlib.metadata.version", _no_meta):
            issues = missing_or_incompatible()
        copier_issues = [i for i in issues if i.dep.import_name == "copier"]
        assert len(copier_issues) == 1
        assert copier_issues[0].kind == "incompatible"
        assert copier_issues[0].installed_version == "unknown"


# ---------------------------------------------------------------------------
# detect_manager + install_suggestion
# ---------------------------------------------------------------------------


class TestDetectManager:
    def test_uv_first(self) -> None:
        with mock.patch.object(shutil, "which", _mock_which({"uv", "pip", "pipx"})):
            assert detect_manager() == "uv"

    def test_pipx_when_no_uv(self) -> None:
        with mock.patch.object(shutil, "which", _mock_which({"pipx", "pip"})):
            assert detect_manager() == "pipx"

    def test_pip(self) -> None:
        with mock.patch.object(shutil, "which", _mock_which({"pip"})):
            assert detect_manager() == "pip"

    def test_pip3_fallback(self) -> None:
        with mock.patch.object(shutil, "which", _mock_which({"pip3"})):
            assert detect_manager() == "pip3"

    def test_none_when_nothing(self) -> None:
        with mock.patch.object(shutil, "which", _mock_which(None)):
            assert detect_manager() is None


class TestInstallSuggestion:
    def _make_missing_issue(self, import_name: str, install_name: str) -> DepIssue:
        dep = next(d for d in REQUIRED_DEPS if d.import_name == import_name)
        return DepIssue(dep=dep, kind="missing", installed_version=None)

    def test_uv_suggestion(self) -> None:
        issues = [self._make_missing_issue("yaml", "pyyaml")]
        with mock.patch.object(shutil, "which", _mock_which({"uv"})):
            suggestion = install_suggestion(issues)
        assert "uv pip install" in suggestion
        assert "pyyaml" in suggestion

    def test_pip_suggestion(self) -> None:
        issues = [self._make_missing_issue("yaml", "pyyaml")]
        with mock.patch.object(shutil, "which", _mock_which({"pip"})):
            suggestion = install_suggestion(issues)
        assert "pip install" in suggestion
        assert "pyyaml" in suggestion

    def test_pipx_falls_back_to_pip(self) -> None:
        issues = [self._make_missing_issue("yaml", "pyyaml")]
        with mock.patch.object(shutil, "which", _mock_which({"pipx"})):
            suggestion = install_suggestion(issues)
        assert "pip install" in suggestion

    def test_no_manager_generic_fallback(self) -> None:
        issues = [self._make_missing_issue("yaml", "pyyaml")]
        with mock.patch.object(shutil, "which", _mock_which(None)):
            suggestion = install_suggestion(issues)
        assert "pip install" in suggestion
        assert "uv" in suggestion.lower()  # pointer to uv

    def test_brew_offered_only_for_copier(self) -> None:
        """brew is offered for copier but NOT for pyyaml/packaging/tomli-w."""
        copier_issue = [self._make_missing_issue("copier", "copier")]
        pyyaml_issue = [self._make_missing_issue("yaml", "pyyaml")]

        with mock.patch.object(shutil, "which", _mock_which({"pip"})):
            copier_sugg = install_suggestion(copier_issue)
            pyyaml_sugg = install_suggestion(pyyaml_issue)

        assert "brew" in copier_sugg
        assert "brew" not in pyyaml_sugg

    def test_empty_issues_returns_empty(self) -> None:
        assert install_suggestion([]) == ""

    def test_partial_only_missing_in_suggestion(self) -> None:
        """Only the missing/incompatible dep appears in the suggestion."""
        issues = [self._make_missing_issue("yaml", "pyyaml")]
        with mock.patch.object(shutil, "which", _mock_which({"pip"})):
            suggestion = install_suggestion(issues)
        assert "pyyaml" in suggestion
        # copier should NOT appear if it wasn't in the issues list
        assert "copier" not in suggestion


# ---------------------------------------------------------------------------
# report()
# ---------------------------------------------------------------------------


class TestReport:
    def test_empty_returns_empty(self) -> None:
        assert report([]) == ""

    def test_missing_dep_named(self) -> None:
        dep = next(d for d in REQUIRED_DEPS if d.import_name == "yaml")
        issue = DepIssue(dep=dep, kind="missing", installed_version=None)
        with mock.patch.object(shutil, "which", _mock_which({"pip"})):
            text = report([issue])
        assert "pyyaml" in text
        assert "not installed" in text

    def test_incompatible_dep_shows_version(self) -> None:
        dep = next(d for d in REQUIRED_DEPS if d.import_name == "copier")
        issue = DepIssue(dep=dep, kind="incompatible", installed_version="9.10.0")
        with mock.patch.object(shutil, "which", _mock_which({"pip"})):
            text = report([issue])
        assert "9.10.0" in text
        assert "incompatible" in text.lower()


# ---------------------------------------------------------------------------
# --help and doctor work with deps missing (preflight after argparse)
# ---------------------------------------------------------------------------


class TestHelpAndDoctorWithMissingDeps:
    """Verify FR-004: --help and doctor exit cleanly even without third-party deps."""

    def _run_bailiff(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS_BAILIFF), *args],
            capture_output=True,
            text=True,
        )

    def test_help_exits_zero(self) -> None:
        """--help should always exit 0 (argparse handles it before preflight)."""
        result = self._run_bailiff("--help")
        assert result.returncode == 0
        assert "bailiff.py" in result.stdout

    def test_doctor_all_present(self) -> None:
        """doctor exits 0 when all deps are present (dev venv)."""
        result = self._run_bailiff("doctor")
        assert result.returncode == 0
        assert "Ready" in result.stdout


# ---------------------------------------------------------------------------
# PEP 723 header == REQUIRED_DEPS (FR-005 equality test)
# ---------------------------------------------------------------------------


class TestPep723HeaderConsistency:
    """The static PEP 723 header comment must list the same deps as PEP723_DEPS."""

    def _parse_pep723_deps(self) -> list[str]:
        """Extract the dependencies list from the # /// script header."""
        text = SCRIPTS_BAILIFF.read_text()
        # Match the block between `# /// script` and `# ///`
        match = re.search(
            r"^# /// script\n(.*?)^# ///$",
            text,
            re.MULTILINE | re.DOTALL,
        )
        assert match, "PEP 723 header block not found in scripts/bailiff.py"
        block = match.group(1)
        # Extract the dependencies = [...] list
        dep_match = re.search(
            r"dependencies\s*=\s*\[(.*?)\]",
            block,
            re.DOTALL,
        )
        assert dep_match, "dependencies field not found in PEP 723 header"
        raw = dep_match.group(1)
        # Parse quoted strings from the list
        return re.findall(r'"([^"]+)"', raw)

    def test_pep723_matches_required_deps(self) -> None:
        """The header deps must equal PEP723_DEPS (the canonical list in _preflight.py)."""
        header_deps = self._parse_pep723_deps()
        assert sorted(header_deps) == sorted(PEP723_DEPS), (
            f"PEP 723 header deps {header_deps!r} do not match "
            f"_preflight.PEP723_DEPS {PEP723_DEPS!r}"
        )
