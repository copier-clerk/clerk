# Feature Specification: clerk delivery reshape — skill-bundled copier wrapper

**Feature Branch**: `010-delivery-reshape`

**Created**: 2026-07-10

**Status**: Draft

**Input**: Session decisions after spec 001 verification (2026-07-10). Governed by
the constitution (Principles I, II, V, VIII) and ADRs 0001/0002/0003/0006.
Supersedes the transitional CLI/justfile delivery shape that slice 001 shipped to
prove the loop.

## Overview

Spec 001 proved the conduct→copier→reproduce loop, but did so with a **transitional
delivery shape** that drifted from the ratified constitution: a `clerk` console
script (`[project.scripts]`) and a generated per-project `justfile` calling
`clerk reproduce`. Both make a *tool* the durable artifact and make generated
projects depend on clerk (and on `just`) to reproduce. Constitution I / C-01 say
the opposite: clerk is **skills + templates + minimal glue, NOT a published
application**.

This spec reshapes the delivery so clerk is a **pure copier wrapper bundled inside a
portable skill**, with **zero clerk-specific artifact committed into a generated
project**. It changes *how the deterministic layer is packaged and invoked* — not
what it does. The `discover`/`trust`/`init`/`reproduce`/`check` logic and its 35
tests from 001 survive nearly intact; this is re-packaging, not a rewrite.

The deterministic layer ships as **one bundled orchestration script**,
`scripts/clerk.py`, run via `./scripts/clerk.py …` or `uv run scripts/clerk.py …`
(a shebang'd, dependency-light Python script — NOT a `[project.scripts] clerk`
console entry, NOT a PyPI package). It is scoped to **only what copier cannot do
itself**: static discovery, trust surfacing, and multi-template dependency
ordering. For everything copier already owns — single-template `copy` / `recopy` /
`update` — the skill instructs the agent (or a human, or CI) to invoke **copier
directly** with the documented command, so `clerk.py` never wraps or
re-implements copier's single-template surface. A single cohesive orchestration
entrypoint is preferred over a scatter of bundled one-liners: it gives one
argparse surface, one place to translate copier's errors, and one unit-testable
seam, without reading as an installable application.

It is a **cross-cutting spec**: specs 002–009 must honor the delivery shape and the
reproduce model it establishes. See "What other specs must take into account" below.

## Motivating decisions (from the 001 debrief)

1. **Everything is a copier wrapper, never a separate tool** (C-01). The deterministic
   coordination is bundled with the skill as **one script, `scripts/clerk.py`**, run
   `./scripts/clerk.py` / `uv run scripts/clerk.py` and invoked by documented
   instructions — not installed as a `[project.scripts] clerk` console script, not
   published to PyPI. The script handles **only the copier-can't work** (discovery,
   trust, multi-template ordering); the agent invokes copier directly for
   single-template `copy`/`recopy`/`update`.
2. **Reproduce MUST work with copier alone.** A generated project's reproducibility
   must never depend on clerk (or `just`) being installed. The committed
   `.copier-answers*.yml` files are the *entire* reproduce state; worst case a human
   runs the `copier recopy` command(s) by hand. `scripts/clerk.py` is **ergonomics +
   the multi-template orchestrator**, never a hard dependency of a generated project.
   For a single-template project there is nothing to orchestrate: the documented
   path is `copier recopy` invoked directly, and `clerk.py` is not required at all.
3. **No clerk-specific artifact is committed into generated projects.** Drop the
   generated `justfile`. Nothing clerk-authored (no frozen recipe, no DAG file) is
   written into the project — only copier-native answers files.
4. **Multi-template reproduce recomputes the order at runtime, deterministically.**
   The DAG is NOT frozen into the project. At reproduce, the skill's script
   enumerates the committed answers files, fetches each template **at its pinned
   `_commit`**, reads its `when:false` edges, and topo-sorts with a **stable
   tie-break**. Pinned commits → identical edges → identical order. Dependency
   *outcome* is what must be identical; exact ordering of mutually-independent
   templates is irrelevant (they write disjoint paths). Determinism comes from
   pinning + a stable sort, and — because it recomputes from committed data — it is
   independent of any clerk-specific file the user might forget to commit.
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
   semantic description) so it works in any project clerk touched. The agent's role in
   these skills is thin — invoke the deterministic script and act on its result — with
   no LLM judgment in the mechanical step (still "agent-free" in the C-02 sense).

## User Scenarios & Testing

### US1 — Reproduce a project with only copier installed (no clerk) (Priority: P1)

A developer clones a clerk-generated project onto a machine that has copier but not
clerk, and reproduces it faithfully.

**Independent Test**: take a project generated by the 001 loop; on an environment
with **no clerk installed and no `just`**, reproduce it from the committed answers
file(s) using copier directly; assert the rendered tree is byte-identical at the
recorded commit.

**Why it matters**: proves reproduce has zero clerk/just dependency (decision 2/3).

### US2 — Reproduce via the portable skill (Priority: P1)

A developer (or agent) in any project invokes the reproduce skill; it runs the
bundled deterministic script, which drives copier and reports the outcome.

**Independent Test**: with the skill available, trigger reproduce; the bundled
script regenerates the project byte-identically with no interactive LLM step in the
mechanical path; a single-template project needs no order computation.

### US3 — Multi-template reproduce recomputes order deterministically (Priority: P1)

A project generated from several layered templates reproduces in correct dependency
order without any committed clerk-specific recipe.

**Independent Test**: generate a project from ≥2 templates with a `depends_on` edge;
delete any non-copier metadata; reproduce; assert (a) order respects the edge, (b)
running reproduce twice yields byte-identical output, (c) the resolution used only
the committed answers files + pinned template fetches. Include a case where two
edge-independent templates write disjoint files → any order is byte-identical.

### US4 — No installed console script; orchestration is a bundled script (Priority: P1)

The deterministic coordination is a bundled `scripts/clerk.py`, not an installed
command on PATH and not a generated per-project file.

**Independent Test**: `pyproject.toml` declares no `[project.scripts] clerk`; the
orchestration is invocable as `./scripts/clerk.py` / `uv run scripts/clerk.py`
without installing the package; `init` writes no `justfile` (nor any clerk-specific
file) into the generated project; the package is not framed as an installable
application.

## Requirements (Functional)

- **FR-001**: The deterministic coordination (discovery, trust, and the
  multi-template ordering/orchestration) MUST be delivered **bundled with the skill
  as a single script `scripts/clerk.py`**, run `./scripts/clerk.py` / `uv run
  scripts/clerk.py` and invoked by documented instructions — NOT as a
  `[project.scripts] clerk` console script and NOT as a PyPI package. Remove
  `[project.scripts] clerk`. The script MUST be scoped to what copier cannot do
  itself; single-template `copy`/`recopy`/`update` are invoked as copier directly
  (the skill documents the command), NOT wrapped by the script.
- **FR-002**: `init` MUST NOT write any clerk-specific artifact into the generated
  project. Remove justfile generation. The only reproduce state is copier's committed
  `.copier-answers*.yml`.
- **FR-003**: Reproduce MUST be performable with copier alone (no clerk, no `just`).
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
  `scripts/clerk.py` (FR-001), invoked by the skill — not an installed `clerk`
  console command.
- **003 (multi-template + ordering):** THIS is where the runtime-recompute
  orchestrator lands. Build the DAG at init/update **and** recompute it at reproduce
  from committed answers + pinned fetches (FR-004); do **not** "generate the ordered
  reproduce recipe" as a committed file (that phrasing in the 003 entry is superseded
  — the recipe is recomputed, not frozen). Guarantee a stable tie-break so byte-output
  is order-independent for edge-independent templates.
- **004 (defaults):** `user_defaults=` prefill is a skill step / bundled helper, not a
  CLI flag. No project-committed defaults artifact.
- **005 (secrets):** secret re-fetch at reproduce is a bundled skill script step
  (FR-001/FR-006), re-fetching identically at init and reproduce; never a
  project-committed recipe.
- **006 (upgrade + migrations):** `update` is the ONLY place dependencies re-resolve
  from newer versions (FR-005). It re-runs the init-time resolution against target
  versions; reproduce stays pinned. Delivered as a portable skill (FR-006).
- **007 (agentic module):** template content only; unaffected by delivery shape but
  MUST NOT reintroduce a project-committed clerk artifact.
- **008 (release + fan-out):** distribute the **skill via APM marketplace** and
  templates via their repos — there is no `clerk` package to publish (already aligned;
  reaffirm no console-script). The example template is published per-repo regardless.
- **009 (project-setup port):** whether the skill is named `clerk` or
  `project-setup:*` is decided here/at 009 (see Open Questions). Reproduce/update
  skills MUST be portable across generated projects either way.

## Success Criteria

- **SC-001**: A clerk-generated project reproduces byte-identically with copier only
  (no clerk, no `just`) from its committed answers file(s).
- **SC-002**: No generated project contains a clerk-specific file (no justfile, no
  frozen recipe, no DAG file).
- **SC-003**: `pyproject.toml` declares no `[project.scripts] clerk` console script;
  the orchestration runs as bundled `scripts/clerk.py` (`./scripts/clerk.py` / `uv
  run scripts/clerk.py`), and reproduce/update ship as portable skills that
  auto-trigger on their descriptions.
- **SC-004**: Multi-template reproduce is byte-identical across repeated runs and
  order-correct, computed solely from committed answers + pinned template fetches.
- **SC-005**: 001's guarantees (faithful reproduce, trust gating, static-safe
  discovery) remain green under the new packaging.

## Out of scope

- The multi-template orchestrator's ordering algorithm details (that is 003; this spec
  fixes the *reproduce-time recompute contract* it must satisfy).
- Catalog design (002), secrets store adapters (005), migration format (006).
- Any change to copier itself or to the template-author contract.

## Open Questions

- **Q-010a — Skill namespace:** is the durable skill `clerk:*` (its own capability,
  which `project-setup`/009 consumes) or folded into `project-setup:*`? Lean:
  keep `clerk` distinct (a general copier conductor shouldn't couple to one module
  family), provided its skill descriptions auto-trigger on the right semantics.
  Resolve at 009 scoping.
- **Q-010b — Language/runtime of bundled script:** RESOLVED. The skill bundles a
  single Python script `scripts/clerk.py`, run `./scripts/clerk.py` (shebang) or
  `uv run scripts/clerk.py` (dependency-light; reuses the 001 logic verbatim). One
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
