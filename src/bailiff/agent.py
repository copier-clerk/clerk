"""The phase-1 agent seam (spec 015).

The deterministic engine (``runner``) invokes agent-projected work
(``_agent_tasks``/``_post_agent_tasks``) through an INJECTED callable so it never
imports an LLM and stays testable (Constitution II). The host/skill supplies the
real binding; tests inject a deterministic stub. This module defines only the
types and a no-op default — it imports nothing beyond the standard library.

Contract: ``contracts/agent-tasks.md`` §3.

Freeze/replay is the ENGINE's job (``runner``), not the agent's: the agent merely
returns the files it wants written; the engine captures them into ``_agent_frozen``
at init and replays them (agent-free) at reproduce.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# The agent's output: a mapping of destination-relative path → file content the
# agent wants written. Empty when the projection produced nothing (e.g. no hook
# manager selected). Content is text; binary projection is out of scope.
AgentResult = dict[str, str]


@dataclass(frozen=True)
class AgentContext:
    """Read-only view the engine hands the agent for one projection (agent-tasks.md §3).

    - ``dest``: the (canonicalized) destination project directory.
    - ``module``: the basename of the module whose task is running (the producer).
    - ``slot``: which slot fired — ``agent_tasks.pre|post`` / ``post_agent_tasks.pre|post``.
    - ``selection``: basenames of every selected module, in render (sort) order — the
      agent MUST base its projection on the actual selection (FR-018).
    - ``answers_files``: basename → that layer's committed ``.copier-answers.*.yml`` path,
      for the agent to read frozen facts (never secret values).
    """

    dest: str
    module: str
    slot: str
    selection: list[str] = field(default_factory=list)
    answers_files: dict[str, str] = field(default_factory=dict)


# The injected callable the engine invokes per agent-task slot. Given the verbatim
# manifest instruction and the context, it returns the files to write.
AgentTask = Callable[[str, AgentContext], AgentResult]


def noop_agent(instruction: str, context: AgentContext) -> AgentResult:  # noqa: ARG001
    """Default binding: project nothing.

    Used when no host agent is wired (e.g. the plain deterministic CLI with no
    phase-1 agent available). A module that declares agent tasks but runs under the
    no-op agent simply produces no projected files — the same inert outcome as a
    capability with no consumer. Real projection is supplied by the skill/host.
    """
    return {}


def prefrozen_agent(projections: dict[str, Any]) -> AgentTask:
    """Build an agent that serves projections the phase-1 agent PRECOMPUTED.

    This is the real binding for the two-phase boundary (Constitution II): the
    engine never calls an LLM. Instead the phase-1 agent (the skill, driven by
    Claude) computes each projection during phase 1 and hands it to bailiff in the
    run-spec — exactly as ``apm_packages`` and ``architecture_md`` are agent-decided
    and frozen (the dep-updates precedent, spec 015 direction principle 3). bailiff
    writes and freezes the supplied output; reproduce replays the frozen record with
    no agent at all.

    ``projections`` is keyed ``{module_basename: {slot_id: {path: content}}}`` where
    ``slot_id`` is one of ``agent_tasks.pre|post`` / ``post_agent_tasks.pre|post``.
    A module/slot absent from the map projects nothing (inert), so a partial map is
    valid. The returned callable is pure — no I/O, no LLM — so the engine stays
    deterministic.
    """

    def _serve(instruction: str, context: AgentContext) -> AgentResult:  # noqa: ARG001
        return dict(projections.get(context.module, {}).get(context.slot, {}))

    return _serve
