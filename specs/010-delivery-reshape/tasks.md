---
description: "Task list for bailiff delivery reshape — skill-bundled copier wrapper (spec 010)"
---

# Tasks: bailiff delivery reshape — skill-bundled copier wrapper

**Input**: Design documents from `specs/010-delivery-reshape/`
**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (user stories),
[contracts/invocation.md](./contracts/invocation.md),
[constitution](../../.specify/memory/constitution.md) v2.1.0

**Tests**: INCLUDED. Constitution VII makes per-step hardening (copier-only
config-consistent reproduce, error surfacing, static-discovery safety) part of this
spec's definition-of-done, so test tasks are first-class.

**Organization**: grouped by user story (US1–US4 from spec.md) so each is
independently verifiable.

## Design decision this task list assumes (from plan.md, per user direction)

- The deterministic coordination is **one bundled script** `scripts/bailiff.py`
  (`./scripts/bailiff.py` / `uv run scripts/bailiff.py`) driving the **full lifecycle**
  — `discover` / `trust` / `init [--check]` / `reproduce` — through **one uniform
  path for 1..N templates**. A single-template project is the **N=1** case: **no
  separate single-template code path, and no verb meaningful only for multiple
  templates.** The script drives copier's public API once per template layer.
- `runner.py` is **retained and ACTIVE**: the per-layer copier driver
  (`run_copy`/`run_recopy` + error translation + reproducibility/trust pre-checks)
  used by `bailiff.py init`/`reproduce` at N=1 today and by 003's ordering for N>1.
  No judgment call outstanding.
- `reproduce` enumerates the committed `.copier-answers*.yml` file(s) and drives
  one `recopy` per layer (N=1 → one file → one recopy). The N>1 dependency
  topo-sort is spec 003, slotting into this loop.
- The Constitution VI reproducibility gate lives at **discovery** and is re-checked
  before `init` writes; the trust prefix suggestion moves to
  `bailiff.py trust --from-source`.
- The **copier-only-by-hand** reproduce (plain `copier recopy`, no bailiff/just) is
  the US1 guarantee/fallback — the exact commands `bailiff.py reproduce` issues.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no incomplete-task dependency)
- **[Story]**: US1–US4 (user-story tasks only)
- Exact file paths included

---

## Phase 1: Setup (packaging + invocation surface)

**Purpose**: strip the console-script/application framing; stand up the bundled
script skeleton. This is the FR-001 / US4 core.

- [ ] T001 [US4] Remove `[project.scripts] bailiff = "bailiff.cli:main"` from `pyproject.toml` (FR-001/SC-003). Decide + apply the lightest layout that keeps `import bailiff` working for tests and `mypy --strict` green: keep `[tool.hatch.build.targets.wheel] packages = ["src/bailiff"]` for editable installs, OR switch tests to a src-on-path layout. Update the `pyproject.toml` description if it still frames bailiff as an installable CLI.
- [ ] T002 [US4] Create `scripts/bailiff.py` skeleton: shebang (`#!/usr/bin/env python3`), executable bit (`chmod +x`), module docstring stating it is the bundled orchestration script driving the full lifecycle through one uniform 1..N path, stdlib `argparse` with subparsers `discover`, `trust`, `init`, `reproduce`, and a `main(argv)` that imports `bailiff.discovery`/`bailiff.trust`/`bailiff.runner`/`bailiff.errors` and dispatches. Mirror 001 cli.py's error→exit mapping (0/1/2/3). Make it importable AND runnable via `uv run scripts/bailiff.py`.
- [ ] T003 [P] [US4] Verify the two run modes work: `uv run scripts/bailiff.py --help` and `./scripts/bailiff.py --help` both print usage. Document any `sys.path` shim `scripts/bailiff.py` needs to import `bailiff.*` when run directly (prefer keeping deps importable via the project env over a bespoke shim).

**Checkpoint**: `pyproject.toml` declares no `bailiff` console script; `uv run scripts/bailiff.py --help` works; `uv sync` + `mypy` clean.

---

## Phase 2: The bundled script's verbs (discover / trust / init / reproduce)

**Purpose**: wire the full lifecycle behind `scripts/bailiff.py` on one uniform 1..N
path, reusing the 001 libraries; relocate the VI gate re-check + prefix suggestion.
**Blocks the story phases** (they invoke these).

- [ ] T004 [US2] Wire `scripts/bailiff.py discover <source> [--ref REF]` to `bailiff.discovery.discover(...)`, printing the same JSON as 001 (`discovery-output.md` shape unchanged). No behavior change to `src/bailiff/discovery.py` — this is re-exposure.
- [ ] T005 [US2] Wire `scripts/bailiff.py trust list` and `trust add <prefix>` to `bailiff.trust.list_trust()`/`add_trust(...)` (idempotent; honors `COPIER_SETTINGS_PATH`). Behavior identical to 001's `bailiff trust`.
- [ ] T006 [US2] Add `scripts/bailiff.py trust add --from-source <src>`: compute the owner-path prefix using the existing suggestion logic (lift `_suggest_prefix` from `src/bailiff/runner.py` into `src/bailiff/trust.py` so both the script and the retained runner share one implementation) and record it. This replaces 001's prefix suggestion that was embedded in the init refusal path.
- [ ] T007 [US2] Wire `scripts/bailiff.py init --run-spec <file> [--check]` to `bailiff.runner.init(...)` (inject `today`; reproducibility + trust pre-checks; `--check` → copier `--pretend`). Behavior identical to 001's `bailiff init` MINUS the justfile write (removed in T008). Single layer today (N=1); the enumerate-and-loop wrapper is T007b.
- [ ] T007b [US3] Add a small answers-file enumeration helper in `src/bailiff/runner.py` (e.g. `enumerate_answers_files(dest)`) and make `scripts/bailiff.py reproduce [DEST]` loop over it, driving `runner.reproduce(...)` per file. At N=1 it finds one `.copier-answers.yml` → one recopy (identical to 001). The multi-file **ordering** is 003 (this just establishes the uniform loop; a single-file project must behave exactly as before).
- [ ] T007c [US1] Confirm the Constitution VI reproducibility refusal is expressed at discovery AND re-checked before `init` writes: `discover` emits `reproducible`; `runner.init` keeps its `_require_reproducible` guard. Ensure the SKILL can stop on `reproducible:false` without invoking init.

**Checkpoint**: `uv run scripts/bailiff.py discover|trust|init|reproduce` all behave as 001's `bailiff` verbs (minus justfile); a single-template init+reproduce round-trips config-consistently.

---

## Phase 3: Remove the generated justfile + delete cli.py (US4)

**Purpose**: no bailiff artifact in generated projects; one entrypoint only.

- [ ] T008 [US4] Delete the justfile writer: remove `_REPRODUCE_JUST`, `_write_reproduce_recipe`, and its call from the init path. `init` (now `runner.init` via `scripts/bailiff.py`) must write **no** bailiff file into the project (FR-002). If the writer lives in `cli.py`, it goes with T009.
- [ ] T009 [US4] Delete `src/bailiff/cli.py` entirely: its verbs now live in `scripts/bailiff.py` (which imports the same `discovery`/`trust`/`runner` libs), so there is nothing left to keep — a lone entrypoint avoids two drifting surfaces. Update `tests/test_smoke.py` (T020) which imported `bailiff.cli:main`.
- [ ] T010 [US4] Grep the repo for stale references and fix each: `grep -rniE 'project.scripts|bailiff.cli|just reproduce|justfile|_REPRODUCE_JUST|uvx bailiff|console script'` across `src/ tests/ skills/ scripts/ specs/010* README.md`. (Do NOT rewrite 001's historical spec/plan/contract prose — those accurately record what 001 shipped.)

**Checkpoint**: no justfile written on init; one entrypoint (`scripts/bailiff.py`); `cli.py` gone; no stale console/just references outside historical 001 docs.

---

## Phase 4: US1 — reproduce config-consistently; copier-only fallback works

**Purpose**: the headline guarantee — `bailiff.py reproduce` and the by-hand
copier-only path produce identical output. **P1.**

- [ ] T011 [P] [US1] Adapt `tests/loop/test_reproduce.py`: (a) reproduce a fixture-generated project via `scripts/bailiff.py reproduce` (subprocess); (b) in a separate clone, reproduce by hand with **`copier recopy --vcs-ref=:current: --defaults --overwrite`** and **no bailiff import, no `just`**; assert both trees are config-consistent to each other and to the recorded commit (empty exclusion set as in 001). Assert the project dir contains **no `justfile`** and no bailiff file (SC-002).
- [ ] T012 [US1] Keep `src/bailiff/runner.reproduce` unit-tested as the per-layer driver; assert the copier-only-by-hand fallback (T011 part b) needs no bailiff on PATH — i.e. `bailiff.py` is ergonomics, not a reproduce-time dependency.

**Checkpoint**: `uv run pytest tests/loop/test_reproduce.py` passes; both the `bailiff.py` path and the copier-only-by-hand path reproduce config-consistently with zero bailiff artifacts.

---

## Phase 5: US2 — the full loop via the portable skill

**Purpose**: the SKILL drives the bundled script across the whole loop with no LLM
in the mechanical path. **P1.**

- [ ] T013 [US2] Rewrite `skills/bailiff/SKILL.md`: update the frontmatter description (portable, auto-trigger; drop "driven by the `bailiff` CLI"); replace every `bailiff <verb>` with `./scripts/bailiff.py discover|trust|init|reproduce` (per `contracts/invocation.md`); remove every `just reproduce` / installed-`bailiff` reference; update Prerequisites (`copier` + `git` + `gh`; `scripts/bailiff.py` runnable via `uv run`, no bailiff on PATH). Keep the two-phase boundary + trust-consent steps intact.
- [ ] T014 [US2] In `SKILL.md` step 5/6, document `scripts/bailiff.py init --run-spec … [--check]` and `scripts/bailiff.py reproduce`, PLUS the copier-only-by-hand fallback (`copier recopy --vcs-ref=:current: --defaults --overwrite` per answers file) stating reproduce needs neither bailiff nor just (FR-003). Point references at `specs/010-delivery-reshape/contracts/invocation.md`.
- [ ] T015 [P] [US2] Adapt `tests/loop/test_init.py` and `tests/loop/test_check.py` to invoke `scripts/bailiff.py init [--check]` for a fixture template; assert recorded answers correctness, that `--check` writes nothing, and that a real init writes no bailiff file.
- [ ] T016 [P] [US2] Adapt `tests/loop/test_trust_refusal.py`: an action-taking untrusted source is refused (bailiff names the prefix / exit 3, copier authoritatively re-checks), then `scripts/bailiff.py trust add --from-source <src>` records consent, then `scripts/bailiff.py init` succeeds. Adapt `tests/loop/test_discover_static_safe.py` + `test_answersfile_refusal.py` + `test_secret_edge_exclusion.py` to the `scripts/bailiff.py` invocation (behavior unchanged; VI refusal asserted via discover output and re-checked at init).

**Checkpoint**: the full loop runs via `scripts/bailiff.py`; all adapted loop tests pass; SKILL has zero console-script/just references.

---

## Phase 6: US3 — multi-template reproduce contract (contract only; impl is 003)

**Purpose**: this spec fixes the **reproduce-time recompute contract**; the
ordering algorithm + orchestrator implementation are spec 003. **P1 (contract).**

- [ ] T017 [US3] In `contracts/invocation.md` (reproduce section) confirm the recompute contract is stated precisely: order recomputed from committed `.copier-answers*.yml` + each template fetched at its pinned `_commit`, `when:false` edges read, topo-sorted with a **stable, documented tie-break**; emits one `copier recopy --vcs-ref=:current:` per layer; **no frozen recipe/DAG file** committed. (No code here — this is the contract 003 must satisfy, FR-004/FR-005.)
- [ ] T018 [P] [US3] Add a SKIPPED/xfail placeholder test `tests/loop/test_multitemplate_recompute.py` referencing spec 003, documenting the intended assertions (order respects edges; twice-run config-consistent; resolution uses only committed answers + pinned fetches; edge-independent disjoint-path templates are order-independent). Mark it clearly deferred so 003 fills it in — do NOT implement ordering here.

**Checkpoint**: the multi-template contract is unambiguous in `invocation.md`; a clearly-deferred placeholder test names the 003 obligations.

---

## Phase 7: US4 — no console script / no generated artifact (verification)

**Purpose**: lock the FR-001/FR-002 outcomes with tests. **P1.**

- [ ] T019 [P] [US4] Add `tests/unit/test_no_console_script.py`: parse `pyproject.toml`, assert it declares no `[project.scripts] bailiff`; assert `scripts/bailiff.py` exists, is executable, and `uv run scripts/bailiff.py --help` exits 0 (subprocess).
- [ ] T020 [P] [US4] Adapt `tests/test_smoke.py`: drop the `from bailiff.cli import main` console assumption; assert the package imports and `scripts/bailiff.py` runs as a script instead.
- [ ] T021 [US4] Update `scripts/try-bailiff.sh`: use `uv run scripts/bailiff.py discover|trust` + direct `copier copy`/`recopy`; remove the "installed `bailiff` console script" framing (line ~7) and the justfile cat step (line ~125). It should demonstrate a copier-only reproduce (no bailiff) as the finale.

**Checkpoint**: `uv run pytest tests/unit/test_no_console_script.py tests/test_smoke.py` passes; `bash scripts/try-bailiff.sh` runs end-to-end.

---

## Phase 8: Live smoke + full quality gate

- [ ] T022 [US2] Adapt `tests/loop/test_smoke_remote.py` (marked `network`) to the new invocation: `scripts/bailiff.py discover|trust|init|reproduce` against `bailiff-io/bailiff-template-example` @ v1.0.0; keep it `-m network` (deselected by default). Also assert the copier-only-by-hand reproduce works against the real remote.
- [ ] T023 Run the full gate and fix to green: `uv run ruff check src/ tests/ scripts/ && uv run ruff format --check src/ tests/ scripts/ && uv run mypy && uv run pytest -q` (hermetic). Then `uv run pytest -m network -v` (live). Confirm `scripts/bailiff.py` is covered by ruff/mypy (add `scripts/` to `[tool.mypy] files` / ruff targets if needed).

**Checkpoint**: ruff + mypy-strict clean over `src/ tests/ scripts/`; all hermetic tests + the live smoke pass.

---

## Phase 9: Docs + spec closeout

- [ ] T024 [P] Update `README.md`: reflect the bundled-script invocation + copier-only reproduce; remove any residual console-script/PyPI/just framing.
- [ ] T025 Mark spec 010 in `.specify/memory/roadmap.md` (`specced` → `implemented`), note the delivery contract is now realized, and confirm the spec-003 entry's dependency on 010's contract still reads correctly.
- [ ] T026 Open the PR (title = user-facing changelog entry, no spec IDs; `## Spec Context` body section per the hook). Push via `dgit push` (not plain `git push`).

---

## Dependencies & parallelism

- **Setup (T001–T003) blocks everything.** Phase 2 (T004–T007c) blocks the story
  phases (they invoke `scripts/bailiff.py`).
- **Phase 3 (T008–T010)** can proceed alongside Phase 2 (different files) but T010's
  grep-sweep should run last in the phase.
- **US1 (T011–T012), US2 (T013–T016), US4 (T019–T021)** are largely parallel across
  files once Phases 1–3 land; `[P]` marks the safe-to-parallelize tasks.
- **US3 (T017–T018)** is contract/doc + a deferred placeholder — no code dependency
  on the others.
- **Phase 8–9** are the closing gate + docs; run after the story phases are green.

## Definition of done (maps to spec Success Criteria)

- SC-001 — US1 test reproduces config-consistently with **copier alone** (T011).
- SC-002 — no bailiff file in a generated project; asserted in T011/T015/T019.
- SC-003 — no `[project.scripts] bailiff`; `scripts/bailiff.py` is the surface;
  reproduce/update are portable skills (T001/T013/T019).
- SC-004 — multi-template recompute **contract** fixed (T017); implementation +
  its config-consistent/order tests are spec 003 (T018 placeholder).
- SC-005 — 001's guarantees (faithful reproduce, trust gating, static-safe
  discovery) stay green under the new packaging (T016/T022/T023).
