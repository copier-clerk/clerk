"""spec 009 US2 #2 / SC-006-style (T025): bailiff-mod-python renders standalone.

Init bailiff-mod-python ALONE (no base layer) → it renders with default
project_name (self-contained; no crash from the missing base). FR-010: the
overlay does not hardcode that base supplied project_name.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bailiff import runner, trust
from tests.conftest import TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def test_python_standalone_renders_with_defaults(
    bailiff_mod_python: TemplateRepo, tmp_path: Path
) -> None:
    """Overlay alone renders pyproject with default project_name and pinned version."""
    trust.add_trust(bailiff_mod_python.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_python.url, dest=str(dest), answers={"python_version": "3.13"}
    )
    runner.init(spec, today="2026-07-13")

    pyproject = (dest / "pyproject.toml").read_text()
    # Self-contained: no upstream project_name → the default fallback renders, no crash.
    assert 'name = "project"' in pyproject, "standalone must fall back to a default name"
    assert 'requires-python = ">=3.13"' in pyproject
    # Mise install sentinel present (init-only guard stub ran).
    assert (dest / ".bailiff-python-mise-installed").is_file()


def test_python_standalone_explicit_name(bailiff_mod_python: TemplateRepo, tmp_path: Path) -> None:
    """A directly supplied project_name is used when no base threads one."""
    trust.add_trust(bailiff_mod_python.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_python.url,
        dest=str(dest),
        answers={"project_name": "solo", "python_version": "3.11"},
    )
    runner.init(spec, today="2026-07-13")
    pyproject = (dest / "pyproject.toml").read_text()
    assert 'name = "solo"' in pyproject
    assert 'requires-python = ">=3.11"' in pyproject
