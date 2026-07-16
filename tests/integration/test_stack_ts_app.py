"""Combination stack: "TypeScript app" — base + ts + precommit + editorconfig +
readme + ci-github.

Asserts the TS overlay coexists with the shared-file single writers:
- .editorconfig carries the TS section per the ts_linter=biome convention;
- CI workflow renders the typescript job from the frozen lang facts;
- precommit hook file carries the contributed biome block exactly once;
- base's .mise.toml carries the node token; reproduce is byte-identical.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.integration.conftest import (
    BIOME_HOOK_BLOCK,
    assert_reproduce_byte_identical,
    init_stack,
)

_LAYERS = [
    (
        "bailiff-mod-base",
        {
            "project_name": "web-demo",
            "org": "acme",
            "description": "A TypeScript app",
            "license": "mit",
            "layout": "single",
            "mise_tools": [{"node": "22"}, {"bun": "1.2.0"}],
            "gitignore_stack": ["ghg:macOS", "Node"],
        },
    ),
    (
        "bailiff-mod-ts",
        {
            "js_pkg_manager": "bun",
            "ts_linter": "biome",
            "test_runner": "vitest-node",
            "node_version": "22",
            "hook_manager": "pre-commit",
        },
    ),
    (
        "bailiff-mod-precommit",
        {"hook_manager": "pre-commit", "hook_blocks": [BIOME_HOOK_BLOCK]},
    ),
    ("bailiff-mod-editorconfig", {"ts_linter": "biome"}),
    (
        "bailiff-mod-readme",
        {"readme_style": "static-skeleton", "stack": "TypeScript/bun"},
    ),
    (
        "bailiff-mod-ci-github",
        {
            "ci_model": "standard",
            "ci_languages": ["typescript"],
            "ci_lang_facts": {
                "typescript": {
                    "manager": "bun",
                    "version": "22",
                    "test_runner": "vitest",
                    "image": "",
                }
            },
            "monorepo_tool": "none",
            "default_branch": "main",
        },
    ),
]


@pytest.fixture(scope="module")
def stack(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("stack_ts_app")
    mp = pytest.MonkeyPatch()
    mp.setenv("COPIER_SETTINGS_PATH", str(root / "settings.yml"))
    try:
        yield init_stack(root, _LAYERS)
    finally:
        mp.undo()


def test_all_layers_rendered(stack: Path) -> None:
    for rel in (
        ".mise.toml",
        "tsconfig.json",
        "biome.json",
        "vitest.config.ts",
        ".pre-commit-config.yaml",
        ".editorconfig",
        "README.md",
        ".github/workflows/ci.yml",
    ):
        assert (stack / rel).is_file(), f"missing output: {rel}"
    assert len(list(stack.glob(".copier-answers.*.yml"))) == len(_LAYERS)


def test_editorconfig_ts_section_biome_convention(stack: Path) -> None:
    """ts_linter=biome frozen fact → 2-space TS section; no Python section invented."""
    text = (stack / ".editorconfig").read_text()
    assert "root = true" in text
    assert "[*.{js" in text, "TS section missing despite ts_linter fact"
    ts_section = text.split("[*.{js")[1]
    assert "indent_size = 2" in ts_section, "biome convention is 2-space indent"
    assert "[*.py]" not in text, "Python section invented without python facts"


def test_ci_workflow_ts_job(stack: Path) -> None:
    ci = (stack / ".github/workflows/ci.yml").read_text()
    assert "typescript-ci:" in ci
    assert "python-ci:" not in ci, "no python job without a python lang fact"


def test_hook_file_biome_block_once(stack: Path) -> None:
    text = (stack / ".pre-commit-config.yaml").read_text()
    assert text.count("biome-check") == 1
    parsed = yaml.safe_load(text)
    assert "repos" in parsed


def test_ts_linter_choice_excludes_eslint(stack: Path) -> None:
    """biome active → biome.json non-empty; eslint/prettier configs render empty."""
    assert len((stack / "biome.json").read_bytes()) > 0
    eslintrc = stack / ".eslintrc.json"
    if eslintrc.exists():
        assert eslintrc.read_bytes() == b"", "eslintrc must be empty when biome is the linter"


def test_mise_union_has_node_and_bun(stack: Path) -> None:
    text = (stack / ".mise.toml").read_text()
    assert 'node = "22"' in text
    assert 'bun = "1.2.0"' in text


def test_readme_static_skeleton(stack: Path) -> None:
    text = (stack / "README.md").read_text()
    assert "# web-demo" in text
    assert "TypeScript/bun" in text
    assert "bun install" in text, "install snippet must follow the bun stack fact"


def test_reproduce_byte_identical(stack: Path) -> None:
    assert_reproduce_byte_identical(stack)
