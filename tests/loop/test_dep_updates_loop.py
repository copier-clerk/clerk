"""spec 012 T006: bailiff-mod-dep-updates loop tests (FR-008).

Pure MANAGED renders — zero _tasks. Assertions (US3 AS1-5):
- github_host=true + default → dep_update_tool resolves to dependabot:
  .github/dependabot.yml present with one entry per frozen ecosystem;
  renovate.json ABSENT;
- github_host=false + default → renovate: renovate.json present,
  dependabot.yml ABSENT;
- dep_update_tool=dependabot + github_host=false → warn-and-render: file
  renders WITH the warning comment;
- never deletes the other tool's file (pre-existing file untouched);
- no secret: questions.
"""

from __future__ import annotations

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
# AS2: github_host=true + default → dependabot branch
# ---------------------------------------------------------------------------


def test_github_host_default_resolves_dependabot(
    bailiff_mod_dep_updates: TemplateRepo, tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_dep_updates,
        dest,
        {"github_host": True, "dep_ecosystems": ["uv", "github-actions"]},
    )

    db = dest / _DEPENDABOT
    assert db.is_file(), "dependabot.yml must render on the default GitHub branch"
    assert not (dest / _RENOVATE).exists(), "renovate.json must not render"

    parsed = yaml.safe_load(db.read_text())
    assert parsed["version"] == 2
    ecosystems = [u["package-ecosystem"] for u in parsed["updates"]]
    assert ecosystems == ["uv", "github-actions"], f"one entry per ecosystem: {ecosystems}"
    # No warning comment on a GitHub-hosted project.
    assert "WARNING" not in db.read_text()


# ---------------------------------------------------------------------------
# AS3: github_host=false + default → renovate branch
# ---------------------------------------------------------------------------


def test_non_github_default_resolves_renovate(
    bailiff_mod_dep_updates: TemplateRepo, tmp_path: Path
) -> None:
    import json

    dest = tmp_path / "proj"
    _init(
        bailiff_mod_dep_updates,
        dest,
        {"github_host": False, "dep_ecosystems": ["pep621", "npm"]},
    )

    rn = dest / _RENOVATE
    assert rn.is_file(), "renovate.json must render on the default non-GitHub branch"
    assert not (dest / _DEPENDABOT).exists(), "dependabot.yml must not render"

    parsed = json.loads(rn.read_text())  # valid JSON
    assert "config:recommended" in parsed["extends"]
    assert parsed["enabledManagers"] == ["pep621", "npm"]


# ---------------------------------------------------------------------------
# AS4: explicit dependabot + github_host=false → warn-and-render
# ---------------------------------------------------------------------------


def test_dependabot_on_non_github_warns_and_renders(
    bailiff_mod_dep_updates: TemplateRepo, tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_dep_updates,
        dest,
        {
            "github_host": False,
            "dep_update_tool": "dependabot",
            "dep_ecosystems": ["gomod"],
        },
    )

    db = dest / _DEPENDABOT
    assert db.is_file(), "warn-and-render: the file must still render"
    text = db.read_text()
    assert "WARNING" in text, "warning comment required when dependabot + github_host=false"
    assert "only runs on GitHub-hosted" in text
    # Still a valid dependabot config.
    parsed = yaml.safe_load(text)
    assert parsed["version"] == 2


# ---------------------------------------------------------------------------
# AS5: never deletes the other tool's file (axis flip on an existing project)
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
        {"github_host": True, "dep_ecosystems": ["uv"]},
    )

    assert stale.is_file(), "the other tool's pre-existing file must survive"
    assert (dest / _DEPENDABOT).is_file()


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


# ---------------------------------------------------------------------------
# Contract: no secret: questions, axis default expression
# ---------------------------------------------------------------------------


def test_no_secret_questions_and_host_derived_default() -> None:
    copier_yml = (_MODULES_DIR / "bailiff-mod-dep-updates" / "copier.yml").read_text()
    assert not re.search(r"^\s+secret\s*:", copier_yml, re.MULTILINE)
    # FR-004: host-derived default expression, not a static literal.
    assert "{{ 'dependabot' if github_host else 'renovate' }}" in copier_yml
