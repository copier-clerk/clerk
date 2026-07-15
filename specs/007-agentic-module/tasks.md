---
description: "Task list for bailiff agentic-ecosystem module — bailiff-mod-apm (spec 007)"
---

# Tasks: bailiff agentic-ecosystem module — `bailiff-mod-apm` (spec 007)

**Input**: Design documents from `specs/007-agentic-module/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md) (Clarified 2026-07-13),
[contracts/agentic-module.md](./contracts/agentic-module.md),
[constitution](../../.specify/memory/constitution.md) v2.1.0

**Scope (clarified, Q1)**: v1 ships `bailiff-mod-apm` ONLY. MCP / SpecKit / steering-ADR
are deferred to their own future `bailiff-mod-*` modules and are NOT part of this task
list. Tests are included (Constitution VII makes per-step hardening mandatory).

**Delivery**: pure template + task content (no `src/bailiff/` code, no new
`scripts/bailiff.py` verb). Authored via the spec-008b tooling (`just new-module`,
`scripts/check_modules.py`), driven by the existing spec-003/010 engine.

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no incomplete-task dependency)
- **[Story]**: US1 (generate) or US2 (reproduce); unlabelled = setup/foundational/polish
- Concrete file paths included in each task

---

## Phase 1: Setup (prerequisites + scaffold)

**Purpose**: get the authoring tooling in place and lay down a contract-complete stub.

- [x] T001 Confirm the spec-008b authoring tooling is present on the implementation
  branch (rebase onto `main` if needed): `_meta/module-template/`, `just new-module`,
  `scripts/check_modules.py`, `scripts/_meta_register.py`, `cog.toml`,
  `catalog-sources.toml`. If absent, 007 implementation is BLOCKED on that merge
  (spec 008b / PR #22). Record the resolved state.
- [x] T002 [P] Verify the APM CLI install interface and record it in
  `specs/007-agentic-module/contracts/agentic-module.md`: the exact pinned command
  (`uv run apm==X.Y.Z <verb>`), whether it reads `apm.yml` and writes `apm.lock.yaml`,
  and the `apm.yml` **catalogue/registry-source** key (Residual Open Item #1/#2 in
  plan.md). Supply a sensible default catalogue source. If APM has no CLI install
  command, record the correct equivalent and adjust T007 accordingly.
- [x] T003 Scaffold the module: `just new-module name=bailiff-mod-apm`. Confirm it
  creates `templates/bailiff-mod-apm/` with `copier.yml`,
  `{{ _copier_conf.answers_file }}.jinja`, `README.md`, `CHANGELOG.md`, and the
  registration edits in `cog.toml [monorepo.packages.bailiff-mod-apm]` +
  `catalog-sources.toml`. Run `just check-modules` — the fresh stub MUST pass.

**Checkpoint**: `templates/bailiff-mod-apm/` exists, is registered three ways, and
passes `check_modules.py` as an empty stub.

---

## Phase 2: Foundational (template contract + threading)

**Purpose**: the copier.yml shell every user story depends on — questions, the
dependency edge, and answer threading — before any rendered content or tasks.

**⚠️ Blocks US1 and US2.**

- [x] T004 Author the `apm_packages` question in
  `templates/bailiff-mod-apm/copier.yml` as a **runtime-injected list-typed answer**
  (ADR-0003 / Q2 / FR-002): `default: []`, populated by the agent via
  `--data apm_packages=[…]`; NO frozen `choices:` list; persists to the answers file.
  DEVIATION from the literal `type: str`/`multiselect: true` wording: used
  `type: yaml` (the proven injected-list convention in `bailiff-mod-base`). Verified
  empirically — copier passes a `data=` list straight through to a `type: yaml`
  question, whereas `multiselect: true` WITHOUT a frozen `choices:` list does NOT
  accept injected values (the validator/render sees an empty list). `type: yaml`
  is the only shape that satisfies FR-002's runtime-injection requirement here.
- [x] T005 [P] Author the threaded `project_name` question in `copier.yml` with
  `default: "{{ project_name }}"` (ADR-0003 threading via `data=`) and a standalone
  fallback default (FR-006, SC-006). Author the `apm_cli_version` question (pinned
  APM tool version, `default:` the version confirmed in T002) used by the install
  `_task` (FR-009). Author `today` as an injected answer (VI/C-05), mirroring
  `examples/bailiff-template-example/copier.yml`.
- [x] T006 [P] Declare the dependency edge in `copier.yml` as a `when:false` hidden
  answer `depends_on` with `default: []` (Q5 / FR-005): 007 does NOT hardcode a base
  layer; ordering is computed at reproduce time by the spec-003 engine from edges.
  Confirm `uv run scripts/bailiff.py discover templates/bailiff-mod-apm` returns
  `reproducible: true`, `has_tasks: true` (after T007), and the `apm_packages` question.

**Checkpoint**: discovery reports the correct shape; `project_name` threads;
`check_modules.py` still passes.

---

## Phase 3: User Story 1 — Generate a project with APM wiring (Priority: P1) 🎯 MVP

**Goal**: selecting `bailiff-mod-apm` with an injected package set produces a valid
`apm.yml` (packages + ≥ 1 catalogue) and runs the trust-gated pinned install task;
an empty set is refused; an untrusted source is refused at exit 3.

**Independent Test**: `copier`/`bailiff init` a `[stub_base, bailiff-mod-apm]` selection
with `--data apm_packages=[…]` on a trusted source → `apm.yml` present and correct;
repeat with `apm_packages=[]` → refusal; repeat untrusted → exit 3.

### Implementation for US1

- [x] T007 [US1] Add the **trust-gated APM install `_task`** to
  `templates/bailiff-mod-apm/copier.yml` (FR-004, FR-009, Q3): a portable shell command
  using the pinned form from T002 (`uv run apm=={{ apm_cli_version }} <verb>`), guarded
  by `when: "{{ apm_packages | length > 0 }}"`, idempotent at reproduce. Document that
  it writes `apm.lock.yaml` as external state.
- [x] T008 [US1] Author `templates/bailiff-mod-apm/apm.yml.jinja` (FR-003): render
  `dependencies.apm[]` from the injected `apm_packages`, plus **≥ 1 catalogue/registry
  source** (Q2 / FR-002a) — supply the default from T002 when the injected data yields
  none. Mirror the schema of the repo's own `/apm.yml`
  (`name`/`version`/`description`/`target`/`dependencies.apm[]`), using threaded
  `{{ project_name }}`.
- [x] T009 [US1] Implement the **empty-set refusal** (Q4 / FR-002b): a template-side
  guard so a reached-with-zero-packages render fails loudly with a message directing
  the user to drop the module — NOT an empty `apm.yml`. Use copier's validator/`when`
  mechanism (e.g. an `apm_packages` validator that rejects an empty list, or a guard
  question); confirm no `apm.yml` is written on refusal.
- [x] T010 [P] [US1] Add the `bailiff-mod-apm` fixture + minimal **stub base layer** to
  `tests/conftest.py` (FR-007), reusing the `build_template_repo` / `multi_template_set`
  pattern. The stub base provides the threaded `project_name`; the install `_task` is
  stubbed to a deterministic offline no-op (writes a marker, no network) so the suite
  stays hermetic.
- [x] T011 [P] [US1] `tests/loop/test_apm_render.py` (US1 acceptance #1, SC-001, SC-006,
  Q2, Q4): render `[stub_base, bailiff-mod-apm]` with an injected `apm_packages` set →
  assert `apm.yml` has the right `dependencies.apm[]` and ≥ 1 catalogue; render
  standalone (no base) → defaults hold; render with `apm_packages=[]` → refusal, no
  `apm.yml` written.
- [x] T012 [P] [US1] `tests/loop/test_apm_trust.py` (US1 acceptance #2, SC-004): an
  untrusted source with `_tasks` refuses at exit 3 naming `trust add`, before any write.

**Checkpoint**: US1 fully functional and independently testable — correct `apm.yml`,
empty-set refusal, trust refusal.

---

## Phase 4: User Story 2 — Reproduce a project with APM wiring (Priority: P1)

**Goal**: reproduce re-renders `apm.yml` byte-identically from committed answers +
pinned commit; the install `_task` re-runs under trust; `apm.lock.yaml` is treated as
external state (NOT asserted byte-identical).

**Independent Test**: generate an APM-wired project, then `reproduce` it → `apm.yml`
byte-identical; assert the lock is regenerated by the task, not diffed.

### Implementation for US2

- [x] T013 [US2] `tests/loop/test_apm_reproduce.py` (US2 acceptance #1/#2, SC-002, Q3):
  from a generated `bailiff-mod-apm` project, `reproduce` re-renders `apm.yml`
  byte-identically (same recorded `apm_packages` + pinned `_commit`). Assert the
  install `_task` re-runs under trust and that `apm.lock.yaml` is regenerated as
  external state — explicitly do NOT assert lock byte-identity. Cover N=1 (apm only)
  and the multi-layer case through `reproduce_many`.
- [x] T014 [P] [US2] `tests/loop/test_apm_ordering.py` (SC-005, Q5): a
  `[stub_base, bailiff-mod-apm]` selection where the edge (if declared) sequences base
  first; assert `init_many` order, `reproduce_many` recomputes the same order from
  committed state, and `project_name` threads from base into the rendered `apm.yml`.
  Confirm no bailiff-specific recipe file is committed to the project (spec-010 invariant).

**Checkpoint**: reproduce byte-identity for `apm.yml`, lock-as-external-state, and
ordering/threading all verified hermetically.

---

## Phase 5: Documentation, contract reconciliation, and gate

**Purpose**: make the flow discoverable and prove the module is contract-clean.

- [x] T015 [P] Extend `skills/bailiff/SKILL.md` (FR-010): add the `bailiff-mod-apm` step —
  when to include it; that the AGENT builds the runtime-injected `apm_packages` list
  from user input + project requirements and the user MAY override; the ≥ 1-package
  precondition and empty-set refusal (Q4); trust consent for the install `_task`; the
  `apm.lock.yaml` external-state note (Q3); and the run-spec handoff shape (reference
  `contracts/agentic-module.md`).
- [x] T016 [P] Finalize `specs/007-agentic-module/contracts/agentic-module.md`: ensure
  it matches the APM-only scope + the verified APM command/catalogue key from T002
  (no residual MCP/SpecKit/steering content, no `[TBD]` in the questions / rendered-
  file / `_task` sections).
- [x] T017 `just check-modules` on the finished `templates/bailiff-mod-apm/`: passes all
  contract checks (answers-file `.jinja`, README, CHANGELOG, three-way registration
  parity, published-label immutability). Update `CHANGELOG.md` for the module.
- [x] T018 Full gate: `uv run ruff check . && uv run ruff format --check . &&
  uv run mypy && uv run pytest -q`. Confirm existing 001/002/003/006/008 suites still
  pass (007 adds zero Python glue) and the new `test_apm_*` fixtures pass hermetically.
- [x] T019 Update `.specify/memory/roadmap.md`: mark spec 007 `planned → implemented`
  with a completion note (bailiff-mod-apm; APM-only v1; Q1–Q5 resolutions; MCP/SpecKit/
  steering deferred to future modules). Confirm 008/009 dependency wording still reads
  correctly (007 independent of 009, Q5).

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (T001–T003)**: T001 is the prerequisite gate (008b tooling present). T002
  is parallelizable with T001. T003 depends on T001.
- **Phase 2 (T004–T006)**: depends on T003 (stub exists). T005/T006 parallelizable with
  T004 (different concerns in the same file — coordinate edits if working concurrently).
- **Phase 3 / US1 (T007–T012)**: depends on Phase 2. T007→T008→T009 touch the same
  template files (sequential); T010 is parallelizable; T011/T012 depend on T007–T010.
- **Phase 4 / US2 (T013–T014)**: depends on US1 (needs a generatable project + fixture).
  T014 parallelizable with T013.
- **Phase 5 (T015–T019)**: T015/T016 parallelizable and can start once the contract is
  stable (after Phase 3). T017 depends on the finished template (Phase 3). T018 depends
  on all tests (Phases 3–4). T019 is closeout after T018.

### Parallel opportunities

- T001 ∥ T002.
- Within US1: T010 ∥ T007-line; T011 ∥ T012 (different test files) once deps are met.
- T014 ∥ T013.
- T015 ∥ T016.

---

## Definition of done (maps to spec Success Criteria)

- SC-001 — APM-wired project has a correct `apm.yml` (deps + ≥ 1 catalogue); install
  task produces `apm.lock.yaml` on a trusted source (T007/T008/T011).
- SC-002 — Reproduce re-renders `apm.yml` byte-identically; lock is external state, not
  asserted byte-identical; task pins the APM version (T013).
- SC-003 — (Component deselection) reduced to the empty-set refusal in v1 (Q1/Q4):
  zero packages → refusal, no `apm.yml` (T009/T011).
- SC-004 — Untrusted source refused at exit 3 before any write (T012).
- SC-005 — Multi-layer `[stub_base, apm]` orders base first and threads `project_name`
  (T014).
- SC-006 — Standalone application (no base layer) renders with defaults (T011).
- Contract: `bailiff-mod-apm` passes `check_modules.py` (T017); SKILL.md documents the
  step (T015).

---

## Notes

- [P] = different files, no incomplete-task dependency.
- No `src/bailiff/` or `scripts/bailiff.py` changes — pure template + task content
  (Principle I / C-11). Any discovered copier gap must be justified against C-11 first.
- MCP, SpecKit-bridge, and steering/ADR are OUT of v1 (Q1) — do not add their questions,
  files, or tasks here; each is a future `bailiff-mod-*` spec.
- The stale US3/US4 scenarios and the "MCP config skeleton" phrase in `spec.md` predate
  the clarification; the Clarifications section governs. Prune them in a separate
  spec-refine pass (not part of these tasks).
