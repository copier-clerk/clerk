"""spec 012 T003: bailiff-mod-devcontainer loop tests (FR-005).

Pure MANAGED render — zero _tasks. Assertions:
- init [base, python, devcontainer] with mise_tools frozen → devcontainer.json
  references the mise devcontainer feature and lists the exact frozen tool set;
- mise_tools=[] → minimal valid JSON (base image + mise feature, no install);
- byte-identical on init AND reproduce (managed lifecycle);
- fixed base image (no devcontainer_image question — ledger FR-005);
- no secret: questions.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from tests.conftest import (
    _BASE_STUB_TASKS,
    _MODULES_DIR,
    _PYTHON_STUB_TASKS,
    TemplateRepo,
    _copy_module_with_stub_tasks,
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


@pytest.fixture
def bailiff_mod_base(tmp_path: Path) -> TemplateRepo:
    return _copy_module_with_stub_tasks(
        "bailiff-mod-base", tmp_path / "bailiff-mod-base", _BASE_STUB_TASKS
    )


@pytest.fixture
def bailiff_mod_python(tmp_path: Path) -> TemplateRepo:
    return _copy_module_with_stub_tasks(
        "bailiff-mod-python", tmp_path / "bailiff-mod-python", _PYTHON_STUB_TASKS
    )


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(full_id: str, repo: TemplateRepo, questions: list[str]) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=questions,
    )


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


# ---------------------------------------------------------------------------
# Reproduce: byte-identical managed render over [base, python, devcontainer]
# ---------------------------------------------------------------------------


def test_devcontainer_byte_identical_on_reproduce(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_python: TemplateRepo,
    bailiff_mod_devcontainer: TemplateRepo,
    tmp_path: Path,
) -> None:
    """US1 AS2 / SC-001: managed render is byte-identical after reproduce, no re-shelling."""
    for repo in (bailiff_mod_base, bailiff_mod_python, bailiff_mod_devcontainer):
        trust.add_trust(repo.url)

    mise_tools = [{"python": "3.13"}]
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/bailiff-mod-base", bailiff_mod_base, ["project_name"]),
            {
                "project_name": "myapp",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": [],
                "mise_tools": mise_tools,
            },
        ),
        (
            _record("demo/bailiff-mod-python", bailiff_mod_python, ["project_name"]),
            {"project_name": "myapp", "mise_tools": mise_tools},
        ),
        (
            _record("demo/bailiff-mod-devcontainer", bailiff_mod_devcontainer, ["project_name"]),
            {"project_name": "myapp", "mise_tools": mise_tools},
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    dc_file = dest / _DC_FILE
    assert dc_file.is_file()
    parsed = json.loads(dc_file.read_text())
    assert "python@3.13" in parsed["postCreateCommand"]
    before = _digest(dc_file)

    runner.reproduce_many(str(dest))

    assert _digest(dc_file) == before, "devcontainer.json changed on reproduce"


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
