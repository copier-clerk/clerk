# Feature Specification: clerk multi-template — dependency ordering + threaded init, recomputed reproduce

**Feature Branch**: `003-multi-template`

**Created**: 2026-07-10

**Status**: Draft

**Input**: Roadmap spec 003 (Multi-template enablement + dependency ordering),
governed by the constitution (II, III, VII) and ADR-0003. Consumes spec 002's
validated selection + the hidden `depends_on` edges `discovery.py` already parses,
and plugs its topological order into spec 010's uniform 1..N reproduce loop.

## Overview

Specs 001/010 proved and reshaped the single-template loop; spec 002 lets a user
select templates from their own catalog. Spec 003 is where clerk earns its
**coordination glue** (C-11, the one place the roadmap sanctions it): apply
**several** templates to one project in **correct dependency order**, threading
answers between them, and — at reproduce — **recompute** that order deterministically
from committed state, never a frozen recipe.

The ordering is a pure function clerk computes from declared edges; copier does
**zero** cross-template coordination (verified, ADR-0003). clerk issues **one
`copier copy` per template layer**, in topological order, each writing a distinct
committed answers file, threading each layer's answers into the next via copier's
`data=` dict (not `_external_data` — ADR-0003).

Crucially, **nothing clerk-authored is committed to encode the order** (the spec-010
invariant). At reproduce, clerk enumerates the committed `.copier-answers*.yml`
files, fetches each template at its recorded `_commit`, re-reads its `when:false`
edges, and **recomputes** the same topological order with a stable tie-break. Pinned
commits → identical edges → identical order, so reproduce is deterministic and
agent-free without any recipe/DAG file the user could forget to commit.

This spec builds the **ordering brain** and slots it into the existing 010 loop
(`runner.reproduce(dest, answers_file=…)` + `enumerate_answers_files`). It also
forward-delivers the **all-gaps preflight** (C-10): collate every question across
the selected templates and `--pretend`-dry-run so a user sees *all* missing answers
at once, not one failed layer at a time.

## Motivating decisions

1. **clerk orders; copier renders one layer at a time.** clerk reads the hidden
   `when:false` edges (`depends_on`/`run_after`/`run_before`) from each selected
   template's `copier.yml` (already parsed into `discovery.Discovery.dependency_edges`),
   builds a DAG, topo-sorts it, and issues one `copier copy` per layer in that order.
   No "ordering template", no user step — a pure function (ADR-0003).
2. **Deterministic order via a documented stable tie-break.** Mutually-independent
   layers (no edge between them) may run in any order; determinism comes from a
   **stable, documented tie-break** (lexicographic by full-id) so the order — and
   thus the byte output for edge-independent layers writing disjoint paths — is
   identical across runs and across init-vs-reproduce.
3. **Reproduce RECOMPUTES the order; nothing clerk-authored is committed** (spec 010
   / Constitution III). At reproduce clerk enumerates committed answers files,
   fetches each at its `_commit`, re-reads edges, re-topo-sorts (same tie-break), and
   drives one `runner.reproduce(dest, answers_file=…)` per layer in that order. No
   recipe/DAG file exists in the project.
4. **Each layer writes a distinct committed answers file.** clerk overrides copier's
   `answers_file=` per layer to `.copier-answers.<template-basename>.yml`. That name
   is the permanent reproduce key. If two *selected* templates share a repo basename,
   init **refuses loudly** (they cannot be layered under distinct files) — a rare
   case, caught before any write, never a silent overwrite. *(Resolves Q-010c; see
   Open Questions for the trade-off vs full-id-namespaced names.)*
5. **Answers thread forward via `data=`, not `_external_data`** (ADR-0003). clerk
   holds all prior layers' answers in memory and passes them into each subsequent
   `copier copy` as `data=`, so a later template can default from an earlier one's
   answer without any cross-file read. `_external_data` stays out of the core; it is
   only for standalone `copier update` runs done *without* clerk.
6. **Cycles and missing dependencies are refused before any write.** A dependency
   cycle, or an edge naming a template not in the selection, is a loud init-time
   error naming the offending edge — never a partial render.
7. **All-gaps preflight (C-10).** Before writing, clerk collates the questions across
   all selected templates and runs copier's `--pretend` per layer (threading answers)
   to surface *every* missing/invalid answer at once, rather than failing at layer N.
8. **Reproduce stays faithful; changed deps are an UPDATE concern (spec 006).**
   Reproduce resolves only from recorded pins and re-orders only from the committed
   layers' recorded edges — it never fetches latest or picks up a newly-added
   dependency. A dependency added to a newer template version is handled at `update`.

## User Scenarios & Testing

### US1 — Generate a project from several templates in dependency order (Priority: P1)

A developer selects multiple templates (e.g. a base + a language layer that
`depends_on` it); clerk applies them in the correct order, threading answers, into
one project.

**Why this priority**: this is the feature — multi-template composition.

**Independent Test**: with two local template fixtures where `B depends_on A`, run
multi-template init for `[B, A]` (deliberately mis-ordered in the selection); assert
A renders before B (observable via a task/marker or answers-file mtime ordering),
each writes its own `.copier-answers.<name>.yml`, and B can default a question from
A's threaded answer.

**Acceptance Scenarios**:
1. **Given** `B depends_on A`, **When** init `[B, A]`, **Then** A's layer applies
   first, B's second; both answers files are committed.
2. **Given** two edge-independent templates C and D writing disjoint paths, **When**
   init `[C, D]` and `[D, C]`, **Then** the rendered tree is byte-identical (order
   independence via the stable tie-break).

### US2 — Reproduce a multi-template project by recomputed order (Priority: P1)

A developer reproduces a multi-template project on a fresh machine; clerk recomputes
the order from committed state — no recipe file involved.

**Why this priority**: the headline determinism guarantee for multi-template.

**Independent Test**: take a project generated by US1; **delete any non-copier
metadata**; reproduce; assert (a) order respects the edges, (b) running reproduce
twice yields byte-identical output, (c) the resolution used only the committed
`.copier-answers*.yml` files + pinned template fetches (no recipe/DAG file exists in
the project), and (d) reproduce also works by hand with plain `copier recopy` per
answers file in the recomputed order (the copier-only fallback, US1 of spec 010).

**Acceptance Scenarios**:
1. **Given** a committed multi-template project, **When** `scripts/clerk.py
   reproduce`, **Then** clerk recomputes the order from the committed files + pinned
   fetches and drives one recopy per layer in that order.
2. **Given** the same project reproduced twice, **Then** the two outputs are
   byte-identical (deterministic recompute).

### US3 — All missing answers reported at once (Priority: P2)

A developer starts a multi-template init with incomplete answers; clerk reports
every missing/invalid answer across all layers in one pass, not one per failed run.

**Why this priority**: ergonomics for multi-template; avoids N round-trips.

**Independent Test**: select two templates each with a required question; provide a
run-spec missing one answer from each; run the multi-template `--check`; assert both
missing answers are reported together and nothing is written.

### US4 — Cycles and dangling edges are refused (Priority: P1)

**Independent Test**: (a) two templates with a `depends_on` cycle → init refuses with
a message naming the cycle, writes nothing; (b) a selected template whose
`depends_on` names a template not in the selection → init refuses naming the missing
dependency (or, per policy, auto-includes it — see Open Questions), writes nothing.

### Edge Cases

- **Single template via the multi path**: N=1 exercises the same code with a
  one-node DAG (spec 010's uniform-path guarantee — no special-casing).
- **Basename collision between two selected templates** (`acme/base` + `other/base`):
  init refuses loudly before writing (decision 4).
- **A layer is not reproducible** (no answers-file `.jinja`): refused at selection
  (spec 002's `unusable`) — it can never be a layer.
- **An edge names a template present in the catalog but not selected**: refuse naming
  it (or auto-include — Open Questions Q-003b).
- **Reproduce when a committed layer's source is unreachable**: fail loudly per-layer
  (reproduce/CI never silently skips a layer).
- **`run_before` vs `depends_on`/`run_after`**: normalized into edges of one
  direction before the sort (a `run_before: X` on A ⇒ edge A→X).

## Requirements

### Functional Requirements

- **FR-001**: clerk MUST build a dependency DAG from the selected templates' hidden
  `when:false` edges (`depends_on`/`run_after`/`run_before`), reusing
  `discovery.Discovery.dependency_edges` (no new parser). `run_before` MUST be
  normalized into the same edge direction as `depends_on`/`run_after`.
- **FR-002**: clerk MUST topologically sort the DAG and apply one `copier copy` per
  template layer in that order, with a **stable, documented tie-break**
  (lexicographic by full-id) for mutually-independent layers.
- **FR-003**: Each layer MUST be written to a **distinct committed answers file**
  (`.copier-answers.<template-basename>.yml`). A basename collision among *selected*
  templates MUST be refused at init before any write.
- **FR-004**: clerk MUST thread earlier layers' answers into later layers via
  copier's `data=` dict (NOT `_external_data`), so a later template can default from
  an earlier answer.
- **FR-005**: Reproduce MUST **recompute** the order at runtime from the committed
  `.copier-answers*.yml` files — fetching each template at its recorded `_commit`,
  re-reading edges, re-sorting with the same tie-break — and drive one
  `runner.reproduce(dest, answers_file=…)` per layer in that order. It MUST NOT read
  or require any frozen recipe/DAG file, and MUST NOT be committed one.
- **FR-006**: The recomputed reproduce MUST be deterministic (same committed state +
  pins → same order → byte-identical output for disjoint-writing layers) and
  agent-free. The plain-`copier recopy`-per-layer-by-hand path MUST reproduce the
  same result (the spec-010 copier-only guarantee extended to N layers).
- **FR-007**: A dependency **cycle**, or an edge naming a template **not in the
  selection**, MUST be refused before any write, with a message naming the offending
  edge/cycle.
- **FR-008**: clerk MUST provide an **all-gaps preflight**: collate questions across
  all selected layers and `--pretend`-dry-run (threading answers) to report every
  missing/invalid answer in one pass (C-10), writing nothing.
- **FR-009**: Reproduce MUST resolve only from recorded pins and MUST NOT reorder
  based on a dependency added in a newer template version; that is an `update`
  concern (spec 006).
- **FR-010**: The orchestrator MUST ship bundled with the skill (`scripts/clerk.py`
  + `src/clerk/`), invoked through the uniform surface — NOT as a separate CLI, and
  the mechanical order/apply/reproduce path MUST contain no LLM judgment (spec 010 /
  Constitution II).

### Key Entities

- **Layer**: one selected template applied as one `copier copy`; identified by its
  full-id, written to `.copier-answers.<basename>.yml`, carrying its `_src_path` +
  `_commit`.
- **Edge**: a `depends_on`/`run_after`/`run_before` relation between two selected
  templates, read statically from `copier.yml` (hidden `when:false` answer).
- **Order**: the topological sort of the layers (stable tie-break) — computed at
  init AND recomputed at reproduce; never persisted.
- **Threaded answers**: the accumulating `data=` dict passed layer-to-layer.

## Success Criteria

- **SC-001**: A project generated from ≥2 edge-linked templates applies them in
  correct dependency order; each layer commits its own answers file; a later layer
  can default from an earlier layer's answer.
- **SC-002**: Multi-template reproduce is byte-identical across repeated runs and
  order-correct, computed **solely** from committed answers files + pinned template
  fetches — no recipe/DAG file exists in the project.
- **SC-003**: Edge-independent layers writing disjoint paths produce byte-identical
  output regardless of selection order (stable tie-break).
- **SC-004**: A dependency cycle or dangling edge is refused before any write, naming
  the offending relation.
- **SC-005**: The all-gaps preflight reports every missing answer across all layers
  in one `--check` pass, writing nothing.
- **SC-006**: N=1 through the multi path behaves identically to spec 010's
  single-template loop (no special-casing, no regression).

## Out of scope

- The catalog + selection itself (spec 002 — consumed here).
- The agentic module's internal skills/mcp/bundles multiselect (spec 007) — that is
  *inside* one template, orthogonal to inter-template ordering.
- Global per-template defaults (004), secrets (005).
- `update`/upgrade + re-resolving newer-version dependencies (spec 006) — reproduce
  here stays pinned (FR-009).
- Any `Template`/`Worker` adapter (static edge parse already exists in `discovery.py`).

## Open Questions

- **Q-003a — Answers-file naming (RESOLVED, flag for review)**: chose
  `.copier-answers.<template-basename>.yml` (copier-native convention, clean
  committed names) with an **init-time refusal on basename collision** among selected
  templates. Alternative considered: `.copier-answers.<catalog>__<template>.yml`
  (full-id, never collides, but leaks the catalog name into committed filenames and
  is uglier). Revisit if basename collisions turn out common in real catalogs.
- **Q-003b — Dangling edge policy**: when a selected template `depends_on` a template
  in the catalog but NOT selected — **refuse** (name it, let the user add it) vs
  **auto-include** it into the selection. Lean: **refuse** for 003 (explicit,
  no surprise layers); auto-include is a later ergonomic nicety. Resolve at planning.
- **Q-003c — Tie-break key**: lexicographic by **full-id** vs by **repo-basename**.
  Lean: full-id (globally unique per spec 002, so the tie-break is always total).
  Resolve at planning.

## Governing constitution & ADRs

- Constitution II (two-phase; the order/apply/reproduce mechanics are LLM-free), III
  (faithful, agent-free, recomputed reproduce), VII (per-step hardening: determinism
  + cycle/gap refusal + tests for the ordering glue).
- ADR-0003 (clerk computes the DAG from hidden `when:false` edges; one `copier copy`
  per template; thread answers via `data=`, not `_external_data`; no ordering
  template), ADR-0002 (`_src_path` = the split per-template repo; answers carry
  state), ADR-0001 (copier is the engine).
- Constraints: C-07, C-10 (all-gaps preflight), C-11 (THIS is the sanctioned
  coordination glue). Delivery + recompute contract from spec 010.
