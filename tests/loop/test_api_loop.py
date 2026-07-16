"""spec 012 T010 / spec 014: bailiff-mod-api loop tests.

Assertions (spec 014 fragment/merge model + FR-001/013):
- seed-once openapi.yaml at the REPO ROOT: minimal valid OpenAPI 3.1 skeleton;
  a project edit survives reproduce over the populated tree;
- managed .spectral.yaml rendered on init;
- managed .mise/conf.d/bailiff-mod-api.toml rendered on init;
- hook_manager=none → .pre-commit.d/bailiff-mod-api.yaml absent or empty (fragment inert);
- hook_manager=pre-commit → .pre-commit.d/bailiff-mod-api.yaml contains spectral-lint block;
- no secret: questions; no mise_tools / hook_blocks union questions.
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
    _PRECOMMIT_STUB_TASKS,
    TemplateRepo,
    _copy_module_with_stub_tasks,
    _git,
)

_OPENAPI = Path("openapi.yaml")
_SPECTRAL = Path(".spectral.yaml")
_MISE_CONF = Path(".mise/conf.d/bailiff-mod-api.toml")
_PRECOMMIT_FRAGMENT = Path(".pre-commit.d/bailiff-mod-api.yaml")


def _copy_api_module(tmp_path: Path) -> TemplateRepo:
    """Clone the real bailiff-mod-api tree (pure render — no tasks to stub)."""
    src = _MODULES_DIR / "bailiff-mod-api"
    dest_root = tmp_path / "bailiff-mod-api"
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest_root, dirs_exist_ok=True)
    _git(dest_root, "init", "-q")
    _git(dest_root, "add", "-A")
    _git(dest_root, "commit", "-qm", "module")
    _git(dest_root, "tag", "v1.0.0")
    return TemplateRepo(path=dest_root, tag="v1.0.0")


@pytest.fixture
def bailiff_mod_api(tmp_path: Path) -> TemplateRepo:
    return _copy_api_module(tmp_path)


@pytest.fixture
def bailiff_mod_base(tmp_path: Path) -> TemplateRepo:
    return _copy_module_with_stub_tasks(
        "bailiff-mod-base", tmp_path / "bailiff-mod-base", _BASE_STUB_TASKS
    )


@pytest.fixture
def bailiff_mod_precommit(tmp_path: Path) -> TemplateRepo:
    return _copy_module_with_stub_tasks(
        "bailiff-mod-precommit", tmp_path / "bailiff-mod-precommit", _PRECOMMIT_STUB_TASKS
    )


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _record(full_id: str, repo: TemplateRepo, has_tasks: bool = False) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=has_tasks,
        questions=["project_name"],
    )


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-14")


# ---------------------------------------------------------------------------
# Seed-once OpenAPI skeleton + managed spectral config + mise conf.d (US7 AS1)
# ---------------------------------------------------------------------------


def test_openapi_skeleton_and_spectral_config(
    bailiff_mod_api: TemplateRepo, tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    # project_name and description are answered directly (standalone — no base answers file)
    _init(
        bailiff_mod_api,
        dest,
        {"project_name": "myapi", "description": "My API", "hook_manager": "pre-commit"},
    )

    oa = dest / _OPENAPI
    assert oa.is_file(), "openapi.yaml not seeded at the repo root"
    parsed = yaml.safe_load(oa.read_text())
    assert parsed["openapi"] == "3.1.0"
    assert parsed["info"]["title"] == "myapi"
    assert parsed["paths"] == {}

    sp = dest / _SPECTRAL
    assert sp.is_file(), ".spectral.yaml not rendered"
    sp_parsed = yaml.safe_load(sp.read_text())
    assert "spectral:oas" in sp_parsed["extends"]

    mc = dest / _MISE_CONF
    assert mc.is_file(), ".mise/conf.d/bailiff-mod-api.toml not rendered"
    mc_text = mc.read_text()
    assert "spectral" in mc_text, "spectral tool missing from mise conf.d"


# ---------------------------------------------------------------------------
# Re-run preserves edited openapi.yaml (seed-once) (US7 AS2)
# ---------------------------------------------------------------------------


def test_edited_openapi_preserved_on_reproduce(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_api: TemplateRepo,
    tmp_path: Path,
) -> None:
    trust.add_trust(bailiff_mod_base.url)
    trust.add_trust(bailiff_mod_precommit.url)
    trust.add_trust(bailiff_mod_api.url)

    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/bailiff-mod-base", bailiff_mod_base, has_tasks=True),
            {
                "project_name": "myapi",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": [],
            },
        ),
        (
            _record("demo/bailiff-mod-precommit", bailiff_mod_precommit, has_tasks=True),
            {
                "hook_manager": "none",
                "install_hooks": False,
            },
        ),
        (
            _record("demo/bailiff-mod-api", bailiff_mod_api),
            {},
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    oa = dest / _OPENAPI
    sp = dest / _SPECTRAL
    assert oa.is_file() and sp.is_file()

    health_path = (
        "paths:\n  /health:\n    get:\n      responses:\n"
        "        '200':\n          description: OK\n"
    )
    edited = oa.read_text().replace("paths: {}", health_path)
    oa.write_text(edited)

    runner.reproduce_many(str(dest))

    assert oa.read_text() == edited, "seed-once openapi.yaml clobbered on reproduce"


# ---------------------------------------------------------------------------
# hook_manager=none → fragment inert; files still render (US7 AS3)
# ---------------------------------------------------------------------------


def test_hook_manager_none_inert(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_api: TemplateRepo,
    tmp_path: Path,
) -> None:
    """hook_manager=none: api renders its files; pre-commit.d fragment is absent or empty."""
    for repo in (bailiff_mod_base, bailiff_mod_precommit, bailiff_mod_api):
        trust.add_trust(repo.url)

    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/bailiff-mod-base", bailiff_mod_base, has_tasks=True),
            {
                "project_name": "myapi",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": [],
            },
        ),
        (
            _record("demo/bailiff-mod-precommit", bailiff_mod_precommit, has_tasks=True),
            {
                "hook_manager": "none",
                "install_hooks": False,
            },
        ),
        (
            _record("demo/bailiff-mod-api", bailiff_mod_api),
            {},
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    assert (dest / _OPENAPI).is_file(), "api files must render even with hook_manager=none"
    assert (dest / _SPECTRAL).is_file()
    fragment = dest / _PRECOMMIT_FRAGMENT
    # Fragment is either absent or empty when hook_manager=none (conditional Jinja).
    assert not fragment.is_file() or not fragment.read_text().strip(), (
        "pre-commit.d fragment must be absent or empty when hook_manager=none"
    )


# ---------------------------------------------------------------------------
# hook_manager=pre-commit → .pre-commit.d fragment contains spectral-lint
# ---------------------------------------------------------------------------


def test_spectral_fragment_rendered_for_precommit(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_api: TemplateRepo,
    tmp_path: Path,
) -> None:
    """hook_manager=pre-commit: api renders the spectral-lint fragment in .pre-commit.d/."""
    for repo in (bailiff_mod_base, bailiff_mod_precommit, bailiff_mod_api):
        trust.add_trust(repo.url)

    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/bailiff-mod-base", bailiff_mod_base, has_tasks=True),
            {
                "project_name": "myapi",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": [],
            },
        ),
        (
            _record("demo/bailiff-mod-precommit", bailiff_mod_precommit, has_tasks=True),
            {
                "hook_manager": "pre-commit",
                "install_hooks": False,
            },
        ),
        (
            _record("demo/bailiff-mod-api", bailiff_mod_api),
            {},
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    fragment = dest / _PRECOMMIT_FRAGMENT
    assert fragment.is_file(), ".pre-commit.d/bailiff-mod-api.yaml must be rendered"
    text = fragment.read_text()
    assert "spectral-lint" in text, "spectral-lint hook missing from fragment"
    parsed = yaml.safe_load(text)
    assert parsed is not None, "fragment must be valid YAML"
    repo_ids = [r["repo"] for r in parsed.get("repos", [])]
    assert "local" in repo_ids, "spectral-lint must be a local repo hook"


# ---------------------------------------------------------------------------
# Contract: zero tasks, seed-once declared, no secret:, no union questions
# ---------------------------------------------------------------------------


def test_zero_tasks_seed_once_no_secrets() -> None:
    raw_text = (_MODULES_DIR / "bailiff-mod-api" / "copier.yml").read_text()
    raw = yaml.safe_load(raw_text)
    assert "_tasks" not in raw, "api module must have zero _tasks"
    assert "openapi.yaml" in raw.get("_skip_if_exists", []), "openapi.yaml must be seed-once"
    assert not re.search(r"^\s+secret\s*:", raw_text, re.MULTILINE)
    # spec 014: union questions are gone
    assert "mise_tools" not in raw, "mise_tools union question must be removed (spec 014)"
    assert "hook_blocks" not in raw, "hook_blocks union question must be removed (spec 014)"
    # spec 014: _external_data aliases present
    assert "_external_data" in raw, "_external_data block must be present (spec 014)"
    assert "base" in raw["_external_data"], "base alias must be present"
    assert "precommit" in raw["_external_data"], "precommit alias must be present"
