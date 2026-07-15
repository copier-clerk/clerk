"""spec 009 US1 / SC-001 (T017): bailiff-mod-base v1.0.0 thinned scaffold.

Init bailiff-mod-base and assert:
- the managed dir scaffold .gitkeep files exist (thinned base dirs);
- AGENTS.md is present with the substituted identity (seed-once render);
- .copier-answers.yml records _src_path + _commit;
- the (stubbed) trust-gated tasks produced .gitignore + LICENSE;
- layout=monorepo adds the 15 monorepo target dirs;
- moved-out / dropped dirs are ABSENT.

Tasks are stubbed to hermetic offline no-ops via the ``bailiff_mod_base`` fixture
(the real gitnr/gh tasks are validated live only outside the suite).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from bailiff import runner, trust
from tests.conftest import TemplateRepo

# Thinned base dirs (v1.0.0): only always-present dirs remain.
_BASE_DIRS = [
    "docs",
    "scripts",
    "tests",
]

# Conditional docs subdirs (present when docs_subdirs=true, the default).
_DOCS_SUBDIRS = [
    "docs/architecture",
    "docs/decisions",
    "docs/runbooks",
]

# The 15 monorepo targets.
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

# Dirs that were moved out or dropped — must be ABSENT.
_MOVED_OUT_DIRS = [
    ".agents",
    ".codex",
    ".github/workflows",
    "infrastructure",
    "specs",
    "archive",
    "assets",
    "docs/api",
    "docs/engineering",
    "docs/operations",
    "docs/product",
    "docs/research",
]


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _init_base(repo: TemplateRepo, dest: Path, answers: dict[str, Any]) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-13")


def test_base_single_scaffold(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """SC-001: base single-layout v1.0.0 scaffold — thinned dirs, seed-once AGENTS.md."""
    dest = tmp_path / "proj"
    _init_base(
        bailiff_mod_base,
        dest,
        {"project_name": "demo", "org": "acme", "license": "mit", "layout": "single"},
    )

    # Always-present managed dirs.
    for d in _BASE_DIRS:
        assert (dest / d / ".gitkeep").is_file(), f"missing managed scaffold dir {d}/.gitkeep"

    # docs subdirs present with default docs_subdirs=true.
    for d in _DOCS_SUBDIRS:
        assert (dest / d / ".gitkeep").is_file(), f"missing docs subdir {d}/.gitkeep"

    # single layout does NOT create monorepo targets.
    for d in _MONOREPO_TARGETS:
        assert not (dest / d).exists(), f"single layout must not create monorepo target {d}"

    # Moved-out / dropped dirs must be absent.
    for d in _MOVED_OUT_DIRS:
        assert not (dest / d).exists(), f"moved-out/dropped dir {d} must not be scaffolded"

    # AGENTS.md: seed-once with substituted identity.
    agents = (dest / "AGENTS.md").read_text()
    assert agents.startswith("# demo\n"), "AGENTS.md title not substituted from project_name"
    assert "feature-branches-squash-merge" in agents, "AGENTS.md must carry branch_strategy line"
    assert "## Path Mapping" in agents
    assert "## Monorepo Structure" not in agents

    # .copier-answers.yml records source + pinned commit.
    af = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert bailiff_mod_base.url in af["_src_path"]
    assert af["_commit"], "answers file must record a pinned _commit"
    assert af["project_name"] == "demo"
    assert "run_after" not in af
    assert "depends_on" not in af

    # Task-output files produced by the (stubbed) trust-gated tasks.
    assert (dest / ".gitignore").is_file(), "gitnr task did not produce .gitignore"
    assert (dest / "LICENSE").is_file(), "gh task did not produce LICENSE"
    assert (dest / ".git").is_dir(), "git init task did not run"


def test_base_monorepo_adds_targets(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """SC-001: layout=monorepo adds the 15 monorepo target dirs on top of the base."""
    dest = tmp_path / "proj"
    _init_base(
        bailiff_mod_base,
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


def test_base_github_host_false_no_github_dir(
    bailiff_mod_base: TemplateRepo, tmp_path: Path
) -> None:
    """github_host=false → .github/ must not be scaffolded at all."""
    dest = tmp_path / "proj"
    _init_base(
        bailiff_mod_base,
        dest,
        {
            "project_name": "demo",
            "org": "acme",
            "license": "mit",
            "github_host": False,
        },
    )
    assert not (dest / ".github").exists(), "github_host=false must not scaffold .github/"


def test_base_github_host_true_scaffolds_github(
    bailiff_mod_base: TemplateRepo, tmp_path: Path
) -> None:
    """github_host=true (default) → minimal .github/ present, no workflows/."""
    dest = tmp_path / "proj"
    _init_base(
        bailiff_mod_base,
        dest,
        {
            "project_name": "demo",
            "org": "acme",
            "license": "mit",
            "github_host": True,
        },
    )
    assert (dest / ".github").is_dir(), "github_host=true must scaffold .github/"
    assert not (dest / ".github" / "workflows").exists(), (
        ".github/workflows must not be scaffolded by base (that is bailiff-mod-ci)"
    )
    assert (dest / ".github" / "CODEOWNERS").is_file(), "CODEOWNERS must be present"
    assert not (dest / ".github" / "dependabot.yml").exists(), (
        "dependabot.yml removed in spec 012 (pre-v1.0.0) — separate bailiff-mod-dep-updates"
    )


def test_base_docs_subdirs_false(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """docs_subdirs=false → docs/ present but lean core subdirs absent."""
    dest = tmp_path / "proj"
    _init_base(
        bailiff_mod_base,
        dest,
        {"project_name": "demo", "org": "acme", "license": "mit", "docs_subdirs": False},
    )
    assert (dest / "docs" / ".gitkeep").is_file(), "docs/ must always be present"
    for d in _DOCS_SUBDIRS:
        assert not (dest / d).exists(), f"docs_subdirs=false must not scaffold {d}"


def test_base_no_initial_commit_by_default(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """Q5 gate: initial_commit defaults false → git repo has no commit yet."""
    import subprocess

    dest = tmp_path / "proj"
    _init_base(bailiff_mod_base, dest, {"project_name": "demo", "license": "mit"})
    r = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=dest,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0, "initial_commit=false must not create a commit"


def test_base_initial_commit_true_commits(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """Q5 gate: initial_commit=true → the scaffold is committed by the last base task."""
    import subprocess

    dest = tmp_path / "proj"
    _init_base(
        bailiff_mod_base,
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


def test_base_run_git_init_false(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """run_git_init=false → no .git/ created."""
    dest = tmp_path / "proj"
    _init_base(
        bailiff_mod_base,
        dest,
        {"project_name": "demo", "license": "mit", "run_git_init": False},
    )
    assert not (dest / ".git").exists(), "run_git_init=false must not run git init"


def test_base_copyright_name_in_license(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """copyright_name is used in LICENSE, not org."""
    dest = tmp_path / "proj"
    _init_base(
        bailiff_mod_base,
        dest,
        {
            "project_name": "demo",
            "org": "myorg",
            "copyright_name": "My Legal Name",
            "license": "mit",
        },
    )
    license_text = (dest / "LICENSE").read_text()
    assert "My Legal Name" in license_text, "copyright_name must appear in LICENSE"


def test_base_mise_toml_rendered(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """MANAGED: .mise.toml is rendered from the frozen mise_tools answer."""
    dest = tmp_path / "proj"
    _init_base(
        bailiff_mod_base,
        dest,
        {
            "project_name": "demo",
            "license": "mit",
            "mise_tools": [{"python": "3.13"}],
        },
    )
    mise = (dest / ".mise.toml").read_text()
    assert "[tools]" in mise, ".mise.toml must contain [tools] section"
    assert "python" in mise, ".mise.toml must list python tool"
