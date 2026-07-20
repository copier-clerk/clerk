# Implementation Plan: Agent-projected capability contract (spec 015)

**Branch**: `015-agent-projected-capabilities` · **Spec**: `spec.md` (this dir) ·
**Depends on**: the spec-014 engine on `main` (private-by-default threading,
`_external_data`, `_post_tasks`, `_bailiff_schema` gate, `_canonical_dest`,
`resolve_locator`).

## Summary

Add a machine-readable contract for the composition tier mechanical merge can't
express: cross-format translation of a capability's neutral intent into the backend a
stack selected. The pieces:

- Two per-module `copier.yml` fields — `_agent_tasks`, `_post_agent_tasks` — each a
  `pre`/`post` map. The engine schedules on the keys and never parses the instruction.
- The phase-1 agent runs these at INIT ONLY; the engine freezes the output so reproduce
  stays agent-free (Constitution III).
- Proving instances: a neutral hook dir consumed by two managers (existing
  `bailiff-mod-precommit`, new `bailiff-mod-lefthook`) and agentic
  `bailiff-mod-editorconfig`.

## Technical Context

The 014 fan-out proved the `.pre-commit.d/` fragment model is pre-commit-format-bound:
language modules drop pre-commit-shaped YAML, a bundler `_post_task` merges it into
`.pre-commit-config.yaml`, and a non-pre-commit hook manager gets nothing. The general
shape — generic intent → tool-specific config — recurs for every pluggable-backend
capability. 015 is the engine + authoring contract for the agent-mediated tier, plus
the first two proving instances. It is a C-11 engine change (sanctioned by the 013
relaxation); no constitution amendment anticipated.

## Constitution Check

- **II/III (two-phase, agent-free reproduce):** agent tasks run at INIT ONLY; the
  engine freezes their output as recorded answers; reproduce replays frozen state with
  no agent. Preserved — this is the load-bearing invariant of the whole spec.
- **V (no silent credential/default):** agent tasks carry NL instructions, never
  secrets; the reproduce-safety lint fails loud when an agent-owned managed path is
  unfrozen.
- **VI (published-label immutability):** `_agent_tasks`/`_post_agent_tasks` are new
  hidden manifest keys, not question choices — no label mutation. `hook_manager` was
  already removed as a question in 014 (R13).

## Key design decisions (resolves spec.md open questions)

### D1 — FR-014 neutral hook dir: `.hooks.d/` (NEW), `.pre-commit.d/` stays pre-commit-native

`.pre-commit.d/` remains what 014 built: pre-commit-shaped fragments, mechanically
merged by the pre-commit bundler (tier 2 — no agent, no translation). It is NOT renamed.

Add a NEW neutral dir **`.hooks.d/`** for cross-format hook intent. A hook-contributing
module MAY write EITHER:
- `.pre-commit.d/<vendor>-<module>.yaml` — when it wants the zero-agent pre-commit path
  (unchanged 014 behavior; inert without `bailiff-mod-precommit`), OR
- `.hooks.d/<module>.yaml` — a neutral, manager-agnostic hook description (id, language,
  entry, files-glob, stages) that ANY selected hook manager projects into its own format
  via `_post_agent_tasks`.

Rationale for two dirs rather than one:

- The pre-commit path is already mechanical and correct; routing it through agent
  translation would add an agent and cost to a path that needs neither.
- `.hooks.d/` is the escalation for backends whose format the bundler can't emit.
- A pre-commit-only module keeps its `.pre-commit.d/` fragment; a portable module writes
  `.hooks.d/` and each manager module translates.
- A later spec MAY migrate language modules to `.hooks.d/` once ≥2 managers exist; 015
  does not force that churn.

### D2 — The neutral `.hooks.d/` schema is descriptive, not a config superset

Each `.hooks.d/<module>.yaml` lists hooks by neutral intent:
```yaml
hooks:
  - id: ruff
    language: python
    entry: "ruff check --fix"
    files: "\\.py$"
    stages: [pre-commit]
```
This is deliberately minimal — enough for a manager module's agent task to render the
tool-specific block. It is NOT a full pre-commit/lefthook schema (spec.md rejects a
static superset). Unknown backends interpret the same neutral fields.

### D3 — Manager modules own projection via `_post_agent_tasks`

- `bailiff-mod-precommit` gains a `_post_agent_tasks.pre` that projects any `.hooks.d/`
  entries into pre-commit blocks BEFORE its existing mechanical bundler `_post_task`
  runs (so the bundler sees them alongside `.pre-commit.d/` fragments).
- `bailiff-mod-lefthook` (NEW) declares `_post_agent_tasks.post` that projects all
  `.hooks.d/` entries into `lefthook.yml` after the render loop.
- Neither module reads the other; `.hooks.d/` is the neutral hand-off. No hook manager
  selected → nothing projects `.hooks.d/` → inert (US2).

### D4 — Engine freeze mechanism (resolves spec.md FR-009 open detail)

The engine captures agent-task output as recorded answers under a reserved key per task
slot, e.g. `_agent_frozen: {<module>: {<slot>: <captured-output>}}`, written to the
producing module's answers file (append-only, like `_bailiff_schema`). On reproduce the
engine detects the frozen block and replays it INSTEAD of invoking the agent. The
captured shape is opaque to bailiff (it is the agent's projected file content + target
path); bailiff only stores and replays it.

### D5 — Reproduce-safety lint (FR-012)

At init, after freezing, the engine checks: for each path an agent task wrote, if that
path is ALSO produced by a MANAGED render (a template file that re-renders on reproduce),
and the agent output was not captured, fail loud (the managed re-render would clobber the
agent output on reproduce). Implemented as a post-render diff: managed-rendered paths ∩
agent-written paths must all be in the frozen set.

## Project Structure

### Documentation (this feature)
```
specs/015-agent-projected-capabilities/
  spec.md                      # done
  plan.md                      # this file
  contracts/
    agent-tasks.md             # _agent_tasks/_post_agent_tasks schema + timeline + freeze
    hooks-neutral-dir.md       # .hooks.d/ schema + manager projection contract
```

### Changed source + template content
```
# Engine (C-11 013 exception — runner + discovery):
src/bailiff/discovery.py    # parse _agent_tasks/_post_agent_tasks; validate pre/post keys (FR-004)
src/bailiff/runner.py       # timeline hooks (FR-006/007), agent invocation seam, freeze + replay, reproduce-safety lint
src/bailiff/agent.py        # NEW: the phase-1 agent seam (injectable; a no-op/echo in tests)

# Neutral hook capability:
templates/bailiff-mod-lefthook/          # NEW module: projects .hooks.d/ -> lefthook.yml
templates/bailiff-mod-precommit/         # gain _post_agent_tasks.pre projecting .hooks.d/
templates/bailiff-mod-editorconfig/      # drop linter questions; agent writes .editorconfig via _agent_tasks

# FR-017/018 authoring docs:
skills/bailiff/SKILL.md                  # phase-1 agent-projection procedure
_meta/module-template/                   # the canonical _agent_tasks pattern
specs/011-.../contracts/_cross-cutting.md
```

## Cross-cutting design (Phase 1 detail → contracts/)

- **Agent seam.** `runner` must invoke "the phase-1 agent" at defined points, but the
  deterministic engine has no LLM. Model the agent as an injected callable
  (`agent(instruction, context) -> {path: content}`); the real binding is supplied by
  the skill/host, tests inject a deterministic stub. This keeps runner LLM-free and
  testable (Constitution II) while giving init a place to call out.
- **Timeline (FR-006/007).** Render loop per module: render → `_agent_tasks.pre` →
  `_tasks` → `_agent_tasks.post`. Post-loop: every `_post_agent_tasks.pre` (sort order)
  → `_post_tasks` → every `_post_agent_tasks.post`. Reproduce: all `pre`/`post` skipped;
  frozen state replays; `_tasks`/`_post_tasks` re-run.
- **Determinism.** Same-stage tie-break is module sort order (same as `_post_tasks`).

## Build / test / release sequencing

1. Contracts (`agent-tasks.md`, `hooks-neutral-dir.md`) — author + review first.
2. Engine: discovery parse + validation → runner timeline seam + freeze/replay →
   reproduce-safety lint. Unit + loop tests with a stubbed agent.
3. `.hooks.d/` neutral dir + `bailiff-mod-lefthook` + precommit projection; integration
   test: `[base + python + lefthook]` gets ruff into `lefthook.yml`; `[base + python +
   precommit]` unchanged; `[base + python]` inert.
4. Agentic `bailiff-mod-editorconfig`.
5. `check_modules` validation of the new fields; regen catalog.
6. Rebase branch onto `main` (pick up merged engine fixes) before release; fan-out +
   PyPI bump handled by the standard release pipeline.

## Complexity Tracking

- The agent seam is the one genuinely new engine concept. Justified: cross-format
  translation cannot be mechanical (spec.md tiering §2), and freezing keeps reproduce
  agent-free. A static neutral superset was rejected in spec.md.
- Two hook dirs (`.pre-commit.d/` + `.hooks.d/`) is deliberate (D1) — not migrated in
  015 to avoid churn; documented as the escalation path.

## Open questions for tasks.md

- Exact `.hooks.d/` neutral schema fields (D2 draft → freeze in `hooks-neutral-dir.md`).
- Frozen-answer key shape (D4 draft `_agent_frozen`) — confirm it survives copier's
  answers-file round-trip like `_bailiff_schema` does.
- Whether `bailiff-mod-editorconfig` fully drops its questions in 015 or keeps a
  standalone fallback for the no-language-module case.
