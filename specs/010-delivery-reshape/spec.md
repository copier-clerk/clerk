# Feature Specification: bailiff delivery reshape — skill-bundled copier wrapper

**Feature Branch**: `010-delivery-reshape`

**Created**: 2026-07-10

**Status**: Draft

**Input**: Session decisions after spec 001 verification (2026-07-10). Governed by
the constitution (Principles I, II, V, VIII) and ADRs 0001/0002/0003/0006.
Supersedes the transitional CLI/justfile delivery shape that slice 001 shipped to
prove the loop.

## Overview

Spec 001 proved the conduct→copier→reproduce loop, but did so with a **transitional
delivery shape** that drifted from the ratified constitution: a `bailiff` console
script (`[project.scripts]`) and a generated per-project `justfile` calling
`bailiff reproduce`. Both make a *tool* the durable artifact and make generated
projects depend on bailiff (and on `just`) to reproduce. Constitution I / C-01 say
the opposite: bailiff is **skills + templates + minimal glue, NOT a published
application**.

This spec reshapes the delivery so bailiff is a **pure copier wrapper bundled inside a
portable skill**, with **zero bailiff-specific artifact committed into a generated
project**. It changes *how the deterministic layer is packaged and invoked* — not
what it does. The `discover`/`trust`/`init`/`reproduce`/`check` logic and its 35
tests from 001 survive nearly intact; this is re-packaging, not a rewrite.

The deterministic layer ships as **one bundled orchestration script**,
`scripts/bailiff.py`, run via `./scripts/bailiff.py …` or `uv run scripts/bailiff.py …`
(a shebang'd, dependency-light Python script — NOT a `[project.scripts] bailiff`
console entry, NOT a PyPI package). It drives the **full lifecycle** — `discover`,
`trust`, `init`, `reproduce` — through **one uniform path for 1..N templates**.
**A single-template project is simply the N=1 case; there is no separate
single-template code path and no command that is meaningful only for multiple
templates.** `reproduce` enumerates the committed `.copier-answers*.yml` file(s)
and issues `copier recopy --vcs-ref=:current:` per layer; at N=1 that is one file
→ one `recopy`. (The dependency topo-sort that orders N>1 layers is spec 003; this
spec builds the uniform loop it plugs into and fixes the reproduce-time recompute
contract.) A single cohesive entrypoint is preferred over a scatter of bundled
one-liners: one argparse surface, one place to translate copier's errors, one
unit-testable seam, without reading as an installable application.

Because `bailiff.py reproduce` only issues plain `copier recopy` commands, the
copier-only guarantee is preserved for free: a human on a machine with copier but
no bailiff can run the exact `copier recopy --vcs-ref=:current: --defaults
--overwrite` per answers file by hand. That direct-copier path is the documented
**fallback** (and the reproducibility guarantee, US1), not a competing primary
path — the primary path for everyone is `bailiff.py`.

It is a **cross-cutting spec**: specs 002–009 must honor the delivery shape and the
reproduce model it establishes. See "What other specs must take into account" below.

## Motivating decisions (from the 001 debrief)

1. **Everything is a copier wrapper, never a separate tool** (C-01). The deterministic
   coordination is bundled with the skill as **one script, `scripts/bailiff.py`**, run
   `./scripts/bailiff.py` / `uv run scripts/bailiff.py` and invoked by documented
   instructions — not installed as a `[project.scripts] bailiff` console script, not
   published to PyPI. The script drives the full lifecycle (`discover`, `trust`,
   `init`, `reproduce`) through **one uniform path for 1..N templates**. A
   single-template project is the N=1 case — **no separate single-template path,
   and no verb that is meaningless at N=1.** The script never re-implements copier;
   it drives copier's public surface once per template layer.
2. **Reproduce MUST work with copier alone.** A generated project's reproducibility
   must never depend on bailiff (or `just`) being installed. The committed
   `.copier-answers*.yml` file(s) are the *entire* reproduce state. Because
   `bailiff.py reproduce` only issues plain `copier recopy --vcs-ref=:current:`
   commands (one per answers file), a human with copier but no bailiff can run those
   by hand — that direct-copier path is the documented **fallback and the
   reproducibility guarantee (US1)**, while `scripts/bailiff.py` is the primary path
   for everyone. `bailiff.py` is ergonomics + orchestration, never a hard dependency
   of a generated project.
3. **No bailiff-specific artifact is committed into generated projects.** Drop the
   generated `justfile`. Nothing bailiff-authored (no frozen recipe, no DAG file) is
   written into the project — only copier-native answers files.
4. **Multi-template reproduce recomputes the order at runtime, deterministically.**
   The DAG is NOT frozen into the project. At reproduce, the skill's script
   enumerates the committed answers files, fetches each template **at its pinned
   `_commit`**, reads its `when:false` edges, and topo-sorts with a **stable
   tie-break**. Pinned commits → identical edges → identical order. Dependency
   *outcome* is what must be identical; exact ordering of mutually-independent
   templates is irrelevant (they write disjoint paths). Determinism comes from
   pinning + a stable sort, and — because it recomputes from committed data — it is
   independent of any bailiff-specific file the user might forget to commit.
5. **Reproduce is faithful; changed deps are an UPDATE concern.** Reproduce resolves
   from recorded pins only and never fetches latest. New/changed dependencies are
   picked up at `update` (the intentional upgrade), which re-resolves from the target
   versions. Reproduce never reorders a historical project.
6. **Dependencies live in each template's `copier.yml`** (`when:false` edges),
   versioned and pinned with the template. NOT relocated to the catalog (the catalog
   holds mutable sources, not version-correct edges — ADR-0002). No catalog
   dependency-cache (not worth the complexity).
7. **Reproduce/update are SKILLS, not slash commands.** A slash command is a per-repo
   typed invocation; a **skill is portable** (ships via APM, auto-triggers on its
   semantic description) so it works in any project bailiff touched. The agent's role in
   these skills is thin — invoke the deterministic script and act on its result — with
   no LLM judgment in the mechanical step (still "agent-free" in the C-02 sense).

## User Scenarios & Testing

### US1 — Reproduce with only copier installed (no bailiff) — the fallback (Priority: P1)

A developer clones a bailiff-generated project onto a machine that has copier but not
bailiff, and reproduces it faithfully **without bailiff** — because `bailiff.py reproduce`
only ever issues plain `copier recopy` commands, the same commands run by hand
reproduce the project identically.

**Independent Test**: take a project generated by the loop; on an environment with
**no bailiff installed and no `just`**, run `copier recopy --vcs-ref=:current:
--defaults --overwrite` per committed answers file by hand; assert the rendered
tree is config-consistent at the recorded commit — matching what `scripts/bailiff.py
reproduce` produces.

**Why it matters**: proves the primary path (`bailiff.py`) adds no reproduce-time
dependency — bailiff is ergonomics over copier, never a hard requirement of a
generated project (decision 2/3).

### US2 — Reproduce via the portable skill (Priority: P1)

A developer (or agent) in any project invokes the reproduce skill; it runs the
bundled deterministic script, which drives copier once per committed answers file
and reports the outcome — the same code path whether the project has one template
or many.

**Independent Test**: with the skill available, trigger `scripts/bailiff.py
reproduce`; the bundled script regenerates the project config-consistently with no
interactive LLM step in the mechanical path. A single-template project exercises
the identical path with N=1 (one answers file → one `copier recopy`), with no
single-template-only branch.

### US3 — Multi-template reproduce recomputes order deterministically (Priority: P1)

A project generated from several layered templates reproduces in correct dependency
order without any committed bailiff-specific recipe.

**Independent Test**: generate a project from ≥2 templates with a `depends_on` edge;
delete any non-copier metadata; reproduce; assert (a) order respects the edge, (b)
running reproduce twice yields config-consistent output, (c) the resolution used only
the committed answers files + pinned template fetches. Include a case where two
edge-independent templates write disjoint files → any order is config-consistent.

### US4 — No installed console script; orchestration is a bundled script (Priority: P1)

The deterministic coordination is a bundled `scripts/bailiff.py`, not an installed
command on PATH and not a generated per-project file.

**Independent Test**: `pyproject.toml` declares no `[project.scripts] bailiff`; the
orchestration is invocable as `./scripts/bailiff.py` / `uv run scripts/bailiff.py`
without installing the package; `init` writes no `justfile` (nor any bailiff-specific
file) into the generated project; the package is not framed as an installable
application.

## Requirements (Functional)

- **FR-001**: The deterministic coordination (discover, trust, init, reproduce, and
  the multi-template ordering/orchestration) MUST be delivered **bundled with the
  skill as a single script `scripts/bailiff.py`**, run `./scripts/bailiff.py` / `uv run
  scripts/bailiff.py` and invoked by documented instructions — NOT as a
  `[project.scripts] bailiff` console script and NOT as a PyPI package. Remove
  `[project.scripts] bailiff`. The script MUST drive the full lifecycle through **one
  uniform path for 1..N templates**: a single-template project is the N=1 case, with
  **no separate single-template code path and no verb meaningful only for multiple
  templates**. The script drives copier's public surface once per template layer; it
  MUST NOT re-implement copier. (The N>1 dependency ordering is spec 003; the
  uniform loop and the reproduce-recompute contract are this spec.)
- **FR-002**: `init` MUST NOT write any bailiff-specific artifact into the generated
  project. Remove justfile generation. The only reproduce state is copier's committed
  `.copier-answers*.yml`.
- **FR-003**: Reproduce MUST be performable with copier alone (no bailiff, no `just`).
  The skill/docs MUST document the exact `copier recopy --vcs-ref=:current: --defaults
  --overwrite` invocation (per answers file) as the copier-only fallback.
- **FR-004**: Multi-template reproduce MUST recompute the execution order at runtime
  from the committed answers files, fetching each template at its recorded `_commit`,
  reading `when:false` edges, and topo-sorting with a **stable, documented tie-break**.
  It MUST NOT read or require any frozen order file.
- **FR-005**: Reproduce MUST resolve only from recorded pins and MUST NOT fetch latest
  or reorder based on newer template versions. Changed dependencies are handled at
  `update` (spec 006), which re-resolves from target versions.
- **FR-006**: Reproduce/update MUST be portable **skills** (semantic auto-trigger
  descriptions), not slash commands. The deterministic step MUST contain no LLM
  judgment.
- **FR-007**: The reshape MUST preserve 001's behavior and test coverage — the
  discover/trust/init/reproduce/check logic and determinism/trust/safety guarantees
  are unchanged; only packaging and invocation change. Existing tests MUST be adapted
  to the new invocation, not weakened.
- **FR-008**: Dependency edges MUST remain in each template's `copier.yml` (versioned,
  pinned). This spec MUST NOT relocate edges to the catalog and MUST NOT add a catalog
  dependency-cache.

## What other specs must take into account

This spec sets contracts the rest of the roadmap depends on. Each affected spec:

- **002 (catalog):** the catalog holds **sources, not dependency edges** — do not put
  version-correct edges there (FR-008). Discovery/parsing lives in the skill-bundled
  `scripts/bailiff.py` (FR-001), invoked by the skill — not an installed `bailiff`
  console command.
- **003 (multi-template + ordering):** the **uniform 1..N orchestration loop** is
  built HERE in 010 (`bailiff.py` drives copier once per committed answers file, N=1
  being the trivial case). 003 adds the **dependency ordering brain** that sorts the
  N>1 layers: build the DAG at init/update **and** recompute it at reproduce from
  committed answers + pinned fetches (FR-004); do **not** "generate the ordered
  reproduce recipe" as a committed file (that phrasing in the 003 entry is superseded
  — the recipe is recomputed, not frozen). Guarantee a stable tie-break so output
  is order-independent for edge-independent templates. 003 plugs its topo-sort into
  010's loop; it does not build a second, separate multi-template path.
- **004 (defaults):** `user_defaults=` prefill is a skill step / bundled helper, not a
  CLI flag. No project-committed defaults artifact.
- **005 (secrets):** secret re-fetch at reproduce is a bundled skill script step
  (FR-001/FR-006), re-fetching identically at init and reproduce; never a
  project-committed recipe.
- **006 (upgrade + migrations):** `update` is the ONLY place dependencies re-resolve
  from newer versions (FR-005). It re-runs the init-time resolution against target
  versions; reproduce stays pinned. Delivered as a portable skill (FR-006).
- **007 (agentic module):** template content only; unaffected by delivery shape but
  MUST NOT reintroduce a project-committed bailiff artifact.
- **008 (release + fan-out):** distribute the **skill via APM marketplace** and
  templates via their repos — there is no `bailiff` package to publish (already aligned;
  reaffirm no console-script). The example template is published per-repo regardless.
- **009 (project-setup port):** whether the skill is named `bailiff` or
  `project-setup:*` is decided here/at 009 (see Open Questions). Reproduce/update
  skills MUST be portable across generated projects either way.

## Success Criteria

- **SC-001**: A bailiff-generated project reproduces config-consistently with copier only
  (no bailiff, no `just`) from its committed answers file(s).
- **SC-002**: No generated project contains a bailiff-specific file (no justfile, no
  frozen recipe, no DAG file).
- **SC-003**: `pyproject.toml` declares no `[project.scripts] bailiff` console script;
  the orchestration runs as bundled `scripts/bailiff.py` (`./scripts/bailiff.py` / `uv
  run scripts/bailiff.py`), and reproduce/update ship as portable skills that
  auto-trigger on their descriptions.
- **SC-004**: Multi-template reproduce is config-consistent across repeated runs and
  order-correct, computed solely from committed answers + pinned template fetches.
- **SC-005**: 001's guarantees (faithful reproduce, trust gating, static-safe
  discovery) remain green under the new packaging.

## Out of scope

- The multi-template orchestrator's ordering algorithm details (that is 003; this spec
  fixes the *reproduce-time recompute contract* it must satisfy).
- Catalog design (002), secrets store adapters (005), migration format (006).
- Any change to copier itself or to the template-author contract.

## Open Questions

- **Q-010a — Skill namespace:** is the durable skill `bailiff:*` (its own capability,
  which `project-setup`/009 consumes) or folded into `project-setup:*`? Lean:
  keep `bailiff` distinct (a general copier conductor shouldn't couple to one module
  family), provided its skill descriptions auto-trigger on the right semantics.
  Resolve at 009 scoping.
- **Q-010b — Language/runtime of bundled script:** RESOLVED. The skill bundles a
  single Python script `scripts/bailiff.py`, run `./scripts/bailiff.py` (shebang) or
  `uv run scripts/bailiff.py` (dependency-light; reuses the 001 logic verbatim). One
  cohesive orchestration entrypoint, not a scatter of one-liners; scoped to
  copier-can't work (discovery/trust/ordering), with single-template copier
  operations invoked directly per FR-001.
- **Q-010c — Answers-file enumeration for multi-template:** how does the reproduce
  script discover *which* `.copier-answers*.yml` files a project has (glob pattern /
  naming convention)? Fixed when 003 defines the per-template answers-file naming.

## Governing constitution & ADRs

- Constitution I (skills+templates+glue, no application), II (two-phase, agent-free
  determinism), III (faithful reproduce), V (trust), VIII (documented handoff).
- ADR-0001 (copier is the engine), 0002 (answers carry state; catalog = sources),
  0003 (selector/runtime injection), 0006 (distribution: skill via APM, templates via
  repos).
- Constraints: C-01 (no application), C-02, C-03, C-11 (glue only when copier cannot).
