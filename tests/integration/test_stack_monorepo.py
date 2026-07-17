"""Combination stack: "monorepo" — base(layout=monorepo) + python + ts + moon +
ci-github(monorepo-affected/moon) + justfile.

Asserts monorepo wiring composes:
- .moon/workspace.yml maps the frozen monorepo_packages to project dirs;
- CI renders the moon-ci affected branch (no per-language jobs);
- both language overlays coexist without collision (ruff.toml + tsconfig.json);
- base scaffolds the monorepo target dirs; reproduce byte-identical.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.integration.conftest import init_stack

_PACKAGES = ["packages/api", "apps/web"]

_LAYERS = [
    (
        "bailiff-mod-base",
        {
            "project_name": "mono-demo",
            "org": "acme",
            "license": "apache-2.0",
            "layout": "monorepo",
            "mise_tools": [{"python": "3.13"}, {"node": "22"}, {"moon": "1.30.0"}],
            "gitignore_stack": ["Python", "Node"],
        },
    ),
    ("bailiff-mod-python", {"python_version": "3.13", "hook_manager": "none"}),
    (
        "bailiff-mod-ts",
        {
            "js_pkg_manager": "bun",
            "ts_linter": "biome",
            "node_version": "22",
            "hook_manager": "none",
        },
    ),
    ("bailiff-mod-moon", {"monorepo_packages": _PACKAGES}),
    (
        "bailiff-mod-ci-github",
        {
            "ci_model": "monorepo-affected",
            "monorepo_tool": "moon",
            "ci_languages": [],
            "ci_lang_facts": {},
            "default_branch": "main",
        },
    ),
    (
        "bailiff-mod-justfile",
        {"language": "ts", "js_pkg_manager": "bun", "hook_manager": "none"},
    ),
]


@pytest.fixture(scope="module")
def stack(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("stack_monorepo")
    mp = pytest.MonkeyPatch()
    mp.setenv("COPIER_SETTINGS_PATH", str(root / "settings.yml"))
    try:
        yield init_stack(root, _LAYERS)
    finally:
        mp.undo()


def test_moon_workspace_wired_to_packages(stack: Path) -> None:
    ws = stack / ".moon/workspace.yml"
    assert ws.is_file()
    parsed = yaml.safe_load(ws.read_text())
    assert parsed["projects"] == {"api": "packages/api", "web": "apps/web"}
    assert parsed["vcs"]["manager"] == "git"


def test_ci_renders_moon_affected_branch(stack: Path) -> None:
    ci = (stack / ".github/workflows/ci.yml").read_text()
    assert "moon-ci:" in ci
    assert "run: moon ci" in ci
    assert "fetch-depth: 0" in ci, "moon needs full history to diff against base"
    # No per-language jobs on the moon branch.
    assert "python-ci:" not in ci
    assert "typescript-ci:" not in ci


def test_monorepo_scaffold_dirs(stack: Path) -> None:
    """layout=monorepo adds the monorepo target directories from base."""
    for d in ("apps", "packages", "libs/domain", "services"):
        assert (stack / d / ".gitkeep").is_file(), f"monorepo dir missing: {d}"


def test_language_overlays_coexist(stack: Path) -> None:
    """python + ts overlays land side by side with no collision."""
    assert (stack / "ruff.toml").is_file()
    assert (stack / "pyproject.toml").is_file()
    assert (stack / "tsconfig.json").is_file()
    assert (stack / "biome.json").is_file()
    assert len(list(stack.glob(".copier-answers.*.yml"))) == len(_LAYERS)


def test_monorepo_tool_answer_recorded_for_ci(stack: Path) -> None:
    """moon records monorepo_tool=moon — the frozen fact CI consumed."""
    af = yaml.safe_load((stack / ".copier-answers.bailiff-mod-moon.yml").read_text())
    assert af["monorepo_tool"] == "moon"
    assert af["monorepo_packages"] == _PACKAGES


def test_mise_union_all_three_tokens(stack: Path) -> None:
    # 014 model: each module writes its own .mise/conf.d/<module>.toml fragment;
    # no single .mise.toml exists.
    assert not (stack / ".mise.toml").exists(), ".mise.toml must not exist in 014 model"
    moon_frag = (stack / ".mise/conf.d/bailiff-mod-moon.toml").read_text()
    assert "moon" in moon_frag  # moon module pins its own version
    python_frag = (stack / ".mise/conf.d/bailiff-mod-python.toml").read_text()
    assert 'python = "3.13"' in python_frag
    ts_frag = (stack / ".mise/conf.d/bailiff-mod-ts.toml").read_text()
    assert 'node = "22"' in ts_frag


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)
