---
description: "Task list — spec 015: agent-projected capability contract (_agent_tasks/_post_agent_tasks, .hooks.d/, lefthook, agentic editorconfig)"
---

# Tasks: Agent-projected capability contract (spec 015)

**Input**: `specs/015-agent-projected-capabilities/` — spec.md (FR-001..018, SC-001..007),
plan.md, contracts/ (`agent-tasks.md`, `hooks-neutral-dir.md`).

**Prerequisites**: on branch `015-agent-projected-capabilities`, rebased onto `origin/main`
(carries the 014 engine + the 0.3.1 fixes: `_finalize_initial_commit`, `resolve_locator`,
`_canonical_dest`). spec + plan + contracts RATIFIED.

**Tests**: SC-001..007 name specific behaviors; test tasks are INCLUDED and written to FAIL
before the engine change lands (engine gate). The agent is a STUB in tests (deterministic,
no LLM) per `agent-tasks.md` §3.

**Organization**: Phase 2 (engine + agent seam) is the blocking gate. After it freezes,
the hook-capability slice (US1/US2) and editorconfig slice (US5) fan out. Phase order =
plan.md sequencing: Engine → Neutral hooks + lefthook → editorconfig → docs → validate.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no incomplete-task dependency)
- **[Story]**: US1..US5 or none (Setup/Foundational/Polish)
- Engine: `src/bailiff/{discovery,runner}.py` + new `src/bailiff/agent.py`;
  tests `tests/loop/`, `tests/integration/`, `tests/unit/`.
- Modules: `templates/bailiff-mod-<name>/`.

---

## Phase 1: Setup

- [ ] T001 Confirm branch rebased on `origin/main`; run full non-network baseline DETACHED
  (`nohup uv run pytest tests/ -q -m "not network" > /tmp/015-baseline.log 2>&1 &`); record pass count.
- [ ] T002 `uv run python scripts/check_modules.py` → record the module-count baseline.
- [ ] T003 [P] Read the timeline seam in `runner.init_many`/`init` (render loop, `_run_post_tasks`,
  `_write_schema_marker`, `_finalize_initial_commit`) and note exact insertion points (no code change).

## Phase 2: Engine + agent seam (BLOCKING GATE) — FR-001..012

- [ ] T004 [P] discovery: parse `_agent_tasks`/`_post_agent_tasks` into the `Discovery` record
  (`agent_tasks`, `post_agent_tasks` dicts); validate keys are a subset of `{pre,post}`, else raise
  a legible DiscoveryError naming module+field+key (FR-004). Include in `has_tasks` (FR-005).
  `src/bailiff/discovery.py`.
- [ ] T005 [P] Tests (FAIL-first): `tests/unit/test_discover.py` — valid pre/post parse; a
  non-pre/post key fails loud; presence surfaces in `to_dict()` (SC-006).
- [ ] T006 New `src/bailiff/agent.py`: the agent seam — `AgentContext`, `AgentResult`, the
  `AgentTask` callable type, and a default no-op binding. Deterministic; imports no LLM.
- [ ] T007 runner: thread an injected `agent` callable through `init`/`init_many` (default from
  `agent.py`); invoke `_agent_tasks.pre/post` inside the render loop and
  `_post_agent_tasks.pre/post` around `_run_post_tasks`, in module sort order (FR-006/007).
  `src/bailiff/runner.py`.
- [ ] T008 runner: freeze — after each agent task, write its `AgentResult` to the producing
  module's answers file as `_agent_frozen.<slot>` (append-only, like `_write_schema_marker`);
  verify round-trip survives copier's answers-file serialization (FR-009). `src/bailiff/runner.py`.
- [ ] T009 runner: replay — on `reproduce_many`, detect `_agent_frozen` and write the recorded
  `{path: content}` INSTEAD of invoking the agent; SKIP all pre/post agent tasks (FR-010/011).
- [ ] T010 runner: reproduce-safety lint — after freezing at init, fail loud if a managed-rendered
  path was written by an agent task but not captured (FR-012); set check
  `(managed ∩ agent_written) ⊆ frozen`. `src/bailiff/runner.py`.
- [ ] T011 Tests (FAIL-first) `tests/loop/test_agent_tasks.py`: stub agent appends a per-slot
  marker → assert timeline order (render→pre→_tasks→post; post-loop pre→_post_tasks→post) and
  module sort order.
- [ ] T012 Tests `tests/loop/test_agent_freeze.py`: init with stub captures `_agent_frozen`;
  reproduce with a RAISING stub (agent must never be called) → byte-consistent tree (SC-003).
- [ ] T013 Tests `tests/loop/test_agent_lint.py`: a module whose agent task writes a
  managed-rendered path without a freeze → init fails naming the path (SC-004).
- [ ] T014 GATE: run Phase-2 tests; engine green before any module work. Commit the engine slice.

## Phase 3: Neutral hooks + `bailiff-mod-lefthook` (US1/US2) — FR-013..015

- [ ] T015 [P][US1] Define `.hooks.d/<module>.yaml` neutral schema in a rendered fragment for
  `bailiff-mod-python` (`hooks: [{id,entry,language,files,stages}]`), rendered unconditionally.
  `templates/bailiff-mod-python/template/.hooks.d/bailiff-mod-python.yaml.jinja`.
- [ ] T016 [US1] NEW module `bailiff-mod-lefthook`: `copier.yml` (`_bailiff_phase: normal`,
  `depends_on: [bailiff-mod-base]`, answers-file template, no secret questions) +
  `_post_agent_tasks.post` projecting `.hooks.d/*` → `lefthook.yml`. Register via
  `scripts/_meta_register.py`; `just new-module` conventions.
- [ ] T017 [US1] `bailiff-mod-precommit`: add `_post_agent_tasks.pre` projecting `.hooks.d/*`
  into a `.pre-commit.d/` fragment BEFORE the bundler `_post_task` (fragment shape per
  `hooks-neutral-dir.md` §3). `templates/bailiff-mod-precommit/copier.yml`.
- [ ] T018 [US1] Integration `tests/integration/test_stack_lefthook.py`: `[base+python+lefthook]`
  → `lefthook.yml` carries the ruff hook, no `.pre-commit-config.yaml`; reproduce agent-free (SC-001).
- [ ] T019 [P][US2] Integration assertion: `[base+python]` (no manager) → no hook config file;
  `.hooks.d/` present + inert (SC-002). Add to `tests/integration/test_stack_python_service.py`
  or a focused test.
- [ ] T020 [US1] Integration: `[base+python+precommit]` → ruff in `.pre-commit-config.yaml` exactly
  once (native + projected dedup); pre-commit validate-config passes.

## Phase 4: Agentic `bailiff-mod-editorconfig` (US5) — FR-016

- [ ] T021 [US5] `bailiff-mod-editorconfig`: drop the per-language linter questions; add
  `_agent_tasks` (or `_post_agent_tasks`) that writes `.editorconfig` language sections from the
  selected language modules; freeze for reproduce. Keep a standalone universal-defaults fallback
  when no language module is present (confirm scope — plan.md open Q3).
  `templates/bailiff-mod-editorconfig/`.
- [ ] T022 [US5] Loop test `tests/loop/test_editorconfig_loop.py`: two language modules →
  per-language `.editorconfig` sections; reproduce agent-free (SC-005). Update any 014 editorconfig
  test that asserted the dropped questions.

## Phase 5: Docs (FR-017/018) + validation

- [ ] T023 [P] SKILL.md: document the phase-1 agent-projection procedure — how the agent redoes the
  projection from the actual SELECTION for every capability. `skills/bailiff/SKILL.md`.
- [ ] T024 [P] `_meta/module-template/` + `specs/011-.../contracts/_cross-cutting.md` §9: replace the
  015 forward-pointer with the canonical `_agent_tasks` authoring pattern (FR-017).
- [ ] T025 `scripts/check_modules.py`: validate the new manifest fields across all modules
  (pre/post keys only); no regression to the 014 gates. Regen `catalog.json`.
- [ ] T026 Full non-network suite DETACHED; confirm 0 failures + the new SC tests pass. Fast gates:
  `check_modules` ok, `bailiff doctor` Ready.

## Phase 6: Release sequencing

- [ ] T027 Rebase onto `origin/main` (pick up any drift); open PR; on green CI merge (fires the
  armed fan-out + release-please). Verify the new/changed module mirrors + a minor PyPI bump.

## Dependencies

- T004–T005 (discovery) before T007 (runner uses parsed fields).
- T006 (agent seam) before T007–T010.
- T014 GATE before Phase 3/4 (modules depend on the engine).
- T015 before T017/T018 (projection needs a `.hooks.d/` producer).
- T016 before T018; T017 before T020.
- Phase 5 after the behavior lands; T025 after all module edits.

<!-- re-fire fan-out after pre-creating bailiff-mod-lefthook mirror (spec 015) -->
