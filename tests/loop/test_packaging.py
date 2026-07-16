"""Tests for the APM packaging config + vendor drift check (spec 008, T011).

These tests are structural/hermetic — they read files and run subprocess commands
(no network, no live APM registry). apm-CLI-dependent steps skip cleanly when
the `apm` binary is not installed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[2]
APM_YML = REPO_ROOT / "apm.yml"
PACKAGES_DIR = REPO_ROOT / "packages" / "bailiff"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apm_available() -> bool:
    return shutil.which("apm") is not None


# ---------------------------------------------------------------------------
# apm.yml structural assertions (no apm binary needed)
# ---------------------------------------------------------------------------


class TestApmYmlMarketplaceBlock:
    def _load(self) -> dict:
        return yaml.safe_load(APM_YML.read_text())

    def test_marketplace_key_present(self) -> None:
        data = self._load()
        assert "marketplace" in data, "apm.yml missing 'marketplace:' block"

    def test_outputs_has_claude_and_codex(self) -> None:
        data = self._load()
        outputs = data["marketplace"]["outputs"]
        assert "claude" in outputs, "marketplace.outputs missing 'claude'"
        assert "codex" in outputs, "marketplace.outputs missing 'codex'"

    def test_packages_list_non_empty(self) -> None:
        data = self._load()
        packages = data["marketplace"]["packages"]
        assert isinstance(packages, list) and packages, (
            "marketplace.packages must be a non-empty list"
        )

    def test_bailiff_package_has_category(self) -> None:
        data = self._load()
        packages = data["marketplace"]["packages"]
        bailiff_pkg = next((p for p in packages if p["name"] == "bailiff"), None)
        assert bailiff_pkg is not None, "No 'bailiff' entry in marketplace.packages"
        assert "category" in bailiff_pkg, (
            "bailiff package missing 'category:' — required when codex output is enabled"
        )

    def test_bailiff_package_has_license(self) -> None:
        data = self._load()
        packages = data["marketplace"]["packages"]
        bailiff_pkg = next(p for p in packages if p["name"] == "bailiff")
        assert "license" in bailiff_pkg, "bailiff package missing 'license:' (SBOM NOASSERTION)"

    def test_bailiff_package_source_is_local_path(self) -> None:
        data = self._load()
        packages = data["marketplace"]["packages"]
        bailiff_pkg = next(p for p in packages if p["name"] == "bailiff")
        assert bailiff_pkg["source"] == "./packages/bailiff", (
            f"Expected source './packages/bailiff', got {bailiff_pkg['source']!r}"
        )

    def test_top_level_license_present(self) -> None:
        data = self._load()
        assert "license" in data, "apm.yml top-level 'license:' missing (SBOM NOASSERTION)"


# ---------------------------------------------------------------------------
# Package layout assertions
# ---------------------------------------------------------------------------


class TestPackageLayout:
    def test_package_apm_yml_exists(self) -> None:
        assert (PACKAGES_DIR / "apm.yml").is_file()

    def test_plugin_json_exists(self) -> None:
        assert (PACKAGES_DIR / ".claude-plugin" / "plugin.json").is_file()

    def test_skill_md_exists(self) -> None:
        # Copied by `just vendor`; check it exists in the vendored location.
        skill_md = PACKAGES_DIR / ".apm" / "skills" / "bailiff" / "SKILL.md"
        assert skill_md.is_file(), f"SKILL.md not found at {skill_md} — run 'just vendor' first"

    def test_no_bundled_script_in_package(self) -> None:
        # Spec 013 FR-006: the skill package ships ONLY SKILL.md; the engine is
        # the bailiff PyPI CLI. A scripts/ tree here means a stale vendor step.
        scripts_dir = PACKAGES_DIR / ".apm" / "skills" / "bailiff" / "scripts"
        assert not scripts_dir.exists(), (
            f"stale vendored scripts tree at {scripts_dir} — spec 013 removed it"
        )


# ---------------------------------------------------------------------------
# Vendor drift check
# ---------------------------------------------------------------------------


class TestVendorDrift:
    """The vendored SKILL.md must match the source after `just vendor`."""

    def test_vendored_skill_md_matches_src(self) -> None:
        src = REPO_ROOT / "skills" / "bailiff" / "SKILL.md"
        dst = PACKAGES_DIR / ".apm" / "skills" / "bailiff" / "SKILL.md"
        assert dst.is_file(), f"Vendored SKILL.md missing at {dst} — run 'just vendor'"
        assert src.read_bytes() == dst.read_bytes(), (
            "Vendor drift: SKILL.md differs from source — run 'just vendor'"
        )


# ---------------------------------------------------------------------------
# apm pack dry-run (skips if apm not installed)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _apm_available(), reason="apm CLI not installed")
class TestApmPackDryRun:
    def test_pack_dry_run_exits_zero(self) -> None:
        result = subprocess.run(
            ["apm", "pack", "--marketplace=claude,codex", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"apm pack --dry-run failed:\n{result.stdout}\n{result.stderr}"
        )

    def test_pack_produces_claude_manifest(self) -> None:
        result = subprocess.run(
            ["apm", "pack", "--marketplace=claude,codex"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        claude_manifest = REPO_ROOT / ".claude-plugin" / "marketplace.json"
        assert claude_manifest.is_file(), ".claude-plugin/marketplace.json not produced"

    def test_pack_produces_codex_manifest(self) -> None:
        result = subprocess.run(
            ["apm", "pack", "--marketplace=claude,codex"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        codex_manifest = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
        assert codex_manifest.is_file(), ".agents/plugins/marketplace.json not produced"


# ---------------------------------------------------------------------------
# bailiff doctor subprocess exit codes
# ---------------------------------------------------------------------------


class TestBailiffDoctorExitCodes:
    def test_doctor_exits_zero_with_all_deps(self) -> None:
        """doctor returns 0 when all deps are present (dev venv has them all)."""
        result = subprocess.run(
            [sys.executable, "-m", "bailiff", "doctor"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"bailiff doctor failed unexpectedly:\n{result.stdout}\n{result.stderr}"
        )

    def test_doctor_output_says_ready(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "bailiff", "doctor"],
            capture_output=True,
            text=True,
        )
        assert "Ready" in result.stdout or "ready" in result.stdout.lower()
