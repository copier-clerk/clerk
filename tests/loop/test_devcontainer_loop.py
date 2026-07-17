"""spec 014 / FR-009: bailiff-mod-devcontainer loop tests.

Pure MANAGED render — zero _tasks. Assertions:
- postCreateCommand is bare `mise trust && mise install` (reads merged .mise/conf.d/
  at runtime — no explicit tool list; FR-009);
- no mise_tools question (removed per spec 014 US3);
- project_name renders in the devcontainer name field;
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
_BARE_INSTALL = "mise install"


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
# Render: postCreateCommand is bare mise install (FR-009)
# ---------------------------------------------------------------------------


def test_devcontainer_post_create_command_bare_mise_install(
    bailiff_mod_devcontainer: TemplateRepo, tmp_path: Path
) -> None:
    """postCreateCommand runs bare `mise install` — no explicit tool list (FR-009).

    The command reads the merged .mise/conf.d/ at container-create time, so the
    devcontainer does not need to know which tools are present.
    """
    dest = tmp_path / "proj"
    _init(bailiff_mod_devcontainer, dest, {"project_name": "myapp"})

    dc_file = dest / _DC_FILE
    assert dc_file.is_file(), "devcontainer.json not rendered"
    parsed = json.loads(dc_file.read_text())

    assert parsed["name"] == "myapp"
    assert parsed["image"] == _BASE_IMAGE
    assert _MISE_FEATURE in parsed["features"]

    install_cmd = parsed["postCreateCommand"]
    assert _BARE_INSTALL in install_cmd, f"expected bare mise install in: {install_cmd!r}"
    # No pinned tool versions — bare install only.
    pins = re.findall(r"\S+@\S+", install_cmd)
    assert pins == [], f"unexpected tool pins in postCreateCommand: {pins}"


# ---------------------------------------------------------------------------
# Render: postCreateCommand always present (not conditional on tool list)
# ---------------------------------------------------------------------------


def test_devcontainer_postCreateCommand_always_present(
    bailiff_mod_devcontainer: TemplateRepo, tmp_path: Path
) -> None:
    """postCreateCommand is unconditional — not gated on a tool list (spec 014 FR-009)."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_devcontainer, dest, {"project_name": "any"})

    dc_file = dest / _DC_FILE
    assert dc_file.is_file()
    parsed = json.loads(dc_file.read_text())  # must be valid JSON
    assert parsed["image"] == _BASE_IMAGE
    assert _MISE_FEATURE in parsed["features"]
    assert "postCreateCommand" in parsed, "postCreateCommand must always be present"
    assert _BARE_INSTALL in parsed["postCreateCommand"]


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


# ---------------------------------------------------------------------------
# Contract: no secret: questions, no devcontainer_image question, no mise_tools
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


def test_no_mise_tools_question() -> None:
    """mise_tools removed per spec 014 US3 (FR-009): no explicit tool list in devcontainer."""
    copier_yml = _MODULES_DIR / "bailiff-mod-devcontainer" / "copier.yml"
    text = copier_yml.read_text()
    # Must not be a top-level question key (unindented).
    assert not re.search(r"^mise_tools\s*:", text, re.MULTILINE), (
        "mise_tools question must be removed (spec 014 US3)"
    )
