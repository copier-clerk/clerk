---
description: "Task list for clerk agentic-ecosystem module (spec 007)"
---

# Tasks: clerk agentic-ecosystem module (spec 007)

**Input**: Design documents from `specs/007-agentic-module/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[contracts/agentic-module.md](./contracts/agentic-module.md),
[constitution](../../.specify/memory/constitution.md) v2.1.0

> **STATUS: BLOCKED — do not begin implementation until Open Questions are resolved.**
>
> This task list is a STRUCTURAL PLACEHOLDER drafted alongside the spec to show the
> shape of work, establish the phase ordering, and make the blocked decisions
> explicit. The actual task content (file paths, question keys, `_task` commands,
> component list) MUST be updated once the following open questions are resolved by
> the orchestrator + user:
>
> - **OQ-007-a** — Fixed vs runtime-injected multiselect (determines `copier.yml` question shape)
> - **OQ-007-b** — v1 component scope (determines rendered file count + `_tasks`)
> - **OQ-007-c** — SpecKit bridge depth (determines whether SpecKit needs a `_task`)
> - **OQ-007-e** — Reproduce contract for `apm.lock.yaml` + `_task` pin form
> - **OQ-007-f** — Monolith vs split (determines directory structure + number of templates)
>
> Re-generate with `/speckit.tasks` after those decisions are documented in `spec.md`
> and `contracts/agentic-module.md`.

---

## Design decisions this task list assumes (TO BE CONFIRMED after OQ resolution)

The tasks below assume the following defaults (placeholder — each is marked [TBD]):

- **[TBD-A]** OQ-007-a: Option (C) hybrid — baked-in curated choices + free-text
  additions. The `copier.yml` uses `multiselect` with a fixed `choices:` list.
- **[TBD-B]** OQ-007-b: v1 scope = APM + SpecKit scaffold. MCP servers and
  steering/ADR are deferred to a follow-on minor version.
- **[TBD-C]** OQ-007-c: SpecKit = config-only (rendered `.specify/` skeleton,
  no additional `_task`).
- **[TBD-E]** OQ-007-e: `apm.lock.yaml` = task side-effect, not committed render.
  The `_task` pins the APM CLI version. Reproduce is process-deterministic, not
  byte-identical for the lock file (documented in contract and SKILL.md).
- **[TBD-F]** OQ-007-f: Monolithic `clerk-mod-apm` template in v1. Split is
  deferred until a second component is developed.
- Reuse: spec 003 `ordering.py` + `runner.init_many` / `reproduce_many` (no
  changes). Spec 010 invocation surface (no changes). Discovery parses
  `depends_on` edge from the new template's `copier.yml` automatically.

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no incomplete-task dependency)
- Exact file paths included where known; [TBD] where pending OQ resolution

---

## Phase 0: Pre-work and OQ resolution [GATE]

> These tasks must complete BEFORE any template content is authored.

- [ ] T001 Resolve OQ-007-a through OQ-007-g by reviewing `spec.md` Open Questions
  with the user/orchestrator. Document each decision in `spec.md` (update the
  relevant OQ entry with "RESOLVED: ...") and in `contracts/agentic-module.md`
  (fill in [TBD] items). Mark this task complete when all blocking OQs are resolved.
- [ ] T002 [P] Verify the APM CLI interface: confirm the exact `apm install` command
  form (or its equivalent) and that it is invokable via `uv run --with 'apm==X.Y.Z'
  apm install`. Document the resolved form in `contracts/agentic-module.md` under
  `_tasks`. If no CLI install command exists, record the correct equivalent and
  update T012 accordingly.

**Checkpoint**: all [TBD-*] decisions documented; contract file has no [TBD] items
in the tasks, question, or file-inventory sections.

---

## Phase 1: Template skeleton

- [ ] T003 Create `clerk-mod-apm/` directory in the monorepo root (or the resolved
  location per OQ-007-f). Scaffold the minimum valid copier template:
  `copier.yml` (stub — no real questions yet, just settings and the `when:false`
  `depends_on` edge declaration), `{{ _copier_conf.answers_file }}.jinja`, and a
  `CHANGELOG.md`. Ensure `discovery.discover` returns `reproducible: true` and
  `dependency_edges` contains the expected edge.
- [ ] T004 [P] Add a local-git fixture to `tests/conftest.py` for `clerk-mod-apm`:
  a minimal stub template with the `depends_on` edge, an `apm_packages` question
  (type `str`, empty default), and the answers-file `.jinja`. Follows the same
  fixture-builder pattern as the existing spec 003 multi-template fixtures. Confirm
  that `ordering.layer_plan([base_record, apm_record])` returns `[base, apm]` (edge
  honoured by spec 003 ordering).

**Checkpoint**: `discovery.discover` on the skeleton returns the correct shape;
ordering engine sequences apm after base; fixture builds hermetically.

---

## Phase 2: Component content — APM [TBD details]

> Content depends on OQ-007-a and OQ-007-b. The task structure below assumes
> [TBD-A] (fixed choices) and [TBD-B] (APM + SpecKit in v1).

- [ ] T005 Add APM component questions to `copier.yml` [TBD: exact keys, choices list
  for the curated package set — to be confirmed with OQ-007-a resolution and the
  current clerk `apm.yml` package list]. Add `speckit_enabled` bool question.
- [ ] T006 Add `apm.yml.jinja`: renders a valid `apm.yml` for the generated project
  with the selected packages in `dependencies.apm[]`. Use the authoring repo's
  `apm.yml` (at `/apm.yml`) as the reference schema. Conditional on
  `apm_packages | length > 0`.
- [ ] T007 Add the trust-gated APM install `_task` to `copier.yml`: runs
  `uv run --with 'apm=={{ apm_cli_version }}' apm install` (or the form resolved in
  T002); conditional on `apm_packages | length > 0`; pinned to the resolved APM CLI
  version.

**Checkpoint**: `copier copy <source> <dest> --data apm_packages=[…]` renders a
correct `apm.yml`; the `_task` command is syntactically valid (can be dry-run
inspected).

---

## Phase 3: Component content — SpecKit scaffold [TBD details]

> Depends on OQ-007-c. Assumes [TBD-C] (config-only, no task).

- [ ] T008 Add `.specify/` scaffold files (conditional on `speckit_enabled: true`):
  `constitution.md.jinja` (stub — project name + date injected), `extensions.yml.jinja`
  (empty skeleton), `feature.json.jinja` (minimal SpecKit integration config).
  Use the authoring repo's `.specify/` structure as the reference.
- [ ] T009 [P] Add `apm.yml.jinja` entries for SpecKit APM packages when
  `speckit_enabled: true` (i.e. merge speckit package entries into the rendered
  `apm.yml`). Ensure deduplication if the user also selected them in `apm_packages`.

**Checkpoint**: with `speckit_enabled: true`, `.specify/` directory is rendered;
with `speckit_enabled: false`, it is absent.

---

## Phase 4: Answer threading + standalone mode

- [ ] T010 Verify that `project_name` is threaded correctly from a base layer:
  in a two-layer init [base, apm], `apm.yml.jinja` renders with the correct
  `project_name` without the user re-answering it. Add an assertion to the test.
- [ ] T011 Verify standalone mode: applying `clerk-mod-apm` WITHOUT a base layer
  (no `project_name` threaded) falls back to a sensible default (e.g. the copier
  `default: "myproject"` or prompts the user). Add a standalone test.

**Checkpoint**: threading works; standalone works with defaults.

---

## Phase 5: Trust + reproduce hardening

- [ ] T012 Trust-refusal test: `tests/loop/test_apm_trust.py` — with an untrusted
  source that has `_tasks`, `init` refuses at exit 3 naming the `trust add` command,
  nothing is written.
- [ ] T013 [P] Reproduce test: `tests/loop/test_apm_reproduce.py` — from a
  generated project, `reproduce` re-renders `apm.yml` + `.specify/` byte-identically.
  Assert no clerk-specific order file in the project. Assert N=1 (apm only, no
  base) reproduces correctly through `reproduce_many`.
- [ ] T014 [P] Component-deselection test: `tests/loop/test_apm_render.py` — with
  `apm_packages=[]`, `apm.yml` is absent or empty-skeleton only. With
  `speckit_enabled: false`, `.specify/` is absent. Assert each conditional file
  correctly absent/present.

**Checkpoint**: trust refusal, reproduce byte-identity, and deselection all verified
hermetically.

---

## Phase 6: Ordering integration

- [ ] T015 Multi-template ordering test: `tests/loop/test_apm_ordering.py` — a
  selection of [base_stub, apm] where `clerk-mod-apm` declares `depends_on:
  [base_stub]`; assert `init_many` applies base before apm; assert `reproduce_many`
  recomputes the same order from committed state; assert `project_name` is threaded
  from base to apm.

**Checkpoint**: spec 003 ordering engine drives apm correctly; no special-casing.

---

## Phase 7: Skill + documentation

- [ ] T016 Extend `skills/clerk/SKILL.md`: add the agentic-module step — when to
  offer `clerk-mod-apm`, what the multiselect presents, trust consent walkthrough,
  handoff shape (reference `contracts/agentic-module.md`). Note the `apm.lock.yaml`
  variance documented in OQ-007-e resolution.
- [ ] T017 [P] Update `contracts/agentic-module.md`: fill all remaining [TBD]
  sections using the OQ resolution decisions from T001. Confirm the discovery
  contract table, rendered file inventory, and `_task` form are accurate.

**Checkpoint**: SKILL.md documents the full flow; contract is complete with no [TBD].

---

## Phase 8: Gate + closeout

- [ ] T018 Full gate: `uv run ruff check src/ tests/ scripts/ && uv run ruff format
  --check src/ tests/ scripts/ && uv run mypy && uv run pytest -q`. Confirm existing
  001/002/003/010 tests still pass (NO regression — this spec adds zero Python code).
  Confirm `clerk-mod-apm` fixture tests pass hermetically.
- [ ] T019 Update `.specify/memory/roadmap.md`: mark spec 007 `planned → implemented`
  with a completion note (template content, component categories shipped, OQ
  resolutions). Confirm 008/009 entries' dependency on 007 still read correctly.
- [ ] T020 Open the PR (title = user-facing changelog entry, no spec IDs; `##
  Spec Context` body per the hook); push via `dgit push`. Do NOT merge without the
  user's go-ahead.

---

## Dependencies & parallelism

- **Phase 0 (T001–T002)** is the gate; ALL other phases are blocked until T001 is
  complete (OQs resolved).
- **Phase 1 (T003–T004)** can start once T001 is done. T004 is parallelizable with T003.
- **Phases 2–3 (T005–T009)** depend on Phase 1 skeleton. T008–T009 are parallelizable
  with T005–T007 (different files, no Python dependency).
- **Phase 4 (T010–T011)** depends on Phases 2–3.
- **Phase 5 (T012–T014)** depends on Phase 2 (needs `_task`). T012–T014 are
  parallelizable with each other.
- **Phase 6 (T015)** depends on Phase 1 skeleton + spec 003 ordering being available.
  Can run in parallel with Phases 2–5 if using the skeleton fixture.
- **Phase 7 (T016–T017)** depends on Phases 2–6 being functionally correct.
- **Phase 8 (T018–T020)** is closeout; T019/T020 can run in parallel with T018 if
  tests pass.

---

## Definition of done (maps to spec Success Criteria)

- SC-001 — APM-wired project contains correct `apm.yml` and task-produced
  `apm.lock.yaml` (T006/T007/T018).
- SC-002 — Reproduce re-renders `apm.yml` byte-identically (T013).
- SC-003 — Component deselection leaves files absent (T014).
- SC-004 — Untrusted source refused at exit 3 before any write (T012).
- SC-005 — Multi-template [base, apm] applies base first; threads `project_name`
  (T010/T015).
- SC-006 — Standalone application (no base layer) works with defaults (T011).
