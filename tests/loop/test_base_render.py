"""spec 009 US1 / SC-001 (T017): clerk-mod-base scaffolds correctly.

Init clerk-mod-base and assert:
- the managed dir scaffold .gitkeep files exist (20 base dirs);
- AGENTS.md is present with the substituted identity (seed-once render);
- .copier-answers.yml records _src_path + _commit;
- the (stubbed) trust-gated tasks produced .gitignore + LICENSE;
- layout=monorepo adds the 15 monorepo target dirs.

Tasks are stubbed to hermetic offline no-ops via the ``clerk_mod_base`` fixture
(the real gitnr/gh tasks are validated live only outside the suite — see the
module README / report; they are tool/network-gated).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from clerk import runner, trust
from tests.conftest import TemplateRepo

# The 20 base dirs (verbatim from dirs-scaffold _BASE_DIRS; count=20 authoritative).
_BASE_DIRS = [
    ".codex",
    ".agents/hooks",
    ".github/workflows",
    "docs/architecture",
    "docs/decisions",
    "docs/research",
    "docs/runbooks",
    "docs/product",
    "docs/engineering",
    "docs/operations",
    "docs/api",
    "specs",
    "infrastructure/environments",
    "infrastructure/terraform/modules",
    "infrastructure/terraform/stacks",
    "infrastructure/terraform/environments",
    "tests",
    "scripts",
    "assets",
    "archive",
]

# The 15 monorepo targets (verbatim from _MONOREPO_TARGETS).
_MONOREPO_TARGETS = [
    "apps",
    "services",
    "functions",
    "workers",
    "libs/domain",
    "libs/application",
    "libs/adapters",
    "libs/config",
    "libs/testing",
    "libs/ui",
    "libs/types",
    "packages",
    "schemas",
    "data/shared",
    "tools",
]


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _init_base(repo: TemplateRepo, dest: Path, answers: dict[str, Any]) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-13")


def test_base_single_scaffold(clerk_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """SC-001: base single-layout scaffold — managed dirs, seed-once AGENTS.md, tasks."""
    dest = tmp_path / "proj"
    _init_base(
        clerk_mod_base,
        dest,
        {"project_name": "demo", "org": "acme", "license": "mit", "layout": "single"},
    )

    # Managed dir scaffold: all 20 base dirs have a .gitkeep.
    for d in _BASE_DIRS:
        assert (dest / d / ".gitkeep").is_file(), f"missing managed scaffold dir {d}/.gitkeep"

    # single layout does NOT create the monorepo targets.
    for d in _MONOREPO_TARGETS:
        assert not (dest / d).exists(), f"single layout must not create monorepo target {d}"

    # AGENTS.md present with substituted identity (seed-once render).
    agents = (dest / "AGENTS.md").read_text()
    assert agents.startswith("# demo\n"), "AGENTS.md title not substituted from project_name"
    assert "acme/demo" in agents, "AGENTS.md repo line not substituted (ORG/PROJECT_NAME)"
    # single layout uses the Path Mapping section, not the Monorepo Structure one.
    assert "## Path Mapping" in agents
    assert "## Monorepo Structure" not in agents

    # .copier-answers.yml records source + pinned commit.
    af = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert clerk_mod_base.url in af["_src_path"]
    assert af["_commit"], "answers file must record a pinned _commit"
    assert af["project_name"] == "demo"
    # hidden edges are never persisted.
    assert "run_after" not in af
    assert "depends_on" not in af

    # Task-output files produced by the (stubbed) trust-gated tasks.
    assert (dest / ".gitignore").is_file(), "gitnr task did not produce .gitignore"
    assert (dest / "LICENSE").is_file(), "gh task did not produce LICENSE"
    # git init task ran.
    assert (dest / ".git").is_dir(), "git init task did not run"


def test_base_monorepo_adds_targets(clerk_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """SC-001: layout=monorepo adds the 15 monorepo target dirs on top of the 20 base."""
    dest = tmp_path / "proj"
    _init_base(
        clerk_mod_base,
        dest,
        {"project_name": "demo", "org": "acme", "license": "apache-2.0", "layout": "monorepo"},
    )

    for d in _BASE_DIRS:
        assert (dest / d / ".gitkeep").is_file(), f"missing base dir {d}"
    for d in _MONOREPO_TARGETS:
        assert (dest / d / ".gitkeep").is_file(), f"missing monorepo target {d}"

    agents = (dest / "AGENTS.md").read_text()
    assert "## Monorepo Structure" in agents
    assert "## Path Mapping" not in agents


def test_base_no_initial_commit_by_default(clerk_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """Q5 gate: initial_commit defaults false → git repo has no commit yet."""
    import subprocess

    dest = tmp_path / "proj"
    _init_base(clerk_mod_base, dest, {"project_name": "demo", "license": "mit"})
    # HEAD should not resolve (no commit made) — default initial_commit=false.
    r = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=dest,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0, "initial_commit=false must not create a commit"


def test_base_initial_commit_true_commits(clerk_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """Q5 gate: initial_commit=true → the scaffold is committed by the last base task."""
    import subprocess

    dest = tmp_path / "proj"
    _init_base(
        clerk_mod_base,
        dest,
        {"project_name": "demo", "license": "mit", "initial_commit": True},
    )
    r = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=dest,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0 and "Initial project scaffold" in r.stdout, (
        f"initial_commit=true must create the scaffold commit; git log: {r.stdout!r}"
    )
