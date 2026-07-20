"""spec 015 (FR-016): bailiff-mod-editorconfig is AGENT-PROJECTED.

The 014 managed-render + linter-question model is gone; `.editorconfig` is now
written by the phase-1 agent from the actual selection (universal defaults + a
section per selected language) via `_post_agent_tasks.post`, and frozen by the
engine so reproduce replays it agent-free.

The agent is a deterministic STUB emulating the projection. Assertions:
- multi-language stack → per-language sections written + frozen;
- no phase-1 agent (no-op) → no `.editorconfig` (agent-projected, inert);
- the module ships no linter questions and no managed `.editorconfig.jinja`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from bailiff import agent as _agent
from tests.conftest import _MODULES_DIR
from tests.integration.conftest import init_stack

_BASE = (
    "bailiff-mod-base",
    {"project_name": "ec-demo", "org": "acme", "license": "mit", "layout": "single"},
)
_PY = ("bailiff-mod-python", {"python_version": "3.13", "python_pkg_manager": "uv"})
_TS = ("bailiff-mod-ts", {"ts_linter": "biome", "js_pkg_manager": "bun"})


def _editorconfig_stub(instruction: str, ctx: _agent.AgentContext) -> _agent.AgentResult:
    """Project .editorconfig from the selection (emulates the phase-1 agent)."""
    if ctx.slot != "post_agent_tasks.post" or ctx.module != "bailiff-mod-editorconfig":
        return {}
    lines = [
        "root = true",
        "",
        "[*]",
        "charset = utf-8",
        "end_of_line = lf",
        "insert_final_newline = true",
        "trim_trailing_whitespace = true",
    ]
    if "bailiff-mod-python" in ctx.selection:
        lines += ["", "[*.py]", "indent_style = space", "indent_size = 4", "max_line_length = 88"]
    if "bailiff-mod-ts" in ctx.selection:
        lines += ["", "[*.{js,jsx,ts,tsx,mjs,cjs}]", "indent_style = space", "indent_size = 2"]
    return {".editorconfig": "\n".join(lines) + "\n"}


def _init(root: Path, layers: list[tuple[str, dict[str, Any]]], *, agent: Any = None) -> Path:
    mp = pytest.MonkeyPatch()
    mp.setenv("COPIER_SETTINGS_PATH", str(root / "settings.yml"))
    try:
        return init_stack(root, layers, agent=agent)
    finally:
        mp.undo()


def test_per_language_sections_projected(tmp_path_factory: pytest.TempPathFactory) -> None:
    """A two-language stack → a section per selected language, frozen for reproduce."""
    root = tmp_path_factory.mktemp("ec_multi")
    dest = _init(
        root,
        [_BASE, _PY, _TS, ("bailiff-mod-editorconfig", {})],
        agent=_editorconfig_stub,
    )
    text = (dest / ".editorconfig").read_text()
    assert "root = true" in text
    assert "[*.py]" in text and "indent_size = 4" in text
    assert "[*.{js,jsx,ts,tsx,mjs,cjs}]" in text
    # frozen into the editorconfig layer's answers file.
    af = (dest / ".copier-answers.bailiff-mod-editorconfig.yml").read_text()
    assert "_agent_frozen:" in af and ".editorconfig" in af


def test_no_agent_leaves_no_editorconfig(tmp_path_factory: pytest.TempPathFactory) -> None:
    """No phase-1 agent (no-op) → agent-projected .editorconfig is simply absent."""
    root = tmp_path_factory.mktemp("ec_noagent")
    dest = _init(root, [_BASE, _PY, ("bailiff-mod-editorconfig", {})])  # no agent
    assert not (dest / ".editorconfig").exists()


def test_module_ships_no_linter_questions_or_managed_render() -> None:
    """The 014 managed model is gone: no linter questions, no .editorconfig.jinja."""
    mod = _MODULES_DIR / "bailiff-mod-editorconfig"
    data = yaml.safe_load((mod / "copier.yml").read_text())
    for dropped in ("ts_linter", "python_linter", "ruff_line_length"):
        assert dropped not in data, f"{dropped} question must be dropped (agent-projected now)"
    assert "_post_agent_tasks" in data
    assert not (mod / "template" / ".editorconfig.jinja").exists(), (
        "managed .editorconfig.jinja must be removed — the agent owns the file"
    )
    assert "_external_data" not in data
