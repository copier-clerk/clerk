# 0003 — a copier selector-template chooses modules; catalog injected at runtime

- Status: accepted
- Date: 2026-07-09

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

- **The primary interview mechanism is a copier selector-template**, driven by a
  `multiselect` "which modules?" question with per-module follow-ups gated by
  `when:` and narrowed by dynamic `choices`.
- **The catalog is injected at runtime via `run_copy(data={"catalog": [...]})`**
  (equivalently `--data`). The agent fetches the live catalog from the
  user-owned sources (per [[0002-catalog-and-answer-model]]) and passes it
  in-memory. No sidecar, no CI catalog generator, no template mutation.
- **`_external_data` is the documented fallback** for the case where the catalog
  is materialized as a YAML file in the destination directory before copier runs.
- **This supersedes the sidecar recommendation** from earlier design notes.

## Residue not expressible as copier answers (kept minimal)

Three concerns are not questions and ride along inside the injected catalog data
or clerk's orchestrator, **not** in `copier.yml` (unknown `_`-prefixed keys are
only silently tolerated today with no forward contract — do not rely on them):
1. `id -> gituser/repo/path#ref` locator map — this *is* the catalog the agent
   injects.
2. Application / topological order — clerk orchestrator logic.
3. per-module "agent-phase vs pure-render" routing flag — carried in the catalog
   entry.

## Consequences

- Clerk carries no per-template sidecar files and no catalog-generation CI. The
  agent + a small orchestrator + copier are the whole surface.
- Reproduce byte-stability depends on pinning the copier version (see
  [[0001-copier-as-engine]]).

## Related

- [[0001-copier-as-engine]], [[0002-catalog-and-answer-model]].
