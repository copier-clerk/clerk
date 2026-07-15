# Implementation Plan: bailiff catalog — user-owned sources, runtime discovery + injection

**Branch**: `002-catalog` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-catalog/spec.md`

## Summary

Give bailiff a **user-owned catalog** of source repos and a **deterministic,
static** way to list the templates they offer, plus a **validation gate** on
selection — all inside the spec-010 skill-bundled shape (`scripts/bailiff.py` +
`SKILL.md`, no console script, no committed bailiff artifact). No repos-collector
template, no selector template (ADR-0003's two-template flow is superseded here).

Concretely:

- **Catalog file** — a plain **TOML** file of named catalog pointers, each listing
  source locators (`gituser/gitrepo` optional `@ref`). Default path via the same
  `platformdirs`/env resolution `trust.py` uses (`user_config_path("bailiff")`),
  overridable with `--catalog PATH`. **Local files only** for 002 (remote/shared
  catalogs are an 008 concern); one or more pointers supported.
- **`scripts/bailiff.py catalog` verbs** — `init` (create if absent), `list`, `add
  <src> [--name N]`, `remove <src>`, `refresh`. `add`/`remove` are idempotent and
  preserve unrelated entries.
- **Deterministic listing** — `catalog list`/`refresh` reuses
  `discovery.discover(source, ref)` per source (already static, no template code, no
  trust) and emits, per template, its **full-id `<catalog>/<template>`**, versions,
  `has_tasks`, `reproducible`, and questions summary. Unusable sources are reported
  per-source with a reason; one bad source never fails the whole catalog.
- **Selection-validation gate** — `catalog validate <full-id> [...]` accepts only
  ids present in the discovered catalog; refuses unknown or **ambiguous bare** ids
  (non-zero) naming the valid ids. No LLM judgment.
- **Full-id namespacing** — `<catalog>` is an **explicit per-pointer name**,
  defaulting to a sanitized file basename. One-or-more pointers; no unnamespaced
  first-wins lookup (ADR-0002).

Selection itself (which templates the user wants) stays with the **phase-1 agent**
(Constitution II); the gate makes that safe deterministically. `--data catalog=[…]`
runtime injection (ADR-0003's verified render-scope fact) is **retained but not
exercised** — it is the mechanism spec 007's apm module uses, not needed by 002.

## Technical Context

**Language/Version**: Python 3.11+ (`scripts/bailiff.py` + `src/bailiff/`). TOML read is
stdlib `tomllib` (3.11+); write needs a small dependency (see below).

**Primary Dependencies**: existing `copier>=9.16,<10`, `packaging`, `pyyaml`,
`platformdirs`. **New: `tomli-w`** (minimal TOML writer) added via `uv add tomli-w`.
Rationale: `tomllib` reads but cannot write; `tomli-w` is the dependency-light
writer (toolchain-defaults leans minimal). Trade-off: it does **not** preserve
comments on round-trip — acceptable because the catalog is bailiff-managed config and
the spec requires preserving *entries*, not formatting ("comments where feasible").
If comment-preservation becomes a real need, `tomlkit` is the drop-in upgrade — a
task-level decision, flagged, not taken now. No pydantic, no adapter.

**Storage**: Files only. Catalog = a user-config TOML file (default
`user_config_path("bailiff")/catalog.toml`, or `--catalog PATH`, or `COPIER`-style
env if we mirror trust — decide in T001). No state written into any generated
project. Discovery clones sources to temp dirs (existing `discovery` behavior).

**Testing**: `pytest`, hermetic/offline via **local git template fixtures** (reuse
`tests/conftest.py`'s builders; add a multi-source catalog fixture). Catalog verbs
tested via subprocess (`uv run scripts/bailiff.py catalog …`) + unit tests on the new
`catalog` module. One marked-`network` smoke may list a real published source
(deselected by default). `mypy --strict` + `ruff` over `src/ tests/ scripts/`.

**Target Platform**: developer workstations + CI (macOS/Linux).

**Project Type**: skill + bundled script + copier templates. No published app.

**Performance**: none; correctness + determinism only. (Discovery clones per source;
`refresh` is explicit/manual per ADR-0002 "freshness is manual" — never implicit.)

**Constraints**: static-parse discovery only (no template code, no trust — C-04/VI);
deterministic listing (same sources+pins → identical output); full-id namespacing;
no committed bailiff artifact (010 invariant); no repos-collector/selector template
(FR-008); glue only where copier cannot (C-11).

**Scale/Scope**: catalog CRUD + deterministic listing + validation gate + SKILL
flow + tests. NO DAG, NO multi-template execution (003), NO apm multiselect (007),
NO catalog publishing (008).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution **v2.1.0**. Initial gate: **PASS**.

| Principle | Gate | How this plan satisfies it |
|---|---|---|
| I — Skills + templates + minimal glue | PASS | One new `src/bailiff/catalog.py` module + `catalog` verbs on `scripts/bailiff.py`; the catalog is user config, not a tool artifact. Glue justified by a copier gap (copier has no catalog/multi-source concept — C-11). |
| II — Two-phase; agent judges, helpers execute | PASS | Discovery + listing + validation are deterministic, LLM-free, subprocess-testable. Selection (judgment) stays with the phase-1 agent; the gate validates the agent's pick mechanically. |
| III — Faithful, agent-free reproduce | PASS (unaffected) | Catalog holds sources, NOT reproduce pins; the reproduce pin stays in each project's answers file. `@ref` is a display/standardization override only (FR-007). Reproduce path untouched. |
| IV — Prefer CLI + static config; adapter only if used | PASS | Discovery stays static `copier.yml`/tree parsing (reuses `discovery.py`); no Jinja env, no `Template`/`Worker`. Adapter introduced ONLY if a real source forces `!include`/inheritance (C-04/Q3) — not here. |
| V — Determinism via pinning; trust by source | PASS | Discovery needs no trust (static, no code). `@ref`/pins are copier's; listing is deterministic. No trust written by catalog ops. |
| VI — Template-author contract at discovery | PASS | The listing surfaces `reproducible` (answers-file `.jinja`) + version resolvability per source; unusable sources reported, not silently included (FR-005) — enforcing the contract at catalog time. |
| VII — Hardening per-step (scaled) | PASS | DoD = deterministic-listing test + per-source-failure isolation test + validation-gate tests (valid/unknown/ambiguous) + idempotent CRUD tests + error surfacing (missing/malformed catalog). Unit tests for the new module. No adapter → no drift test. |
| VIII — Documented, dry-run-validated handoff | PASS (n/a-ish) | No new handoff format; catalog TOML is a documented plain file, listing is documented JSON. No pydantic/JSON-Schema. |

**Complexity deviations**: none. One new module + one new (minimal) dependency,
each justified by a concrete copier gap. ADR-0003's two-template machinery is
*removed* from the design, not added.

Post-design re-check (after Phase 1): **PASS** — the seam is a plain TOML file + the
existing static Discovery shape; no deprecated surface, no reproduce-path change.

## Project Structure

### Documentation (this feature)

```text
specs/002-catalog/
├── spec.md              # The catalog spec (+ ADR-0003 reconciliation)
├── plan.md              # This file
├── contracts/
│   └── catalog.md       # Phase 1 — catalog TOML shape + `catalog` verbs + listing JSON + validation gate
└── tasks.md             # Phase 2 (/speckit.tasks)
```

Phase-0 research is not re-generated: the load-bearing copier facts (static-parse
safety, PEP 440 tag filtering, `1 template = 1 repo`, runtime `--data catalog=`
render scope) are verified in ADR-0002/0003 and
`specs/001-bailiff-vertical-slice/research.md`. A data-model doc is unnecessary — the
entities (catalog file, source, listing, selection) are captured in the spec + the
contract.

### Source Code (repository root)

```text
src/bailiff/
├── catalog.py           # NEW: the catalog module — TOML read (tomllib) / write (tomli-w);
│                        #   load/save, add/remove/list sources, resolve pointers,
│                        #   build the deterministic listing (calls discovery.discover per source),
│                        #   full-id namespacing, validate_selection(full_ids) gate.
├── discovery.py         # REUSED unchanged — discover(source, ref) is the per-source parser.
├── errors.py            # EXTEND: add CatalogError (missing/malformed file, unknown/ambiguous id).
├── trust.py             # REUSED as the pattern for user-config path resolution (platformdirs/env).
└── runner.py            # unchanged (init/reproduce; 002 doesn't touch the render path).

scripts/bailiff.py         # EXTEND: add the `catalog` subcommand group
                         #   (init/list/add/remove/refresh/validate); dispatch to bailiff.catalog.
                         #   Reuse the existing argparse + error→exit (0/1/2/3) structure.

pyproject.toml           # EDIT: `uv add tomli-w`. (tomllib is stdlib.)

skills/bailiff/SKILL.md    # EXTEND: a catalog step before discovery/selection —
                         #   manage sources (add/list/remove), present the verified listing,
                         #   collect the user's pick, pass validated full-id(s) to init.
                         #   Selection is phase-1 judgment; discovery+validation are LLM-free.

tests/
├── conftest.py          # EXTEND: a multi-source catalog fixture (≥2 local git template repos +
│                        #   one unusable source: no PEP440 tag / no answers-file .jinja).
├── unit/
│   └── test_catalog.py  # NEW: load/save round-trip, add/remove idempotency + entry preservation,
│                        #   full-id namespacing + basename-default, listing determinism,
│                        #   validate_selection valid/unknown/ambiguous, TOML parse-error handling.
└── loop/
    ├── test_catalog_cli.py     # NEW: subprocess `catalog init/add/list/remove/refresh/validate`;
    │                           #   create-if-absent, per-source failure isolation, deterministic listing.
    └── test_catalog_smoke.py   # NEW (marked network): list a real published source; deselected by default.
```

**Structure Decision**: One new `src/bailiff/catalog.py` (the copier-gap glue: copier
has no multi-source/catalog concept), surfaced through new `catalog` verbs on the
existing `scripts/bailiff.py`, reusing `discovery.discover` verbatim for the per-source
parse and `trust.py`'s user-config-path pattern. No new engine, no template, no
adapter. The catalog is user config; nothing bailiff-authored enters a generated
project.

## Complexity Tracking

No constitutional violations. Additions: one module, one minimal dependency
(`tomli-w`), one SKILL step — each tied to a concrete copier gap (no catalog / no
multi-source concept, C-11). The design *removes* ADR-0003's repos-collector +
selector templates rather than building them. The one flagged sub-decision
(`tomli-w` vs `tomlkit` for comment-preservation) is documented in Technical
Context with its upgrade path; `tomli-w` chosen as the dependency-light default.
