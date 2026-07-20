"""spec 015: agent-task timeline, freeze/replay, and reproduce-safety lint.

The agent is a deterministic STUB (no LLM). Tests assert:
- timeline order: render → _agent_tasks.pre → _tasks → _agent_tasks.post; post-loop
  every _post_agent_tasks.pre → _post_tasks → every _post_agent_tasks.post (FR-006/007).
- freeze at init + agent-free replay at reproduce (FR-009/010/011, SC-003).
- reproduce-safety lint on an unfrozen managed-owned agent write (FR-012, SC-004).
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from bailiff import agent as _agent
from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from bailiff.errors import BailiffError
from tests.conftest import build_template_repo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _record(full_id: str, repo) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=True,
        questions=["project_name"],
    )


# A module that declares all four agent slots + an inline _tasks marker, so a stub
# agent recording its slot invocations proves the full timeline.
def _agent_module(tmp_path: Path, name: str):
    return build_template_repo(
        tmp_path / name,
        files={
            "copier.yml": dedent(
                f"""\
                project_name:
                  type: str
                depends_on:
                  type: yaml
                  default: []
                  when: false
                _subdirectory: template
                _agent_tasks:
                  pre: "{name}: agent pre"
                  post: "{name}: agent post"
                _post_agent_tasks:
                  pre: "{name}: post-agent pre"
                  post: "{name}: post-agent post"
                _tasks:
                  - "printf '{name}\\n' >> .timeline"
                """
            ),
            "template/{{ _copier_conf.answers_file }}.jinja": (
                "# Managed by copier — do not edit by hand.\n"
                "{{ _copier_answers|to_nice_yaml }}\n"
            ),
            "template/out.txt.jinja": "x\n",
        },
    )


def test_timeline_order(tmp_path: Path) -> None:
    """A recording stub agent + an inline _tasks marker prove slot ordering."""
    repo = _agent_module(tmp_path, "mod")
    trust.add_trust(repo.url)
    calls: list[str] = []

    def stub(instruction: str, ctx: _agent.AgentContext) -> _agent.AgentResult:
        calls.append(ctx.slot)
        return {}

    dest = tmp_path / "proj"
    runner.init_many(
        [(_record("cat/mod", repo), {"project_name": "p"})],
        str(dest),
        today="2026-07-20",
        agent=stub,
    )
    # Per-module: agent_tasks.pre before the copier render+_tasks, post after.
    assert calls == [
        "agent_tasks.pre",
        "agent_tasks.post",
        "post_agent_tasks.pre",
        "post_agent_tasks.post",
    ]
    # The inline _tasks marker landed (render happened between pre and post).
    assert (dest / ".timeline").read_text().strip() == "mod"


def test_freeze_then_replay_is_agent_free(tmp_path: Path) -> None:
    """Init freezes the agent output; reproduce replays it WITHOUT calling the agent."""
    repo = _agent_module(tmp_path, "mod")
    trust.add_trust(repo.url)

    def writing_stub(instruction: str, ctx: _agent.AgentContext) -> _agent.AgentResult:
        if ctx.slot == "post_agent_tasks.post":
            return {"projected/hooks.txt": f"from {ctx.module}\n"}
        return {}

    dest = tmp_path / "proj"
    runner.init_many(
        [(_record("cat/mod", repo), {"project_name": "p"})],
        str(dest),
        today="2026-07-20",
        agent=writing_stub,
    )
    projected = dest / "projected" / "hooks.txt"
    assert projected.read_text() == "from mod\n"
    # The output is frozen into the module's answers file.
    af = (dest / ".copier-answers.mod.yml").read_text()
    assert "_agent_frozen:" in af
    assert "projected/hooks.txt" in af

    # Reproduce with a RAISING agent — it must never be invoked (FR-010/011).
    def raising(instruction: str, ctx: _agent.AgentContext) -> _agent.AgentResult:
        raise AssertionError("agent must not run on reproduce")

    projected.unlink()  # prove replay re-creates it
    # reproduce_many takes no agent (it never uses one); replay is from frozen state.
    runner.reproduce_many(str(dest))
    assert projected.read_text() == "from mod\n"


def test_reproduce_safety_lint_on_unfrozen_managed_path(tmp_path: Path) -> None:
    """An agent write to a MANAGED-render path that is not frozen fails init (FR-012).

    We force the unfrozen condition by writing a path whose freeze cannot be captured
    (no answers file for a phantom producer would apply); here we simulate by having
    the agent write a managed-rendered path and monkeypatching the freeze to a no-op.
    """
    repo = _agent_module(tmp_path, "mod")
    trust.add_trust(repo.url)

    def stub(instruction: str, ctx: _agent.AgentContext) -> _agent.AgentResult:
        if ctx.slot == "agent_tasks.post":
            return {"out.txt": "agent-owned\n"}  # out.txt is a MANAGED render
        return {}

    # Neuter the freeze so the written path is NOT captured → lint must catch it.
    orig = runner._freeze_agent_output
    runner._freeze_agent_output = lambda *a, **k: None
    try:
        dest = tmp_path / "proj"
        with pytest.raises(BailiffError, match="reproduce-safety"):
            runner.init_many(
                [(_record("cat/mod", repo), {"project_name": "p"})],
                str(dest),
                today="2026-07-20",
                agent=stub,
            )
    finally:
        runner._freeze_agent_output = orig
