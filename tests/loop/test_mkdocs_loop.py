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


# ---------------------------------------------------------------------------
# spec 014 T027: mise conf.d drop-in rendered; no .mise.toml (FR-008)
# ---------------------------------------------------------------------------


def test_mise_confd_rendered(bailiff_mod_mkdocs: TemplateRepo, tmp_path: Path) -> None:
    """mkdocs renders its own .mise/conf.d fragment; no .mise.toml is produced."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_mkdocs,
        dest,
        {"project_name": "myapp", "description": "docs"},
    )

    confd = dest / ".mise" / "conf.d" / "bailiff-mod-mkdocs.toml"
    assert confd.is_file(), ".mise/conf.d/bailiff-mod-mkdocs.toml not rendered (T027)"

    # Fragment must carry [tools] with mkdocs + mkdocs-material — no other tools.
    import tomllib

    with confd.open("rb") as fh:
        parsed = tomllib.load(fh)
    assert "tools" in parsed, "conf.d fragment missing [tools] section"
    tools = parsed["tools"]
    assert "mkdocs" in tools, "mkdocs not in conf.d [tools]"
    assert "mkdocs-material" in tools, "mkdocs-material not in conf.d [tools]"

    # No .mise.toml written by this module (base owned the union writer; it is
    # also gone after T019, but mkdocs must never be the fallback writer).
    assert not (dest / ".mise.toml").exists(), ".mise.toml must not be written by mkdocs module"


# ---------------------------------------------------------------------------
# spec 014 T035/T037: _external_data alias declared for base facts (FR-004)
# ---------------------------------------------------------------------------


def test_external_data_alias_declared() -> None:
    """copier.yml declares _external_data: {base: .copier-answers.bailiff-mod-base.yml}."""
    raw = yaml.safe_load((_MODULES_DIR / "bailiff-mod-mkdocs" / "copier.yml").read_text())
    ext = raw.get("_external_data", {})
    assert ext.get("base") == ".copier-answers.bailiff-mod-base.yml", (
        "_external_data.base must point to .copier-answers.bailiff-mod-base.yml"
    )


def test_depends_on_edge_and_phase() -> None:
    """copier.yml uses depends_on (not run_after) and declares phase: normal (spec 014 T027)."""
    raw = yaml.safe_load((_MODULES_DIR / "bailiff-mod-mkdocs" / "copier.yml").read_text())
    assert "run_after" not in raw, "run_after must be removed; use depends_on"
    deps = raw.get("depends_on", {}).get("default", [])
    assert "bailiff-mod-base" in deps, "depends_on must include bailiff-mod-base"
    assert raw.get("phase", {}).get("default") == "normal", "phase must be normal"
