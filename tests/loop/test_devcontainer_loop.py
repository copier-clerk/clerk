"""spec 012 T003: bailiff-mod-devcontainer loop tests (FR-005).

Pure MANAGED render — zero _tasks. Assertions:
- init [base, python, devcontainer] with mise_tools frozen → devcontainer.json
  references the mise devcontainer feature and lists the exact frozen tool set;
- mise_tools=[] → minimal valid JSON (base image + mise feature, no install);
- fixed base image (no devcontainer_image question — ledger FR-005);
- no secret: questions.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from bailiff import runner, trust
from tests.conftest import (
    _MODULES_DIR,
    TemplateRepo,
    _git,
)

_DC_FILE = Path(".devcontainer/devcontainer.json")
_MISE_FEATURE = "ghcr.io/devcontainers-extra/features/mise:1"
_BASE_IMAGE = "mcr.microsoft.com/devcontainers/base:ubuntu"


def _copy_devcontainer_module(tmp_path: Path) -> TemplateRepo:
    """Clone the real bailiff-mod-devcontainer tree (pure render — no tasks to stub)."""
    src = _MODULES_DIR / "bailiff-mod-devcontainer"
    dest_root = tmp_path / "bailiff-mod-devcontainer"
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest_root, dirs_exist_ok=True)
    _git(dest_root, "init", "-q")
    _git(dest_root, "add", "-A")
    _git(dest_root, "commit", "-qm", "module")
    _git(dest_root, "tag", "v1.0.0")
    return TemplateRepo(path=dest_root, tag="v1.0.0")


@pytest.fixture
def bailiff_mod_devcontainer(tmp_path: Path) -> TemplateRepo:
    return _copy_devcontainer_module(tmp_path)


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> None:
    """Init devcontainer standalone — used for render-only tests."""
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-14")


# ---------------------------------------------------------------------------
# Render: frozen mise_tools → exact tool set via the mise feature (US1 AS1)
# ---------------------------------------------------------------------------


def test_devcontainer_derives_from_mise_tools(
    bailiff_mod_devcontainer: TemplateRepo, tmp_path: Path
) -> None:
    """devcontainer.json lists exactly the frozen mise_tools set — none extra, none missing."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_devcontainer,
        dest,
        {"project_name": "myapp", "mise_tools": [{"python": "3.13"}, {"node": "22"}]},
    )

    dc_file = dest / _DC_FILE
    assert dc_file.is_file(), "devcontainer.json not rendered"
    parsed = json.loads(dc_file.read_text())

    assert parsed["name"] == "myapp"
    assert parsed["image"] == _BASE_IMAGE
    assert _MISE_FEATURE in parsed["features"]

    install_cmd = parsed["postCreateCommand"]
    assert "python@3.13" in install_cmd
    assert "node@22" in install_cmd
    # No tool listed that is absent from mise_tools: only the two pins appear.
    pins = re.findall(r"\S+@\S+", install_cmd)
    assert sorted(pins) == ["node@22", "python@3.13"], f"unexpected pins: {pins}"


# ---------------------------------------------------------------------------
# Render: empty mise_tools → minimal valid JSON (edge case)
# ---------------------------------------------------------------------------


def test_devcontainer_empty_mise_tools_minimal_valid(
    bailiff_mod_devcontainer: TemplateRepo, tmp_path: Path
) -> None:
    """mise_tools=[] renders a minimal VALID devcontainer.json (no install command)."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_devcontainer, dest, {"project_name": "empty", "mise_tools": []})

    dc_file = dest / _DC_FILE
    assert dc_file.is_file()
    parsed = json.loads(dc_file.read_text())  # must be valid JSON
    assert parsed["image"] == _BASE_IMAGE
    assert _MISE_FEATURE in parsed["features"]
    assert "postCreateCommand" not in parsed, "no install command when mise_tools is empty"


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


# ---------------------------------------------------------------------------
# Contract: no secret: questions, no devcontainer_image question
# ---------------------------------------------------------------------------


def test_no_secret_and_no_image_question() -> None:
    """FR-005 ledger: fixed base image (no devcontainer_image question); no secret:."""
    copier_yml = _MODULES_DIR / "bailiff-mod-devcontainer" / "copier.yml"
    text = copier_yml.read_text()
    assert not re.search(r"^\s+secret\s*:", text, re.MULTILINE), "secret: question found"
    # As a QUESTION key (top-level, unindented) — comments may mention the name.
    assert not re.search(r"^devcontainer_image\s*:", text, re.MULTILINE), (
        "base image must be fixed, not a question"
    )
