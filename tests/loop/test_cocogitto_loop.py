"""spec 012/014: bailiff-mod-cocogitto loop tests (FR-007, spec 014 _external_data migration).

Assertions:
- single layout → managed cog.toml (no [monorepo] section); layout read from base answers file;
- monorepo layout → [monorepo] section with per-package entries; packages from agent-fed --data;
- [base+cocogitto] WITHOUT moon initialises cleanly (non-monorepo stack);
- monorepo stack (base+cocogitto with monorepo_packages) populates [monorepo];
- ZERO release side effects: no git tag, no CHANGELOG.md written by the module;
- pre-commit fragment: .pre-commit.d/bailiff-mod-cocogitto.yaml rendered with commit-msg-lint hook;
- mise conf.d drop-in: .mise/conf.d/bailiff-mod-cocogitto.toml rendered with cog tool;
- preflight is init-only-guarded (stubbed offline);
- no secret: questions.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from bailiff import runner, trust
from tests.conftest import (
    _BASE_STUB_TASKS,
    _COG_STUB_TASKS,
    _MODULES_DIR,
    TemplateRepo,
    _copy_module_with_stub_tasks,
)

_COG_FILE = Path("cog.toml")
_FRAGMENT_FILE = Path(".pre-commit.d/bailiff-mod-cocogitto.yaml")
_MISE_FILE = Path(".mise/conf.d/bailiff-mod-cocogitto.toml")


def _seed_base_answers(dest: Path, project_name: str = "myapp", layout: str = "single") -> None:
    """Pre-seed the base answers file so _external_data.base resolves."""
    dest.mkdir(parents=True, exist_ok=True)
    data = {
        "_src_path": "https://github.com/bailiff-io/bailiff-mod-base.git",
        "_commit": "v1.0.0",
        "project_name": project_name,
        "layout": layout,
    }
    (dest / ".copier-answers.bailiff-mod-base.yml").write_text(yaml.dump(data))


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


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _init_with_facts(
    repo: TemplateRepo,
    dest: Path,
    *,
    project_name: str = "myapp",
    layout: str = "single",
    monorepo_packages: list[str] | None = None,
) -> str:
    """Init cocogitto after pre-seeding the base answers file.

    monorepo_packages is agent-fed via answers (--data), not read from a moon
    answers file — moon is sometimes-absent (R13 GENERALIZED).
    """
    _seed_base_answers(dest, project_name=project_name, layout=layout)
    answers: dict = {}
    if monorepo_packages is not None:
        answers["monorepo_packages"] = monorepo_packages
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-14")
    cog = dest / _COG_FILE
    assert cog.is_file(), "cog.toml not rendered"
    return cog.read_text()


# ---------------------------------------------------------------------------
# Single layout — cog.toml shape (US2 AS1)
# ---------------------------------------------------------------------------


def test_single_layout_cog_toml(bailiff_mod_cocogitto: TemplateRepo, tmp_path: Path) -> None:
    """Single layout: cog.toml with changelog path, no [monorepo] section."""
    text = _init_with_facts(
        bailiff_mod_cocogitto,
        tmp_path / "proj",
        layout="single",
    )
    assert 'tag_prefix = "v"' in text
    assert "[changelog]" in text
    assert "[monorepo]" not in text


# ---------------------------------------------------------------------------
# Monorepo layout — [monorepo] section with packages from moon (US2)
# ---------------------------------------------------------------------------


def test_monorepo_layout_cog_toml(bailiff_mod_cocogitto: TemplateRepo, tmp_path: Path) -> None:
    """Monorepo layout: [monorepo] section with one entry per package from agent-fed --data (monorepo_packages)."""
    text = _init_with_facts(
        bailiff_mod_cocogitto,
        tmp_path / "proj",
        layout="monorepo",
        monorepo_packages=["packages/api", "packages/web"],
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
    import subprocess

    dest = tmp_path / "proj"
    _init_with_facts(bailiff_mod_cocogitto, dest, layout="single")

    assert not (dest / "CHANGELOG.md").exists(), "module must not write a changelog"
    if (dest / ".git").exists():
        tags = subprocess.run(
            ["git", "tag"], cwd=dest, capture_output=True, text=True, check=False
        ).stdout.strip()
        assert not tags, f"module must not create tags: {tags}"


# ---------------------------------------------------------------------------
# Fragment outputs: mise conf.d + pre-commit.d (spec 014)
# ---------------------------------------------------------------------------


def test_mise_confd_drop_in_rendered(bailiff_mod_cocogitto: TemplateRepo, tmp_path: Path) -> None:
    """Mise conf.d drop-in is rendered with cog tool entry."""
    dest = tmp_path / "proj"
    _init_with_facts(bailiff_mod_cocogitto, dest, layout="single")
    mise_file = dest / _MISE_FILE
    assert mise_file.is_file(), f"{_MISE_FILE} not rendered"
    text = mise_file.read_text()
    assert "[tools]" in text
    assert "cog" in text


def test_precommit_fragment_rendered(bailiff_mod_cocogitto: TemplateRepo, tmp_path: Path) -> None:
    """Pre-commit fragment is rendered in .pre-commit.d/ with the commit-msg-lint hook."""
    dest = tmp_path / "proj"
    _init_with_facts(bailiff_mod_cocogitto, dest, layout="single")
    frag = dest / _FRAGMENT_FILE
    assert frag.is_file(), f"{_FRAGMENT_FILE} not rendered"
    text = frag.read_text()
    assert "cocogitto-commit-msg" in text
    assert "cog verify --file" in text
    assert "commit-msg" in text


def test_cocogitto_does_not_write_hook_config(
    bailiff_mod_cocogitto: TemplateRepo, tmp_path: Path
) -> None:
    """cocogitto never writes .pre-commit-config.yaml — that belongs to precommit's bundler."""
    dest = tmp_path / "proj"
    _init_with_facts(bailiff_mod_cocogitto, dest, layout="single")
    assert not (dest / ".pre-commit-config.yaml").exists(), (
        "cocogitto must not write the merged hook file — only precommit's bundler may"
    )


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


def test_no_union_questions_in_copier_yml() -> None:
    """copier.yml must not declare mise_tools or hook_blocks union questions (spec 014)."""
    copier_yml = (_MODULES_DIR / "bailiff-mod-cocogitto" / "copier.yml").read_text()
    assert "mise_tools" not in copier_yml, "mise_tools union removed in spec 014"
    assert "hook_blocks" not in copier_yml, "hook_blocks union removed in spec 014"


def test_depends_on_base_only() -> None:
    """copier.yml depends_on lists only bailiff-mod-base; moon removed (R13 GENERALIZED)."""
    import yaml as _yaml

    raw = (_MODULES_DIR / "bailiff-mod-cocogitto" / "copier.yml").read_text()
    data = _yaml.safe_load(raw)
    deps = data.get("depends_on", {}).get("default", [])
    assert "bailiff-mod-base" in deps
    assert "bailiff-mod-moon" not in deps
    assert "run_after" not in raw, "run_after replaced by depends_on in spec 014"


def test_monorepo_packages_is_agent_fed() -> None:
    """monorepo_packages is a hidden question (agent-fed --data), not _external_data.moon."""
    copier_yml = (_MODULES_DIR / "bailiff-mod-cocogitto" / "copier.yml").read_text()
    assert "monorepo_packages" in copier_yml, "monorepo_packages hidden question must exist"
    assert "_external_data.moon" not in copier_yml, "moon must not appear in _external_data"


def test_no_moon_dep_init_cleanly(bailiff_mod_cocogitto: TemplateRepo, tmp_path: Path) -> None:
    """[base+cocogitto] without moon (monorepo_packages absent) initialises cleanly."""
    text = _init_with_facts(
        bailiff_mod_cocogitto,
        tmp_path / "proj",
        layout="single",
        # No monorepo_packages supplied — simulates a non-monorepo stack without moon.
    )
    assert 'tag_prefix = "v"' in text
    assert "[monorepo]" not in text
