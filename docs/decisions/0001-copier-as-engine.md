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
- **copier runs WITH `--trust`, in BOTH init and reproduce.** Template `_tasks`
  and `migrations` are needed (e.g. `specify init`, `apm install`), including at
  reproduce when a module was added/changed. `--trust` blast radius is bounded:
  clerk drives **one template per `copier` invocation**, so trust is scoped to a
  single pinned, user-selected template's tasks per run — not a whole bundle.
- **copier is invoked via its Python API / `uvx`**, never vendored. Only `uv`
  remains a hard prerequisite; copier's 13-dep tree is fetched ephemerally.
- **The reproduce invariant is "no AGENT", NOT "no side effects".** Reproduce
  (`copier recopy` / `just reproduce`, run by a human or CI) replays the
  committed answers and MAY run tasks, but no LLM/agent participates. Reproduce
  is therefore **process-deterministic** (same frozen answers + same pinned
  refs → same commands executed), **not** output-byte-deterministic — tasks like
  `apm install` touch network/external state.

## Constraint — determinism discipline

Because tasks run at reproduce, byte-identity holds only as far as pins hold.
Everything a task consumes MUST be pinned: module `#ref` (tag or sha), `apm.lock`,
and tool versions (incl. the copier version, `copier>=9.16,<10`). Unpinned inputs
make reproduce drift; this is the accepted bargain for supporting `_tasks`.

## Consequences

- Strict "stdlib-only" is given up (copier pulls jinja2, pydantic v2,
  questionary, plumbum, …), accepted because it is fetched ephemerally, not
  vendored.
- Determinism now rides on copier + Jinja + the pinned task inputs rather than a
  hand-rolled canonical serializer. See the determinism-discipline constraint
  above.
- Open verification (before build): confirm against copier source whether
  `recopy` fires `_tasks`/`migrations` the same way `copy`/`update` do, so the
  reproduce-runs-tasks assumption holds for the chosen replay command.
- The agentic layer (APM/MCP/SpecKit) has no off-the-shelf analog and stays
  bespoke — this is clerk's distinctive value.

## Related

- Supersedes the "harden the bespoke runner" path for this project.
- See [[0002-catalog-and-answer-model]] and
  [[0003-selector-template-and-runtime-injection]].
