# 0002 — user-owned catalog; copier answers carry the state

- Status: accepted
- Date: 2026-07-09

## Context

Clerk must let users point the agent at *their own* templates, not depend on a
first-party hub. Separately, we needed to decide where the per-module answer
state and agentic metadata live.

## Decision — catalog

- The catalog is **user-owned configuration**, not baked into clerk's repo. It
  lists **sources**, not templates.
- **Source reference format is APM-style**: `gituser/gitrepo/filepath#tagorsha`.
  Expose all three pin kinds — exact tag, exact sha, and branch.
- **Freshness is manual**: an explicit `just catalog` / CLI invocation refreshes;
  CI is just one caller of the same entrypoint, never a dependency.
- **Merge / id collisions: full-id always** (`catalog/template`). No
  unnamespaced first-wins convenience lookup.
- Clerk may ship an **optional, swappable** reference catalog; the engine works
  against any user-supplied sources with zero reference templates.

## Decision — answer model (supersedes the sidecar idea)

- **copier's committed answers file is the source of truth**, and its
  answer-source precedence ladder enforces the two-phase split for free:
  `CLI/API args > ask user > answer from last execution > copier.yml defaults`.
  - Init: the agent injects computed answers at priority 1 (`--data` /
    `run_copy(data=...)`); copier does not re-prompt them.
  - Reproduce: copier replays "answer from last execution" (priority 3) from the
    committed answers file — **agent not involved**.
- **Per-question metadata is native copier** (`type`, `choices`, `when`,
  `validator`, `help`) and carries "what is valid" and "how to fill this". A
  dedicated `clerk.yml` sidecar for that content is therefore **not needed** and
  is rejected (see [[0003-selector-template-and-runtime-injection]] for how the
  catalog and agent guidance are supplied at runtime instead).

## Consequences

- Decentralization is native: copier's answers file records `_src_path` +
  `_commit`, so an answers file points at *its own* template at its own pin —
  users bring their own templates and never depend on clerk's repo at reproduce
  time.
- Agent-authored answers must be replayed with `recopy` (full re-render), not
  `update` (smart 3-way merge), because copier's docs forbid hand-editing the
  answers file and `update`'s diff assumes prompt-captured answers.

## Related

- [[0001-copier-as-engine]], [[0003-selector-template-and-runtime-injection]].
