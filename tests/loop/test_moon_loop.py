"""spec 012 T007: bailiff-mod-moon loop tests (FR-010).

Assertions (US4 AS1-3):
- monorepo layout + frozen monorepo_packages → managed .moon/workspace.yml with
  an explicit projects map;
- monorepo_tool=moon is recorded in the answers (the frozen answer CI consumes);
- CI can consume it: ci-github monorepo-affected + monorepo_tool=moon renders
  the moon ci invocation (supplier + FR-010a amendment together — SC-004);
- single-package layout: warn-and-render — workspace file still renders (valid,
  minimal root project) and the authored preflight carries the ratified warning;
- no secret: questions; preflight init-only-guarded.

spec 014: project_name and layout are no longer threaded questions — they are
read from base via _external_data.  Tests that exercise layout-dependent
rendering pre-seed the base answers file in dest.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from bailiff import runner, trust
from tests.conftest import (
    _MODULES_DIR,
    _MOON_STUB_TASKS,
    TemplateRepo,
    _copy_module_with_stub_tasks,
)

_WS_FILE = Path(".moon/workspace.yml")

# Name of the base answers file that moon reads via _external_data.
_BASE_ANSWERS_FILE = ".copier-answers.bailiff-mod-base.yml"


@pytest.fixture
def bailiff_mod_moon(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-moon with the mise preflight stubbed offline."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-moon", tmp_path / "bailiff-mod-moon", _MOON_STUB_TASKS
    )


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _seed_base_answers(dest: Path, layout: str, project_name: str = "myapp") -> None:
    """Write a minimal base answers file so _external_data.base resolves in tests.

    In a real stack base runs first; in standalone moon tests we pre-seed the
    file that copier would otherwise warn-and-skip (returning {}).
    """
    dest.mkdir(parents=True, exist_ok=True)
    answers = {
        "_src_path": "bailiff-mod-base",
        "project_name": project_name,
        "layout": layout,
    }
    (dest / _BASE_ANSWERS_FILE).write_text(yaml.dump(answers))


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-14")


# ---------------------------------------------------------------------------
# Monorepo: explicit projects map from frozen packages (US4 AS1)
# ---------------------------------------------------------------------------


def test_monorepo_workspace_projects_map(bailiff_mod_moon: TemplateRepo, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    _seed_base_answers(dest, layout="monorepo", project_name="myapp")
    _init(
        bailiff_mod_moon,
        dest,
        {"monorepo_packages": ["packages/api", "apps/web"]},
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
    _seed_base_answers(dest, layout="monorepo")
    _init(bailiff_mod_moon, dest, {"monorepo_packages": []})
    parsed = yaml.safe_load((dest / _WS_FILE).read_text())
    assert "apps/*" in parsed["projects"]["globs"]
    assert "packages/*" in parsed["projects"]["globs"]


# ---------------------------------------------------------------------------
# monorepo_tool=moon frozen answer → CI consumption (US4 AS2 / SC-004)
# ---------------------------------------------------------------------------


def test_monorepo_tool_answer_recorded(bailiff_mod_moon: TemplateRepo, tmp_path: Path) -> None:
    """The frozen monorepo_tool=moon answer is persisted for CI consumption."""
    dest = tmp_path / "proj"
    _seed_base_answers(dest, layout="monorepo")
    _init(bailiff_mod_moon, dest, {"monorepo_packages": ["packages/api"]})
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
    _seed_base_answers(dest, layout="single", project_name="solo")
    _init(bailiff_mod_moon, dest, {})

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
    # spec 014: layout is read via _external_data.base.layout, not a bare threaded key.
    assert "{% if _external_data.base.layout != 'monorepo' %}" in copier_yml


# ---------------------------------------------------------------------------
# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Contract: no secret:, init-only guard
# ---------------------------------------------------------------------------


def test_no_secret_and_init_only_guard() -> None:
    copier_yml = (_MODULES_DIR / "bailiff-mod-moon" / "copier.yml").read_text()
    assert not re.search(r"^\s+secret\s*:", copier_yml, re.MULTILINE)
    assert "test -f .bailiff-moon-preflight ||" in copier_yml, (
        "preflight must be init-only-guarded via the committed sentinel"
    )


# ---------------------------------------------------------------------------
# spec 014: _external_data alias is declared; producer facts are bare questions
# ---------------------------------------------------------------------------


def test_external_data_alias_declared() -> None:
    """copier.yml declares _external_data.base pointing at the base answers file."""
    copier_yml = (_MODULES_DIR / "bailiff-mod-moon" / "copier.yml").read_text()
    assert "_external_data:" in copier_yml
    assert "base: .copier-answers.bailiff-mod-base.yml" in copier_yml


def test_moon_is_producer_for_moon_alias() -> None:
    """monorepo_tool and monorepo_packages are bare questions — moon is the producer."""
    copier_yml = (_MODULES_DIR / "bailiff-mod-moon" / "copier.yml").read_text()
    data = yaml.safe_load(copier_yml)
    assert "monorepo_tool" in data, "monorepo_tool must be a bare question (producer fact)"
    assert "monorepo_packages" in data, "monorepo_packages must be a bare question"
    # project_name and layout must NOT be declared as questions (spec 014 — no threading)
    assert "project_name" not in data, "project_name must be removed (read via _external_data)"
    assert "layout" not in data or data.get("layout") is None, (
        "layout must be removed (read via _external_data.base.layout)"
    )


def test_depends_on_base_and_phase_normal() -> None:
    """Edge uses depends_on (not run_after); phase is normal (spec 014 / FR-019/FR-020)."""
    copier_yml = (_MODULES_DIR / "bailiff-mod-moon" / "copier.yml").read_text()
    data = yaml.safe_load(copier_yml)
    assert "run_after" not in data, "run_after must be replaced by depends_on (FR-019)"
    assert data.get("depends_on", {}).get("default") == ["bailiff-mod-base"]
    assert data.get("phase", {}).get("default") == "normal"


def test_mise_confd_fragment_present() -> None:
    """moon renders its tool into .mise/conf.d/bailiff-mod-moon.toml (FR-008)."""
    confd = (
        _MODULES_DIR
        / "bailiff-mod-moon"
        / "template"
        / ".mise"
        / "conf.d"
        / "bailiff-mod-moon.toml.jinja"
    )
    assert confd.is_file(), ".mise/conf.d/bailiff-mod-moon.toml.jinja must exist"
    content = confd.read_text()
    assert "[tools]" in content
    assert "moon" in content
