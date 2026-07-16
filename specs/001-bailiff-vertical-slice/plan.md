# Implementation Plan: bailiff Single-Template Vertical Slice

**Branch**: `001-bailiff-vertical-slice` | **Date**: 2026-07-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-bailiff-vertical-slice/spec.md`

## Summary

Prove the whole conduct → copier → reproduce loop for ONE trusted source with ONE
template, delivered as **an agent skill + one example template + minimal
deterministic glue** — not a Python package. copier's own CLI already performs
init, reproduce, and trust refusal each in a single command (verified); bailiff adds
the conducting `SKILL.md`, the `bailiff-template-example` template, and the small glue copier
cannot provide by itself (a static discovery/validation helper and a generated
per-project reproduce recipe).

Technical approach, verified against copier 9.16.0:
- **init** = `copier copy --data-file <answers.yml> --defaults --overwrite --trust
  <src> <dst>` (all flags exist on the CLI).
- **reproduce** = a generated `just reproduce` running `copier recopy
  --vcs-ref=:current: --defaults --overwrite` — the `:current:` pin is baked into
  the recipe so it can never silently upgrade; agent-free by construction (CI runs
  the recipe).
- **discovery** = static read of `copier.yml` (questions, secret flags, `when:false`
  edges, `_jinja_extensions`) + a file-tree glob for
  `{{ _copier_conf.answers_file }}.jinja` + `git ls-remote` filtered by
  `packaging.Version`. No Jinja env is built and no template code runs → safe on
  untrusted sources, and no `copier.Template`/`Worker` is touched → **no adapter
  this slice**.
- **trust** = read copier's `settings.yml` `trust:`; surface copier's own refusal
  (exit 4) or an equivalent clear message; record trust only via an explicit
  consent step that appends the fully-expanded `https://` prefix.
- **validation** = copier's own `--pretend` dry run; surface copier's
  `copier.errors.*` and the bare `builtins.ValueError` (missing-required-question)
  as-is with a readable message.

## Technical Context

**Language/Version**: Python 3.11+ **only where glue needs it**; shell + `just`
for the invocations that are one command. (`pyproject.toml` already targets 3.11+.)

**Primary Dependencies**: `copier>=9.16,<10` (the engine, pinned). `packaging` for
PEP 440 tag filtering (declared direct if the discovery helper is Python).
**No pydantic, no CLI framework, no adapter** in this slice. `git` and `just` are
host tools.

**Storage**: Files only. Inputs = a copier answers/`--data-file` document the skill
authors (documented plain YAML — Constitution VIII). Outputs = the generated
project tree + copier's `.copier-answers.yml`. Trust lives in copier's
`settings.yml` (`~/.config/copier/settings.yml` or `COPIER_SETTINGS_PATH`).

**Testing**: `pytest` for any Python helper + `bats`/pytest-driven subprocess tests
for the shell recipes; hermetic and offline using local `git` template fixtures.
One clearly-marked network smoke test against the hand-published `bailiff-template-example`.
`mypy`/`ruff` apply only to Python glue that exists.

**Target Platform**: Developer workstations + CI (macOS/Linux).

**Project Type**: A skill + a copier template + a little glue. NOT a published
application (no `uvx bailiff` / PyPI target this slice; the existing `pyproject.toml`
`[project.scripts]` entry is dropped or reduced to the discovery helper only).

**Performance Goals**: None; correctness + determinism only.

**Constraints**: Hermetic/offline tests except one marked smoke test; deterministic
reproduce (config-consistent over an enumerated path set, empty exclusion list); no
deprecated copier surface (static parsing suffices, so no adapter); the
deterministic path never prompts and never writes trust; glue justified only by a
copier gap (Constitution I / C-11).

**Scale/Scope**: One template, one source, one render. A `SKILL.md`, one example
template, one small discovery/validation helper, a generated reproduce recipe, and
their tests. Everything else is deferred (roadmap 002–009).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution **v2.0.0** (Principles I–VIII). Initial gate: **PASS**.

| Principle | Gate | How this plan satisfies it |
|---|---|---|
| I — Skills + templates + minimal glue | PASS | Deliverables are a `SKILL.md`, the `bailiff-template-example` template, and a small discovery/validation helper + generated reproduce recipe. No package, no wrapper re-implementing copier. |
| II — Two-phase; skill conducts, helpers execute | PASS | Skill authors a documented answers document; the deterministic phase is copier CLI calls (± the helper), runnable/testable with no LLM. Agent never in reproduce. |
| III — Faithful, agent-free reproduce | PASS | Generated `just reproduce` pins `--vcs-ref=:current: --defaults --overwrite`; bare recopy never used; upgrade out of scope. Determinism test asserts config-consistency. |
| IV — Prefer CLI + static config; adapter only if used | PASS | Discovery is a static `copier.yml`/file-tree parse; no Jinja env, no `Template`/`Worker` → **no adapter, no drift test** this slice. copier pinned `<10`. |
| V — Determinism via pinning; trust by source | PASS | `today` injected via `--data`; template forbids clock/random; trust in `settings.yml` (expanded-https); deterministic phase never writes trust; CI fails loudly. |
| VI — Template-author contract at discovery | PASS | Discovery statically checks the answers-file `.jinja` (FR-016) + version resolvability (FR-016a) and refuses non-conforming; `bailiff-template-example` conforms + clean `v1.0.0`. |
| VII — Hardening per-step (scaled) | PASS | DoD = determinism test + error surfacing (copier.errors.* AND ValueError) + tests for the helper + template loop. No adapter drift test needed (no adapter). |
| VIII — Documented, dry-run-validated handoff | PASS | Handoff is a documented plain YAML answers document; validation is copier's `--pretend`. No pydantic, no committed JSON Schema, no schema-drift test. |

**Complexity deviations**: none. The plan *removes* the prior structure (package,
pydantic seam, adapter) rather than adding any.

Post-design re-check (after Phase 1): **PASS** — data model is copier's existing
answers/settings shapes plus a small discovery result; no new dependency or
deprecated surface introduced.

## Project Structure

### Documentation (this feature)

```text
specs/001-bailiff-vertical-slice/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions + copier-9.16.0 verifications
├── data-model.md        # Phase 1 — the (small) data at the seam: answers doc, discovery result, trust entry, recorded answers
├── quickstart.md        # Phase 1 — runnable validation scenarios (the loop, by hand + tests)
├── contracts/           # Phase 1 — documented handoff + CLI/recipe contract (prose + examples, NOT JSON Schema)
│   ├── answers-doc.md    # the plain-YAML inputs the skill authors
│   ├── discovery-output.md  # the shape the discovery helper prints (documented, not schema-enforced)
│   └── commands.md       # the exact copier invocations + the reproduce recipe
└── tasks.md             # Phase 2 (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
skills/bailiff/
└── SKILL.md             # THE primary deliverable: the phase-1 conductor procedure
                         # (inspect → present questions → collect answers → trust consent → init → reproduce → hand off)

examples/bailiff-template-example/  # The example template (hand-published to its own repo; roadmap 008 automates)
├── copier.yml            # identity questions + when:false edge (fixture-style) + _tasks: git init (no commit)
└── template/
    ├── README.md.jinja
    ├── LICENSE.jinja
    ├── .gitignore.jinja
    └── {{ _copier_conf.answers_file }}.jinja   # REQUIRED for reproducibility (Principle VI)

scripts/                  # Minimal glue — only what copier CLI + agent cannot do directly
├── bailiff-discover        # static copier.yml + file-tree + git-ls-remote inspection → prints discovery result
│                         #   (Python if it needs packaging.Version + YAML; kept to one small module/file)
└── reproduce.just        # the generated per-project reproduce recipe template (:current: pinned)

# NOTE: no src/bailiff/ package, no models.py/pydantic, no _copier_adapter.py, no schema/.
# If a later spec (003) proves coordination needs a real module, it is introduced THEN (C-11, Q4).

tests/
├── loop/
│   ├── test_init_reproduce.py       # US1+US2: copier copy → recorded answers → recopy :current: (SC-002 config-consistent, empty exclusion)
│   ├── test_trust_refusal.py        # US4: untrusted action-taking template refused (exit 4 / clear error) → consent → success
│   ├── test_discover_static_safe.py # US3/FR-004a: discovery reads statically, executes no template code, needs no trust
│   ├── test_answersfile_refusal.py  # US5/FR-016: refuse template lacking the answers-file .jinja
│   ├── test_secret_edge_exclusion.py# FR-013 fixture: secret + when:false NOT persisted
│   └── test_smoke_remote.py         # marked network smoke vs hand-published bailiff-template-example
└── unit/
    └── test_discover.py             # tag PEP440 filtering, when:false edge parsing, answers-file detection, --pretend validation surfacing
```

**Structure Decision**: No Python package. The primary artifact is
`skills/bailiff/SKILL.md`; the product artifact is `examples/bailiff-template-example/`; the
only code is a single small `scripts/bailiff-discover` helper (justified by C-11: it
does the static discovery/validation copier's CLI does not expose as one command)
plus a generated reproduce recipe. Hermetic tests build throwaway local `git`
template fixtures; only `test_smoke_remote.py` touches the network. If roadmap 003's
coordination logic outgrows a helper, a minimal module is introduced there, with
evidence (Q4) — not now.

## Complexity Tracking

No constitutional violations; no complexity deviations. This plan reduces surface
versus the superseded v1 tool-centric plan (removed: 9-module package, pydantic
seam models, committed JSON Schemas + drift test, deprecated-surface adapter +
contract test, typed-error hierarchy).
