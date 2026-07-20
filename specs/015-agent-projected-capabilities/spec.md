# Feature Specification: Agent-projected capability contract — `_agent_tasks` / `_post_agent_tasks`, neutral drop-dirs, cross-format translation (spec 015)

**Feature Branch**: `015-agent-projected-capabilities`

**Created**: 2026-07-17

**Status**: Draft — research-first. Direction ratified in
`specs/014-namespaced-question-keys/decisions-ledger.md` (R13, R13-GENERALIZED, and the
spec-015 direction block). This spec formalizes that direction into testable requirements;
plan.md + tasks.md follow after the spec is accepted.

**Input**: The spec-014 fan-out finding that the `.pre-commit.d/` fragment model is
pre-commit-FORMAT-specific — with a non-pre-commit hook manager, language hooks
(ruff/biome/clippy/golangci) silently vanish because nothing projects the fragments into the
other manager's format. Generalized in the 014 ledger to every capability with pluggable
backends. Governed by the constitution (v3.0.0) and ADRs 0001–0008. Builds on the spec-014
engine (private-by-default threading, `_external_data`, `_post_tasks`, `_bailiff_schema:014`).

---

## Overview

bailiff composes a project from independent `bailiff-mod-*` copier templates applied as
layers. Spec 014 established two mechanical composition surfaces: native drop-in merge
(`.mise/conf.d/`, merged by mise itself) and single-manager mechanical merge (the
`.pre-commit.d/` bundler `_post_task`, the `.gitignore.d/` concat). Both are FORMAT-bound: the
`.pre-commit.d/` bundler emits `.pre-commit-config.yaml` and nothing else. A stack that selects
a different hook manager gets no language hooks — a silent capability loss.

The general problem is generic-intent → tool-specific-config translation. It is not
hooks-specific: it applies to every capability with pluggable backends (hooks:
pre-commit/lefthook; CI providers; formatters; unknown third-party managers). Spec 015
introduces a uniform, machine-readable contract for the tier of composition that mechanical
merge cannot express — cross-format translation — performed by the phase-1 agent at init and
frozen as recorded answers so reproduce stays agent-free and deterministic (Constitution III).

The philosophy is inherited from specs 013 and 014: **enforce structure, don't trust author
discipline**. Today "the agent fills this" exists only as scattered free-text `copier.yml`
comments and narrative in contracts — no uniform, tool-readable marker. Spec 015 makes the
agent-projection points a structured, discoverable part of the module manifest.

---

## Translation tiering (the design frame)

Composition escalates only when the lower tier cannot express the result:

1. **Native drop-in merge** — the manager reads a directory of fragments itself (mise reads
   `.mise/conf.d/*.toml`). No bailiff code runs. Contributor drops a fragment; consumer never
   imported.
2. **Mechanical same-format merge** — a single manager's config is assembled from same-format
   fragments by a deterministic `_post_task` (the pre-commit bundler; the gitignore concat).
3. **Agent-mediated cross-format translation** — the target format is not known ahead of time
   or differs per selected backend (pre-commit YAML vs lefthook YAML vs a third-party schema).
   The phase-1 agent translates neutral intent into the selected backend's vocabulary and the
   engine freezes the result.

A static neutral schema for tier 3 was rejected: it cannot cover unknown third-party managers
and becomes a leaky superset of every backend's config. See ADR (to be written this spec).

---

## User Scenarios & Testing

### US1 — Language hooks reach the selected hook manager (primary)

A maintainer assembles a stack with a language module (contributes hook intent) and a hook
manager module that is NOT pre-commit (e.g. a `bailiff-mod-lefthook`). The language module's
hook intent is projected into the selected manager's config format; no hook silently vanishes.

**Acceptance**: init a `[base + <language> + <non-pre-commit hook manager>]` stack; the
selected manager's config file contains the language's hooks (translated to that format); the
neutral fragment dir is consumed, not copied verbatim.

### US2 — No hook manager selected → inert

A stack selects a language module but no hook manager module. The language module still drops
its neutral hook fragment; nothing projects it; no manager config file is written.

**Acceptance**: init `[base + <language>]` with no hook manager; no `.pre-commit-config.yaml`,
no `lefthook.yml`; the neutral fragment dir is present and inert (the spec-014 R13-GENERALIZED
guarantee, extended to the neutral dir).

### US3 — Reproduce runs no agent and reproduces the frozen projection

A project generated in US1 is reproduced (`bailiff reproduce`). The phase-1 agent does NOT
run. The frozen projection replays; mechanical `_tasks`/`_post_tasks` re-run and consume the
frozen output. The reproduced manager config is identical to the init output.

**Acceptance**: reproduce over a committed US1 tree with no agent available; the manager config
is byte-consistent with init; no network/agent call occurs.

### US4 — Reproduce-safety lint catches an unfrozen agent-owned path

An `_agent_tasks`/`_post_agent_tasks` projection writes a path that the module also re-renders
as a MANAGED file, but its output is not captured as a frozen answer. The engine flags this at
init: the managed re-render would clobber the agent output on reproduce.

**Acceptance**: a module whose agent task writes a managed-owned path without a captured freeze
fails an engine lint at init with a legible error naming the path.

### US5 — Agentic editorconfig (second instance, proves generality)

`bailiff-mod-editorconfig` drops its per-language linter questions. The agent writes
`.editorconfig` sections from the selected language modules via `_agent_tasks`, frozen for
reproduce. The same contract that projects hooks projects editorconfig — no capability-specific
engine code.

**Acceptance**: init a stack with two language modules; `.editorconfig` carries a section per
selected language derived by the agent; reproduce replays it agent-free.

### Edge cases

- Two modules declare `_post_agent_tasks.post` → both run, in module sort order (same tie-break
  as `_post_tasks`).
- A module declares only `_agent_tasks.pre` (no `.post`) → only the pre point runs.
- An agent task produces empty output (nothing to project) → engine freezes empty; reproduce is
  a clean no-op; no manager file appears.
- `update` (re-init) → agent re-runs and re-freezes against the current selection (init-class,
  not reproduce-class).

---

## Requirements

### Manifest schema

- **FR-001**: A module MAY declare `_agent_tasks` in its `copier.yml`, a map with optional
  string values under keys `pre` and `post`. Each value is a freeform natural-language
  instruction to the phase-1 agent.
- **FR-002**: A module MAY declare `_post_agent_tasks` in its `copier.yml`, a map with the same
  optional `pre`/`post` string shape.
- **FR-003**: The engine schedules agent work on the KEYS (`pre`/`post`) alone. bailiff MUST
  NOT parse, interpret, or validate the instruction string beyond its type (string).
- **FR-004**: Any key other than `pre`/`post` in `_agent_tasks`/`_post_agent_tasks` is a
  manifest error surfaced at discovery (fail loud, name the module and key).
- **FR-005**: `_agent_tasks`/`_post_agent_tasks` are discoverable via the existing module
  discovery path (siblings to `_tasks`/`_post_tasks`); their presence is reported in the
  module's `Discovery` record.

### Execution model — init

- **FR-006**: At init, within the render loop (phase → `depends_on` DAG → basename sort), each
  module runs in order: render → `_agent_tasks.pre` → inline `_tasks` → `_agent_tasks.post`.
- **FR-007**: At init, after the render loop: every `_post_agent_tasks.pre` (module sort order)
  → mechanical `_post_tasks` merges → every `_post_agent_tasks.post` (module sort order).
- **FR-008**: Agent `pre`/`post` instructions run the phase-1 AGENT at INIT ONLY.

### Execution model — reproduce / freeze

- **FR-009**: The engine captures the output of every agent task as frozen recorded state at
  init. The author declares NO `freeze`/`outputs` annotation — freezing is engine behavior.
- **FR-010**: At reproduce, the phase-1 agent is SKIPPED for all `_agent_tasks`/
  `_post_agent_tasks` (`pre` and `post`). Frozen state replays; `_tasks`/`_post_tasks` re-run
  and consume it.
- **FR-011**: Reproduce over a tree generated with agent projection MUST be agent-free and
  deterministic (Constitution III preserved).
- **FR-012**: The engine runs a reproduce-safety LINT at init: if an agent task writes a path
  owned by a MANAGED render whose output is not captured as frozen state, init fails with an
  error naming the path (the managed re-render would clobber the agent output on reproduce).

### Neutral drop-dir contribution

- **FR-013**: A capability contributor drops fragments into a neutral, manager-agnostic
  directory and declares NO `depends_on` on any specific manager module. The selected manager
  module scans the neutral dir; none selected → inert.
- **FR-014**: The hook capability neutral dir generalizes the spec-014 `.pre-commit.d/` model
  to a manager-agnostic dir consumed by whichever hook manager module is selected. [NEEDS
  DESIGN: the neutral dir name and whether the existing `.pre-commit.d/` is renamed or a
  pre-commit manager module reads it as one backend among several — resolve in plan.md.]

### New module + module changes

- **FR-015**: A `bailiff-mod-lefthook` module projects the neutral hook fragments into
  `lefthook.yml` via `_post_agent_tasks`. lefthook was stripped from `bailiff-mod-precommit` in
  spec 014; this is its own module.
- **FR-016**: `bailiff-mod-editorconfig` drops its per-language linter questions; the agent
  writes `.editorconfig` sections from the selected languages via `_agent_tasks`, frozen for
  reproduce.

### Documentation (authoring guide)

- **FR-017**: The one canonical agent-projection pattern is documented in the FR-018 authoring
  guide (`_meta/module-template/`) and the cross-cutting contract, so every module — first- or
  third-party — follows the same shape.
- **FR-018**: The `SKILL.md` phase-1 procedure documents how the agent MUST re-check and redo
  the projection based on the actual module SELECTION, for all capabilities.

---

## Success Criteria

- **SC-001**: A `[base + language + non-pre-commit hook manager]` stack init produces a manager
  config containing the language's hooks (US1).
- **SC-002**: A `[base + language]` stack with no hook manager writes no manager config and
  leaves the neutral fragment dir inert (US2).
- **SC-003**: Reproduce over an agent-projected tree is agent-free and byte-consistent with
  init (US3).
- **SC-004**: An unfrozen agent-owned managed path fails the reproduce-safety lint at init
  (US4).
- **SC-005**: Agentic editorconfig produces a per-language `.editorconfig` on init and replays
  agent-free on reproduce, using the same contract as hooks (US5).
- **SC-006**: A non-`pre`/`post` key in `_agent_tasks`/`_post_agent_tasks` fails discovery with
  a legible error (FR-004).
- **SC-007**: `check_modules` validates the new manifest fields across all modules with no
  regressions to the spec-014 gates.

---

## Out of scope

- A static neutral config schema for cross-format translation (rejected — cannot cover unknown
  third-party managers).
- A per-CAPABILITY agent-projection registry (rejected — a closed list bailiff must maintain;
  the contract is per-MODULE self-declaration, which is open).
- A `slot:`/`outputs:`/`freeze:` structured envelope on agent tasks (rejected — the map key
  already encodes the schedule; freeze is a global engine rule).
- A `during` scheduling slot (rejected — atomic tasks have no inside).
- Importing live remote state back into answers (breaks agent-free reproduce; separate future
  feature).
- New user-facing capabilities beyond the hook-manager and editorconfig instances needed to
  prove the contract.
- Constitution amendment (none anticipated; engine changes fall under the 013 C-11 relaxation).

---

## Dependencies

- Spec 014 engine (private-by-default threading, `_external_data`, `_post_tasks`,
  `_bailiff_schema` gate) merged to main.
- Precedent: `bailiff-mod-dep-updates` already maps package managers into a chosen tool's
  vocabulary and freezes the result — the reference implementation of "agent translates, engine
  freezes".

## Governed by

ADR-0001..0008; Constitution I–VIII; C-06 (published-label immutability — note the
`hook_manager` question was already removed in 014, R13), C-07, C-11 (engine exception).
