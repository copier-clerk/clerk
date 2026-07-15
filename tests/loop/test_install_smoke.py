"""End-to-end install smoke: install bailiff from its APM marketplace into a scratch
project and assert the skill lands correctly (spec 008, T011a, FR-008a, SC-001).

Marked `network` — skipped by default. Run explicitly with:
    pytest -m network tests/loop/test_install_smoke.py

Requires:
  - `apm` CLI installed
  - Network access to github.com (to fetch bailiff-io/bailiff)

This is the only end-to-end proof of SC-001 (installed bailiff.py --help runs from
consumer project root with its modules resolving, not from the skill dir).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_BAILIFF = REPO_ROOT / "scripts" / "bailiff.py"

pytestmark = pytest.mark.network


def _apm_available() -> bool:
    return shutil.which("apm") is not None


@pytest.mark.skipif(not _apm_available(), reason="apm CLI not installed")
class TestInstallSmoke:
    """Install bailiff from the marketplace into a temp scratch project and validate."""

    def test_install_into_scratch_project(self, tmp_path: Path) -> None:
        """SC-001: install from marketplace; bailiff.py --help runs from consumer root."""
        # 1. Add the marketplace (git-repo form per FR-008a).
        result = subprocess.run(
            ["apm", "marketplace", "add", "bailiff-io/bailiff"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0, (
            f"apm marketplace add failed:\n{result.stdout}\n{result.stderr}"
        )

        # 2. Install the bailiff package.
        result = subprocess.run(
            ["apm", "install", "bailiff"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0, (
            f"apm install bailiff failed:\n{result.stdout}\n{result.stderr}"
        )

        # 3. Locate the installed bailiff.py.
        # APM installs skills under .claude/skills/<name>/; find bailiff.py.
        skill_script = None
        for candidate in tmp_path.rglob("bailiff.py"):
            if candidate.parent.name == "scripts":
                skill_script = candidate
                break
        assert skill_script is not None, (
            "bailiff.py not found in installed skill tree — check APM install layout"
        )

        # 4. Assert that the vendored bailiff/ package sits beside bailiff.py.
        vendored_pkg = skill_script.parent / "bailiff"
        assert vendored_pkg.is_dir(), (
            f"Vendored bailiff/ package not found beside {skill_script} — "
            "install layout broken (vendoring step not run before apm pack?)"
        )
        assert (vendored_pkg / "__init__.py").is_file(), "vendored bailiff/__init__.py missing"

        # 5. Run --help from the CONSUMER PROJECT ROOT (not the skill dir).
        # This is the BLOCKER-1 / Finding-4 test: the agent's CWD is the project
        # root, so the script must resolve its modules without relying on CWD.
        result = subprocess.run(
            [sys.executable, str(skill_script), "--help"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),  # consumer project root, NOT the skill dir
        )
        assert result.returncode == 0, (
            f"bailiff.py --help failed from consumer root:\n{result.stdout}\n{result.stderr}"
        )
        assert "bailiff.py" in result.stdout, (
            f"--help output did not mention bailiff.py:\n{result.stdout}"
        )

    def test_doctor_from_consumer_root(self, tmp_path: Path) -> None:
        """doctor works from consumer project root after install."""
        subprocess.run(
            ["apm", "marketplace", "add", "bailiff-io/bailiff"],
            capture_output=True,
            cwd=str(tmp_path),
            check=True,
        )
        subprocess.run(
            ["apm", "install", "bailiff"],
            capture_output=True,
            cwd=str(tmp_path),
            check=True,
        )

        skill_script = None
        for candidate in tmp_path.rglob("bailiff.py"):
            if candidate.parent.name == "scripts":
                skill_script = candidate
                break
        assert skill_script is not None

        result = subprocess.run(
            [sys.executable, str(skill_script), "doctor"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0, f"doctor failed:\n{result.stdout}\n{result.stderr}"
