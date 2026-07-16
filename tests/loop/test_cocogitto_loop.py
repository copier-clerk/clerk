"""spec 012 T005: bailiff-mod-cocogitto loop tests (FR-007).

Assertions:
- single layout → managed cog.toml (no [monorepo] section);
- monorepo layout → [monorepo] section with per-package entries;
- ZERO release side effects: no git tag, no CHANGELOG.md written by the module;
- hook_blocks contribution: the commit-msg-lint block flows through precommit
  (the single writer) when frozen into the union;
- preflight is init-only-guarded (stubbed offline);
- no secret: questions.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from tests.conftest import (
    _BASE_STUB_TASKS,
    _COG_STUB_TASKS,
    _MODULES_DIR,
    _PRECOMMIT_STUB_TASKS,
    TemplateRepo,
    _copy_module_with_stub_tasks,
)

_COG_FILE = Path("cog.toml")

# The commit-msg-lint block cocogitto contributes to the frozen hook_blocks
# union (rendered by bailiff-mod-precommit, the single writer).
_COG_HOOK_BLOCK = (
    "  - repo: local\n"
    "    hooks:\n"
    "      - id: cocogitto-commit-msg\n"
    "        name: cocogitto verify (conventional commits)\n"
    "        entry: cog verify --file\n"
    "        language: system\n"
    "        stages: [commit-msg]\n"
)


@pytest.fixture
def bailiff_mod_cocogitto(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-cocogitto with the mise/cog preflight stubbed offline."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-cocogitto", tmp_path / "bailiff-mod-cocogitto", _COG_STUB_TASKS
    )


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


def _record(full_id: str, repo: TemplateRepo, questions: list[str]) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=True,
        questions=questions,
    )


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> str:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-14")
    cog = dest / _COG_FILE
    assert cog.is_file(), "cog.toml not rendered"
    return cog.read_text()


# ---------------------------------------------------------------------------
# Single layout (US2 AS1)
# ---------------------------------------------------------------------------


def test_single_layout_cog_toml(bailiff_mod_cocogitto: TemplateRepo, tmp_path: Path) -> None:
    """Single layout: cog.toml with changelog path, no [monorepo] section."""
    text = _init(
        bailiff_mod_cocogitto,
        tmp_path / "proj",
        {"project_name": "myapp", "layout": "single"},
    )
    assert 'tag_prefix = "v"' in text
    assert "[changelog]" in text
    assert "[monorepo]" not in text


# ---------------------------------------------------------------------------
# Monorepo layout (US2 / plan: monorepo section present)
# ---------------------------------------------------------------------------


def test_monorepo_layout_cog_toml(bailiff_mod_cocogitto: TemplateRepo, tmp_path: Path) -> None:
    """Monorepo layout: [monorepo] section with one entry per frozen package path."""
    text = _init(
        bailiff_mod_cocogitto,
        tmp_path / "proj",
        {
            "project_name": "myapp",
            "layout": "monorepo",
            "monorepo_packages": ["packages/api", "packages/web"],
        },
    )
    assert "[monorepo]" in text
    assert "generate_mono_repository_global_tag = false" in text
    assert "[monorepo.packages.packages-api]" in text
    assert 'path = "packages/api"' in text
    assert "[monorepo.packages.packages-web]" in text


# ---------------------------------------------------------------------------
# Zero release side effects (US2 AS3 / SC-003)
# ---------------------------------------------------------------------------


def test_no_release_side_effects(bailiff_mod_cocogitto: TemplateRepo, tmp_path: Path) -> None:
    """Init creates no git tag and no CHANGELOG.md — release actions are the project's."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_cocogitto, dest, {"project_name": "myapp", "layout": "single"})

    assert not (dest / "CHANGELOG.md").exists(), "module must not write a changelog"
    # No tags in the destination repo (if the dest is even a git repo).
    if (dest / ".git").exists():
        tags = subprocess.run(
            ["git", "tag"], cwd=dest, capture_output=True, text=True, check=False
        ).stdout.strip()
        assert not tags, f"module must not create tags: {tags}"


# ---------------------------------------------------------------------------
# hook_blocks contribution flows through precommit (US2 AS2)
# ---------------------------------------------------------------------------


def test_hook_block_written_by_precommit(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_cocogitto: TemplateRepo,
    tmp_path: Path,
) -> None:
    """The commit-msg-lint block appears in the hook file via precommit (single writer)."""
    for repo in (bailiff_mod_base, bailiff_mod_precommit, bailiff_mod_cocogitto):
        trust.add_trust(repo.url)

    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/bailiff-mod-base", bailiff_mod_base, ["project_name"]),
            {
                "project_name": "myapp",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": [],
            },
        ),
        (
            _record("demo/bailiff-mod-cocogitto", bailiff_mod_cocogitto, ["project_name"]),
            {
                "project_name": "myapp",
                "layout": "single",
                "hook_blocks": [_COG_HOOK_BLOCK],
            },
        ),
        (
            _record("demo/bailiff-mod-precommit", bailiff_mod_precommit, ["hook_manager"]),
            {"hook_manager": "pre-commit", "hook_blocks": [_COG_HOOK_BLOCK]},
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    hook_file = dest / ".pre-commit-config.yaml"
    assert hook_file.is_file(), "precommit must write the hook file"
    text = hook_file.read_text()
    assert "cocogitto-commit-msg" in text, "cog hook block missing from hook file"
    assert text.count("cocogitto-commit-msg") == 1, "hook block injected more than once"
    # cocogitto itself never writes hook config.
    assert (dest / _COG_FILE).is_file()


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


# ---------------------------------------------------------------------------
# Contract: init-only guard + no secret: questions
# ---------------------------------------------------------------------------


def test_preflight_is_init_only_guarded_and_no_secrets() -> None:
    """The authored preflight is guarded by the committed sentinel (FR-012a)."""
    copier_yml = (_MODULES_DIR / "bailiff-mod-cocogitto" / "copier.yml").read_text()
    assert "test -f .bailiff-cocogitto-preflight ||" in copier_yml, (
        "preflight must be init-only-guarded via the committed sentinel"
    )
    assert not re.search(r"^\s+secret\s*:", copier_yml, re.MULTILINE)
    # No release actions in the executable _tasks block (comments may name them).
    tasks_block = copier_yml.split("_tasks:")[-1]
    executable = "\n".join(
        line for line in tasks_block.splitlines() if not line.lstrip().startswith("#")
    )
    for forbidden in ("cog bump", "cog changelog", "git tag"):
        assert forbidden not in executable, f"forbidden release action in tasks: {forbidden}"
