---
description: "Task list for bailiff multi-template — dependency ordering + threaded init, recomputed reproduce (spec 003)"
---

# Tasks: bailiff multi-template — dependency ordering + threaded init, recomputed reproduce

**Input**: Design documents from `specs/003-multi-template/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[contracts/ordering.md](./contracts/ordering.md),
[constitution](../../.specify/memory/constitution.md) v2.1.0

**Tests**: INCLUDED. Constitution VII makes per-step hardening (deterministic order,
recompute==init order, cycle/dangling/collision refusal, all-gaps preflight,
threaded answers, N=1 no-regression) part of this spec's definition-of-done.

**Organization**: grouped by user story (US1–US4 from spec.md).

## Design decisions this task list assumes (resolved; flagged for review)

- Answers-file name = `.copier-answers.<template-basename>.yml`; **basename collision
  among selected templates → refuse at init** (Q-003a).
- Dangling edge (selected template depends_on an unselected one) → **refuse**, name
  it (Q-003b).
- Tie-break = lexicographic by **repo-basename** — unique within a valid selection,
  stable across init vs reproduce (Q-003c).
- Reuse: `discovery.dependency_edges` (parser), `catalog.validate_selection`
  (selection), `runner.reproduce(dest, answers_file=…)` + `enumerate_answers_files`
  (the 010 per-layer loop). New glue = ONE module `src/bailiff/ordering.py`. Stdlib
  `graphlib` for topo-sort; no new dependency.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no incomplete-task dependency)
- Exact file paths included

---

## Phase 1: Setup + fixtures

- [ ] T001 Add `OrderingError(BailiffError)` to `src/bailiff/errors.py` (cycle / dangling edge / basename collision; message names the offending relation). Create `src/bailiff/ordering.py` skeleton (module docstring: the C-11 coordination glue — DAG build, validation, stable topo-sort, layer naming; pure functions, no copier import).
- [ ] T002 [P] Extend `tests/conftest.py` with multi-template local-git fixtures (reuse the existing template-repo builder + when:false-edge support): (a) A (no edges); (b) B with `depends_on: [A]`; (c) C, D edge-independent, writing DISJOINT paths; (d) a cycle pair (E depends_on F, F depends_on E); (e) a basename-collision pair (two repos whose basename is identical under different parents). Each ships the answers-file .jinja (reproducible). Return handles + a helper to assemble a selection/run-spec over them.

**Checkpoint**: `import bailiff.ordering` works; fixtures build; `mypy` clean on the skeleton.

---

## Phase 2: The ordering module (pure functions) — blocks the story phases

- [ ] T003 [US1] `ordering.build_dag(records)` — from each selected TemplateRecord's `discovery` edges (call discovery.discover per layer, or accept pre-discovered edges), normalize `depends_on`/`run_after` → (dep → self) and `run_before: Y` → (self → Y); build the node/edge graph keyed by the identity the contract specifies (repo-basename within a valid selection, which is also the tie-break key).
- [ ] T004 [US4] `ordering` validation: detect a **cycle** (raise OrderingError naming the cycle members); detect a **dangling edge** (edge target not among selected → raise naming the missing dependency); detect a **basename collision** among selected templates (raise naming the colliding basename). All BEFORE any sort/return.
- [ ] T005 [US1] `ordering.topo_sort(dag)` — topological order with a **stable tie-break: lexicographic by repo-basename** among constraint-free nodes (graphlib.TopologicalSorter fed ready-sets in tie-break order, or Kahn's with a sorted ready-queue). Deterministic + total.
- [ ] T006 [US1] `ordering.answers_file_name(record)` → `.copier-answers.<template-basename>.yml`; and a `layer_plan(records)` convenience returning ordered (record, answers_file) pairs (used by init + reproduce).
- [ ] T007 [P] [US1/US4] `tests/unit/test_ordering.py` (NEW): build_dag normalization incl. run_before→edge; topo_sort determinism (same input → same order) + stable tie-break (edge-independent nodes ordered by basename) + order-independence (shuffled input → same order); cycle → OrderingError naming it; dangling edge → OrderingError naming it; basename collision → OrderingError naming it.

**Checkpoint**: `uv run pytest tests/unit/test_ordering.py` green; ordering is pure, deterministic, and refuses bad graphs.

---

## Phase 3: US1 — multi-template init (ordered apply + threaded answers)

- [ ] T008 [US1] `runner.init_many(selection, dest, *, today, check)` — compute order via `ordering.layer_plan`; for each layer in order, `run_copy(source, dest, data=<accumulated answers + today>, vcs_ref=ref, answers_file=".copier-answers.<basename>.yml", defaults=True, overwrite=True, quiet=True, pretend=check)`; merge each layer's answers into the accumulating `data=` dict BEFORE the next layer (threading, ADR-0003); reuse the existing trust/reproducibility pre-checks per layer. Writes NO bailiff order file. Surface copier errors via the existing `_translate`.
- [ ] T009 [US1] `tests/loop/test_multi_init.py` (NEW): B depends_on A, selection given mis-ordered [B,A] → A applies before B (assert via a per-layer marker/task or answers-file presence order); each layer commits its own `.copier-answers.<name>.yml`; a threaded answer from A is visible as B's default; **order-independence** — init [C,D] and [D,C] into fresh dests → config-consistent trees (SC-003). Assert NO bailiff recipe/order file exists in dest (SC-002 partial).

**Checkpoint**: multi-template init applies in order, threads answers, commits per-layer files, order-independent for disjoint layers.

---

## Phase 4: US2 — recomputed reproduce (the headline guarantee)

- [ ] T010 [US2] `runner.reproduce_many(dest)` — `enumerate_answers_files(dest)`; for each, read recorded `_src_path`+`_commit`, re-discover the template at that pin to re-read edges; rebuild DAG + `ordering.topo_sort` (SAME tie-break) → recomputed order; drive `runner.reproduce(dest, answers_file=<file>)` per layer in that order. Uses ONLY committed files + pinned fetches; reads/requires NO recipe file. Fail loudly per-layer if a source is unreachable.
- [ ] T011 [US2] `tests/loop/test_multi_reproduce.py` (NEW): from a US1-generated project — reproduce recomputes order respecting edges; reproduce TWICE → config-consistent (SC-002); assert resolution used only committed answers files + fetches (no recipe/DAG file present in dest); **copier-only-by-hand parity** — plain `copier recopy --vcs-ref=:current: -a <each file>` in the recomputed order yields the same tree (spec-010 fallback, N layers); **N=1 no-regression** — a single-template project reproduces identically through reproduce_many as through the 010 single path.

**Checkpoint**: multi-template reproduce is deterministic, recomputed-from-committed-state, recipe-free, and matches the by-hand copier path; N=1 unaffected.

---

## Phase 5: US3 — all-gaps preflight

- [ ] T012 [US3] Ensure `init_many(..., check=True)` runs every layer with `pretend=True`, threading answers, and **collates** the missing/invalid answers across ALL layers into one report (rather than stopping at the first failing layer) — surface copier's `ValueError`/`copier.errors.*` per layer, aggregated. Writes nothing.
- [ ] T013 [P] [US3] `tests/loop/test_multi_preflight.py` (NEW): two layers each with a required question, run-spec missing one answer from EACH → `--check` reports BOTH missing answers in one pass, writes nothing (SC-005).

**Checkpoint**: `--check` on a multi-template selection reports all gaps at once.

---

## Phase 6: US4 — refusal tests (cycle / dangling / collision, end-to-end)

- [ ] T014 [P] [US4] `tests/loop/test_multi_refusal.py` (NEW): via the CLI/init_many — a cycle pair → refused before any write (dest untouched), message names the cycle; a selection where a layer depends_on an UNselected template → refused naming the missing dependency; a basename-collision selection → refused naming the basename. Assert nothing is written in every refusal case (SC-004).

**Checkpoint**: every bad-graph case fails loud and clean, pre-write.

---

## Phase 7: CLI surface + SKILL

- [ ] T015 Wire the multi-template surface into `scripts/bailiff.py`: extend `init`/`reproduce` (or add multi handling that N=1 folds into) so a selection / multi-answers-file project routes through `init_many`/`reproduce_many`, while a single template stays the N=1 case with NO behavior change (spec 010 uniform loop). Accept the multi run-spec shape (contracts/ordering.md). Reuse error→exit mapping (0/1/2/3; OrderingError → exit 1). Do NOT regress the existing single-template verbs.
- [ ] T016 [P] Extend `skills/bailiff/SKILL.md`: after catalog selection (spec 002), document the multi-template flow — validated selection + per-layer answers → bailiff orders + applies layers → recomputed reproduce. State that selection/answers are agent judgment; ordering/apply/reproduce are LLM-free. Note the copier-only-by-hand fallback for N layers. Reference specs/003-multi-template/contracts/ordering.md. Use `uv run scripts/bailiff.py …` form.

**Checkpoint**: `uv run pytest -q` green (hermetic); multi + single both work through the one surface; SKILL documents the flow.

---

## Phase 8: Gate + closeout

- [ ] T017 Full gate on the branch: `uv run ruff check src/ tests/ scripts/ && uv run ruff format --check src/ tests/ scripts/ && uv run mypy && uv run pytest -q`. Confirm existing 001/010/002 tests still pass (NO regression, esp. single-template init/reproduce and catalog). Run `-m network` if reachable, else note untested.
- [ ] T018 Update `.specify/memory/roadmap.md`: mark spec 003 `planned → implemented` with a completion note (ordering.py DAG + stable basename tie-break; init_many threads answers; reproduce_many recomputes from committed state, no recipe; all-gaps preflight; N=1 unchanged). Confirm 004/005/006 entries' dependency on 003 still read correctly.
- [ ] T019 Update `README.md`: brief `## Multi-template` note — select several templates, applied in dependency order, reproduced by recomputed order (no committed recipe). Then open the PR (title = user-facing changelog entry, no spec IDs; `## Spec Context` body per the hook); push via `dgit push`. Do NOT merge without the user's go-ahead.

---

## Dependencies & parallelism

- **Setup (T001–T002) blocks everything.**
- **Phase 2 ordering module (T003–T006)** is sequential (builds one module); its test
  T007 follows. Ordering blocks Phases 3–6 (they call it).
- **US1 init (T008–T009)** → **US2 reproduce (T010–T011)** are sequential in
  `runner.py` (reproduce_many reuses the layer plan + the init-produced project).
- **US3 (T012–T013)** builds on init_many's check path; **US4 (T014)** builds on
  init_many's refusals — both after Phase 3.
- **Phase 7 (T015–T016)** depends on the runner functions existing.
- **Phase 8 (T017–T019)** is closeout; T018/T019 docs can run parallel to late code.

## Definition of done (maps to spec Success Criteria)

- SC-001 — ordered apply + per-layer answers files + threaded answer (T008/T009).
- SC-002 — recomputed reproduce, twice-identical, no recipe file (T010/T011).
- SC-003 — order-independence for disjoint layers via stable tie-break (T005/T007/T009).
- SC-004 — cycle/dangling/collision refused pre-write, named (T004/T007/T014).
- SC-005 — all-gaps preflight in one --check pass (T012/T013).
- SC-006 — N=1 through the multi path == 010 single path, no regression (T011/T015/T017).
