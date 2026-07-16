# Tasks: bailiff engine — PyPI packaging, capabilities, collision, cache (013)

**Input**: Design documents in `specs/013-engine-capabilities-pypi/`

**Prerequisites**: plan.md, spec.md, decisions-ledger.md (FR-021 — must exist before plan phase)

**Branch**: `013-engine-capabilities-pypi`

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with its phase-siblings (no inter-task data dependency)
- **[US#]**: User-story traceability label from spec.md
- Every task names exact file paths

---

## Definition of Done (applies to EVERY task)

Unless a task explicitly states otherwise, "done" means:
1. **Implementation** matches the plan's design for that work stream.
2. **Tests** exist for every new function or behavior change: unit tests where the logic is isolated, integration tests where the boundary matters (wheel install, end-to-end run-spec).
3. **SC-003 regression**: `pytest tests/` (full suite, `-m 'not network'`) passes. No existing test is modified to accommodate new code.
4. **Type check**: `mypy` passes on `src/bailiff/` and (if touched) `scripts/bailiff.py`.
5. **Lint**: `ruff check` and `ruff format --check` pass.
6. No new `secret:` questions anywhere; `tests/loop/test_secrets_policy.py` stays green.

---

## Phase 1: Prerequisites

**Purpose**: Verify that the two hard gates — the decisions-ledger document and a green
baseline — are in place. Nothing proceeds if either gate is red.

- [x] T001 Verify the FR-021 prerequisite: `test -f specs/013-engine-capabilities-pypi/decisions-ledger.md` MUST succeed. If the file is absent, STOP — author or vendor it before any other task begins. This is the documented "before the plan phase" gate.
- [x] T002 Establish a green baseline: run `pytest`, `mypy`, `ruff check`, `ruff format --check` on the unmodified tree; record the result so any regression introduced by subsequent tasks is immediately attributable. Fix pre-existing failures (if any) as a separate commit BEFORE starting Phase 2 work. Confirm `tests/loop/test_secrets_policy.py` is green.

---

## Phase 2: Governance

**Purpose**: Land the constitution amendment that gates all PyPI publish work. Engine code (Phases 3-4) may proceed in parallel on the branch; the `[project.scripts]` addition and publish steps (Phases 5-6) MUST NOT merge before this task is complete.

- [x] T003 [US3] Author and commit the governance amendment in one atomic change:
  (1) Amend `specs/013-engine-capabilities-pypi/decisions-ledger.md` — confirm it captures all ratified decisions from the 2026-07-14 adjudication session.
  (2) Amend `.specify/memory/constitution.md` to v3.0.0 (MAJOR): rewrite Principle I to permit and scope the published CLI (bailiff = the tool, bailiff-mod-* = the modules); scope C-11 to module-authoring specs; add a sync-impact report comment block at the top of the file recording the MAJOR bump rationale, the reconciled files list, and that spec 011's FR-011 gate remains honored for its scope. The existing v2.3.0 sync-impact comment MUST be preserved (prior history).
  (3) Amend `.specify/memory/roadmap.md`: scope the C-11 "glue only for capabilities copier lacks" rule to module-authoring specs; add a note that spec 013 is the governed engine exception.
  (4) Write `docs/decisions/0008-pypi-packaging-repositioning.md`: record the repositioning decision (bailiff as tool vs skill-only), the distribution-name situation (FR-005 NEEDS CLARIFICATION), the FR-019 Constitution VIII unlock scope, the `exclusive_capabilities` frozenset interface rationale (plan Complexity Tracking), and the ratified "warn not block" design for capability conflicts.
  Gate check after commit: `grep "Version: 3.0.0" .specify/memory/constitution.md` AND `test -f docs/decisions/0008-pypi-packaging-repositioning.md` both pass.

---

## Phase 3: Engine Subsystems

**Purpose**: All five engine work streams. Tasks in this phase are grouped by dependency
but many are parallel-eligible; the dependency DAG is explicit below.

### Group A: Foundational types (prerequisites for groups B and C)

- [x] T004 [US4] Add `CollisionError` to `src/bailiff/errors.py`:
  ```python
  class CollisionError(BailiffError):
      def __init__(self, path: str, modules: list[str]) -> None:
          ...
  ```
  Carries `self.path: str` and `self.modules: list[str]`. The error message names the overlapping path and both module full-ids. Maps to exit 1 in the CLI (same handler as other `BailiffError` subclasses — no new exit code branch needed). Write `tests/test_errors.py` assertions for the constructor, `self.path`, `self.modules`, and str output. Must pass mypy.

- [x] T005 [P] [US1] [US2] Extend `src/bailiff/discovery.py` to read `_bailiff_provides` and `_bailiff_exclusive` from copier.yml statically:
  (1) Add `provides: list[str]` and `exclusive: bool` to the `Discovery` dataclass (frozen).
  (2) In `_describe()`, read them BEFORE the question-iteration loop (same pattern as `has_tasks = bool(raw.get("_tasks"))`):
  ```python
  provides: list[str] = list(raw.get("_bailiff_provides") or [])
  exclusive: bool = bool(raw.get("_bailiff_exclusive", False))
  ```
  Malformed third-party values (non-list `_bailiff_provides`, non-bool `_bailiff_exclusive`, non-kebab-case entries): emit a `warnings.warn` and treat the declaration as absent (never raise DiscoveryError here). Well-formedness check is first-party CI only (T008).
  (3) Include `provides` and `exclusive` in `Discovery.to_dict()`.
  (4) Write `tests/test_discovery_capabilities.py`: fixture templates (parametrized inline copier.yml dicts, not network calls) covering: well-formed list, empty/absent key, malformed non-list (warns and treated as absent), non-kebab-case entry (warned), `_bailiff_exclusive: true`, `_bailiff_exclusive: false`/absent.

### Group B: Catalog data model and listing (depends on T005)

- [x] T006 [US1] [US2] [US5] [US6] Extend `src/bailiff/catalog.py`:
  (1) Add fields to `TemplateRecord`: `provides: list[str] = field(default_factory=list)`, `exclusive: bool = False`, `shadowed: bool = False`.
  (2) Extend `FullListing.to_dict()` to include `provides`, `exclusive`, `shadowed` per template entry.
  (3) In `build_listing()`: populate `provides`/`exclusive` from `disc.provides`/`disc.exclusive`; implement the shadow-tracking pass. Add `seen_bare_names: set[str] = set()` across the pointer loop. For each template: compute `bare_name = full_id.split("/", 1)[-1]`; if `bare_name in seen_bare_names`, set `template.shadowed = True`; else add to `seen_bare_names`.
  (4) Write `tests/test_catalog_capabilities.py`: tests for `TemplateRecord` field defaults; `FullListing.to_dict()` with `provides`/`exclusive`/`shadowed` fields; `build_listing()` shadow logic with a two-pointer fixture (use a monkeypatched `discovery.discover` returning `Discovery` objects with known `provides`/`exclusive`).
  Dependency: T005 (provides Discovery.provides and Discovery.exclusive).

### Group C: Independent engine tasks (no Group B prerequisite)

- [x] T007 [P] [US2] Extend `scripts/generate_catalog.py` to emit `_bailiff_provides` and `_bailiff_exclusive` in catalog.json module entries: read them from each module's `copier.yml` using the same static YAML read already done for name/description; emit as `"provides": [...]` and `"exclusive": <bool>` alongside the existing fields. Absent keys → `"provides": []`, `"exclusive": false`. Write or extend unit tests for the output shape (use a temporary `templates/` fixture tree).

- [x] T008 [P] [US2] Extend `scripts/check_modules.py` with two new first-party-only lint rules:
  (1) Well-formedness: `_bailiff_provides` must be a list of strings each matching `^[a-z][a-z0-9-]*$`; `_bailiff_exclusive` must be a boolean. Any violation → exit 1, naming the module and the offending value and key.
  (2) Mixed exclusivity: collect all first-party modules' `(capability, exclusive)` pairs; for each capability where N≥2 modules exist and only a strict subset declares `_bailiff_exclusive: true`, flag as a hard author-time error (exit 1, naming all members of the mixed group). Absence of `_bailiff_provides` is never an error.
  Write `tests/test_check_modules_capabilities.py`: fixture `templates/` trees covering: well-formed declarations pass; non-list `_bailiff_provides` fails; non-kebab-case entry fails; non-bool `_bailiff_exclusive` fails; consistent all-exclusive group passes; consistent all-non-exclusive group passes; mixed group fails.

### Group D: init_many extensions (depends on T005, T006 for capability warning; T004 for collision)

- [x] T009 [US1] Add the capability conflict warning to `src/bailiff/runner.py` `init_many()`:
  (1) Add a new parameter: `exclusive_capabilities: frozenset[str] = frozenset()`. This is the catalog-wide set of capability names where ANY provider declares `exclusive: true` (computed by the CLI before calling `init_many`; passed as a frozen set so `init_many` has no catalog awareness).
  (2) Implement `_check_capability_conflicts(records, dest, exclusive_capabilities)` per the plan's Group B / Work stream 3 algorithm: collect `provides` from selected records + already-installed modules (read from `.copier-answers.*.yml` in dest, discover each recorded source at its `_commit`); for each capability with >1 provider where the capability is in `exclusive_capabilities`, emit a `warnings.warn` loud warning naming the capability and conflicting members; proceed (never raise).
  (3) Call `_check_capability_conflicts()` from BOTH the `check=False` and `check=True` branches of `init_many`, immediately after `layer_plan()` and before any render.
  (4) FR-012: `reproduce`, `reproduce_many`, `update`, `update_many` are NOT touched.
  (5) Write `tests/test_runner_capability_warning.py`: use a monkeypatched/fixture `discovery.discover`; test: single provider = no warning; two providers of non-exclusive capability = no warning; two providers of exclusive capability = warning emitted; incremental add (dest has existing answers file with a recorded module) = warning fires; four modules where third (not selected) declares exclusive = warning fires (group-infection); no-capability modules = byte-identical to pre-013 (SC-003 proxy).
  Dependency: T005 (Discovery.provides), T006 (TemplateRecord.provides / exclusive_capabilities must be derivable from the listing).

- [x] T010 [US4] Add the init-time file-collision scan to `src/bailiff/runner.py` `init_many()`:
  (1) Implement `_scan_init_collisions(plan, dest, accumulated, answers_map, today)` per the plan's Work stream 4 design: for each layer in `plan`, render into `tempfile.mkdtemp(prefix="bailiff-collision-")` using `run_copy` with the layer's answers and **`skip_tasks=True`** (SAFETY: prevents task execution — `gh repo create`, git init, network calls — during the side-effect-free scan); collect all written files as relative paths (exclude `.copier-answers*.yml`); raise `CollisionError(path, [module_a, module_b])` on the first overlapping path.
  (2) Call `_scan_init_collisions()` from the `check=False` branch ONLY, BEFORE the main render loop, AFTER the capability check. The check=True (preflight) branch uses pretend=True and does not invoke the scan.
  (3) FR-013 scope: collision scan is init-only; `reproduce`, `reproduce_many`, `update`, `update_many` unchanged.
  (4) Write `tests/test_runner_collision.py`: use two in-repo fixture templates (tiny, offline-safe) that write a shared path; verify CollisionError is raised before any file appears in the real dest dir; verify dest is untouched; verify a disjoint pair passes silently. Additionally test that `skip_tasks=True` is being passed (monkeypatch `run_copy` and assert kwarg).
  Dependency: T004 (CollisionError), T006 (TemplateRecord has the right shape).

### Group E: Multi-catalog precedence (independent)

- [x] T011 [P] [US5] Fix bare-name resolution in `src/bailiff/catalog.py` `validate_selection()` and extend `build_listing()` for shadow tracking:
  (1) In `validate_selection()`, replace the `len(matches) > 1` ambiguity `CatalogError` branch (catalog.py:462-466) with first-listed-wins: take `matches[0]`, emit a `warnings.warn` loud shadow warning naming the winner full-id and all shadowed full-ids, resolve.
  (2) `build_listing()` shadow tracking is delivered as part of T006. This task ensures `validate_selection()` correctly reads and surfaces `shadowed` in its table output.
  (3) Update `_print_catalog_table` (in `scripts/bailiff.py` or `src/bailiff/cli.py` when T013 lands) to display `[shadowed by <winner>]` on shadowed entries and `[provides: <caps>]` / `[exclusive]` tags.
  (4) Write `tests/test_catalog_precedence.py`: configure a `CatalogModel` with two pointers both containing a module of the same bare name; assert: bare name resolves to first-pointer's entry; shadow warning is emitted; full-id of second entry resolves normally; listing shows both with the second marked `shadowed=True`; single-pointer config is unchanged.

### Group F: Listing cache (depends on T006 for full TemplateRecord)

- [x] T012 [US6] Add the persisted listing cache to `src/bailiff/catalog.py` and wire it into the `catalog` CLI verb:
  (1) Add `listing_cache_path() -> Path` using `platformdirs.user_cache_path("bailiff", appauthor=False) / "listing.json"`.
  (2) Add `persist_listing(listing: FullListing, cache_path: Path | None = None) -> None`: serialize via `FullListing.to_dict()`, write atomically (write to `<path>.tmp`, rename — avoids corrupt partial writes).
  (3) Add `load_listing_cache(cache_path: Path | None = None) -> FullListing | None`: deserialize; return None on absent/corrupt file (never raise).
  (4) Add `build_and_cache_listing(catalog_path: Path) -> FullListing`: calls `build_listing(catalog_path)` then `persist_listing(…)`.
  (5) Wire into CLI dispatch (`scripts/bailiff.py` → later `cli.py` T013): `refresh` calls `build_and_cache_listing` and prints the cache path; `list` and `validate` call `load_listing_cache` first; if None, call `build_and_cache_listing` with a stderr notice that the cache was built automatically.
  (6) Write `tests/test_catalog_cache.py`: persist + load round-trip (all fields including provides/exclusive/shadowed); corrupt cache → returns None; absent cache → returns None; atomic write (temp file replaced); CLI dispatch: `list` with no cache auto-builds; `refresh` writes cache; two consecutive `list` calls after `refresh` are byte-identical.
  Dependency: T006 (TemplateRecord extended, to_dict includes new fields).

---

## Phase 4: CLI Packaging

**Purpose**: Extract `cli.py`, add the console entry point, declare `platformdirs`,
single-source the version. **Depends on T003 governance gate for the `[project.scripts]`
addition** (the gate permits publishing the console entry — the entry point itself is
inert until published, so it can be code-reviewed on the branch before T003 lands, but
must not appear in a release commit before T003 is in).

- [x] T013 [US3] Extract `src/bailiff/cli.py`, delete the bundled script, wire the console entry point:
  (1) Create `src/bailiff/cli.py`: copy `main()`, `_build_parser()`, `_run_preflight_or_exit()`, `_cmd_doctor()`, `_deferred_dispatch()`, `_real_dispatch()`, `_print_catalog_table()` from `scripts/bailiff.py` verbatim, with three changes: remove the dual-mode `sys.path` shim block entirely; change `prog="bailiff.py"` → `prog="bailiff"`; remove `if __name__ == "__main__"` guard. All imports stay identical.
  (2) Update `_print_catalog_table` in `cli.py` to display capability tags (`provides`, `exclusive`) and shadow marks (`shadowed`) per the plan's Work stream 5 display format.
  (3) **DELETE `scripts/bailiff.py`** (decisions-ledger FR-006 resolution). Update SKILL.md to use `uvx bailiff` as the invocation. Remove `scripts/bailiff.py` from mypy's `files` configuration.
  (4) Add `[project.scripts] bailiff = "bailiff.cli:main"` to `pyproject.toml`.
  (5) Ensure `mypy` is configured to check `src/bailiff/cli.py` (add to `files` in `[tool.mypy]`).
  (6) Write `tests/test_cli_extraction.py`: import `from bailiff.cli import main`; invoke each verb via `main(["--version"])`, `main(["doctor"])`, `main(["catalog", "--help"])` (no network required); verify exit code contract.

- [ ] T014 [US3] Packaging correctness — dependency declaration and single-source version:
  (1) Add `"platformdirs"` to `[project.dependencies]` in `pyproject.toml`. Verify: `python -c "import importlib.metadata; print(importlib.metadata.requires('bailiff'))"` shows `platformdirs` in the declared deps (after `uv sync`).
  (2) Replace the literal `__version__ = "0.1.0"` in `src/bailiff/__init__.py` with:
  ```python
  from importlib.metadata import version as _version
  __version__: str = _version("bailiff")
  ```
  No bare-checkout fallback needed: `scripts/bailiff.py` is deleted, so `__version__` is only
  accessed from an installed context (editable or wheel). If `importlib.metadata` raises, the
  ImportError surfaces cleanly.
  (3) Write `tests/test_version.py`: `from bailiff import __version__`; assert it is a non-empty string and does not raise; assert `bailiff --version` output (via `main(["--version"])`) contains the same string.

---

## Phase 5: Integration and Verification

**Purpose**: Whole-spec validation before the maintainer-gated release work.

- [ ] T015 Run the full gate suite and drive it to green: `pytest tests/` (all non-network tests), `mypy` on `src/bailiff/` + `src/bailiff/cli.py`, `ruff check .`, `ruff format --check .`. This is the SC-003 gate: every existing test must pass unmodified alongside the new tests. Fix any regression introduced by the work streams above.

- [ ] T016 [US3] Wheel build and clean-venv install verification (SC-001):
  (1) `uv build` — verify the wheel is produced without error.
  (2) Install the wheel into a fresh `venv` (not `uv sync` dev environment): `python -m venv /tmp/bailiff-test-venv && /tmp/bailiff-test-venv/bin/pip install dist/bailiff-*.whl`.
  (3) Verify the `bailiff` console command exists and:
      - `bailiff --version` matches `pyproject.toml`'s `version` field.
      - `bailiff doctor` exits 0.
      - `bailiff discover --help` prints help without error.
  (4) Declared-dependency audit: `python -c "import importlib.metadata; print(importlib.metadata.requires('bailiff'))"` in the clean venv lists `platformdirs` as a declared dep; verify no directly-imported third-party package in `src/bailiff/` is missing from the declared deps list (manual check, or run `deptry src/bailiff` if available).
  (5) Document the result as a comment in the PR (not a committed file).

---

## Phase 6: Release Workflow

**Purpose**: Add the publish step to CI — the step is inert until the maintainer
triggers it. Depends on Phase 5 (verified green build).

- [ ] T017 [US3] Add the PyPI publish step to `.github/workflows/release.yml` (or create the file if absent):
  (1) Add a `publish` job that runs ONLY on a pushed tag matching `v*.*.*`.
  (2) Uses OIDC trusted-publisher (PyPI environment `release`, audience `pypi`) if supported; otherwise uses a `PYPI_API_TOKEN` secret. OIDC is preferred (FR-004).
  (3) Steps: `uv build` → `uv publish` (or `twine upload`) with the built wheel.
  (4) The job definition is committed but NOT triggered — first publish is maintainer-confirmed (SC-010).
  (5) Confirm the workflow file is valid YAML and the job name/step names are consistent with the existing CI structure.

---

## Phase 7: Maintainer-Gated Publish (reconfirm-gated — never unattended)

**Purpose**: Irreversible public actions. NOTHING in this phase runs without explicit
maintainer confirmation at each step. These tasks are executed BY or WITH the maintainer.

- [ ] T018 [RECONFIRM-GATED] Pre-publish confirmation (NC items already resolved in decisions-ledger 2026-07-15):
  (1) FR-005 — Re-verify `bailiff` PyPI availability at this moment (squatting window since 2026-07-14). Confirm `pyproject.toml` name, `importlib.metadata.version(...)` call, SKILL.md uvx invocation, and ADR-0008 all reference `bailiff`.
  (2) FR-006 — Confirm `scripts/bailiff.py` is deleted and SKILL.md uses `uvx bailiff`.
  (3) FR-017 — Confirm presets remain deferred (or scope-gate T021 if the decision has been reversed since 2026-07-15).
  Record confirmation in a commit to `decisions-ledger.md`.

- [ ] T019 [RECONFIRM-GATED] Version-bump commit: bump `pyproject.toml` `version` from `"0.1.0"` to the release version (e.g. `"0.2.0"` or `"1.0.0"` — maintainer picks the semantic); commit with message `chore: release v<version> (first PyPI publish)`; tag `v<version>`. Push tag — this triggers the T017 publish CI job.

- [ ] T020 [RECONFIRM-GATED] Post-publish verification: confirm the package appears on PyPI; `uvx --from <dist-name> bailiff --version` resolves and prints the expected version; `uvx --from <dist-name> bailiff doctor` passes; document the result.

---

## Optional Task: Stack Presets (FR-017 — gated on T018 decision)

- [ ] T021 [OPTIONAL, FR-017] Stack presets if the T018 decision is "in scope for first release":
  (1) Extend `catalog.toml` TOML shape to accept an optional `presets` table per pointer:
  ```toml
  [[catalog]]
  name = "internal"
  sources = [...]
  [catalog.presets]
  python-service = ["base", "python", "precommit", "quality", "ci-github"]
  ```
  (2) Extend `CatalogPointer` dataclass with `presets: dict[str, list[str]] = field(default_factory=dict)`.
  (3) Extend `load()` to parse `presets` from each pointer's TOML table.
  (4) Expand presets in `validate_selection()` before the capability warning and collision scan: a preset ID `internal/python-service` expands to `["internal/base", "internal/python", ...]` (pointer namespace applied to bare module names in the preset list). Presets get no bypass — they are expanded into the normal module list.
  (5) Extend `_print_catalog_table` to show each pointer's presets namespaced as `<pointer>/<preset-name>`.
  (6) Write tests covering preset expansion, conflict detection through presets, and collision scan through preset expansion.
  (7) Update ADR-0008 and plan.md to record the decision.

---

## Dependencies & Execution Order

### Phase DAG

```
Phase 1 (T001, T002) — gates, baseline
  └─> Phase 2 (T003) — governance gate [required before T013/T014/T019]
  └─> Phase 3 engine (parallel groups):
        T004 ──────────────────────────────────────> T010
        T005 ──> T006 ──> T009 (capability warning)
                  T006 ──> T010 (collision scan)
                  T006 ──> T011 (precedence)
                  T006 ──> T012 (cache)
        T007 [independent]
        T008 [independent]
        T011 [independent of T006 for precedence logic; T006 provides shadowed field]
  └─> Phase 4 (T013, T014) — [DEPENDS ON T003 for project.scripts addition]
        T013 [depends on T012 for cache-aware catalog list display]
        T014 [independent of T013]
  └─> Phase 5 (T015, T016) — integration gate
        T015 first (full test suite), then T016 (wheel verify)
  └─> Phase 6 (T017) — release workflow setup
  └─> Phase 7 (T018 → T019 → T020) — strictly serial, each maintainer-gated
```

### Intra-phase parallel opportunities

- **Phase 3 Groups A+C**: T004, T005, T007, T008 can all start simultaneously (independent).
- **Phase 3 Group B**: T006 starts as soon as T005 is complete.
- **Phase 3 Group D**: T009 starts when T005+T006 are complete; T010 starts when T004+T006 are complete. T009 and T010 can run in parallel.
- **Phase 3 Groups E+F**: T011 and T012 can start when T006 is complete; they are independent of each other and of T009/T010.
- **Phase 4**: T013 and T014 are independent of each other; both can start once T003 is complete.

### Why the key ordering constraints

- **T003 before T013/T014**: `[project.scripts] bailiff` and the `platformdirs` dep
  declaration are packaging changes that require the amended constitution (the current
  constitution explicitly forbids `[project.scripts] bailiff`).
- **T005 before T006 before T009/T010**: Discovery.provides → TemplateRecord.provides
  → capability warning and collision scan consume TemplateRecord.
- **T004 before T010**: CollisionError must exist before the collision scan raises it.
- **T006 before T012**: the cache serializes/deserializes the full TemplateRecord shape
  including the new fields; building the cache before T006 extends the dataclass would
  produce a stale schema.
- **T015 before T016 before T017**: integration test must be green before wheel build
  verification; wheel verification must pass before the publish workflow is trusted.
- **Phase 7 strictly serial and gated**: the three-decision confirmation (T018) must
  land before the version bump (T019) or the tag will be stamped against unresolved
  open items.

---

## Story completion by phase

| Phase | Completes | Extends |
|---|---|---|
| Phase 2 | SC-009 (governance gate) | — |
| Phase 3 Group A/D | US4 (collision hard-stop) | — |
| Phase 3 Group A/B/D | US1 (capability declarations), US2 (author lint) | — |
| Phase 3 Group E/F | US5 (multi-catalog precedence), US6 (listing cache) | — |
| Phase 4 | US3 (install + run via uvx) | — |
| Phase 5 | SC-001, SC-003, SC-004 verification | — |
| Phase 7 | SC-010 (maintainer-confirmed publish) | — |
