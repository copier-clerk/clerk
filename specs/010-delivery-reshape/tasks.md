---
description: "Task list for clerk delivery reshape — skill-bundled copier wrapper (spec 010)"
---

# Tasks: clerk delivery reshape — skill-bundled copier wrapper

**Input**: Design documents from `specs/010-delivery-reshape/`
**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (user stories),
[contracts/invocation.md](./contracts/invocation.md),
[constitution](../../.specify/memory/constitution.md) v2.1.0

**Tests**: INCLUDED. Constitution VII makes per-step hardening (copier-only
byte-identical reproduce, error surfacing, static-discovery safety) part of this
spec's definition-of-done, so test tasks are first-class.

**Organization**: grouped by user story (US1–US4 from spec.md) so each is
independently verifiable.

## Design decision this task list assumes (from plan.md)

- The deterministic coordination is **one bundled script** `scripts/clerk.py`
  (`./scripts/clerk.py` / `uv run scripts/clerk.py`), scoped to `discover` +
  `trust` (copier-can't work). Single-template init/reproduce/check are invoked as
  **copier directly**, documented in the SKILL — NOT wrapped by clerk.
- `runner.py` is **retained as library substrate** for the spec-003 orchestrator
  (plan.md "Open decision" option (a), RECOMMENDED). If you instead choose the
  YAGNI-strict option (b), delete tasks T012, T031 and remove `runner.py` +
  `tests/unit` runner coverage instead of retaining them.
- The Constitution VI reproducibility gate lives at **discovery**; the trust
  prefix suggestion moves to `clerk.py trust --from-source`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no incomplete-task dependency)
- **[Story]**: US1–US4 (user-story tasks only)
- Exact file paths included

---

## Phase 1: Setup (packaging + invocation surface)

**Purpose**: strip the console-script/application framing; stand up the bundled
script skeleton. This is the FR-001 / US4 core.

- [ ] T001 [US4] Remove `[project.scripts] clerk = "clerk.cli:main"` from `pyproject.toml` (FR-001/SC-003). Decide + apply the lightest layout that keeps `import clerk` working for tests and `mypy --strict` green: keep `[tool.hatch.build.targets.wheel] packages = ["src/clerk"]` for editable installs, OR switch tests to a src-on-path layout. Update the `pyproject.toml` description if it still frames clerk as an installable CLI.
- [ ] T002 [US4] Create `scripts/clerk.py` skeleton: shebang (`#!/usr/bin/env python3`), executable bit (`chmod +x`), module docstring stating it is the bundled orchestration script (discover/trust only; copier invoked directly for the rest), stdlib `argparse` with subparsers `discover` and `trust`, and a `main(argv)` that imports `clerk.discovery`/`clerk.trust`/`clerk.errors` and dispatches. Mirror 001 cli.py's error→exit mapping (0/1/2/3). Make it importable AND runnable via `uv run scripts/clerk.py`.
- [ ] T003 [P] [US4] Verify the two run modes work: `uv run scripts/clerk.py --help` and `./scripts/clerk.py --help` both print usage. Document any `sys.path` shim `scripts/clerk.py` needs to import `clerk.*` when run directly (prefer keeping deps importable via the project env over a bespoke shim).

**Checkpoint**: `pyproject.toml` declares no `clerk` console script; `uv run scripts/clerk.py --help` works; `uv sync` + `mypy` clean.

---

## Phase 2: The bundled script's verbs (discover + trust)

**Purpose**: move the copier-can't logic behind `scripts/clerk.py`; relocate the
VI gate and prefix suggestion. **Blocks the story phases** (they invoke these).

- [ ] T004 [US2] Wire `scripts/clerk.py discover <source> [--ref REF]` to `clerk.discovery.discover(...)`, printing the same JSON as 001 (`discovery-output.md` shape unchanged). No behavior change to `src/clerk/discovery.py` — this is re-exposure.
- [ ] T005 [US2] Wire `scripts/clerk.py trust list` and `trust add <prefix>` to `clerk.trust.list_trust()`/`add_trust(...)` (idempotent; honors `COPIER_SETTINGS_PATH`). Behavior identical to 001's `clerk trust`.
- [ ] T006 [US2] Add `scripts/clerk.py trust add --from-source <src>`: compute the owner-path prefix using the existing suggestion logic (lift `_suggest_prefix` from `src/clerk/runner.py` into `src/clerk/trust.py` so both the script and the retained runner share one implementation) and record it. This replaces 001's prefix suggestion that was embedded in the init refusal path.
- [ ] T007 [US1] Confirm the Constitution VI reproducibility refusal is fully expressible at discovery: `discover` already emits `reproducible`; ensure the JSON + `DiscoveryError` messaging make "stop, do not init" unambiguous for the SKILL. If any refusal logic only existed inside `runner._require_reproducible`, ensure the equivalent is reachable from discover output (do not rely on init to surface it).

**Checkpoint**: `uv run scripts/clerk.py discover <fixture>` and `trust add|list` behave exactly as 001's `clerk` verbs; VI gate surfaced by discover.

---

## Phase 3: Remove the generated justfile + reduce cli.py (US4)

**Purpose**: no clerk artifact in generated projects; retire the console entry
point wiring.

- [ ] T008 [US4] Delete the justfile writer from `src/clerk/cli.py`: remove `_REPRODUCE_JUST`, `_write_reproduce_recipe`, and the `_write_reproduce_recipe(...)` call in `_cmd_init`. `init` must write **no** clerk file into the project (FR-002).
- [ ] T009 [US4] Remove the console-script wiring from `src/clerk/cli.py` (the `init`/`reproduce` command dispatch and `main()` as a `[project.scripts]` entry). Since `scripts/clerk.py` now owns discover/trust, either (a) delete `src/clerk/cli.py` entirely if nothing imports it, or (b) reduce it to a thin shim that `scripts/clerk.py` re-uses — a code check decides; prefer deletion to avoid two entrypoints.
- [ ] T010 [US4] Grep the repo for stale references and fix each: `grep -rniE 'project.scripts|clerk.cli|just reproduce|justfile|_REPRODUCE_JUST|uvx clerk|console script'` across `src/ tests/ skills/ scripts/ specs/010* README.md`. (Do NOT rewrite 001's historical spec/plan/contract prose — those accurately record what 001 shipped.)

**Checkpoint**: no justfile written on init; one entrypoint (`scripts/clerk.py`); no stale console/just references outside historical 001 docs.

---

## Phase 4: US1 — reproduce with copier alone (no clerk, no just)

**Purpose**: the headline guarantee. **P1.**

- [ ] T011 [P] [US1] Adapt `tests/loop/test_reproduce.py`: reproduce a fixture-generated project by invoking **`copier recopy --vcs-ref=:current: --defaults --overwrite` directly** (subprocess, in the project dir) with **no clerk import and no `just`**; assert the rendered tree is byte-identical at the recorded commit (empty exclusion set as in 001). Add an assertion that the project dir contains **no `justfile`** and no clerk-specific file (SC-002).
- [ ] T012 [US1] (Option (a) only) Keep `src/clerk/runner.reproduce` as library substrate with its unit coverage, but ensure NO test requires clerk to be installed for the US1 path — the US1 test uses direct copier. (If option (b): delete `runner.reproduce` + its tests instead.)

**Checkpoint**: `uv run pytest tests/loop/test_reproduce.py` passes; the reproduce assertion uses copier directly and verifies zero clerk artifacts.

---

## Phase 5: US2 — reproduce/act via the portable skill

**Purpose**: the SKILL drives the bundled script + direct copier with no LLM in the
mechanical path. **P1.**

- [ ] T013 [US2] Rewrite `skills/clerk/SKILL.md`: update the frontmatter description (portable, auto-trigger; drop "driven by the `clerk` CLI"); replace `clerk discover|init|reproduce|trust` with `./scripts/clerk.py discover|trust` + **direct copier** for init/check/reproduce (per `contracts/invocation.md`); remove every `just reproduce` / installed-`clerk` reference; update Prerequisites (`copier` + `git` + `gh`; `scripts/clerk.py` runnable via `uv run`, no clerk on PATH). Keep the two-phase boundary + trust-consent steps intact.
- [ ] T014 [US2] In `SKILL.md` step 5/6, document the exact init command (`copier copy --data-file … --defaults --overwrite --trust <src> <dst>`) and the copier-only reproduce fallback (`copier recopy --vcs-ref=:current: --defaults --overwrite`), stating reproduce needs neither clerk nor just (FR-003). Point references at `specs/010-delivery-reshape/contracts/invocation.md`.
- [ ] T015 [P] [US2] Add/adapt `tests/loop/test_init.py` and `tests/loop/test_check.py` to invoke **direct copier** (`copier copy [--pretend] --data-file …`) for a fixture template; assert recorded answers correctness, that `--pretend` writes nothing, and that a real init writes no clerk file. Trust/discover steps in these tests go through `scripts/clerk.py`.
- [ ] T016 [P] [US2] Adapt `tests/loop/test_trust_refusal.py`: an action-taking untrusted source is refused **by copier itself** on direct `copier copy` (assert copier's refusal / non-zero), then `scripts/clerk.py trust add --from-source <src>` records consent, then the direct init succeeds. Adapt `tests/loop/test_discover_static_safe.py` + `test_answersfile_refusal.py` + `test_secret_edge_exclusion.py` to the `scripts/clerk.py discover` invocation (behavior unchanged; the VI refusal now asserted via discover output, not init).

**Checkpoint**: the full loop runs via `scripts/clerk.py` + direct copier; all adapted loop tests pass; SKILL has zero console-script/just references.

---

## Phase 6: US3 — multi-template reproduce contract (contract only; impl is 003)

**Purpose**: this spec fixes the **reproduce-time recompute contract**; the
ordering algorithm + orchestrator implementation are spec 003. **P1 (contract).**

- [ ] T017 [US3] In `contracts/invocation.md` (reproduce section) confirm the recompute contract is stated precisely: order recomputed from committed `.copier-answers*.yml` + each template fetched at its pinned `_commit`, `when:false` edges read, topo-sorted with a **stable, documented tie-break**; emits one `copier recopy --vcs-ref=:current:` per layer; **no frozen recipe/DAG file** committed. (No code here — this is the contract 003 must satisfy, FR-004/FR-005.)
- [ ] T018 [P] [US3] Add a SKIPPED/xfail placeholder test `tests/loop/test_multitemplate_recompute.py` referencing spec 003, documenting the intended assertions (order respects edges; twice-run byte-identical; resolution uses only committed answers + pinned fetches; edge-independent disjoint-path templates are order-independent). Mark it clearly deferred so 003 fills it in — do NOT implement ordering here.

**Checkpoint**: the multi-template contract is unambiguous in `invocation.md`; a clearly-deferred placeholder test names the 003 obligations.

---

## Phase 7: US4 — no console script / no generated artifact (verification)

**Purpose**: lock the FR-001/FR-002 outcomes with tests. **P1.**

- [ ] T019 [P] [US4] Add `tests/unit/test_no_console_script.py`: parse `pyproject.toml`, assert it declares no `[project.scripts] clerk`; assert `scripts/clerk.py` exists, is executable, and `uv run scripts/clerk.py --help` exits 0 (subprocess).
- [ ] T020 [P] [US4] Adapt `tests/test_smoke.py`: drop the `from clerk.cli import main` console assumption; assert the package imports and `scripts/clerk.py` runs as a script instead.
- [ ] T021 [US4] Update `scripts/try-clerk.sh`: use `uv run scripts/clerk.py discover|trust` + direct `copier copy`/`recopy`; remove the "installed `clerk` console script" framing (line ~7) and the justfile cat step (line ~125). It should demonstrate a copier-only reproduce (no clerk) as the finale.

**Checkpoint**: `uv run pytest tests/unit/test_no_console_script.py tests/test_smoke.py` passes; `bash scripts/try-clerk.sh` runs end-to-end.

---

## Phase 8: Live smoke + full quality gate

- [ ] T022 [US2] Adapt `tests/loop/test_smoke_remote.py` (marked `network`) to the new invocation: `scripts/clerk.py discover` + trust + **direct copier** init/reproduce against `copier-clerk/clerk-template-example` @ v1.0.0; keep it `-m network` (deselected by default). Assert copier-only reproduce works against the real remote.
- [ ] T023 Run the full gate and fix to green: `uv run ruff check src/ tests/ scripts/ && uv run ruff format --check src/ tests/ scripts/ && uv run mypy && uv run pytest -q` (hermetic). Then `uv run pytest -m network -v` (live). Confirm `scripts/clerk.py` is covered by ruff/mypy (add `scripts/` to `[tool.mypy] files` / ruff targets if needed).

**Checkpoint**: ruff + mypy-strict clean over `src/ tests/ scripts/`; all hermetic tests + the live smoke pass.

---

## Phase 9: Docs + spec closeout

- [ ] T024 [P] Update `README.md`: reflect the bundled-script invocation + copier-only reproduce; remove any residual console-script/PyPI/just framing.
- [ ] T025 Mark spec 010 in `.specify/memory/roadmap.md` (`specced` → `implemented`), note the delivery contract is now realized, and confirm the spec-003 entry's dependency on 010's contract still reads correctly.
- [ ] T026 Open the PR (title = user-facing changelog entry, no spec IDs; `## Spec Context` body section per the hook). Push via `dgit push` (not plain `git push`).

---

## Dependencies & parallelism

- **Setup (T001–T003) blocks everything.** Phase 2 (T004–T007) blocks the story
  phases (they invoke `scripts/clerk.py`).
- **Phase 3 (T008–T010)** can proceed alongside Phase 2 (different files) but T010's
  grep-sweep should run last in the phase.
- **US1 (T011–T012), US2 (T013–T016), US4 (T019–T021)** are largely parallel across
  files once Phases 1–3 land; `[P]` marks the safe-to-parallelize tasks.
- **US3 (T017–T018)** is contract/doc + a deferred placeholder — no code dependency
  on the others.
- **Phase 8–9** are the closing gate + docs; run after the story phases are green.

## Definition of done (maps to spec Success Criteria)

- SC-001 — US1 test reproduces byte-identically with **copier alone** (T011).
- SC-002 — no clerk file in a generated project; asserted in T011/T015/T019.
- SC-003 — no `[project.scripts] clerk`; `scripts/clerk.py` is the surface;
  reproduce/update are portable skills (T001/T013/T019).
- SC-004 — multi-template recompute **contract** fixed (T017); implementation +
  its byte-identical/order tests are spec 003 (T018 placeholder).
- SC-005 — 001's guarantees (faithful reproduce, trust gating, static-safe
  discovery) stay green under the new packaging (T016/T022/T023).
