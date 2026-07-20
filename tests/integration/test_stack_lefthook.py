"""Combination stack: neutral hooks → hook-manager projection (spec 015).

Exercises the .hooks.d/ neutral dir consumed by two different hook managers via
_post_agent_tasks, plus the no-manager inert case. The phase-1 agent is a
deterministic STUB emulating cross-format projection (a real LLM is not available
in tests); the ENGINE's timeline/freeze/replay is what these assert.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from bailiff import agent as _agent
from tests.integration.conftest import init_stack

_PY = ("bailiff-mod-python", {"python_version": "3.13", "python_pkg_manager": "uv"})
_BASE = (
    "bailiff-mod-base",
    {"project_name": "hooks-demo", "org": "acme", "license": "mit", "layout": "single"},
)


def _read_hooks_d(dest: Path) -> list[dict[str, Any]]:
    """Aggregate every .hooks.d/*.yaml hook entry present in the tree."""
    entries: list[dict[str, Any]] = []
    for frag in sorted((dest).rglob(".hooks.d/*.yaml")):
        data = yaml.safe_load(frag.read_text()) or {}
        entries.extend(data.get("hooks", []))
    return entries


def _lefthook_stub(instruction: str, ctx: _agent.AgentContext) -> _agent.AgentResult:
    """Project .hooks.d/ → lefthook.yml (emulates the phase-1 agent, deterministically)."""
    if ctx.slot != "post_agent_tasks.post":
        return {}
    hooks = _read_hooks_d(Path(ctx.dest))
    if not hooks:
        return {}
    commands = {
        h["id"]: {"run": h["entry"], "glob": h.get("files", "")}
        for h in hooks
        if "pre-commit" in (h.get("stages") or ["pre-commit"])
    }
    return {"lefthook.yml": yaml.safe_dump({"pre-commit": {"commands": commands}}, sort_keys=True)}


class TestLefthookProjection:
    def test_lefthook_gets_language_hooks(self, tmp_path_factory: pytest.TempPathFactory) -> None:
        """[base+python+lefthook] → lefthook.yml carries ruff; no pre-commit config (SC-001)."""
        root = tmp_path_factory.mktemp("stack_lefthook")
        mp = pytest.MonkeyPatch()
        mp.setenv("COPIER_SETTINGS_PATH", str(root / "settings.yml"))
        try:
            dest = init_stack(
                root,
                [_BASE, _PY, ("bailiff-mod-lefthook", {"install_hooks": False})],
                agent=_lefthook_stub,
            )
        finally:
            mp.undo()
        lh = dest / "lefthook.yml"
        assert lh.is_file(), "lefthook.yml was not projected from .hooks.d/"
        cfg = yaml.safe_load(lh.read_text())
        assert "ruff" in cfg["pre-commit"]["commands"]
        assert not (dest / ".pre-commit-config.yaml").exists()
        # frozen into the lefthook layer's answers file → reproduce is agent-free.
        af = (dest / ".copier-answers.bailiff-mod-lefthook.yml").read_text()
        assert "_agent_frozen:" in af and "lefthook.yml" in af


class TestNoManagerInert:
    def test_no_hook_manager_leaves_hooks_d_inert(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """[base+python] with no manager → no hook config; .hooks.d/ present + inert (SC-002)."""
        root = tmp_path_factory.mktemp("stack_no_manager")
        mp = pytest.MonkeyPatch()
        mp.setenv("COPIER_SETTINGS_PATH", str(root / "settings.yml"))
        try:
            dest = init_stack(root, [_BASE, _PY], agent=_lefthook_stub)
        finally:
            mp.undo()
        assert not (dest / "lefthook.yml").exists()
        assert not (dest / ".pre-commit-config.yaml").exists()
        # the neutral fragment is present but unconsumed.
        assert (dest / ".hooks.d" / "bailiff-mod-python.yaml").is_file()
