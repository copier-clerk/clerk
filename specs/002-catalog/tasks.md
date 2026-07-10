---
description: "Task list for clerk catalog — user-owned sources, runtime discovery + injection (spec 002)"
---

# Tasks: clerk catalog — user-owned sources, runtime discovery + injection

**Input**: Design documents from `specs/002-catalog/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[contracts/catalog.md](./contracts/catalog.md),
[constitution](../../.specify/memory/constitution.md) v2.1.0

**Tests**: INCLUDED. Constitution VII makes per-step hardening (deterministic
listing, per-source failure isolation, validation-gate correctness, idempotent CRUD,
error surfacing) part of this spec's definition-of-done.

**Organization**: grouped by user story (US1–US3 from spec.md).

## Design decisions this task list assumes (resolved with the user)

- Catalog file = **TOML** (read: stdlib `tomllib`; write: **`tomli-w`**, added via
  `uv add`; does not preserve comments — acceptable, `tomlkit` is the upgrade path if
  ever needed).
- Catalog pointers = **local files only** for 002 (remote/shared = 008).
- Full-id namespace = **explicit per-pointer `name`, defaulting to a sanitized
  basename**.
- No repos-collector template, no selector template (ADR-0003 two-template flow
  superseded — reconciled in spec.md + this PR). Selection stays with the phase-1
  agent; `catalog validate` is the deterministic gate.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no incomplete-task dependency)
- Exact file paths included

---

## Phase 1: Setup (dependency + module skeleton)

- [ ] T001 Add the TOML writer: `uv add tomli-w`. Confirm `tomllib` (stdlib) reads and `tomli_w` writes; `uv sync` clean. Decide + document the catalog default path in `src/clerk/catalog.py` docstring: `user_config_path("clerk", appauthor=False)/catalog.toml` with a `CLERK_CATALOG_PATH` env override (mirror `trust.py`'s `settings_path()` pattern) and a `--catalog PATH` CLI override.
- [ ] T002 Create `src/clerk/catalog.py` skeleton: module docstring (catalog = user-owned TOML of sources, static/deterministic listing, no template code, no committed artifact), imports, and the `catalog_path()` resolver (env → platformdirs default). Add `CatalogError` to `src/clerk/errors.py` (missing/malformed file; unknown/ambiguous full-id).
- [ ] T003 [P] Extend `tests/conftest.py` with a **multi-source catalog fixture**: a builder that writes a `catalog.toml` naming ≥2 usable local git template repos (reuse the existing local-git-template fixture builder) plus one **unusable** source (a repo with no PEP 440 tag AND/OR no answers-file `.jinja`). Return the catalog path + the source paths.

**Checkpoint**: `uv sync` clean; `import clerk.catalog` works; `mypy` clean on the skeleton.

---

## Phase 2: Catalog file model + CRUD (US2 — manage the catalog)

**Purpose**: create-if-absent, list, add, remove — idempotent, entry-preserving.

- [ ] T004 [US2] In `catalog.py`: `load(path)` (tomllib read → in-memory model; missing file → empty model, NOT an error for read-with-default; malformed TOML → `CatalogError` with a clear message, never silently clobbered) and `save(path, model)` (tomli-w write; `mkdir -p` parent like `trust._write_raw`). Model = named pointers each with a `sources` list of `(locator, ref|None)`.
- [ ] T005 [US2] In `catalog.py`: `add_source(path, source, name=None)` — create file if absent; resolve pointer by `name` (default pointer); parse optional `@ref`; idempotent (present source → no-op, no duplicate); preserve other pointers/sources. `remove_source(path, source, name=None)` — idempotent removal, preserve the rest. `list_sources(path)` — return the model for display.
- [ ] T006 [US2] In `catalog.py`: `pointer_name(...)` helper — explicit name wins; else sanitize the file/source basename to a namespace token (documented rule: lowercase, non-alnum→`-`, trim). Used for full-id construction.
- [ ] T007 [P] [US2] `tests/unit/test_catalog.py` (CRUD half): load/save round-trip; add creates-if-absent; add idempotent + no duplicate; add/remove preserve unrelated pointers+sources; remove idempotent; malformed TOML → `CatalogError`; `@ref` parsed and retained but flagged as non-pin.

**Checkpoint**: `uv run pytest tests/unit/test_catalog.py -k crud` green; CRUD is idempotent and non-destructive.

---

## Phase 3: Deterministic listing (US1 — see the templates)

**Purpose**: derive the verified template listing from sources, statically.

- [ ] T008 [US1] In `catalog.py`: `build_listing(path)` — for each pointer, for each source, call `discovery.discover(source, ref)` (reused unchanged); construct `full_id = <pointer-name>/<repo-basename>`; collect `versions/reproducible/has_tasks/questions-keys`. A source that raises `DiscoveryError` (no PEP440 tag, bad copier.yml, unreachable) OR is `reproducible: false` is placed in `unusable` with the reason — it MUST NOT abort the whole listing (FR-005). Output matches contracts/catalog.md JSON shape.
- [ ] T009 [US1] Ensure the listing is **deterministic**: stable ordering (pointers in file order; templates sorted by full-id; versions oldest→newest as `list_versions` already returns); no timestamps/absolute-temp-paths in the emitted structure. Add a `to_dict()`/JSON serializer.
- [ ] T010 [P] [US1] `tests/unit/test_catalog.py` (listing half): a 2-usable-+1-unusable fixture yields both usable templates under their full-ids with correct metadata, and the unusable source under `unusable` with a reason; **determinism** assertion — `build_listing` twice → identical dict; full-id namespacing correct (basename default + explicit name).

**Checkpoint**: `uv run pytest tests/unit/test_catalog.py` green; listing deterministic and per-source-failure-isolated.

---

## Phase 4: Selection-validation gate (US3 — safe selection)

**Purpose**: the deterministic gate that makes agent-driven selection safe.

- [ ] T011 [US3] In `catalog.py`: `validate_selection(path, full_ids)` — build the listing, accept only ids present among usable templates; unknown id → `CatalogError` naming the valid ids; a **bare** name matching >1 catalog → `CatalogError` "ambiguous, use full-id". Returns the resolved template records for accepted ids. No LLM, no network beyond the discovery the listing already does.
- [ ] T012 [P] [US3] `tests/unit/test_catalog.py` (validation half): valid full-id accepted; unknown full-id refused (message lists valid ids); bare name that is unambiguous — decide + test the documented behavior (accept iff exactly one match, else refuse); bare name ambiguous across two catalogs → refused; an id pointing at an `unusable` source → refused (can't select what can't be used).

**Checkpoint**: `uv run pytest tests/unit/test_catalog.py -k valid` green; gate correct for valid/unknown/ambiguous/unusable.

---

## Phase 5: CLI surface (wire `catalog` verbs onto scripts/clerk.py)

- [ ] T013 Extend `scripts/clerk.py`: add a `catalog` subparser group with `init`, `add <source> [--name]`, `remove <source> [--name]`, `list [--json]`, `refresh`, `validate <full-id>...`; all accept `--catalog PATH`. Dispatch to `clerk.catalog`. Reuse the existing error→exit mapping (0 ok / 1 CatalogError|ClerkError / 2 usage). Human table for `list` by default, `--json` for the machine shape.
- [ ] T014 [P] `tests/loop/test_catalog_cli.py` (NEW): subprocess-drive the verbs against the fixture catalog — `init` create-if-absent; `add` on a no-file machine creates it; `add`/`remove` idempotent; `list`/`list --json` shape + determinism (run twice, diff-clean); per-source failure isolation (one bad source, others still list); `validate` exit codes (0 valid / 1 unknown / 1 ambiguous). Use `--catalog <tmp>` to stay hermetic; no writes to the real user config.
- [ ] T015 [P] `tests/loop/test_catalog_smoke.py` (NEW, marked `network`): a `--catalog` pointing at `copier-clerk/clerk-template-example`; `catalog list` shows it usable with `v1.0.0`. Marked `-m network`, deselected by default.

**Checkpoint**: `uv run pytest -q` green (hermetic); all `catalog` verbs behave per contract.

---

## Phase 6: SKILL flow (US2/US1 — the agent uses the catalog)

- [ ] T016 [US1] Extend `skills/clerk/SKILL.md`: add a **catalog step** before discovery/selection — (1) ensure a catalog exists (`catalog init`/`add` if the user names new sources; the agent manages it, never hand-waves it); (2) `catalog list` to present the verified templates (full-ids, versions, reproducible flag); (3) collect the user's pick; (4) `catalog validate <full-id>` before init; (5) hand the validated full-id → its resolved source/ref to the existing init step. State plainly: discovery + validation are LLM-free; the *pick* is the agent's judgment (Constitution II). Point references at `specs/002-catalog/contracts/catalog.md`.

**Checkpoint**: SKILL documents catalog-manage → list → pick → validate → init, matching the real verbs.

---

## Phase 7: Reconciliation + quality gate + closeout

- [ ] T017 Reconcile ADR-0003: add a "Superseded in part (spec 002)" note — the repos-collector + selector templates are replaced by the plain catalog file + agent-selection + validation gate; the runtime `--data catalog=` render-scope fact is RETAINED for spec 007. Do NOT rewrite ADR-0002 (honored in full). Keep it a focused amendment, not a rewrite.
- [ ] T018 Update `.specify/memory/roadmap.md`: mark spec 002 `planned → implemented` with a completion note (catalog = user TOML managed by scripts/clerk.py; deterministic listing; validation gate; ADR-0003 two-template flow superseded); confirm spec-003's dependency reads "consumes 002's validated selection + the hidden depends_on edges".
- [ ] T019 Full gate on the branch: `uv run ruff check src/ tests/ scripts/ && uv run ruff format --check src/ tests/ scripts/ && uv run mypy && uv run pytest -q`. Add `tomli-w` type handling if mypy needs it. Then `uv run pytest -m network -v` if reachable (else note untested, correctly marked). Confirm existing 001/010 tests still pass (no regression).
- [ ] T020 Update `README.md`: brief `## Catalog` note — user-owned sources, `catalog` verbs, full-id selection. Then open the PR (title = user-facing changelog entry, no spec IDs; `## Spec Context` body per the hook); push via `dgit push`. Do NOT merge without the user's go-ahead.

---

## Dependencies & parallelism

- **Setup (T001–T003) blocks everything.**
- **Phase 2 (T004–T007)** → **Phase 3 (T008–T010)** → **Phase 4 (T011–T012)** are
  sequential in `catalog.py` (each builds on the prior), though their `[P]` test
  tasks parallelize once their impl lands.
- **Phase 5 (T013–T015)** depends on Phases 2–4 (the verbs call the module).
- **Phase 6 (T016)** depends on Phase 5 (documents the real verbs).
- **Phase 7 (T017–T020)** is closeout; T017/T018 (docs) can run parallel to code once
  the design is stable.

## Definition of done (maps to spec Success Criteria)

- SC-001 — `catalog list` enumerates usable templates + flags unusable sources
  (T008/T010/T014).
- SC-002 — listing is deterministic across repeated runs (T009/T010/T014).
- SC-003 — agent can create/add/remove/list idempotently, non-destructively
  (T004–T007/T014).
- SC-004 — `validate` accepts valid / refuses unknown+ambiguous, LLM-free
  (T011/T012/T014).
- SC-005 — no clerk artifact in generated projects; no template code in catalog ops
  (inherent to static discovery; assert in T014).
