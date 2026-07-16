"""spec 012 T008: bailiff-mod-mkdocs loop tests (FR-011).

Pure render — zero _tasks. Assertions (US5 AS1-3):
- managed mkdocs.yml wired to docs/;
- docs/index.md is seed-once (_skip_if_exists): a project edit survives
  reproduce over the populated tree;
- no _tasks at all (no build/deploy/network at scaffold time);
- no secret: questions.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from tests.conftest import (
    _BASE_STUB_TASKS,
    _MODULES_DIR,
    TemplateRepo,
    _copy_module_with_stub_tasks,
    _git,
)

_MKDOCS = Path("mkdocs.yml")
_INDEX = Path("docs/index.md")


def _copy_mkdocs_module(tmp_path: Path) -> TemplateRepo:
    """Clone the real bailiff-mod-mkdocs tree (pure render — no tasks to stub)."""
    src = _MODULES_DIR / "bailiff-mod-mkdocs"
    dest_root = tmp_path / "bailiff-mod-mkdocs"
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest_root, dirs_exist_ok=True)
    _git(dest_root, "init", "-q")
    _git(dest_root, "add", "-A")
    _git(dest_root, "commit", "-qm", "module")
    _git(dest_root, "tag", "v1.0.0")
    return TemplateRepo(path=dest_root, tag="v1.0.0")


@pytest.fixture
def bailiff_mod_mkdocs(tmp_path: Path) -> TemplateRepo:
    return _copy_mkdocs_module(tmp_path)


@pytest.fixture
def bailiff_mod_base(tmp_path: Path) -> TemplateRepo:
    return _copy_module_with_stub_tasks(
        "bailiff-mod-base", tmp_path / "bailiff-mod-base", _BASE_STUB_TASKS
    )


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _record(full_id: str, repo: TemplateRepo) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=["project_name"],
    )


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-14")


# ---------------------------------------------------------------------------
# Managed mkdocs.yml wired to docs/ + seed-once starter page (US5 AS1)
# ---------------------------------------------------------------------------


def test_mkdocs_yml_and_seeded_index(bailiff_mod_mkdocs: TemplateRepo, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_mkdocs,
        dest,
        {"project_name": "myapp", "description": "My docs site"},
    )

    mk = dest / _MKDOCS
    assert mk.is_file(), "mkdocs.yml not rendered"
    parsed = yaml.safe_load(mk.read_text())
    assert parsed["site_name"] == "myapp"
    assert parsed["docs_dir"] == "docs"
    assert parsed["theme"]["name"] == "material"

    idx = dest / _INDEX
    assert idx.is_file(), "docs/index.md not seeded"
    assert "# myapp" in idx.read_text()


# ---------------------------------------------------------------------------
# Seed-once + managed reproduce (US5 AS2 / SC-006)
# ---------------------------------------------------------------------------


def test_edited_index_preserved_on_reproduce(
    bailiff_mod_base: TemplateRepo, bailiff_mod_mkdocs: TemplateRepo, tmp_path: Path
) -> None:
    """A project edit to docs/index.md survives reproduce (seed-once)."""
    trust.add_trust(bailiff_mod_base.url)
    trust.add_trust(bailiff_mod_mkdocs.url)

    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/bailiff-mod-base", bailiff_mod_base),
            {
                "project_name": "myapp",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": [],
            },
        ),
        (
            _record("demo/bailiff-mod-mkdocs", bailiff_mod_mkdocs),
            {"project_name": "myapp", "description": ""},
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    mk = dest / _MKDOCS
    idx = dest / _INDEX
    assert mk.is_file() and idx.is_file()

    edited = "# My edited docs\n\nproject-owned content\n"
    idx.write_text(edited)

    runner.reproduce_many(str(dest))

    assert idx.read_text() == edited, "seed-once docs/index.md clobbered on reproduce"


# ---------------------------------------------------------------------------
# Contract: zero tasks, seed-once declared, no secret: (US5 AS3)
# ---------------------------------------------------------------------------


def test_zero_tasks_and_skip_if_exists() -> None:
    raw = yaml.safe_load((_MODULES_DIR / "bailiff-mod-mkdocs" / "copier.yml").read_text())
    assert "_tasks" not in raw, "mkdocs module must have zero _tasks (no build/deploy)"
    assert "docs/index.md" in raw.get("_skip_if_exists", []), "index.md must be seed-once"


def test_no_secret_questions() -> None:
    text = (_MODULES_DIR / "bailiff-mod-mkdocs" / "copier.yml").read_text()
    assert not re.search(r"^\s+secret\s*:", text, re.MULTILINE)
