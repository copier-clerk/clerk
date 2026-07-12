# Implementation Plan: clerk global per-template defaults

**Branch**: `004-defaults` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-defaults/spec.md`

## Summary

Add a `src/clerk/defaults.py` module (mirroring `catalog.py` in structure:
platformdirs path resolution, env override) and extend `runner.init` + `runner.init_many`
to load, filter, and pass `user_defaults=` to each `copier run_copy` call. The entire
feature is approximately one new module + small additions to two existing functions.

No new dependency: PyYAML is already a project dependency (`yaml.safe_load` used in
`runner.py`, `discovery.py`, `trust.py`); `copier`'s `user_defaults=` parameter is
already part of the public `run_copy` API in copier ≥9.16 (C-04, verified). The
`settings.yml` fallback uses `copier`'s own `load_settings()` (best-effort, degrades
gracefully).

Resolved planning decisions (flagged for review):
- **File format** = YAML at `~/.config/clerk/defaults.yml` — aligned with ADR-0005
  and clerk's other YAML configs (Q-004a: no deviation from ADR).
- **`CLERK_DEFAULTS_PATH` on nonexistent file** = `DefaultsError` (explicit override
  silently no-oping is surprising) — Q-004c.
- **`settings.yml` fallback** = best-effort (graceful degradation on `load_settings`
  failure) — Q-004b.
- **Hidden question exclusion** = SHOULD (not MUST); filtering `when:false` keys
  from `user_defaults` avoids confusion but is not safety-critical — Q-004d.

## Technical Context

**Language/Version**: Python 3.11+ (`src/clerk/` + `scripts/clerk.py`).

**Primary Dependencies**: no new dependencies. `pyyaml` (already a project dependency),
`platformdirs` (already used by `catalog.py`), `copier>=9.16` (`user_defaults=` in `run_copy`).

**Storage**: `~/.config/clerk/defaults.yml` (user-side config; NEVER written into
the generated project — spec 010 invariant). The `discovery.Discovery.questions` list
already carries `secret` and `when`-condition metadata for key filtering.

**Testing**: `pytest`, hermetic/offline. Template fixtures can be the same as 003's
(reuse `conftest.py`). Need a small fixture that marks a question `secret: true`.
`mypy --strict` + `ruff` over `src/ tests/ scripts/`.

**Target Platform**: developer workstations + CI (macOS/Linux).

**Project Type**: bundled script + `src/clerk/` package. No published app.

**Performance**: none; the defaults file is tiny; the load + filter is <1 ms.

**Constraints**: no break to the precedence ladder (`user_defaults=` not `data=`);
never pre-fill secret questions; no clerk file committed to the project; YAML format;
env override; best-effort `settings.yml` fold; per-layer independence in multi path.

**Scale/Scope**: one new module + two function extensions + tests. The multi-template
path (spec 003) MUST be available for the per-layer test (US2); this spec depends on
003.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution **v2.1.0**. Initial gate: **PASS**.

| Principle | Gate | How this plan satisfies it |
|---|---|---|
| I — Skills + templates + minimal glue | PASS | One new `defaults.py` (≈50 LOC: load, filter, merge). No new copier surface — `user_defaults=` is part of `run_copy`'s existing public API. No template change, no adapter, no new CLI verb. Justified by C-11: copier's `settings.yml defaults:` is flat/global with no per-template scoping — the filtering step is a genuine gap clerk fills. |
| II — Two-phase; agent judges, helpers execute | PASS | Defaults loading + key selection is deterministic, LLM-free, fully hermetic-testable. The agent's only role is collecting the explicit answers to place in `data=`; the defaults selection is a pure function of the template's question list and the user's config file. |
| III — Faithful, agent-free, recomputed reproduce | PASS | User defaults flow into the answers file as normal copier answers and are replayed faithfully at reproduce via `recopy --vcs-ref=:current:`. No new reproduce mechanic. The defaults file is user-side config; the project's committed answers file is the single source of reproduce truth (unchanged). |
| IV — Prefer CLI + static config; contain deprecated surface | PASS | `user_defaults=` is a documented parameter of `run_copy` (public API, not deprecated). Key selection reuses the `discovery.Discovery.questions` list already parsed statically. No `Template`/`Worker` adapter needed. |
| V — Determinism via pinning; trust by source | PASS | User defaults are soft-pre-filled and captured in the committed answers file, so reproduce replays the actual answered values — not the defaults file. The defaults file can change between runs without affecting reproduce (the answers file is pinned). Trust semantics are unchanged. |
| VI — Template-author contract at discovery | PASS | `secret: true` is statically discoverable from `copier.yml` (part of `discovery.Question`). The key-selection step enforces that secret questions are never pre-filled (FR-004). No template contract change. |
| VII — Hardening per-step | PASS | DoD = precedence test (`data=` wins over `user_defaults=`; `user_defaults=` wins over `copier.yml` default); secret-exclusion test; missing-file no-op test; malformed YAML error test; per-layer independence test (US2); `settings.yml` fallback test (US3). Unit tests for `defaults.py`; integration via `runner.init` tests. |
| VIII — Documented, dry-run-validated handoff | PASS | The defaults dict merges into the existing `user_defaults=` parameter at the `run_copy` seam — no new handoff format, no new schema. The `contracts/defaults.md` documents the YAML shape and injection point. Validation unchanged: copier's `--pretend` preflight (FR-008) now runs with the same `user_defaults` as the real init. |

**Complexity deviations**: none. This is the defaults capability the roadmap reserved
for 004 (C-11 / ADR-0005) — introduced now with two consumers (single path + multi
path), not speculatively. No new dependency.

**Constitution genuine challenge — Principle I**: could copier's native `settings.yml
defaults:` (with a flat global dict) be sufficient? For single-template use yes, but
for multi-template (003) it fails: two templates with the same question name would
both see the global default, which is correct, but there is no way to give DIFFERENT
defaults to two templates for a same-named key. Per-template scoping via key
selection is the genuine gap. The C-11 check passes.

## Project Structure

### Documentation (this feature)

```text
specs/004-defaults/
├── spec.md              # The defaults spec
├── plan.md              # This file
├── contracts/
│   └── defaults.md      # YAML shape, key-selection algorithm, injection point,
│                        #   precedence ladder, settings.yml fallback, exit codes
└── tasks.md             # Dependency-ordered tasks
```

### Source Code (repository root)

```text
src/clerk/
├── defaults.py          # NEW: load(path) → dict; select_keys(defaults, questions) → dict;
│                        #   defaults_path() via platformdirs + CLERK_DEFAULTS_PATH env;
│                        #   fold_settings_defaults(user_defaults) → merged dict (best-effort).
│                        #   DefaultsError(ClerkError) lives here or in errors.py (task decides).
├── runner.py            # EXTEND: init() and init_many() each call
│                        #   defaults.select_keys(loaded_defaults, disc.questions) per template
│                        #   and pass the result as user_defaults= to run_copy. The load step
│                        #   is once per init call; the select step is once per template layer.
├── errors.py            # EXTEND: add DefaultsError(ClerkError) — malformed YAML or
│                        #   nonexistent explicit-override path.
└── discovery.py         # UNCHANGED — Question.secret already present; questions list reused.

scripts/clerk.py         # NO change needed at the CLI surface: defaults injection is transparent
                         #   to the caller (happens inside runner.init/init_many). A future
                         #   `clerk defaults` verb (manage the file) is out of scope (YAGNI).

skills/clerk/SKILL.md    # EXTEND: document that clerk pre-fills soft defaults from
                         #   ~/.config/clerk/defaults.yml; note that secret questions are
                         #   never defaulted; point at specs/004-defaults/contracts/defaults.md.

tests/
├── conftest.py          # EXTEND: add a fixture variant with a secret question (`secret: true`);
│                        #   add a helper to write a temp defaults.yml at a path and return it.
├── unit/
│   └── test_defaults.py # NEW: load() missing file → empty dict; malformed YAML → DefaultsError;
│                        #   CLERK_DEFAULTS_PATH pointing at nonexistent file → DefaultsError;
│                        #   select_keys() excludes secrets; select_keys() excludes keys not in
│                        #   questions; select_keys() includes non-secret matching keys;
│                        #   fold_settings_defaults() merges correctly (yaml wins on collision);
│                        #   fold_settings_defaults() fails gracefully (no error if load_settings
│                        #   raises).
└── loop/
    ├── test_defaults_init.py       # NEW: US1 — pre-fill single-template init; precedence
    │                               #   (data= wins); secret not pre-filled; missing file no-op.
    └── test_defaults_multi.py      # NEW: US2 — per-layer defaults in init_many; threaded
                                    #   answer wins over defaults; per-layer independence.
```

**Structure Decision**: `defaults.py` is a separate module (not inlined into
`runner.py`) for the same reason `catalog.py` is separate — it owns a user-config
concern (path resolution, load, YAML parse, key selection, settings fold) that is
orthogonal to the execution concern of `runner.py`. Size is small (≈50–80 LOC), but
the separation keeps `runner.py` focused on driving copier.

`DefaultsError` could live in `errors.py` (consistent with `CatalogError`) or in
`defaults.py` (co-located with the code that raises it). Lean: `errors.py` for
consistency; the task decides.

## Complexity Tracking

No constitutional violations. One new module of ≈50–80 LOC + small runner.py
extensions, tied to the genuine copier gap (no per-template scoping in
`settings.yml defaults:`). No new dependency (PyYAML already imported). Four flagged
open questions resolved with defaults + rationale; each is a small, easily-revised
decision.
