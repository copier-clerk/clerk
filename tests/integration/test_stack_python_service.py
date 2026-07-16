"""Combination stack: "Python service" — base + python + precommit + quality +
justfile + ci-github + dep-updates.

Verifies the frozen-union / single-writer contract (_cross-cutting §2/§4/§5/§6)
holds when the whole realistic stack composes:
- base is the only writer of .mise.toml (all contributed tokens present);
- precommit is the only writer of the hook config (contributed blocks present once);
- quality writes the quality-languages hook file;
- dep-updates resolves dependabot from the THREADED github_host=true base answer;
- reproduce over the committed tree is byte-identical.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.integration.conftest import (
    RUFF_HOOK_BLOCK,
    assert_reproduce_byte_identical,
    init_stack,
)

_MISE_TOOLS = [{"python": "3.13"}, {"uv": "0.11.8"}]

_LAYERS = [
    (
        "bailiff-mod-base",
        {
            "project_name": "svc-demo",
            "org": "acme",
            "description": "A Python service",
            "license": "apache-2.0",
            "layout": "single",
            "github_host": True,
            "mise_tools": _MISE_TOOLS,
            "gitignore_stack": ["ghg:macOS", "Python"],
        },
    ),
    (
        "bailiff-mod-python",
        {
            "python_version": "3.13",
            "python_pkg_manager": "uv",
            "python_layout": "src",
            "ruff_line_length": "88",
            "hook_manager": "pre-commit",
        },
    ),
    (
        "bailiff-mod-precommit",
        {"hook_manager": "pre-commit", "hook_blocks": [RUFF_HOOK_BLOCK]},
    ),
    ("bailiff-mod-quality", {"quality_languages": ["python"]}),
    (
        "bailiff-mod-justfile",
        {"language": "python", "js_pkg_manager": "bun", "hook_manager": "pre-commit"},
    ),
    (
        "bailiff-mod-ci-github",
        {
            "ci_model": "standard",
            "ci_languages": ["python"],
            "ci_lang_facts": {
                "python": {"manager": "uv", "version": "3.13", "test_runner": "pytest", "image": ""}
            },
            "monorepo_tool": "none",
            "default_branch": "main",
        },
    ),
    # github_host is deliberately NOT passed: it must THREAD from base's answer
    # (dep-updates sorts after base) and resolve dep_update_tool=dependabot.
    ("bailiff-mod-dep-updates", {"dep_ecosystems": ["uv", "github-actions"]}),
]


@pytest.fixture(scope="module")
def stack(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("stack_python_service")
    mp = pytest.MonkeyPatch()
    mp.setenv("COPIER_SETTINGS_PATH", str(root / "settings.yml"))
    try:
        yield init_stack(root, _LAYERS)
    finally:
        mp.undo()


def test_all_layers_rendered(stack: Path) -> None:
    """Every module's principal output landed; one answers file per layer."""
    for rel in (
        "AGENTS.md",  # base
        ".mise.toml",  # base (single writer)
        "ruff.toml",  # python
        "pyproject.toml",  # python (stubbed native init)
        ".pre-commit-config.yaml",  # precommit (single writer)
        ".agents/hooks/quality-languages",  # quality
        "justfile",  # justfile
        ".github/workflows/ci.yml",  # ci-github
        ".github/dependabot.yml",  # dep-updates
    ):
        assert (stack / rel).is_file(), f"missing output: {rel}"
    answers = sorted(p.name for p in stack.glob(".copier-answers.*.yml"))
    assert len(answers) == len(_LAYERS), f"one answers file per layer, got {answers}"


def test_mise_toml_single_writer_union(stack: Path) -> None:
    """base writes .mise.toml once with ALL contributed tokens (and only those)."""
    text = (stack / ".mise.toml").read_text()
    assert "managed by bailiff-mod-base" in text
    assert 'python = "3.13"' in text
    assert 'uv = "0.11.8"' in text
    # No module in this stack contributes cog — it must be absent.
    assert "cog" not in text
    # Single writer: exactly one .mise.toml anywhere in the tree.
    assert len(list(stack.rglob(".mise.toml"))) == 1


def test_hook_file_single_writer_with_blocks(stack: Path) -> None:
    """precommit writes the hook file once; the frozen ruff block appears exactly once."""
    cfg = stack / ".pre-commit-config.yaml"
    text = cfg.read_text()
    assert "managed by bailiff-mod-precommit" in text
    assert text.count("ruff-pre-commit") == 1, "contributed block must appear exactly once"
    parsed = yaml.safe_load(text)
    repo_urls = [r.get("repo", "") for r in parsed["repos"]]
    assert any("ruff-pre-commit" in u for u in repo_urls), "block must parse into repos"
    # No second hook-manager file.
    assert not (stack / "lefthook.yml").exists()


def test_quality_languages_file(stack: Path) -> None:
    assert (stack / ".agents/hooks/quality-languages").read_text().split() == ["python"]


def test_justfile_python_recipes(stack: Path) -> None:
    justfile = (stack / "justfile").read_text()
    assert "uv run pytest" in justfile
    assert "pre-commit run --all-files" in justfile


def test_ci_workflow_python_jobs(stack: Path) -> None:
    ci = (stack / ".github/workflows/ci.yml").read_text()
    assert "# Model: standard" in ci
    assert "python-ci:" in ci
    assert "gate:" in ci


def test_dependabot_from_threaded_github_host(stack: Path) -> None:
    """github_host=true threads from base → dependabot branch, no renovate."""
    db = stack / ".github/dependabot.yml"
    parsed = yaml.safe_load(db.read_text())
    assert parsed["version"] == 2
    assert [u["package-ecosystem"] for u in parsed["updates"]] == ["uv", "github-actions"]
    assert "WARNING" not in db.read_text()
    assert not (stack / "renovate.json").exists()


def test_reproduce_byte_identical(stack: Path) -> None:
    assert_reproduce_byte_identical(stack)
