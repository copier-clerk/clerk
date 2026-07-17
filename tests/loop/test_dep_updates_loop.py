"""spec 012 T006: bailiff-mod-dep-updates loop tests (FR-008 / FR-023 / R12).

Pure MANAGED renders — zero _tasks. Assertions:
- default dep_update_tool=renovate → renovate.json present, dependabot.yml ABSENT;
- dep_update_tool=dependabot → .github/dependabot.yml present with one entry per ecosystem;
- never deletes the other tool's file (pre-existing file untouched);
- no secret: questions; dep_update_tool static default is 'renovate'.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
import yaml

from bailiff import runner, trust
from tests.conftest import (
    _MODULES_DIR,
    TemplateRepo,
    _git,
)

_RENOVATE = Path("renovate.json")
_DEPENDABOT = Path(".github/dependabot.yml")


def _copy_dep_updates_module(tmp_path: Path) -> TemplateRepo:
    """Clone the real bailiff-mod-dep-updates tree (pure render — no tasks to stub)."""
    src = _MODULES_DIR / "bailiff-mod-dep-updates"
    dest_root = tmp_path / "bailiff-mod-dep-updates"
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest_root, dirs_exist_ok=True)
    _git(dest_root, "init", "-q")
    _git(dest_root, "add", "-A")
    _git(dest_root, "commit", "-qm", "module")
    _git(dest_root, "tag", "v1.0.0")
    return TemplateRepo(path=dest_root, tag="v1.0.0")


@pytest.fixture
def bailiff_mod_dep_updates(tmp_path: Path) -> TemplateRepo:
    return _copy_dep_updates_module(tmp_path)


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-14")


# ---------------------------------------------------------------------------
# Default: dep_update_tool=renovate → renovate branch (FR-023/R12)
# ---------------------------------------------------------------------------


def test_default_resolves_renovate(bailiff_mod_dep_updates: TemplateRepo, tmp_path: Path) -> None:
    """Default dep_update_tool=renovate: renovate.json renders, dependabot.yml absent."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_dep_updates, dest, {"dep_ecosystems": ["pep621", "npm"]})

    rn = dest / _RENOVATE
    assert rn.is_file(), "renovate.json must render by default"
    assert not (dest / _DEPENDABOT).exists(), "dependabot.yml must not render"

    parsed = json.loads(rn.read_text())
    assert "config:recommended" in parsed["extends"]
    assert parsed["enabledManagers"] == ["pep621", "npm"]


# ---------------------------------------------------------------------------
# Explicit dependabot → dependabot branch
# ---------------------------------------------------------------------------


def test_explicit_dependabot_renders(bailiff_mod_dep_updates: TemplateRepo, tmp_path: Path) -> None:
    """Explicit dep_update_tool=dependabot: dependabot.yml renders, renovate.json absent."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_dep_updates,
        dest,
        {"dep_update_tool": "dependabot", "dep_ecosystems": ["uv", "github-actions"]},
    )

    db = dest / _DEPENDABOT
    assert db.is_file(), "dependabot.yml must render when dep_update_tool=dependabot"
    assert not (dest / _RENOVATE).exists(), "renovate.json must not render"

    parsed = yaml.safe_load(db.read_text())
    assert parsed["version"] == 2
    ecosystems = [u["package-ecosystem"] for u in parsed["updates"]]
    assert ecosystems == ["uv", "github-actions"], f"one entry per ecosystem: {ecosystems}"


# ---------------------------------------------------------------------------
# Never deletes the other tool's file (axis flip on an existing project)
# ---------------------------------------------------------------------------


def test_never_deletes_other_tools_file(
    bailiff_mod_dep_updates: TemplateRepo, tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    dest.mkdir()
    stale = dest / _RENOVATE
    stale.write_text('{"extends": ["config:recommended"]}\n')

    _init(
        bailiff_mod_dep_updates,
        dest,
        {"dep_update_tool": "dependabot", "dep_ecosystems": ["uv"]},
    )

    assert stale.is_file(), "the other tool's pre-existing file must survive"
    assert (dest / _DEPENDABOT).is_file()


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


# ---------------------------------------------------------------------------
# Contract: no secret: questions; dep_update_tool default is 'renovate'
# ---------------------------------------------------------------------------


def test_no_secret_questions_and_static_default() -> None:
    """No secret: questions; dep_update_tool default is the static literal 'renovate' (FR-023)."""
    copier_yml = (_MODULES_DIR / "bailiff-mod-dep-updates" / "copier.yml").read_text()
    assert not re.search(r"^\s+secret\s*:", copier_yml, re.MULTILINE)
    # FR-023/R12: github_host must not be a question key (comments referencing it are allowed).
    assert not re.search(r"^github_host\s*:", copier_yml, re.MULTILINE), (
        "github_host must not be a question key (R12/FR-023)"
    )
    # Static default (not host-derived).
    assert "default: renovate" in copier_yml
