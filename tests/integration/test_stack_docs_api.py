"""Combination stack: "documented API" — base + python + api + mkdocs + precommit.

Asserts the docs/API lifecycles compose:
- openapi.yaml is SEED-ONCE at the repo root (a project edit survives reproduce);
- .spectral.yaml is MANAGED (byte-identical);
- mkdocs.yml is wired to docs/ and docs/index.md is SEED-ONCE;
- the spectral hook block lands (once) in the precommit-written hook file.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from bailiff import runner
from tests.integration.conftest import (
    RUFF_HOOK_BLOCK,
    SPECTRAL_HOOK_BLOCK,
    init_stack,
)

_LAYERS = [
    (
        "bailiff-mod-base",
        {
            "project_name": "api-demo",
            "org": "acme",
            "description": "A documented API",
            "license": "apache-2.0",
            "layout": "single",
            "mise_tools": [
                {"python": "3.13"},
                {"spectral": "6.13.0"},
                {"mkdocs": "1.6.1"},
            ],
            "gitignore_stack": ["Python"],
        },
    ),
    ("bailiff-mod-python", {"python_version": "3.13", "hook_manager": "pre-commit"}),
    ("bailiff-mod-api", {"description": "A documented API"}),
    ("bailiff-mod-mkdocs", {"description": "A documented API"}),
    (
        "bailiff-mod-precommit",
        {
            "hook_manager": "pre-commit",
            "hook_blocks": [RUFF_HOOK_BLOCK, SPECTRAL_HOOK_BLOCK],
        },
    ),
]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def stack(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("stack_docs_api")
    mp = pytest.MonkeyPatch()
    mp.setenv("COPIER_SETTINGS_PATH", str(root / "settings.yml"))
    try:
        yield init_stack(root, _LAYERS)
    finally:
        mp.undo()


def test_openapi_seeded_at_root(stack: Path) -> None:
    oa = stack / "openapi.yaml"
    assert oa.is_file()
    parsed = yaml.safe_load(oa.read_text())
    assert parsed["openapi"] == "3.1.0"
    assert parsed["info"]["title"] == "api-demo"


def test_spectral_managed_and_hook_block_in_hook_file(stack: Path) -> None:
    assert (stack / ".spectral.yaml").is_file()
    hook_text = (stack / ".pre-commit-config.yaml").read_text()
    assert hook_text.count("spectral-lint") == 1, "spectral block exactly once"
    assert hook_text.count("ruff-pre-commit") == 1, "ruff block exactly once"
    parsed = yaml.safe_load(hook_text)
    assert "repos" in parsed


def test_mkdocs_wired_to_docs(stack: Path) -> None:
    mk = yaml.safe_load((stack / "mkdocs.yml").read_text())
    assert mk["site_name"] == "api-demo"
    assert mk["docs_dir"] == "docs"
    assert (stack / "docs/index.md").is_file()


def test_mise_union_docs_api_tokens(stack: Path) -> None:
    # 014 model: each module writes its own .mise/conf.d/<module>.toml fragment.
    assert not (stack / ".mise.toml").exists(), ".mise.toml must not exist in 014 model"
    api_frag = (stack / ".mise/conf.d/bailiff-mod-api.toml").read_text()
    assert "spectral" in api_frag  # api module pins its own spectral version
    mkdocs_frag = (stack / ".mise/conf.d/bailiff-mod-mkdocs.toml").read_text()
    assert "mkdocs" in mkdocs_frag  # mkdocs module pins its own version
    python_frag = (stack / ".mise/conf.d/bailiff-mod-python.toml").read_text()
    assert 'python = "3.13"' in python_frag


def test_seed_once_edits_survive_reproduce(stack: Path) -> None:
    """Project edits to openapi.yaml + docs/index.md survive a re-run;
    the managed .spectral.yaml stays byte-identical."""
    oa = stack / "openapi.yaml"
    idx = stack / "docs/index.md"
    spectral_before = _digest(stack / ".spectral.yaml")

    oa_edit = oa.read_text() + "\n# project-owned edit\n"
    oa.write_text(oa_edit)
    idx_edit = "# My docs\n\nproject-owned content\n"
    idx.write_text(idx_edit)

    runner.reproduce_many(str(stack))

    assert oa.read_text() == oa_edit, "openapi.yaml edit clobbered (seed-once broken)"
    assert idx.read_text() == idx_edit, "docs/index.md edit clobbered (seed-once broken)"
    assert _digest(stack / ".spectral.yaml") == spectral_before, ".spectral.yaml not managed"

    # (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)
