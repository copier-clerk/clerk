"""End-to-end install smoke: install bailiff from its APM marketplace into a scratch
project and assert the skill lands correctly (spec 008 T011a; reshaped by spec 013).

Marked `network` — skipped by default. Run explicitly with:
    pytest -m network tests/loop/test_install_smoke.py

Requires:
  - `apm` CLI installed
  - Network access to github.com (to fetch bailiff-io/bailiff)

Spec 013 (ADR-0008): the skill package ships ONLY SKILL.md; the deterministic
engine is the `bailiff` PyPI CLI (`uvx bailiff`). The install smoke therefore
asserts the skill lands WITHOUT any bundled script or vendored module tree.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.network


def _apm_available() -> bool:
    return shutil.which("apm") is not None


@pytest.mark.skipif(not _apm_available(), reason="apm CLI not installed")
class TestInstallSmoke:
    """Install bailiff from the marketplace into a temp scratch project and validate."""

    def _install(self, tmp_path: Path) -> Path:
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
        skill_md = None
        for candidate in tmp_path.rglob("SKILL.md"):
            if candidate.parent.name == "bailiff":
                skill_md = candidate
                break
        assert skill_md is not None, "bailiff SKILL.md not found in installed tree"
        return skill_md

    def test_install_lands_skill_without_bundled_script(self, tmp_path: Path) -> None:
        skill_md = self._install(tmp_path)
        # Spec 013 FR-006: no bundled script, no vendored module tree.
        skill_dir = skill_md.parent
        assert not (skill_dir / "scripts").exists(), (
            "installed skill still carries a scripts/ tree — vendor step not updated?"
        )
        assert "uvx bailiff" in skill_md.read_text(), (
            "installed SKILL.md does not reference the uvx bailiff invocation"
        )

    def test_uvx_bailiff_doctor(self, tmp_path: Path) -> None:
        """The documented invocation path works from a consumer project root."""
        if shutil.which("uvx") is None:
            pytest.skip("uvx not installed")
        result = subprocess.run(
            ["uvx", "bailiff", "doctor"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0, f"doctor failed:\n{result.stdout}\n{result.stderr}"
