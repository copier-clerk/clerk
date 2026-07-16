"""spec 011 T004: bailiff-mod-base v1.0.0 loop tests.

Covers the full init→reproduce loop for the thinned base scaffold including:
- Both layouts (single + monorepo): thinned dirs PRESENT, moved-out ABSENT.
- github_host=false → no .github/ at all.
- docs_subdirs gates lean core subdirs.
- AGENTS.md seed-once: substituted with project_name / description / branch_strategy.
- .mise.toml MANAGED: rendered from frozen mise_tools.
- .gitignore and LICENSE TASK-OUTPUT: present after init, guarded on reproduce.
- Sentinel .bailiff-base-init-done: present after init, skips heavy tasks on reproduce.
- reproduce leaves TASK-OUTPUT and MANAGED dirs present and guard-idempotent.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from bailiff import runner, trust
from tests.conftest import TemplateRepo

# Always-present managed dirs (thinned v1.0.0).
_ALWAYS_DIRS = ["docs", "scripts", "tests"]

# docs subdirs present only when docs_subdirs=true (the default).
_DOCS_SUBDIRS = ["docs/architecture", "docs/decisions", "docs/runbooks"]

# Monorepo targets — present only when layout=monorepo.
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

# Dirs moved out of base — MUST be absent.
_ABSENT_DIRS = [
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


def _init(repo: TemplateRepo, dest: Path, answers: dict[str, Any]) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-14")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Init: single layout
# ---------------------------------------------------------------------------


def test_init_single_thinned_dirs_present(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """MANAGED dirs always present; moved-out dirs absent after single-layout init."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_base, dest, {"project_name": "myproj", "org": "acme", "license": "mit"})

    for d in _ALWAYS_DIRS:
        assert (dest / d / ".gitkeep").is_file(), f"always-present dir {d}/.gitkeep missing"

    for d in _DOCS_SUBDIRS:
        assert (dest / d / ".gitkeep").is_file(), f"docs_subdirs=true: {d}/.gitkeep missing"

    for d in _MONOREPO_TARGETS:
        assert not (dest / d).exists(), f"single layout must not scaffold monorepo dir {d}"

    for d in _ABSENT_DIRS:
        assert not (dest / d).exists(), f"moved-out/dropped dir {d} must be absent"


# ---------------------------------------------------------------------------
# Init: monorepo layout
# ---------------------------------------------------------------------------


def test_init_monorepo_thinned_dirs_present(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """layout=monorepo: always dirs + 15 monorepo targets present; moved-out absent."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_base,
        dest,
        {"project_name": "myproj", "org": "acme", "license": "mit", "layout": "monorepo"},
    )

    for d in _ALWAYS_DIRS:
        assert (dest / d / ".gitkeep").is_file(), f"always-present dir {d}/.gitkeep missing"

    for d in _MONOREPO_TARGETS:
        assert (dest / d / ".gitkeep").is_file(), f"monorepo target {d}/.gitkeep missing"

    for d in _ABSENT_DIRS:
        assert not (dest / d).exists(), f"moved-out/dropped dir {d} must be absent"


# ---------------------------------------------------------------------------
# github_host gate
# ---------------------------------------------------------------------------


def test_init_github_host_false_no_github(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """github_host=false → no .github/ at all."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_base,
        dest,
        {"project_name": "myproj", "org": "acme", "license": "mit", "github_host": False},
    )
    assert not (dest / ".github").exists(), "github_host=false must not scaffold .github/"


def test_init_github_host_true_no_workflows(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """github_host=true → minimal .github/ present; workflows/ absent (belongs to ci)."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_base,
        dest,
        {"project_name": "myproj", "org": "acme", "license": "mit", "github_host": True},
    )
    assert (dest / ".github" / "CODEOWNERS").is_file(), "CODEOWNERS missing"
    # dependabot.yml moved OUT of base to bailiff-mod-dep-updates (spec 012 amendment,
    # applied pre-v1.0.0 so base ships clean).
    assert not (dest / ".github" / "dependabot.yml").exists(), (
        "dependabot.yml must not be scaffolded by base — owned by bailiff-mod-dep-updates (012)"
    )
    assert not (dest / ".github" / "workflows").exists(), (
        ".github/workflows must not be scaffolded by base"
    )


# ---------------------------------------------------------------------------
# docs_subdirs gate
# ---------------------------------------------------------------------------


def test_init_docs_subdirs_false(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """docs_subdirs=false → docs/ present but architecture/decisions/runbooks absent."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_base,
        dest,
        {"project_name": "myproj", "license": "mit", "docs_subdirs": False},
    )
    assert (dest / "docs" / ".gitkeep").is_file(), "docs/ must always be present"
    for d in _DOCS_SUBDIRS:
        assert not (dest / d).exists(), f"docs_subdirs=false must not scaffold {d}"


# ---------------------------------------------------------------------------
# AGENTS.md seed-once: substitution with project_name / description / branch_strategy
# ---------------------------------------------------------------------------


def test_init_agents_md_substituted(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """AGENTS.md is seed-once with correct project_name, description, branch_strategy."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_base,
        dest,
        {
            "project_name": "alpha",
            "org": "corp",
            "description": "The alpha project",
            "license": "mit",
            "branch_strategy": "trunk-based",
        },
    )
    agents = (dest / "AGENTS.md").read_text()
    assert agents.startswith("# alpha\n"), "project_name not substituted in AGENTS.md"
    assert "The alpha project" in agents, "description not substituted in AGENTS.md"
    assert "trunk-based" in agents, "branch_strategy not substituted in AGENTS.md"


def test_init_agents_md_seed_once_not_overwritten(
    bailiff_mod_base: TemplateRepo, tmp_path: Path
) -> None:
    """AGENTS.md is NOT overwritten on reproduce (_skip_if_exists)."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_base, dest, {"project_name": "beta", "license": "mit"})
    hand_edit = "# HAND EDITED\ndo not clobber\n"
    (dest / "AGENTS.md").write_text(hand_edit)

    runner.reproduce(str(dest))

    assert (dest / "AGENTS.md").read_text() == hand_edit, (
        "AGENTS.md was clobbered on reproduce (seed-once violated)"
    )


# ---------------------------------------------------------------------------
# .mise.toml MANAGED: rendered from mise_tools
# ---------------------------------------------------------------------------


def test_init_mise_toml_managed_rendered(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """MANAGED: .mise.toml rendered from frozen mise_tools answer."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_base,
        dest,
        {
            "project_name": "gamma",
            "license": "mit",
            "mise_tools": [{"python": "3.13"}, {"node": "22"}],
        },
    )
    mise = (dest / ".mise.toml").read_text()
    assert "[tools]" in mise, ".mise.toml must have [tools] section"
    assert "python" in mise and "3.13" in mise, "python 3.13 not in .mise.toml"
    assert "node" in mise and "22" in mise, "node 22 not in .mise.toml"


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


# ---------------------------------------------------------------------------
# TASK-OUTPUT: .gitignore and LICENSE present; idempotent on reproduce
# ---------------------------------------------------------------------------


def test_init_task_outputs_present(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """TASK-OUTPUT: .gitignore and LICENSE produced by trust-gated tasks on init."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_base, dest, {"project_name": "delta", "license": "apache-2.0"})
    assert (dest / ".gitignore").is_file(), ".gitignore missing after init"
    assert (dest / "LICENSE").is_file(), "LICENSE missing after init"


def test_reproduce_task_outputs_idempotent(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """TASK-OUTPUT: reproduce does not regenerate .gitignore or LICENSE (guards hold)."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_base, dest, {"project_name": "delta", "license": "mit"})
    gi_digest = _digest(dest / ".gitignore")
    lic_digest = _digest(dest / "LICENSE")

    runner.reproduce(str(dest))

    assert (dest / ".gitignore").is_file(), ".gitignore missing after reproduce"
    assert (dest / "LICENSE").is_file(), "LICENSE missing after reproduce"
    assert _digest(dest / ".gitignore") == gi_digest, ".gitignore changed on reproduce"
    assert _digest(dest / "LICENSE") == lic_digest, "LICENSE changed on reproduce"


# ---------------------------------------------------------------------------
# Sentinel: init-only guard (FR-012a)
# ---------------------------------------------------------------------------


def test_init_sentinel_created(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """Sentinel .bailiff-base-init-done is written after successful init."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_base, dest, {"project_name": "eps", "license": "mit"})
    assert (dest / ".bailiff-base-init-done").is_file(), (
        ".bailiff-base-init-done sentinel must exist after init"
    )


# ---------------------------------------------------------------------------
# extra_dirs: freeform append-only dirs (MANAGED lifecycle)
# ---------------------------------------------------------------------------


def test_init_extra_dirs_created(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """extra_dirs entries are created as .gitkeep dirs on init (MANAGED)."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_base,
        dest,
        {
            "project_name": "xdtest",
            "license": "mit",
            "extra_dirs": ["foo", "bar/baz"],
        },
    )
    assert (dest / "foo" / ".gitkeep").is_file(), "extra_dirs 'foo' not created"
    assert (dest / "bar" / "baz" / ".gitkeep").is_file(), "extra_dirs 'bar/baz' not created"


def test_reproduce_extra_dirs_idempotent(bailiff_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """extra_dirs .gitkeep files survive reproduce unchanged (MANAGED idempotent)."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_base,
        dest,
        {
            "project_name": "xdtest",
            "license": "mit",
            "extra_dirs": ["mydir"],
        },
    )
    digest_before = _digest(dest / "mydir" / ".gitkeep")

    runner.reproduce(str(dest))

    assert (dest / "mydir" / ".gitkeep").is_file(), "extra_dirs dir missing after reproduce"
    assert _digest(dest / "mydir" / ".gitkeep") == digest_before, (
        "extra_dirs .gitkeep changed on reproduce"
    )


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)
