"""Shared helpers for the combination integration tests (tests/integration/).

These tests compose REAL authored modules from templates/ into realistic
multi-module stacks and drive them through ``runner.init_many`` /
``runner.reproduce_many``. Everything is hermetic/offline: each module is
copied into a local tagged git repo with its native/network ``_tasks``
swapped for the deterministic stubs defined in tests/conftest.py
(the ``_copy_module_with_stub_tasks`` pattern).

Stacks are expensive (one shallow clone per layer for discovery + collision
scan + render), so test files build them ONCE via module-scoped fixtures and
assert read-only on the resulting tree.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from tests.conftest import (
    _BASE_STUB_TASKS,
    _BUN_STUB_TASKS,
    _CFN_STUB_TASKS,
    _COG_STUB_TASKS,
    _MOON_STUB_TASKS,
    _PRECOMMIT_STUB_TASKS,
    _PYTHON_STUB_TASKS,
    _TERRAFORM_STUB_TASKS,
    TemplateRepo,
    _copy_module_with_stub_tasks,
)

# Per-module offline stub-task blocks. Modules absent from this map ship ZERO
# _tasks (pure renders) — an empty stub leaves their copier.yml unchanged.
_STUBS: dict[str, str] = {
    "bailiff-mod-base": _BASE_STUB_TASKS,
    "bailiff-mod-python": _PYTHON_STUB_TASKS,
    "bailiff-mod-ts": _BUN_STUB_TASKS,
    "bailiff-mod-precommit": _PRECOMMIT_STUB_TASKS,
    "bailiff-mod-terraform": _TERRAFORM_STUB_TASKS,
    "bailiff-mod-cloudformation": _CFN_STUB_TASKS,
    "bailiff-mod-moon": _MOON_STUB_TASKS,
    "bailiff-mod-cocogitto": _COG_STUB_TASKS,
}

# Language hook blocks contributed to the frozen hook_blocks union (the shapes
# the phase-1 agent would freeze — same as the per-module loop tests use).
RUFF_HOOK_BLOCK = (
    "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
    "    rev: v0.6.9\n"
    "    hooks:\n"
    "      - id: ruff\n"
    "        args: [--fix]\n"
    "      - id: ruff-format\n"
)

BIOME_HOOK_BLOCK = (
    "  - repo: local\n"
    "    hooks:\n"
    "      - id: biome-check\n"
    "        name: biome check\n"
    "        entry: bunx biome check --write\n"
    "        language: system\n"
    "        files: \\.(js|ts|jsx|tsx|json)$\n"
)

SPECTRAL_HOOK_BLOCK = (
    "  - repo: local\n"
    "    hooks:\n"
    "      - id: spectral-lint\n"
    "        name: spectral lint (OpenAPI)\n"
    "        entry: spectral lint openapi.yaml\n"
    "        language: system\n"
    "        files: ^openapi\\.yaml$\n"
    "        pass_filenames: false\n"
)

COG_HOOK_BLOCK = (
    "  - repo: local\n"
    "    hooks:\n"
    "      - id: cocogitto-commit-msg\n"
    "        name: cocogitto verify (conventional commits)\n"
    "        entry: cog verify --file\n"
    "        language: system\n"
    "        stages: [commit-msg]\n"
)


def build_module_repo(name: str, root: Path) -> TemplateRepo:
    """Copy the real authored module into a hermetic tagged repo under root."""
    return _copy_module_with_stub_tasks(name, root / name, _STUBS.get(name, ""))


def make_record(
    name: str,
    repo: TemplateRepo,
    *,
    provides: list[str] | None = None,
) -> TemplateRecord:
    """A minimal TemplateRecord for a local hermetic module repo."""
    return TemplateRecord(
        full_id=f"demo/{name}",
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=True,
        questions=[],
        provides=provides or [],
    )


def init_stack(
    root: Path,
    layers: list[tuple[str, dict[str, Any]]],
    *,
    dest_name: str = "proj",
    exclusive_capabilities: frozenset[str] = frozenset(),
) -> Path:
    """Build module repos, trust them, and init the multi-layer stack.

    ``layers`` is ``[(module_name, answers), ...]`` — order irrelevant
    (init_many topo-sorts). Returns the project dest path.
    """
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = []
    for name, answers in layers:
        repo = build_module_repo(name, root)
        trust.add_trust(repo.url)
        selection.append((make_record(name, repo), answers))
    dest = root / dest_name
    runner.init_many(
        selection,
        str(dest),
        today="2026-07-15",
        exclusive_capabilities=exclusive_capabilities,
    )
    return dest


@pytest.fixture(scope="module")
def module_monkeypatch() -> Any:
    """A module-scoped MonkeyPatch (pytest's monkeypatch is function-scoped)."""
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def isolated_settings(mp: pytest.MonkeyPatch, root: Path) -> None:
    """Point copier's settings (trust store) at a throwaway file under root."""
    mp.setenv("COPIER_SETTINGS_PATH", str(root / "settings.yml"))
