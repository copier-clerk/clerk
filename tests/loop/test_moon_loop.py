"""spec 012 T007: bailiff-mod-moon loop tests (FR-010).

Assertions (US4 AS1-3):
- monorepo layout + frozen monorepo_packages → managed .moon/workspace.yml with
  an explicit projects map, byte-identical on reproduce;
- monorepo_tool=moon is recorded in the answers (the frozen answer CI consumes);
- CI can consume it: ci-github monorepo-affected + monorepo_tool=moon renders
  the moon ci invocation (supplier + FR-010a amendment together — SC-004);
- single-package layout: warn-and-render — workspace file still renders (valid,
  minimal root project) and the authored preflight carries the ratified warning;
- no secret: questions; preflight init-only-guarded.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from bailiff import runner, trust
from tests.conftest import (
    _BASE_STUB_TASKS,
    _MODULES_DIR,
    _MOON_STUB_TASKS,
    TemplateRepo,
    _copy_module_with_stub_tasks,
)

_WS_FILE = Path(".moon/workspace.yml")


@pytest.fixture
def bailiff_mod_moon(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-moon with the mise preflight stubbed offline."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-moon", tmp_path / "bailiff-mod-moon", _MOON_STUB_TASKS
    )


@pytest.fixture
def bailiff_mod_base(tmp_path: Path) -> TemplateRepo:
    return _copy_module_with_stub_tasks(
        "bailiff-mod-base", tmp_path / "bailiff-mod-base", _BASE_STUB_TASKS
    )


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-14")


# ---------------------------------------------------------------------------
# Monorepo: explicit projects map from frozen packages (US4 AS1)
# ---------------------------------------------------------------------------


def test_monorepo_workspace_projects_map(bailiff_mod_moon: TemplateRepo, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_moon,
        dest,
        {
            "project_name": "myapp",
            "layout": "monorepo",
            "monorepo_packages": ["packages/api", "apps/web"],
        },
    )

    ws = dest / _WS_FILE
    assert ws.is_file(), ".moon/workspace.yml not rendered"
    parsed = yaml.safe_load(ws.read_text())
    assert parsed["projects"] == {"api": "packages/api", "web": "apps/web"}
    assert parsed["vcs"]["manager"] == "git"


def test_monorepo_no_packages_glob_discovery(
    bailiff_mod_moon: TemplateRepo, tmp_path: Path
) -> None:
    """Monorepo without frozen packages → glob discovery over standard base dirs."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_moon,
        dest,
        {"project_name": "myapp", "layout": "monorepo", "monorepo_packages": []},
    )
    parsed = yaml.safe_load((dest / _WS_FILE).read_text())
    assert "apps/*" in parsed["projects"]["globs"]
    assert "packages/*" in parsed["projects"]["globs"]


# ---------------------------------------------------------------------------
# monorepo_tool=moon frozen answer → CI consumption (US4 AS2 / SC-004)
# ---------------------------------------------------------------------------


def test_monorepo_tool_answer_recorded(bailiff_mod_moon: TemplateRepo, tmp_path: Path) -> None:
    """The frozen monorepo_tool=moon answer is persisted for CI consumption."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_moon,
        dest,
        {"project_name": "myapp", "layout": "monorepo", "monorepo_packages": ["packages/api"]},
    )
    af = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert af["monorepo_tool"] == "moon"


def test_ci_consumes_monorepo_tool_moon(tmp_path: Path) -> None:
    """SC-004 end-to-end: ci-github monorepo-affected sized by monorepo_tool=moon → moon ci."""
    import copier

    ci_repo = _copy_module_with_stub_tasks("bailiff-mod-ci-github", tmp_path / "ci", "")
    dest = tmp_path / "proj"
    dest.mkdir()
    copier.run_copy(
        src_path=ci_repo.url,
        dst_path=str(dest),
        vcs_ref=ci_repo.tag,
        data={
            "ci_model": "monorepo-affected",
            "monorepo_tool": "moon",
            "ci_languages": [],
            "ci_lang_facts": {},
            "default_branch": "main",
        },
        defaults=True,
        quiet=True,
    )
    ci = (dest / ".github/workflows/ci.yml").read_text()
    assert "run: moon ci" in ci, "CI must consume monorepo_tool=moon (FR-010a)"


# ---------------------------------------------------------------------------
# Single-package: warn-and-render (US4 AS3 / ledger FR-010)
# ---------------------------------------------------------------------------


def test_single_package_warn_and_render(bailiff_mod_moon: TemplateRepo, tmp_path: Path) -> None:
    """Single layout still renders a VALID minimal workspace (never refused/broken)."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_moon, dest, {"project_name": "solo", "layout": "single"})

    ws = dest / _WS_FILE
    assert ws.is_file(), "warn-and-render: workspace must still render on single layout"
    parsed = yaml.safe_load(ws.read_text())
    assert parsed["projects"] == {"root": "."}, "minimal root project map expected"


def test_authored_preflight_warns_on_single_layout() -> None:
    """The authored template carries the ratified warning text on the single branch."""
    copier_yml = (_MODULES_DIR / "bailiff-mod-moon" / "copier.yml").read_text()
    assert "moon is primarily a monorepo workspace tool" in copier_yml
    assert "single-package config will be minimal" in copier_yml
    # Warning is warn-and-render: inside the guarded preflight, no exit 1 tied to it.
    assert "{% if layout != 'monorepo' %}" in copier_yml


# ---------------------------------------------------------------------------
# Reproduce: byte-identical managed render (US4 AS1)
# ---------------------------------------------------------------------------


def test_workspace_byte_identical_on_reproduce(
    bailiff_mod_base: TemplateRepo, bailiff_mod_moon: TemplateRepo, tmp_path: Path
) -> None:
    from bailiff.catalog import TemplateRecord

    def _record(full_id: str, repo: TemplateRepo) -> TemplateRecord:
        return TemplateRecord(
            full_id=full_id,
            source=repo.url,
            ref=repo.tag,
            versions=[repo.tag],
            reproducible=True,
            has_tasks=True,
            questions=["project_name"],
        )

    trust.add_trust(bailiff_mod_base.url)
    trust.add_trust(bailiff_mod_moon.url)

    selection: list[tuple[Any, dict[str, Any]]] = [
        (
            _record("demo/bailiff-mod-base", bailiff_mod_base),
            {
                "project_name": "myapp",
                "org": "acme",
                "license": "mit",
                "layout": "monorepo",
                "gitignore_stack": [],
            },
        ),
        (
            _record("demo/bailiff-mod-moon", bailiff_mod_moon),
            {
                "project_name": "myapp",
                "layout": "monorepo",
                "monorepo_packages": ["packages/api", "packages/web"],
            },
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    ws = dest / _WS_FILE
    assert ws.is_file()
    before = _digest(ws)

    runner.reproduce_many(str(dest))

    assert _digest(ws) == before, ".moon/workspace.yml changed on reproduce"


# ---------------------------------------------------------------------------
# Contract: no secret:, init-only guard
# ---------------------------------------------------------------------------


def test_no_secret_and_init_only_guard() -> None:
    copier_yml = (_MODULES_DIR / "bailiff-mod-moon" / "copier.yml").read_text()
    assert not re.search(r"^\s+secret\s*:", copier_yml, re.MULTILINE)
    assert "test -f .bailiff-moon-preflight ||" in copier_yml, (
        "preflight must be init-only-guarded via the committed sentinel"
    )
