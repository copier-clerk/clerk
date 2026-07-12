# Implementation Plan: clerk multi-template — dependency ordering + threaded init, recomputed reproduce

**Branch**: `003-multi-template` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-multi-template/spec.md`

## Summary

Build clerk's **ordering brain** and slot it into the existing pieces: it consumes
spec 002's `catalog.validate_selection` (the selected `TemplateRecord`s) + the
`when:false` edges already in `discovery.Discovery.dependency_edges`, computes a
topological order, drives one `copier copy` per layer (threading answers via
`data=`), and — at reproduce — **recomputes** the same order from committed state and
drives spec 010's existing `runner.reproduce(dest, answers_file=…)` per layer. No
recipe/DAG file is ever committed (Constitution III / spec 010).

New glue — a single `src/clerk/ordering.py` module (the C-11-sanctioned coordination
code) — plus multi-layer entry points wired into `runner.py` and surfaced through
`scripts/clerk.py`. Everything mechanical stays LLM-free (Constitution II).

Resolved planning decisions (flagged for review in spec Open Questions):
- **Answers-file name** = `.copier-answers.<template-basename>.yml`; **basename
  collision among selected templates → refuse at init** (Q-003a).
- **Dangling edge** (selected template `depends_on` an unselected one) → **refuse**,
  naming it (Q-003b); auto-include deferred as a later nicety.
- **Tie-break** = lexicographic by **repo-basename** — unique within a valid
  selection (collision refused) and stable across init vs reproduce, which
  reconstruct full-ids differently (Q-003c).

## Technical Context

**Language/Version**: Python 3.11+ (`src/clerk/` + `scripts/clerk.py`).

**Primary Dependencies**: existing only — `copier>=9.16,<10`, `packaging`, `pyyaml`,
`platformdirs`, `tomli-w`. **No new dependency**: the topological sort is stdlib
(`graphlib.TopologicalSorter` is 3.9+; use it with a stable tie-break wrapper, or a
small hand-rolled Kahn's algorithm if a fully-controlled tie-break is cleaner —
decide in T-impl). No adapter (static edge parse already exists).

**Storage**: Files only. Each layer → its own committed `.copier-answers.<name>.yml`
(copier writes it; clerk sets `answers_file=`). NO clerk-authored order/recipe file
in the project. Reproduce reads only those committed files + re-fetched templates.

**Testing**: `pytest`, hermetic/offline via **local git template fixtures** with
declared `when:false` edges (extend `tests/conftest.py`: a small multi-template
fixture set — A, B `depends_on` A, plus two edge-independent C/D writing disjoint
paths, plus a cycle pair, plus a basename-collision pair). Multi-template init +
recomputed reproduce tested end-to-end + via subprocess through `scripts/clerk.py`.
One marked-`network` smoke optional. `mypy --strict` + `ruff` over `src/ tests/
scripts/`.

**Target Platform**: developer workstations + CI (macOS/Linux).

**Project Type**: skill + bundled script + copier templates. No published app.

**Performance**: none; correctness + determinism only. (Reproduce re-fetches each
layer's template to re-read edges — acceptable; freshness/fetch cost is inherent to
recompute-from-pins and is the deliberate trade for committing no recipe.)

**Constraints**: deterministic order (stable tie-break; init order == reproduce
order); recompute-not-freeze (no committed recipe/DAG — Constitution III); thread via
`data=` not `_external_data` (ADR-0003); refuse cycles/dangling-edges/basename-
collisions before any write; all-gaps `--pretend` preflight (C-10); orchestrator
bundled, LLM-free (spec 010 / II); N=1 uses the same path (spec 010 uniform loop).

**Scale/Scope**: the ordering module + multi-layer init/reproduce/check wiring +
preflight + SKILL update + tests. NO catalog/selection (002), NO update/upgrade
(006), NO apm internal multiselect (007).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution **v2.1.0**. Initial gate: **PASS**.

| Principle | Gate | How this plan satisfies it |
|---|---|---|
| I — Skills + templates + minimal glue | PASS | One new `ordering.py` module — THE sanctioned coordination glue (C-11: copier does zero cross-template coordination). Surfaced via existing `scripts/clerk.py`; no new tool, no template, no adapter. |
| II — Two-phase; agent judges, helpers execute | PASS | Order computation + apply + recompute-reproduce are pure/deterministic, LLM-free, subprocess-testable. The agent's only role is selection (spec 002) + answer collection; it is never in the ordering or reproduce path. |
| III — Faithful, agent-free, RECOMPUTED reproduce | PASS | Reproduce recomputes order from committed answers + pinned fetches (stable tie-break); no recipe/DAG file committed; `run_recopy(vcs_ref=CURRENT)` per layer via the existing 010 loop; never bare recopy; changed deps deferred to update (FR-009). |
| IV — Prefer CLI + static config; adapter only if used | PASS | Edges read from the existing static `discovery.dependency_edges` (no Jinja env, no Template/Worker). copier driven via public `run_copy`/`run_recopy`. No adapter. |
| V — Determinism via pinning; trust by source | PASS | Order determinism from pins + stable tie-break. Trust unchanged: each layer's `copier copy` trust-gates via settings.yml; clerk writes no trust. A layer needing tasks surfaces the existing UntrustedSourceError. |
| VI — Template-author contract at discovery | PASS | A non-reproducible template can't be a layer (refused at selection, spec 002). Edges are the VI-mandated `when:false` hidden answers, statically read. |
| VII — Hardening per-step (scaled) | PASS | DoD = deterministic-order test (init==reproduce, order-independence for disjoint layers) + cycle/dangling/collision refusal tests + all-gaps preflight test + threaded-answer test + N=1-no-regression. Unit tests for `ordering.py`. No adapter → no drift test. |
| VIII — Documented, dry-run-validated handoff | PASS | The multi-template run-spec is a documented extension of the 001 run-spec (a selection list + per-layer answers); validation reuses copier `--pretend` (the preflight). No pydantic/JSON-Schema. |

**Complexity deviations**: none. `ordering.py` is the coordination code the roadmap
explicitly reserved for 003 (C-11 / Q4) — justified by a real copier gap (no
cross-template ordering), introduced now with evidence (two real specs, 002 + 010,
depend on it), not speculatively. No new dependency; stdlib `graphlib`.

Post-design re-check (after Phase 1): **PASS** — the seam is the existing Discovery
edges + copier's public multi-answers-file mechanism; no deprecated surface, and the
reproduce path reuses 010's `runner.reproduce`.

## Project Structure

### Documentation (this feature)

```text
specs/003-multi-template/
├── spec.md              # The multi-template spec
├── plan.md              # This file
├── contracts/
│   └── ordering.md      # Phase 1 — run-spec (multi) shape, answers-file naming, order algorithm + tie-break, recompute contract, exit codes
└── tasks.md             # Phase 2 (/speckit.tasks)
```

Phase-0 research is not re-generated: the load-bearing copier facts (one `run_copy`
per template, `data=` threading, `answers_file=` per layer, `run_recopy` VcsRef
semantics, static edge parse) are verified in ADR-0003 and already exercised by the
001/010/002 code. No data-model doc — the entities are in the spec + contract.

### Source Code (repository root)

```text
src/clerk/
├── ordering.py          # NEW: the coordination glue. build_dag(records) from Discovery edges
│                        #   (depends_on/run_after/run_before → normalized edges); detect cycles +
│                        #   dangling edges (raise OrderingError); topo_sort with stable full-id
│                        #   tie-break; answers_file name per layer (.copier-answers.<basename>.yml)
│                        #   + basename-collision refusal.
├── runner.py            # EXTEND: init_many(selection, answers, dest, check) — order via ordering,
│                        #   loop copier copy per layer threading `data=`, distinct answers_file;
│                        #   reproduce_many(dest) — enumerate committed answers files, recompute order
│                        #   (re-discover each at its _commit, rebuild+sort DAG), loop existing
│                        #   reproduce(dest, answers_file=…) per layer. Reuse enumerate_answers_files.
├── discovery.py         # REUSED unchanged — dependency_edges already parsed.
├── catalog.py           # REUSED unchanged — validate_selection yields the selected TemplateRecords.
└── errors.py            # EXTEND: OrderingError(ClerkError) — cycle / dangling edge / basename collision.

scripts/clerk.py         # EXTEND: multi-template surface. Either extend `init`/`reproduce` to accept
                         #   a selection (≥1 full-id / multi-answers-file project) so N=1 and N>1 use
                         #   ONE path (spec 010 uniform-loop principle), or add explicit multi handling
                         #   that N=1 folds into — a task decides, but the N=1 path MUST NOT regress.

skills/clerk/SKILL.md    # EXTEND: after catalog selection (spec 002), document the multi-template
                         #   flow — validated selection → clerk orders + applies layers → recomputed
                         #   reproduce. Selection/answers are agent judgment; ordering/apply/reproduce
                         #   are LLM-free. Point at specs/003-multi-template/contracts/ordering.md.

tests/
├── conftest.py          # EXTEND: multi-template fixtures — A; B depends_on A; C,D edge-independent
│                        #   disjoint-writers; a cycle pair; a basename-collision pair. All local git.
├── unit/
│   └── test_ordering.py # NEW: build_dag + normalization (run_before→edge); topo_sort determinism +
│                        #   stable tie-break; cycle detection; dangling-edge detection; collision refusal.
└── loop/
    ├── test_multi_init.py       # NEW: US1 — ordered apply, threaded answers, per-layer answers files,
    │                            #   order-independence for disjoint layers (byte-identical both orders).
    ├── test_multi_reproduce.py  # NEW: US2 — recompute from committed state, twice-identical, no recipe
    │                            #   file present, copier-only-by-hand parity; N=1 no-regression.
    ├── test_multi_preflight.py  # NEW: US3 — all-gaps --check reports every missing answer, writes nothing.
    └── test_multi_refusal.py    # NEW: US4 — cycle + dangling-edge + basename-collision refused pre-write.
```

**Structure Decision**: One new `src/clerk/ordering.py` (pure functions: DAG build,
validation, topo-sort, layer naming), consumed by new `runner.init_many` /
`runner.reproduce_many`, surfaced through `scripts/clerk.py`. Reuses
`discovery`/`catalog`/`runner.reproduce` verbatim. The single-template path (spec
010) stays the N=1 case of the multi path — no special-casing, no regression.

## Complexity Tracking

No constitutional violations. One new module + extensions to `runner.py`/`scripts`,
all tied to the one copier gap the roadmap reserved for 003 (cross-template
ordering, C-11/Q4) — introduced now with concrete consumers (002 selection + 010
loop), not speculatively. No new dependency (stdlib `graphlib`). Three flagged
planning decisions (answers-file naming, dangling-edge policy, tie-break key) are
resolved above with defaults + rationale; each is a small, reversible change if the
reviewer prefers the alternative.
