# 0003 — a copier selector-template chooses modules; catalog injected at runtime

- Status: accepted (superseded in part — see below)
- Date: 2026-07-09

## Superseded in part (spec 002)

Spec 010 reshaped clerk to a **skill-bundled copier wrapper with no committed
clerk artifacts**. Spec 002 (implemented 2026-07-10) consequently supersedes the
two-template meta-flow described in the Decision section below:

- **repos-collector template → plain user-owned catalog file.** Sources are
  managed by `scripts/clerk.py catalog` verbs (`init`/`add`/`remove`/`list`/
  `validate`) in a user-config TOML file. No copier template whose only job is
  holding a list; no `.copier-answers.yml` acting as a catalog store. See
  `specs/002-catalog/spec.md` §"Reconciliation" and
  `specs/002-catalog/contracts/catalog.md`.

- **selector template → agent presentation + deterministic validation gate.**
  Template selection is the phase-1 agent's job: it presents the deterministic
  listing from `catalog list` and collects the user's pick. `catalog validate
  <full-id>` is the mechanical gate that makes agent selection safe — it accepts
  only ids present in the discovered catalog (exit 0) and refuses unknown or
  ambiguous ids (non-zero, listing valid ids). No selector copier template; no
  multiselect-in-a-template machinery at this layer.

**Retained unchanged from this ADR:**

- The source-verified fact that a runtime-injected `catalog` value is in copier's
  render scope from question 1 (`--data catalog=[…]` / `run_copy(data=…)`) is
  **still true and still used** — it is the mechanism spec 007's apm module
  template uses for its own internal `choices: "{{ catalog }}"` multiselect. That
  use is explicitly internal to the apm module template and is not built in spec
  002.
- The hidden `when:false` dependency edges in each template's `copier.yml`
  (statically parsed by `discovery.py`). Spec 003 consumes these to build its DAG.
- ADR-0002 (user-owned catalog of sources; answers carry state; full-id collisions;
  no submodules) is honored in full and not superseded.

## Context

Two candidate designs for how the agent learns the available modules and how the
user selects among them:
- **(A) Sidecar `clerk.yml`** per template carrying agentic metadata + a CI
  *catalog generator* that regenerates a selector's baked-in `choices`.
- **(B) A copier "selector template"** whose questions enumerate the catalog,
  with the catalog supplied at **runtime** rather than baked into the template.

The hinge was whether copier's dynamic `choices` / render context can read a
runtime-supplied catalog. This was verified against copier v9.16.0 **source**.

## Verified facts (copier v9.16.0 source)

- Every rendered question field (`choices`, `default`, `when`, `validator`,
  `help`) renders through `Question.render_value` (`_user_data.py:475-498`) with
  the **full render context** — `Worker._render_context()` (`_main.py:429-465`).
- `--data` / `run_copy(data=...)` values live in `AnswersMap.combined` at
  **priority 2**, in scope **from question 1**. So `choices: "{{ catalog }}"`
  renders whatever list the agent injects.
- `_external_data` is also in scope during the questionnaire (attached before the
  loop, `_main.py:588`); usable when the catalog is a YAML file written to the
  destination dir first.
- `!include` is **template-root-relative, parse-time only**; absolute/external
  paths raise `ValueError` (`_template.py:95-106`) — cannot reach a runtime
  catalog.
- Regenerating a template's `copier.yml` breaks VCS integrity for pinned remote
  templates — rejected.

## Decision

- **Two-template meta flow.** (1) A *repos-collector* template asks the user for
  one or more source github repos; those repo URLs + refs persist in its
  `.copier-answers.yml` (re-answering updates them — no `catalog.yml` file). (2)
  clerk extracts + verifies the templates found in those repos, then invokes a
  *selector* template with the discovered catalog injected via
  `run_copy(data={"catalog": [...]})`. Extraction is clerk's job, NOT a copier
  task (copier cannot run a command mid-questionnaire).
- **Selection is one or more `multiselect` questions.** Grouping (skills / mcp /
  bundles vs plain templates) is by template metadata or filename when there are
  many; a single group when few. The skills/agents/bundles/mcp multiselect is
  **internal to the apm module template**, reusing copier's own multiselect
  there — it is NOT the meta-template's concern.
- **The catalog is injected at runtime via `run_copy(data={"catalog": [...]})`**
  (equivalently `--data`) — source-verified in scope from question 1. No sidecar,
  no CI catalog generator, no template mutation.
- **`_external_data` is NOT part of the core design.** clerk drives every run and
  threads one module's answers into the next via `--data`, so cross-template
  answer sharing does not need `_external_data`. It remains only as an optional
  nicety for standalone per-module `copier update` runs done WITHOUT clerk.
- **This supersedes the sidecar recommendation** from earlier design notes.

## Dependencies + ordering — hidden answer, clerk-generated DAG

- Each module declares its edges as a **hidden computed answer** (`when: false`)
  in its own `copier.yml`: `depends_on` / `run_after` / `run_before`. This travels
  with the template at its pinned ref and is statically readable from `copier.yml`
  at selection time. (Note: a `when: false` answer is not written to the answers
  file, but its default is in `copier.yml`, so clerk parses it directly — it never
  needs to be persisted.)
- **clerk builds a DAG from these declarations and drives the copier invocations
  in topological order.** Modules with no edges run in any order; edges force
  sequence. There is NO separate "ordering template" — ordering is a pure function
  clerk computes, not a user step or artifact.
- This also orders the imperative task-bearing runs (a module whose `_tasks` must
  run after another's) since clerk sequences the whole graph.

- **Verified: `when:false` beats the alternatives for this.** Research confirmed
  hidden answers are statically parseable (clerk reads `copier.yml` at catalog
  time), require **no trust**, and travel with the pinned ref. The
  `copier-template-extensions` **context-hook** was considered and rejected for
  metadata: it escalates the whole invocation to `unsafe=True`, adds a pip dep,
  and its computed output is not statically parseable. Context-hook is blessed
  only for the narrow case of slug-derived *filenames* (see
  [[0004-rendering-and-extensions]]).

## Multi-template composition (verified)

- copier does **zero** cross-template coordination — clerk issues **one
  `run_copy` call per template**, in DAG order, each with a distinct
  `answers_file` so per-module answers do not collide.
- clerk threads one module's answers into the next via the `data=` dict (it holds
  all prior answers in memory). This is why `_external_data` is not needed in the
  core: `_external_data` only earns its place if a template must read a sibling's
  answers during a **standalone** `copier update` run done without clerk.
- If a template's `_external_data` paths traverse **outside** the destination
  directory, that specific run needs `unsafe=True` — a per-template opt-in flag in
  the catalog entry, never a global default.

## Residue not expressible as plain copier questions (kept minimal)

Carried inside the injected catalog data or the hidden `depends_on` answers,
**not** in unknown `_`-prefixed keys (only silently tolerated today, no forward
contract):
1. `id -> gituser/repo/path#ref` locator map — this *is* the catalog the agent
   injects.
2. Dependency edges — the hidden `depends_on` answers above; clerk builds the DAG.

## Consequences

- Clerk carries no per-template sidecar files and no catalog-generation CI. The
  agent + a small orchestrator + copier are the whole surface.
- Reproduce byte-stability depends on pinning the copier version (see
  [[0001-copier-as-engine]]).

## Related

- [[0001-copier-as-engine]], [[0002-catalog-and-answer-model]].
