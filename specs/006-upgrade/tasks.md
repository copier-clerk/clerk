---
description: "Task list for clerk upgrade — explicit version upgrade + copier migrations (spec 006)"
---

# Tasks: clerk upgrade — explicit version upgrade + copier migrations

**Input**: Design documents from `specs/006-upgrade/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[contracts/upgrade.md](./contracts/upgrade.md),
[constitution](../../.specify/memory/constitution.md) v2.1.0

**Hard dependency**: spec 003 MUST be implemented before this spec
(`src/clerk/ordering.py`, `runner.init_many`/`reproduce_many`, and the
multi-template fixtures in `tests/conftest.py` are reused here).

**Tests**: INCLUDED. Constitution VII makes per-step hardening (trust-gate,
migration format rejection, conflict detection, DAG re-solution, N=1 no-regression)
part of this spec's definition-of-done.

**Organization**: grouped by user story (US1–US5 from spec.md), preceded by
research tasks for the two open questions that must resolve before implementation.

## Design decisions this task list assumes (resolved; flagged for review)

- Q-006a (conflict UX): post-update scan for `<<<<<<< ` markers (inline) or
  `.rej` files. `MergeConflictError` → exit 4.
- Q-006b (new deps on upgrade): refuse with clear remediation message, same as
  spec 003's dangling-edge policy. `OrderingError` → exit 1.
- Q-006d (multi `--vcs-ref`): one ref applies to all layers; per-layer map deferred.
- Q-006e (`conflict` flag): expose as `--conflict inline|rej`; default `inline`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no incomplete-task dependency)
- Exact file paths included

---

## Phase 0: Research (blocks implementation phases)

- [ ] T001 Verify: does copier 9.16 `run_update` suppress `_migrations` when
  `skip_tasks=True`? Read `copier/_main.py` Worker's `run_update` / `run_update_internal`
  method: look for whether `migration_tasks(stage, …)` is called inside the same
  `skip_tasks` guard as `_tasks`, or unconditionally. Record the finding in a
  comment on this task. **Decision gates T011 (flag design) and `scripts/clerk.py`
  `update` verb.**

- [ ] T002 Verify: what does `run_update` return / raise when conflicts are present
  in `conflict='inline'` mode — does it raise, return with a flag, or just write
  markers and return a `Worker`? Check `copier/_main.py` for any
  `ConflictError`/exception or result field. **Decision gates T012 (conflict
  detection implementation).** Also confirm `.rej` file location (same dir as the
  source file, or `_conflict_files` attribute on `Worker`?).

**Checkpoint**: T001 and T002 answered; findings recorded; T003 onwards can proceed.

---

## Phase 1: Errors + discovery extension

- [ ] T003 Add to `src/clerk/errors.py`:
  - `DeprecatedMigrationFormatError(ClerkError)` — deprecated `_migrations` format
    detected; message names the template source and the offending entry.
  - `MergeConflictError(ClerkError)` — conflict markers or `.rej` files present;
    `conflicted_paths: list[str]` attribute; message lists them.
  - `DowngradeError(ClerkError)` — target version is older than current `_commit`
    version; message names from/to.

- [ ] T004 Extend `src/clerk/discovery.py`:
  Add `_check_migrations_format(raw: dict) -> None` — static check: iterate
  `raw.get("_migrations", [])`, raise `DeprecatedMigrationFormatError` if any entry
  is a dict containing `"before"` or `"after"` as keys. Also add `has_migrations:
  bool` to `Discovery` dataclass (True if `_raw_config.get("_migrations")`
  is non-empty) and populate it in `_describe()`. Update `to_dict()`.

**Checkpoint**: `mypy` clean on `errors.py` + `discovery.py`; `DeprecatedMigrationFormatError`
raises correctly on a hand-crafted deprecated dict.

---

## Phase 2: Fixtures (parallelizable with Phase 1)

- [ ] T005 [P] Extend `tests/conftest.py` with upgrade fixtures (local git repos
  with two tagged versions):
  - `single_upgrade_fixture`: template at v1.0.0 (one file); v1.1.0 adds a new
    file + one `_migrations` entry (`command: "touch .migrated"`, `version: "v1.1.0"`).
  - `deprecated_migrations_fixture`: template at v1.0.0 with the deprecated
    `{version, before, after}` `_migrations` form in `copier.yml`.
  - `multi_upgrade_fixture`: pair A (no deps) + B (`depends_on: A`); both v1.0.0
    and v1.1.0 tagged.
  - `new_dep_upgrade_fixture`: single template B at v1.0.0 (no deps); v1.1.0 adds
    `depends_on: [C]` where C is a separate fixture with no committed project layer.
  - `conflict_upgrade_fixture`: template at v1.0.0 renders `hello.txt` with content
    "line1\n"; v1.1.0 changes `hello.txt` to "changed_line1\n"; project also has
    `hello.txt` with "local_edit\n".
  All fixtures ship the `{{ _copier_conf.answers_file }}.jinja` (reproducible). Use
  the existing multi-template fixture builder from spec 003 (reuse its helpers).

**Checkpoint**: all fixtures importable; `pytest --collect-only` shows them.

---

## Phase 3: US1 — single-layer upgrade (runner.update)

- [ ] T006 [US1] Add `runner.update(dest, *, vcs_ref, answers_file, today,
  pretend, conflict)` to `src/clerk/runner.py`:
  - Pre-checks: format-check migrations (`_check_migrations_format`); trust pre-check
    (if `has_migrations` or `has_tasks` and source untrusted → `UntrustedSourceError`);
    downgrade check (if target version < current `_commit` version →  `DowngradeError`);
    "already at target" check → return early with a message.
  - Call `run_update(dest, data=data, answers_file=rel_answers, vcs_ref=vcs_ref_or_none,
    defaults=True, overwrite=True, quiet=True, conflict=conflict, pretend=pretend)`.
  - Post-update conflict scan (per T002 findings): if `conflict='inline'`, scan
    dest tree for files containing `<<<<<<< `; if `conflict='rej'`, find `.rej`
    files. If found, raise `MergeConflictError(conflicted_paths=[…])`.
  - Return `RunResult` (reuse existing dataclass; add `upgraded_to: str | None` field
    or embed in the `ref` field — decide at implementation).
  - Translate copier errors via `_translate` (same as init/reproduce).

- [ ] T007 [US1] `tests/loop/test_update_single.py` (NEW):
  - US1-AS1: single fixture v1.0.0 → v1.1.0; assert new file present; answers file
    `_commit` updated to v1.1.0 sha.
  - US1-AS2: `--vcs-ref v1.1.0` explicit; same result.
  - Already-at-target: upgrade to the current version → exit 0, nothing changed.
  - Untrusted-source + migrations → `UntrustedSourceError` raised; `run_update` NOT
    called (assert via mock or absence of filesystem change).
  - Downgrade → `DowngradeError`; nothing written.

**Checkpoint**: `runner.update` works for single-layer; trust + downgrade guards fire.

---

## Phase 4: US2 — migration version crossing

- [ ] T008 [US2] `tests/loop/test_update_migration.py` (NEW):
  - US2-AS1: fixture v1.0.0 → v1.1.0; `_migrations` entry with `version: v1.1.0`;
    assert migration ran (`.migrated` sentinel file present).
  - US2-AS2: fixture v1.1.0 → v1.2.0; no migration entry at v1.2.0; assert `.migrated`
    NOT freshly created (idempotent check — file may exist from prior upgrade, but
    migration task was not re-run).
  - US2-AS3: deprecated `_migrations` format → `DeprecatedMigrationFormatError` raised
    before `run_update`; nothing written.

**Checkpoint**: migration fires at the correct version crossing; deprecated format
rejected.

---

## Phase 5: US3 — multi-layer upgrade (runner.update_many)

- [ ] T009 [US3] Add `runner.update_many(dest, *, vcs_ref, today, pretend, conflict)`
  to `src/clerk/runner.py`:
  1. `enumerate_answers_files(dest)` → committed layers.
  2. For each, read `_src_path` (+ `_commit` for downgrade check).
  3. Discover each template at the **target version** (`vcs_ref` or latest).
  4. Check `_check_migrations_format` + trust pre-check for each layer.
  5. Rebuild DAG via `ordering.build_dag(records, edges_by_basename)` +
     `ordering.topo_sort` using the target-version discoveries. If the rebuilt
     DAG introduces a dangling edge (new dep not in project) → `OrderingError`
     with remediation message (Q-006b resolution).
  6. Emit the per-layer upgrade announcements to stdout.
  7. Loop `runner.update(dest, …, answers_file=layer_af)` per layer in order.
  8. Return `list[RunResult]`.
  Single-layer (`len(answers_files)==1`) routes through this same path (N=1 uniform loop).

- [ ] T010 [US3] `tests/loop/test_update_multi.py` (NEW):
  - US3-AS1: `multi_upgrade_fixture` both layers v1.0.0 → v1.1.0; assert B upgraded
    after A (answers file mtimes or _commit order); both answers files updated.
  - US3-AS2: `new_dep_upgrade_fixture` — upgraded B v1.1.0 declares `depends_on: C`
    which is not in project → `OrderingError` with remediation message; nothing written.
  - N=1 via multi path: single-layer project through `update_many` → same result as
    `update` (no regression).

**Checkpoint**: multi-layer upgrade in order; new-dep refused; N=1 unaffected.

---

## Phase 6: US4 — conflict detection

- [ ] T011 [US4] `tests/loop/test_update_conflict.py` (NEW):
  - US4-AS1: `conflict_upgrade_fixture` with `conflict='inline'`; assert
    `MergeConflictError` raised; exit 4; conflicted path `hello.txt` named in
    exception; inline markers present in file.
  - US4-AS2: same fixture with `conflict='rej'`; assert `MergeConflictError` raised;
    `hello.txt.rej` present.

**Checkpoint**: conflicts detected in both modes; exit 4; paths named.

---

## Phase 7: US5 + pretend mode

- [ ] T012 [P] [US5] (covered by T010 US3-AS2 above; no additional task needed
  unless Q-006b is revised to warn-and-continue — re-evaluate at planning review).

- [ ] T013 [P] `tests/loop/test_update_pretend.py` (NEW):
  - `--pretend` on `single_upgrade_fixture`: no new file written; return `RunResult`
    with `pretend=True`.
  - `--pretend` on `multi_upgrade_fixture`: no answers files modified; announcements
    printed.
  - N=1 pretend regression check.

**Checkpoint**: pretend mode writes nothing.

---

## Phase 8: CLI surface + SKILL

- [ ] T014 Wire the `update` verb into `scripts/clerk.py`:
  - Arguments: `dest` (required positional); `--vcs-ref` (optional); `--pretend`
    (flag); `--conflict inline|rej` (default `inline`); `--skip-tasks` (flag,
    gated on T001 finding — if `skip_tasks` also suppresses migrations, document
    and add `--skip-migrations` separately if needed).
  - Route: count `.copier-answers*.yml` files in `dest`; call `runner.update_many`
    (handles N=1 and N>1 uniformly).
  - Exit-code map: 0 ok; 1 `ClerkError`/`OrderingError`/`DeprecatedMigrationFormatError`/
    `DowngradeError`; 2 argparse; 3 `UntrustedSourceError`; 4 `MergeConflictError`.
  - Print per-layer announcements (from→to) and results.

- [ ] T015 [P] Extend `skills/clerk/SKILL.md`:
  Document the upgrade/migration sub-procedure (the end-state component from
  `docs/architecture/end-state-components.md` for spec 006):
  - Pre-upgrade: inspect current `_commit` (from answers file) vs available tags
    (via `scripts/clerk.py discover`); announce from→to; check trust; confirm
    with user.
  - Run: `uv run scripts/clerk.py update <dest> [--vcs-ref <tag>] [--pretend]`.
  - Post-upgrade: surface migration effects (files changed, migrations run); resolve
    any conflicts named in exit-4 output.
  - Note: deprecated `_migrations` format refused at discovery (point template authors
    to the new format in contracts/upgrade.md).

**Checkpoint**: `uv run scripts/clerk.py update --help` works; SKILL documents the flow.

---

## Phase 9: Gate + closeout

- [ ] T016 Full gate on the branch: `uv run ruff check src/ tests/ scripts/ &&
  uv run ruff format --check src/ tests/ scripts/ && uv run mypy && uv run pytest -q`.
  Confirm 001/010/002/003 tests still pass (NO regression — esp. single-template
  init/reproduce/multi-layer). Run `-m network` if reachable, else note untested.

- [ ] T017 Update `.specify/memory/roadmap.md`: mark spec 006 `planned → implemented`
  with completion note (run_update wrapper; migration format enforcement; DAG re-
  solved at target versions; conflict detection; Q-006a/b resolved, Q-006c/d
  resolved during implementation).

- [ ] T018 Update `README.md`: brief `## Upgrade` note — upgrade from one template
  version to another via `scripts/clerk.py update`; version-crossing migrations
  handled by copier; multi-layer upgrade in dependency order. Open PR.

---

## Dependencies & parallelism

- **Research T001–T002** (Phase 0) block T006 (conflict scan implementation), T014
  (skip_tasks flag design).
- **Phase 1 errors/discovery (T003–T004)** can run in parallel with **Phase 2
  fixtures (T005)**.
- **Phase 3 (T006–T007)** requires T003/T004 (errors + format check).
- **Phase 4 (T008)** requires T006 (runner.update) + T005 (fixtures).
- **Phase 5 (T009–T010)** requires T006 (runner.update) + T005 + `ordering.py`
  (spec 003, hard dependency).
- **Phase 6 (T011)** requires T006 + T005 (conflict fixture).
- **T012 (US5)** is covered by T010; covered if Q-006b unchanged.
- **T013 (pretend)** requires T006/T009; can run parallel to T011.
- **Phase 8 CLI (T014–T015)**: T014 requires Phases 3–6 complete; T015 is
  parallelizable with T014.
- **Phase 9 (T016–T018)**: closeout; T017/T018 docs can run parallel to late code.

## Definition of done (maps to spec Success Criteria)

- SC-001 — single-layer upgrade; answers file updated (T006/T007).
- SC-002 — migration fires at correct version crossing; deprecated form refused
  (T004/T008).
- SC-003 — multi-layer ordered upgrade; both answers files updated; new-dep refused
  (T009/T010).
- SC-004 — conflict exit 4; named paths; rej mode (T011).
- SC-005 — untrusted source exit 3 before run_update (T007 US1-AS3).
- SC-006 — N=1 via multi path equals single path; no regression (T010/T013/T016).
- SC-007 — pretend writes nothing; reports what would change (T013).
