---
description: "Task list for bailiff global per-template defaults (spec 004)"
---

# Tasks: bailiff global per-template defaults

**Input**: Design documents from `specs/004-defaults/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[contracts/defaults.md](./contracts/defaults.md),
[constitution](../../.specify/memory/constitution.md) v2.1.0

**Depends on**: spec 003 (`runner.init_many` + `discovery.Question` with `.secret`
attribute must be present; `conftest.py` multi-template fixtures reused).

**Tests**: INCLUDED. Constitution VII requires per-step hardening: precedence
verification (`data=` wins; threaded answer wins), secret exclusion, missing-file
no-op, malformed YAML error, per-layer independence, and `settings.yml` fallback.

**Organization**: grouped by user story (US1–US4 from spec.md).

## Design decisions this task list assumes (resolved; flagged for review)

- Config format = YAML at `~/.config/bailiff/defaults.yml` — aligned with ADR-0005
  and bailiff's existing YAML configs (Q-004a: no ADR deviation).
- `BAILIFF_DEFAULTS_PATH` pointing at a nonexistent file → `DefaultsError` (Q-004c).
- `settings.yml` fallback = best-effort; gracefully degrades (Q-004b).
- Hidden `when:false` questions = SHOULD exclude from `user_defaults=` (Q-004d).
- `DefaultsError` lives in `src/bailiff/errors.py` (consistent with `CatalogError`).
- `defaults.py` is a standalone module (not inlined into `runner.py`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no incomplete-task dependency)
- Exact file paths included

---

## Phase 1: Setup + error type

- [ ] T001 Add `DefaultsError(BailiffError)` to `src/bailiff/errors.py` (malformed YAML
  or nonexistent explicit-override path; message includes path + reason). Create the
  `src/bailiff/defaults.py` module skeleton (module docstring: user-config store for
  soft per-template defaults — mirrors `catalog.py`'s path-resolution pattern; pure
  functions, no copier import in the load/select path).

**Checkpoint**: `import bailiff.defaults` works; `DefaultsError` importable; `mypy`
clean on skeletons.

---

## Phase 2: `defaults.py` — load, path resolution, key selection

- [ ] T002 [US1/US4] `defaults.defaults_path() -> Path`: resolve `BAILIFF_DEFAULTS_PATH`
  env var → if set and file missing, raise `DefaultsError`; else return `Path(env)`.
  Fallback: `user_config_path("bailiff", appauthor=False) / "defaults.yml"`. Mirror
  `catalog.catalog_path()` in `src/bailiff/catalog.py:50-59`.
- [ ] T003 [US1/US4] `defaults.load(path: Path) -> dict[str, Any]`: missing file →
  return `{}` (no error); malformed YAML → raise `DefaultsError(f"defaults file is
  not valid YAML: {path}\n  {exc}")`. Use `yaml.safe_load`. Mirror the error-handling
  pattern in `catalog.load()` at `src/bailiff/catalog.py:111-138`.
- [ ] T004 [US1/US3] `defaults.select_keys(defaults: dict, questions: list[Question])
  -> dict`: filter to keys present in `questions`, excluding `question.secret is True`,
  excluding questions whose `when` is statically `False` (SHOULD). Return the filtered
  subset. Pure function — no I/O.
- [ ] T005 [US3] `defaults.fold_settings_defaults(yaml_defaults: dict) -> dict`:
  best-effort call to `copier.load_settings()` (or the equivalent public surface);
  extract `.defaults` mapping (empty dict if absent); return
  `{**settings_defaults, **yaml_defaults}` (yaml wins). Any exception from
  `load_settings()` is caught and swallowed (debug-log only); return `yaml_defaults`
  unchanged. Flag: if `copier.load_settings` is not part of the public API (verify
  before implementation), use `copier.settings.Settings.from_file()` or skip the
  fold if there is no public surface (document the gap).
- [ ] T006 [P] [US1–US4] `tests/unit/test_defaults.py` (NEW):
  - `defaults_path()`: env unset → platformdirs path; env set to existing file →
    that path; env set to missing file → `DefaultsError`.
  - `load()`: missing file → `{}`; malformed YAML → `DefaultsError` with path;
    valid flat YAML → correct dict.
  - `select_keys()`: excludes keys absent from questions; excludes `secret: true`
    question; includes non-secret matching keys; handles `when: false` SHOULD
    exclusion.
  - `fold_settings_defaults()`: yaml defaults win on collision; exception from
    `load_settings` → returns yaml defaults unchanged.

**Checkpoint**: `uv run pytest tests/unit/test_defaults.py` green; `mypy` clean.

---

## Phase 3: US1 — single-template init with defaults

- [ ] T007 [US1] Extend `runner.init()` in `src/bailiff/runner.py`: before calling
  `run_copy`, load defaults (`defaults.load(defaults.defaults_path())`), fold
  settings (`defaults.fold_settings_defaults`), discover the template to get
  `disc.questions`, call `defaults.select_keys(merged_defaults, disc.questions)`,
  and pass the result as `user_defaults=` to `run_copy`. The load + fold step is
  ONCE per `init` call. The `check=True` (dry-run) path MUST receive the same
  `user_defaults` (FR-008).
- [ ] T008 [P] [US1] `tests/loop/test_defaults_init.py` (NEW):
  - **US1 SC-001**: fixture with questions `author_name` + `author_email`; write a
    temp `defaults.yml`; run `init`; assert answers file records the defaults.
  - **US1 SC-002 (precedence)**: same setup but pass `author_name` in `data=`; assert
    answers file records the `data=` value (hard override wins).
  - **US1 SC-003 (secret exclusion)**: fixture with a `secret: true` question and
    the same key in `defaults.yml`; assert the answers file does NOT record the
    default value for the secret question.
  - **US1 SC-004 (missing file)**: no `defaults.yml`; assert init runs without
    error and behavior is identical to pre-004 (no `user_defaults` passed, or empty
    dict).
  - **SC-007 (no project file)**: assert the generated project contains no
    defaults-related file written by bailiff.

**Checkpoint**: single-template defaults injection works; precedence intact; secrets
excluded; missing file is a no-op; no bailiff file in the project.

---

## Phase 4: US2 — per-layer defaults in multi-template init

- [ ] T009 [US2] Extend `runner.init_many()` in `src/bailiff/runner.py`: load +
  fold defaults ONCE per `init_many` call (before the per-layer loop). Inside the
  loop, for each layer, call `defaults.select_keys(merged_defaults, disc.questions)`
  and pass the result as `user_defaults=` to `run_copy`. The `disc` (discovery
  result) is already fetched per-layer in the loop (for trust + reproducibility
  checks) — reuse it. The `check=True` preflight path MUST also pass `user_defaults`
  per layer (FR-008).
- [ ] T010 [P] [US2] `tests/loop/test_defaults_multi.py` (NEW):
  - **US2 SC-005 (per-layer)**: two template fixtures each asking `author_name`;
    `defaults.yml` with `author_name = "Ada"`; run `init_many`; assert both answers
    files record `author_name: Ada`.
  - **US2 SC-002 (threaded answer wins)**: layer A provides `author_name = "Org"`
    in `data=`; it threads forward to layer B; `defaults.yml` has `author_name =
    "Ada"`; assert layer B records `author_name: Org` (threaded `data=` wins over
    `user_defaults=` — precedence check across the multi-layer seam).
  - **US2 SC-007**: assert no bailiff defaults file in the generated project tree.

**Checkpoint**: per-layer defaults injection works; threaded answer wins; no project
file.

---

## Phase 5: US3 — `settings.yml` fallback

- [ ] T011 [P] [US3] `tests/loop/test_defaults_settings.py` (NEW, if `load_settings`
  surface is verifiable):
  - **US3 SC-001**: write a test `settings.yml` with `defaults: {user_name: "Turing"}`
    at a temp path; monkeypatch copier's settings lookup to use it; run `init` with
    a template asking `user_name` and no entry in `defaults.yml`; assert answers
    file records `user_name: Turing`.
  - **US3 SC-002 (yaml wins)**: same setup but `defaults.yml` also has `user_name: Babbage`;
    assert answers file records `user_name: Babbage`.
  - **US3 graceful degradation**: monkeypatch `load_settings` to raise; assert init
    completes without error and falls back to YAML-only defaults.
  - **NOTE**: if `copier.load_settings()` has no stable public surface (verify via
    `copier.settings` module), mark T011 as a research task first; skip the settings
    fold if no public API exists and document the gap in the spec's Open Questions.

**Checkpoint**: `settings.yml` fallback works; degrades gracefully.

---

## Phase 6: SKILL update

- [ ] T012 [P] Extend `skills/bailiff/SKILL.md`: add a note that bailiff pre-fills soft
  defaults from `~/.config/bailiff/defaults.yml` (env-overridable via
  `BAILIFF_DEFAULTS_PATH`); state that secret questions are never pre-filled; state
  that the defaults file is user-side config and never written into the project;
  point at `specs/004-defaults/contracts/defaults.md`. Keep the update terse — one
  short paragraph.

**Checkpoint**: SKILL documents the defaults behavior.

---

## Phase 7: ADR reconciliation + gate

- [ ] T013 Update `docs/decisions/0005-global-per-module-defaults.md`: the ADR
  names `defaults.yml`; this spec also uses `defaults.yml` (YAML) — aligned.
  Add one line to the ADR's Consequences section confirming the file is YAML
  (`yaml.safe_load`), consistent with bailiff's other YAML configs and PyYAML
  already being a project dependency.
- [ ] T014 Full gate: `uv run ruff check src/ tests/ scripts/ && uv run ruff format
  --check src/ tests/ scripts/ && uv run mypy && uv run pytest -q`. Confirm existing
  001/010/002/003 tests still pass (NO regression). Run `-m network` if reachable,
  else note untested.
- [ ] T015 [P] Update `.specify/memory/roadmap.md`: mark spec 004 `planned →
  implemented` with a completion note (YAML defaults at `~/.config/bailiff/defaults.yml`;
  `user_defaults=` injection; key selection excludes secrets; multi-layer per-layer;
  settings.yml best-effort fold). Confirm 005/006 entries' dependency on 003 still
  read correctly (004 does not add a new dependency for 005).

---

## Dependencies & parallelism

- **Setup (T001) blocks everything.**
- **Phase 2 (T002–T005)** is sequential within `defaults.py`; T006 (unit tests)
  can run in parallel with T005 after T002–T004 are done.
- **Phase 3 (T007–T008)** — single-template — blocks Phase 4 (multi-template
  extends the same function).
- **Phase 4 (T009–T010)** depends on spec 003's `init_many` being present. Blocked
  by Phase 3 (T007 must exist before extending `init_many`).
- **Phase 5 (T011)** is independent of Phase 4; can run in parallel with Phase 4
  after Phase 2.
- **Phase 6 (T012)** is purely docs; parallelizable after Phase 3.
- **Phase 7 (T013–T015)**: T013 (ADR) and T015 (roadmap) are parallelizable docs;
  T014 (gate) is last.

## Definition of done (maps to spec Success Criteria)

- SC-001 — default key pre-fills answers file when not overridden (T008).
- SC-002 — `data=` wins; threaded answer wins in multi-layer (T008, T010).
- SC-003 — secret question not pre-filled (T006, T008).
- SC-004 — missing file no-op (T006, T008).
- SC-005 — multi-layer per-layer defaults; threaded answer wins (T009, T010).
- SC-006 — malformed YAML → `DefaultsError` (T006).
- SC-007 — no bailiff defaults file written into the generated project (T008, T010).
