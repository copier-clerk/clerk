# Implementation Plan: bailiff upgrade — explicit version upgrade + copier migrations

**Branch**: `006-upgrade` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-upgrade/spec.md`

## Summary

Add a `run_update` wrapper to `runner.py` and an `update` verb to
`scripts/bailiff.py`. For multi-layer projects, reuse spec 003's DAG — re-solved
against target versions — from `src/bailiff/ordering.py`. Surface migrations
(trust-gated, new format enforced at discovery), announce per-layer from→to
versions, and detect/report merge conflicts. copier owns the 3-way merge and
migration execution; bailiff adds only the DAG re-solution and the multi-layer loop
that copier cannot supply across templates.

No new module is added. The additions are: `runner.update` + `runner.update_many`
functions (analogous to `runner.init` / `runner.init_many`); a migration-format
check in `discovery.py`; and a new `update` verb in `scripts/bailiff.py`. The
conflict-detection helper (post-update tree scan) is the single novel piece not
already anticipated by prior specs.

Resolved planning decisions flagged for review:
- **Q-006a (conflict UX)**: post-update scan for `<<<<<<< HEAD` markers in
  destination tree. Simple, no copier-internals dependency. Exit 4 on conflict.
  `.rej` mode is a flag (`--conflict rej`).
- **Q-006b (new deps on upgrade)**: **refuse with a clear remediation message**,
  consistent with spec 003's dangling-edge policy. New layer must be added by the
  user before upgrading the template that depends on it.
- **Q-006c (`skip_tasks` vs migrations)**: defer verification to T-impl research.
  **Needs source verification** against copier 9.16 before implementing. If they
  are separate code paths, expose separately.
- **Q-006d (multi-layer `--vcs-ref`)**: single `--vcs-ref` applies to ALL layers
  in a homogeneous upgrade. Per-layer ref map is a future extension.
- **Q-006e (`conflict` param)**: expose as `--conflict inline|rej`; default
  `inline`.

## Technical Context

**Language/Version**: Python 3.11+ (`src/bailiff/` + `scripts/bailiff.py`).

**Primary Dependencies**: existing only — `copier>=9.16,<10` (`run_update` is in
the verified public surface, ADR-0001), `packaging`, `pyyaml`. No new dependency.

**copier API surface for upgrade** (`run_update` signature, verified 9.16):
```python
run_update(
    dst_path: str | Path = '.',
    data: dict[str, Any] | None = None,
    *,
    answers_file: Path | str | None = None,
    vcs_ref: str | VcsRef | None = None,     # target version (None = latest tag)
    settings: Settings | SettingsModel | None = None,
    defaults: bool = False,
    overwrite: bool = False,
    pretend: bool = False,
    quiet: bool = False,
    conflict: Literal['inline', 'rej'] = 'inline',
    context_lines: PositiveInt = 3,
    unsafe: bool = False,
    skip_tasks: bool = False,
    # … (other kwargs bailiff does not set)
) -> Worker
```

bailiff's canonical call: `run_update(dest, data=answers, answers_file=rel_answers,
vcs_ref=vcs_ref_or_none, defaults=True, overwrite=True, quiet=True,
conflict=conflict, pretend=pretend)`. Trust via `settings=` (not `unsafe=True`).

**Storage**: committed `.copier-answers*.yml` files are the upgrade state. After
upgrade, copier rewrites each layer's answers file with the new `_commit`. No
bailiff-authored artifact is written.

**Testing**: `pytest`, hermetic/offline via local git template fixtures. Reuse
and extend `tests/conftest.py` (multi-template fixtures from spec 003). New
fixtures: a template with a v1.0.0 → v1.1.0 bump adding a new file + a `_migrations`
entry; a template pair with a `depends_on` edge across versions; a template adding
a new dep in v1.1.0. Conflict fixture: v1.0.0 → v1.1.0 changes a line that the
project also edits locally. `mypy --strict` + `ruff` over `src/ tests/ scripts/`.

**Target Platform**: developer workstations + CI (macOS/Linux).

**Constraints**: copier owns the merge (C-11); new `_migrations` format enforced
at discovery (Constitution VI); trust-gates identical to `_tasks` (ADR-0001,
Constitution V); DAG re-solved at target versions for multi-layer (new dep visible);
N=1 uniform loop (spec 010); no brownfield path (no `.copier-answers.yml` → refuse).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution **v2.1.0**. Initial gate: **PASS**.

| Principle | Gate | How this plan satisfies it |
|---|---|---|
| I — Skills + templates + minimal glue | PASS | New glue = `runner.update`/`update_many` + discovery format-check + CLI verb. copier owns the merge. No new module; extends existing files. The DAG re-solution for multi-layer upgrade is the C-11-sanctioned coordination gap copier has no cross-template equivalent for. |
| II — Two-phase; agent judges, helpers execute | PASS | Upgrade is mechanical (announced versions → `run_update` per layer); the agent's role is selecting the target version and consenting to trust. The `update`/`update_many` path is LLM-free, subprocess-testable. |
| III — Faithful, agent-free, RECOMPUTED reproduce | PASS | Upgrade is the explicit, announced departure from pinned state. Reproduce path (spec 003) is unchanged. Constitution III distinguishes the two operations explicitly; this spec is the intentional upgrade side of that boundary. |
| IV — Prefer CLI + static config; adapter only if used | PASS | `run_update` is in copier's verified public surface (ADR-0001). Migration-format validation is a static `copier.yml` parse (same `discovery.py` approach). No `Template`/`Worker` adapter. |
| V — Determinism via pinning; trust by source | PASS | After upgrade the new `_commit` is the pin. Trust gates upgrade identically to init: `settings=` param, no `unsafe=True`. Untrusted source with migrations → `UntrustedSourceError` before calling `run_update`. |
| VI — Template-author contract at discovery | PASS | Discovery checks for the deprecated `before`/`after` dict form in `_migrations` and refuses (new format only). This is enforced at the upgrade discovery pre-check, not silently skipped. |
| VII — Hardening per-step (scaled) | PASS | DoD = per-layer trust-gate test; migration-format rejection test; conflict detection test; DAG re-solution test; N=1 no-regression; `mypy`/`ruff` clean. All in this spec's test suite. |
| VIII — Documented, dry-run-validated handoff | PASS | Upgrade run-spec documented in `contracts/upgrade.md`; `--pretend` is the dry-run gate (copier's own). No pydantic/JSON-Schema. |

**Complexity deviations**: none. The run_update wrapper is a direct parallel of
the existing init/reproduce wrappers (same error-translation, same trust guard);
the DAG re-resolution at target versions is the only genuinely new computation,
and it reuses the existing `ordering.py` functions. Conflict detection is a post-
update tree scan — one small helper.

Post-design re-check: **PASS** — the spec clarifies that two open questions
(Q-006a conflict UX, Q-006b new deps) are resolved in this plan and the two still
open (Q-006c skip_tasks/migrations, Q-006d multi-vcs-ref) are explicitly deferred
to research tasks (T002/T003).

## Project Structure

### Documentation (this feature)

```text
specs/006-upgrade/
├── spec.md              # The upgrade spec
├── plan.md              # This file
├── contracts/
│   └── upgrade.md       # run_update invocation, migration format + trust gating,
│                        #   multi-layer update ordering, conflict surfacing, exit codes
└── tasks.md             # Task list (/speckit.tasks)
```

### Source Code (repository root)

```text
src/bailiff/
├── runner.py            # EXTEND: update(dest, *, vcs_ref, answers_file, today,
│                        #   pretend, conflict) — single-layer run_update wrapper
│                        #   (mirrors init; same trust + format pre-checks; translate
│                        #   copier errors; post-update conflict scan);
│                        #   update_many(dest, *, vcs_ref, today, pretend, conflict)
│                        #   — multi-layer: re-discover at target versions, rebuild
│                        #   DAG via ordering.layer_plan, loop update() per layer in
│                        #   order; refuse if upgraded template declares new dep not
│                        #   in project (Q-006b: dangling-edge → refuse with message).
├── discovery.py         # EXTEND: _check_migrations_format(raw) — static check
│                        #   that _migrations entries use the new format (no
│                        #   before/after dict form); called from the upgrade
│                        #   pre-check (not from init/reproduce, where migrations
│                        #   don't run); raises DeprecatedMigrationFormatError.
├── ordering.py          # REUSED unchanged — layer_plan / build_dag / topo_sort
│                        #   called from update_many with target-version discoveries.
└── errors.py            # EXTEND: DeprecatedMigrationFormatError(BailiffError) —
│                        #   deprecated _migrations format detected; MergeConflictError
│                        #   (BailiffError, exit 4) — lists conflicted paths;
│                        #   DowngradeError(BailiffError) — target < current version.

scripts/bailiff.py         # EXTEND: add 'update' verb — parses dest (required),
                         #   optional --vcs-ref, --pretend, --conflict inline|rej,
                         #   --skip-tasks; maps to runner.update / runner.update_many
                         #   based on how many answers files are present. Exit-code
                         #   map: 0 ok; 1 BailiffError/OrderingError; 2 argparse; 3
                         #   UntrustedSourceError; 4 MergeConflictError.

skills/bailiff/SKILL.md    # EXTEND: upgrade/migration sub-procedure (end-state
                         #   component table, end-state-components.md row for spec
                         #   006): inspect current _commit vs available versions;
                         #   announce from→to; obtain trust consent if needed;
                         #   run scripts/bailiff.py update. Document migration
                         #   awareness (migrations are copier-run, trust-gated).

tests/
├── conftest.py          # EXTEND: upgrade-specific fixtures — single-layer fixture
│                        #   bumped v1.0.0→v1.1.0 (new file + migration entry);
│                        #   fixture with deprecated _migrations format; pair with
│                        #   depends_on edge across versions; pair where v1.1.0 adds
│                        #   new dep; conflict fixture (template + local edit on same
│                        #   line).
├── unit/
│   └── test_update_discovery.py  # NEW: migration format check — new format accepted;
│                        #   deprecated form raises DeprecatedMigrationFormatError;
│                        #   downgrade detection.
└── loop/
    ├── test_update_single.py     # NEW: US1 — single-layer upgrade: answers file
    │                             #   updated; new file present; skip if already at
    │                             #   target; trust-gate (untrusted → exit 3);
    │                             #   downgrade refused.
    ├── test_update_migration.py  # NEW: US2 — migration fires at correct version
    │                             #   crossing; does not fire outside window; deprecated
    │                             #   format refused.
    ├── test_update_multi.py      # NEW: US3 — multi-layer ordered upgrade; both
    │                             #   answers files updated; dependency order correct;
    │                             #   new dep in upgraded template refused with message
    │                             #   (Q-006b resolution).
    ├── test_update_conflict.py   # NEW: US4 — conflict markers detected; exit 4;
    │                             #   paths named in output; --conflict rej mode.
    └── test_update_pretend.py    # NEW: --pretend writes nothing; reports what would
                                  #   change; N=1 via multi path no-regression.
```

**Structure Decision**: no new module; extend existing `runner.py` (two new
functions), `discovery.py` (one format-check helper), `errors.py` (two new error
types), and `scripts/bailiff.py` (one new verb). All analogous to existing patterns.
The `_check_migrations_format` helper in discovery is ~10 lines; justified because
discovery is already the static parse layer and the format check is a static
`copier.yml` parse (no copier runtime call needed).

## Complexity Tracking

No constitutional violations. Scope is tightly bounded: one new CLI verb + two new
runner functions + one discovery helper + two new error types. All follow existing
patterns exactly. The only genuinely novel piece (conflict detection via post-update
marker scan) is a single function < 20 lines. Two open questions (Q-006c, Q-006d)
require research tasks before implementation; they cannot change the structure, only
the number of flags.
