"""spec 012 T010 / spec 014 R13: bailiff-mod-api loop tests.

Assertions (spec 014 fragment/merge model + FR-001/013 + R13):
- seed-once openapi.yaml at the REPO ROOT: minimal valid OpenAPI 3.1 skeleton;
  a project edit survives reproduce over the populated tree;
- managed .spectral.yaml rendered on init;
- managed .mise/conf.d/bailiff-mod-api.toml rendered on init;
- .pre-commit.d/bailiff-mod-api.yaml renders UNCONDITIONALLY (bundler decides);
- api depends only on base, not on precommit (R13 ruling);
- [base+api] with no precommit inits cleanly;
- no secret: questions; no mise_tools / hook_blocks / hook_manager union questions.
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
    # project_name / description answered directly (standalone — no base answers file present)
    _init(bailiff_mod_api, dest, {"project_name": "myapi", "description": "My API"})

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
    assert "spectral" in mc.read_text(), "spectral tool missing from mise conf.d"


# ---------------------------------------------------------------------------
# Fragment renders unconditionally (R13: bundler decides, not the contributor)
# ---------------------------------------------------------------------------


def test_precommit_fragment_renders_unconditionally(
    bailiff_mod_api: TemplateRepo, tmp_path: Path
) -> None:
    """Fragment is always written regardless of hook manager (R13 ruling)."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_api, dest, {"project_name": "myapi"})

    fragment = dest / _PRECOMMIT_FRAGMENT
    assert fragment.is_file(), ".pre-commit.d/bailiff-mod-api.yaml must always render"
    text = fragment.read_text()
    assert "spectral-lint" in text, "spectral-lint hook missing from unconditional fragment"
    parsed = yaml.safe_load(text)
    assert parsed is not None
    repo_ids = [r["repo"] for r in parsed.get("repos", [])]
    assert "local" in repo_ids


# ---------------------------------------------------------------------------
# [base + api] without precommit inits cleanly (R13: no precommit dependency)
# ---------------------------------------------------------------------------


def test_base_plus_api_no_precommit(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_api: TemplateRepo,
    tmp_path: Path,
) -> None:
    """api depends only on base; a [base+api] stack needs no precommit (R13)."""
    trust.add_trust(bailiff_mod_base.url)
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
            _record("demo/bailiff-mod-api", bailiff_mod_api),
            {},
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    assert (dest / _OPENAPI).is_file()
    assert (dest / _SPECTRAL).is_file()
    assert (dest / _MISE_CONF).is_file()
    # Fragment renders unconditionally even without precommit in the stack.
    assert (dest / _PRECOMMIT_FRAGMENT).is_file()


# ---------------------------------------------------------------------------
# Re-run preserves edited openapi.yaml (seed-once) (US7 AS2)
# ---------------------------------------------------------------------------


def test_edited_openapi_preserved_on_reproduce(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_api: TemplateRepo,
    tmp_path: Path,
) -> None:
    trust.add_trust(bailiff_mod_base.url)
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
            _record("demo/bailiff-mod-api", bailiff_mod_api),
            {},
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    oa = dest / _OPENAPI
    assert oa.is_file()

    health_path = (
        "paths:\n  /health:\n    get:\n      responses:\n"
        "        '200':\n          description: OK\n"
    )
    edited = oa.read_text().replace("paths: {}", health_path)
    oa.write_text(edited)

    runner.reproduce_many(str(dest))

    assert oa.read_text() == edited, "seed-once openapi.yaml clobbered on reproduce"


# ---------------------------------------------------------------------------
# Contract: zero tasks, seed-once declared, no secret:, no union questions
# ---------------------------------------------------------------------------


def test_zero_tasks_seed_once_no_secrets() -> None:
    raw_text = (_MODULES_DIR / "bailiff-mod-api" / "copier.yml").read_text()
    raw = yaml.safe_load(raw_text)
    assert "_tasks" not in raw, "api module must have zero _tasks"
    assert "openapi.yaml" in raw.get("_skip_if_exists", []), "openapi.yaml must be seed-once"
    assert not re.search(r"^\s+secret\s*:", raw_text, re.MULTILINE)
    # spec 014: union questions removed
    assert "mise_tools" not in raw, "mise_tools union question must be removed (spec 014)"
    assert "hook_blocks" not in raw, "hook_blocks union question must be removed (spec 014)"
    assert "hook_manager" not in raw, "hook_manager must be removed (spec 014 R13)"
    # spec 014 R13: only base alias; no precommit dependency
    assert "_external_data" in raw, "_external_data block must be present (spec 014)"
    ext = raw["_external_data"]
    assert "base" in ext, "base alias must be present"
    assert "precommit" not in ext, "precommit alias must be absent (R13)"
    deps = raw.get("depends_on", {}).get("default", [])
    assert "bailiff-mod-base" in deps
    assert "bailiff-mod-precommit" not in deps, "precommit must not be a dependency (R13)"
