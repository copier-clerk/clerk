# 0001 — copier is the deterministic engine; clerk is the agentic conductor

- Status: accepted
- Date: 2026-07-09

## Context

`clerk` grew out of `project-setup`, a bespoke, stdlib-only, deterministic
scaffolding runner (frozen plan, canonical JSON, hand-rolled TOML emitter,
git-fetched modules, reproduce-from-answers). A formal debate (6 code-grounded
research angles + adversarial challenge; see
`project-setup/research/debate-copier-vs-bespoke-engine.md`) established that the
bespoke engine's determinism goal was ~80% already met, and that migrating to
copier would *relocate* rather than remove the hard problems.

The owner nonetheless chose to build on copier: effort is explicitly **not** the
optimization metric, and copier has already solved the deterministic
render + reproduce + git-ref-pinning problem that the bespoke runner re-invents.
The value clerk adds is the layer copier structurally lacks — an agentic
conductor.

## Decision

- **copier is the engine.** It owns deterministic rendering, the committed
  answers file, git-ref-pinned remote templates, and the reproduce/update cycle.
- **clerk is a thin agentic conductor on top.** It owns: an init-time agent that
  selects modules and authors answers (the *inputs*); a thin orchestrator for
  multi-module enablement + topological ordering; and the agentic-ecosystem
  wiring copier has no concept of (APM / MCP / SpecKit / ADR).
- **copier runs WITHOUT `--trust`** — pure file renderer, no template `_tasks`.
  All action-taking (installs, shell) stays in clerk's controlled orchestrator.
- **copier is invoked via its Python API / `uvx`**, never vendored. Only `uv`
  remains a hard prerequisite; copier's 13-dep tree is fetched ephemerally.
- **The reproduce path is agent-free**: `copier recopy --defaults` (or a
  `just reproduce`) run by a human or CI, replaying the committed answers with
  no agent involvement.

## Consequences

- Strict "stdlib-only" is given up (copier pulls jinja2, pydantic v2,
  questionary, plumbum, …), accepted because it is fetched ephemerally, not
  vendored.
- Determinism now rides on copier + Jinja rather than a hand-rolled canonical
  serializer. Reproduce byte-stability requires pinning the copier version
  (see repo dependency pin `copier>=9.16,<10`).
- The agentic layer (APM/MCP/SpecKit) has no off-the-shelf analog and stays
  bespoke — this is clerk's distinctive value.

## Related

- Supersedes the "harden the bespoke runner" path for this project.
- See [[0002-catalog-and-answer-model]] and
  [[0003-selector-template-and-runtime-injection]].
