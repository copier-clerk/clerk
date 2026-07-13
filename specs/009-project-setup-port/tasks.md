---
description: "Phase-0 task list for spec 009 (clerk-mod-base + clerk-mod-python)"
---

# Tasks: project-setup module port → clerk-mod-* — **Phase 0 (v1)**

**Input**: [plan.md](./plan.md) + [spec.md](./spec.md) (CLARIFIED).

**Scope**: Phase 0 = collapsed `clerk-mod-base` + `clerk-mod-python` ONLY. Phases 1–3 are
deferred (plan.md *Forward note*). Do NOT author later-phase modules.

**Tests**: REQUIRED. The spec mandates an init+reproduce integration test per module
(FR-008, Constitution VII c) and a contract-lint gate (FR-009). Test tasks are included.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency).
- **[Story]**: US1–US5 from spec.md.
- All paths are relative to the monorepo root (the worktree).

## Constants / source references

- project-setup source (READ-ONLY): `~/.claude/skills/project-setup/modules/<m>/`.
- Authoring plane: `just new-module name=…`, `just check-modules`, `_meta/module-template/`.
- Trust-gated `_task` pattern to copy: `examples/clerk-template-example/copier.yml`.
- Threading + `when:false` edge pattern to copy: `specs/007-agentic-module/tasks.md`
  T004–T006 and `templates/clerk-mod-apm/copier.yml` once it exists.
- Fixtures: `tests/loop/` + `build_template_repo` / `multi_template_set` in `tests/conftest.py`.

---

## Phase 1: Setup — scaffold both modules

**Purpose**: contract-complete stubs registered three ways; empty stubs pass the lint.

- [x] T001 Verify Phase-0 source manifests before porting (Assumptions caveat): read
  `~/.claude/skills/project-setup/modules/{core-identity,dirs-scaffold,gitignore-generate,license-write,agents-md,git-init}/module.toml`
  + `module.py`, and the `agents-md/steering/resolve-arch.md` + `templates/{single,monorepo}.md`.
  For `clerk-mod-python`: its full manifest is **NOT locally present** — record the exact
  ported behaviour from `~/.claude/skills/project-setup/addons/catalog.json` (lang-python
  entry) + SKILL.md characterization (`pins 3.13, uv + pyproject.toml`, appends Python
  `.gitignore` entries, ruff hooks). Write findings inline as porting notes; do NOT invent
  behaviour beyond these sources (FR-011).
- [x] T002 Scaffold base: `just new-module name=clerk-mod-base`. Confirm it creates
  `templates/clerk-mod-base/` with `copier.yml`, `{{ _copier_conf.answers_file }}.jinja`,
  `README.md`, `CHANGELOG.md`, and the registration edits in
  `cog.toml [monorepo.packages.clerk-mod-base]` + `catalog-sources.toml`.
- [x] T003 [P] Scaffold python: `just new-module name=clerk-mod-python`. Same
  confirmation for `templates/clerk-mod-python/`.
- [x] T004 Run `just check-modules` — both fresh stubs MUST report `ok` (three-way
  registration parity green). (SC-006 pre-check.)

**Checkpoint**: two registered empty stubs; lint green.

---

## Phase 2: Foundational — questions, edges, threading, answers files

**Purpose**: the `copier.yml` shells every user story depends on. **Blocks US1–US5.**

- [x] T005 [US1] Author `clerk-mod-base` identity + choice questions in
  `templates/clerk-mod-base/copier.yml` (FR-003 / Q7): `project_name` (str),
  `org` (str, default `acme`), `description` (str, default `""`), `layout`
  (choices `[single, monorepo]`, default `single`), `license` (choices = the **13** SPDX
  keys VERBATIM from `license-write/module.toml`: agpl-3.0, apache-2.0, bsd-2-clause,
  bsd-3-clause, bsl-1.0, cc0-1.0, epl-2.0, gpl-2.0, gpl-3.0, lgpl-2.1, mit, mpl-2.0,
  unlicense; default apache-2.0), and `today` (injected answer, blank default — mirror
  `clerk-template-example`). NO `secret:` questions (FR-002 / SC-007).
- [x] T006 [US1] Author `clerk-mod-base` gate + task-control booleans (Q5 / FR-007a):
  `write_architecture: bool = false` (gates the AGENTS.md arch splice),
  `initial_commit: bool = false` (gates the git commit task). Author the
  `gitignore_stack` list answer (default `[]`; injected via `--data` at init — Q7) and the
  frozen agent facts `architecture_md: str = ""` + `agent_editable_globs` (list, default
  `[]`) as normal answers (FR-006). Author `_subdirectory: template`.
- [x] T007 [US1] Declare `clerk-mod-base` edges as `when:false` hidden answers with
  `default: []` (FR-004): `depends_on`, `run_after`, `run_before` — all empty (base is the
  upstream root; its internal 6-module ordering is template-internal per Q1/FR-013, NOT
  cross-module edges).
- [x] T008 [P] [US2] Author `clerk-mod-python` questions in
  `templates/clerk-mod-python/copier.yml`: threaded `project_name`
  (`default: "{{ project_name }}"`, standalone fallback — FR-010, SC-006-style),
  `python_version` (fixed `choices:` incl. the pinned default `3.13` per SKILL.md — Q7),
  and `today` injected. Confirm python contributes `python` into the shared
  `gitignore_stack` (see T017), not its own `.gitignore`.
- [x] T009 [US2] Declare `clerk-mod-python` edge in `copier.yml` as a `when:false` hidden
  answer `run_after: [clerk-mod-base]` (ADR-0003 / plan *Ordering*); `depends_on`/
  `run_before` default `[]`. Do NOT hardcode that base supplies `project_name` (FR-010).
- [x] T010 Confirm both answers-file `.jinja` files exist and render the copier answers
  (`{{ _copier_answers|to_nice_yaml }}`); run `just check-modules` — still `ok`. (VI a.)

**Checkpoint**: both `copier.yml` shells complete; `project_name` threads base→python;
edges parse; lint green.

---

## Phase 3: US1 — Scaffold a project from the base module (Priority: P1) 🎯 MVP

**Goal**: selecting `clerk-mod-base` produces the dir scaffold, `.gitignore`, `LICENSE`,
`AGENTS.md`, and a committed `.copier-answers.yml`; `git init` runs as a trust-gated task;
untrusted source is refused at exit 3 before any task runs. (Spec US1 / SC-001, SC-004.)

**Independent Test**: `clerk init` `clerk-mod-base` with `project_name=demo org=acme
license=MIT` on a trusted source → scaffold + answers present; repeat untrusted → exit 3.

### Implementation for US1

- [x] T011 [P] [US1] Author the **managed dir scaffold**: create
  `templates/clerk-mod-base/template/<dir>/.gitkeep` for each base dir taken VERBATIM from
  `dirs-scaffold/module.py` `_BASE_DIRS` (verify the EXACT count/list at port — the
  docstring says 21 but the local array is 20; FR-011 forbids drift). Gate the 15
  `_MONOREPO_TARGETS` dirs on `layout=monorepo` (a Jinja `{% if %}` in a computed path or
  a `_skip_if_exists`-independent conditional subtree). MANAGED lifecycle (byte-identical).
- [x] T012 [US1] Author `templates/clerk-mod-base/template/AGENTS.md.jinja` (SEED-ONCE):
  render the `single.md` or `monorepo.md` body (from agents-md/templates/) chosen by
  `layout`, substituting `PROJECT_NAME`→`project_name`, `ORG`→`org`, and the description
  placeholder from `description`. Render the `## Architecture` sentinel span from frozen
  `architecture_md` **iff `write_architecture=true`** (else leave the empty sentinel pair
  — Q3/Q5). Keep the sentinel markers verbatim.
- [x] T013 [US1] Add the base `_tasks` block to `copier.yml` in the plan's order
  (FR-007 / Q6 / Q7): (1) **preflight** `_task` FIRST checking `git`/`gh`/`gitnr` on PATH,
  failing with explicit install guidance (FR-007b); (2) **gitnr** `.gitignore` generation
  from `gitignore_stack`, `gitnr` **version-pinned** in the command (Q7 — task-output);
  (3) **gh** LICENSE fetch `test -f LICENSE || gh api /licenses/{{ license }}` filling
  `[year]`/`[fullname]` from `{{ today }}`/`{{ org }}` (copy `clerk-template-example`);
  (4) `git init --quiet`; (5) `git add -A && git commit` guarded `when: initial_commit`.
  Token read from ambient env, never an answer (FR-002).
- [x] T014 [US1] Add `_skip_if_exists: ["AGENTS.md"]` to `clerk-mod-base/copier.yml`
  (FR-005a / D-009-7). `.gitignore` and `LICENSE` are task-output so are NOT in the
  `_skip_if_exists` render list; their idempotency is the task guard (T013).
- [x] T015 [US1] Author `clerk-mod-base` README prerequisites section documenting
  `git` + `gh` (authenticated) + `gitnr` (FR-007b) and the seed-once/managed lifecycle.
- [x] T016 [P] [US1] Add the `clerk-mod-base` fixture to `tests/conftest.py` reusing
  `build_template_repo`; stub the gitnr/gh/git `_tasks` to deterministic offline no-ops
  (write marker files, no network) so the suite is hermetic.
- [x] T017 [P] [US1] `tests/loop/test_base_render.py` (US1 #1, SC-001): init
  `clerk-mod-base` with `project_name=demo org=acme license=mit layout=single` → assert
  the base dir scaffold `.gitkeep`s exist (managed), `AGENTS.md` present with substituted
  identity, `.copier-answers.yml` records `_src_path` + `_commit`, and the stubbed tasks
  produced `.gitignore` + `LICENSE`. Assert `layout=monorepo` adds the 15 targets.
- [x] T018 [US1] `tests/loop/test_base_trust.py` (US1 #2, SC-004): init an UNTRUSTED
  base source → assert refusal at exit 3 naming `trust add`, BEFORE any `_task` runs
  (no `.git`, no LICENSE written).

**Checkpoint**: base scaffolds correctly; untrusted refused; `check_modules` green.

---

## Phase 4: US2 — Add the Python overlay on top of base (Priority: P1)

**Goal**: `[clerk-mod-base, clerk-mod-python]` applies base first (edge-ordered), threads
`project_name`, and produces `pyproject.toml` + Python `.gitignore` entries — the output
lang-python produces. (Spec US2 / SC-002.)

**Independent Test**: init `[base, python]` with `python_version=3.13` → base renders
first, python after; `project_name` threaded; `pyproject.toml` present. Init python alone
→ renders standalone with defaults.

### Implementation for US2

- [x] T019 [US2] Author `templates/clerk-mod-python/template/pyproject.toml.jinja`
  (SEED-ONCE): uv/ruff/pytest config + `requires-python` pinned from `python_version`;
  `[project].name = "{{ project_name }}"`. Port config faithfully from the lang-python
  characterization recorded in T001 (do NOT invent fields beyond it; flag gaps — FR-011).
- [x] T020 [US2] Add `_skip_if_exists: ["pyproject.toml"]` to
  `clerk-mod-python/copier.yml` (FR-005a — language manifest is seed-once).
- [x] T021 [US2] Add the `clerk-mod-python` **uv preflight `_task`** ordered FIRST
  (FR-007b / Q6): checks `uv` on PATH, fails with the astral install URL. Document `uv` in
  the module README.
- [x] T022 [US2] Thread the Python `.gitignore` contribution through base's
  `gitignore_stack` (plan *Ordering*): at init the skill injects `python` into
  `gitignore_stack` via `--data`; confirm python's template writes NO `.gitignore` itself
  (single writer, idempotent reproduce). Flag if the local characterization disagrees.
- [x] T023 [P] [US2] Add the `clerk-mod-python` fixture to `tests/conftest.py`; extend
  `multi_template_set` to build the ordered `[clerk-mod-base, clerk-mod-python]` pair with
  the `run_after` edge.
- [x] T024 [US2] `tests/loop/test_python_overlay.py` (US2 #1, SC-002): init
  `[base, python]` `python_version=3.13` → assert base rendered before python (edge order),
  `pyproject.toml` present with threaded `project_name` + pinned `requires-python`, and
  the gitnr stack included `python`.
- [x] T025 [P] [US2] `tests/loop/test_python_standalone.py` (US2 #2, SC-006-style):
  init `clerk-mod-python` ALONE → renders with default `project_name`; no crash from the
  missing base layer.

**Checkpoint**: overlay renders after base; threading works; standalone works.

---

## Phase 5: US3 — Reproduce faithfully (Priority: P1)

**Goal**: reproduce `[base, python]` on a fresh checkout re-renders managed files
byte-identically and re-runs trust-gated tasks; order recomputed from committed answers.
(Spec US3 / SC-003.)

### Implementation for US3

- [x] T026 [US3] `tests/loop/test_base_python_reproduce.py` (US3 #1, SC-003): generate
  `[base, python]`, then reproduce onto a fresh checkout → assert MANAGED files (dir
  scaffold `.gitkeep`s, `AGENTS.md` on fresh tree, `pyproject.toml` on fresh tree,
  `.copier-answers.yml`) are byte-identical; assert reproduce order recomputed from
  committed answers + pinned edges (base before python), not a frozen recipe.
- [x] T027 [US3] Extend the reproduce test (US3 #2): assert trust-gated tasks
  (git init, gitnr `.gitignore`, gh LICENSE) RE-RUN under trust at reproduce and are
  idempotent (the `test -f` / `git init` no-op guards hold); their outputs are
  process-deterministic, not asserted byte-identical (Constitution III).

**Checkpoint**: managed byte-identical; tasks re-run idempotently.

---

## Phase 6: US4 — Agent-steered replay + seed-once protection (Priority: P2)

**Goal**: the `agents-md` architecture decision (frozen structured facts) replays
deterministically at reproduce with no agent; seed-once files edited after init are NOT
clobbered on a re-run. (Spec US4 / SC-005, SC-003a.)

### Implementation for US4

- [x] T028 [US4] `tests/loop/test_arch_replay.py` (US4 #1, SC-005): init base with
  `write_architecture=true` + frozen `architecture_md` (+ `agent_editable_globs`) injected
  as `--data` → assert the `## Architecture` sentinel span renders those facts. Reproduce
  → assert the span re-renders byte-identically from the frozen answer, NO agent call.
  Also assert `write_architecture=false` leaves the empty sentinel pair (Q5 gate).
- [x] T029 [US4] `tests/loop/test_seed_once.py` (US4 #2, SC-003a): generate `[base,
  python]`, hand-edit `AGENTS.md` and `pyproject.toml`, then re-run/`update` over the
  populated tree → assert both edited files are PRESERVED (`_skip_if_exists`), while a
  managed file (a scaffold `.gitkeep`) is still re-rendered.

**Checkpoint**: frozen arch facts replay agent-free; seed-once files protected.

---

## Phase 7: US5 — Contract lint + registration + docs (Priority: P1)

**Goal**: both modules pass `just check-modules` and are fan-out-registered; SKILL.md
documents the family. (Spec US5 / SC-006, SC-008.)

### Implementation for US5

- [x] T030 [US5] Run `just check-modules` on the finished modules → MUST report `ok`:
  answers-file `.jinja` present, README + CHANGELOG present, three-way registration
  parity (`templates/` == `cog.toml [monorepo.packages]` == `catalog-sources.toml`), no
  published-label mutation (SC-006).
- [x] T031 [P] [US5] Add the spec-005 secrets-policy assertion coverage: confirm neither
  module declares a `secret:` question so `tests/loop/test_secrets_policy.py` stays green
  (SC-007). (No new test if the existing lint already scans `templates/`.)
- [x] T032 [P] [US5] Update `skills/clerk/SKILL.md` (FR-012): document the ported family
  (which modules exist: `clerk-mod-base` + `clerk-mod-python`), the **base-selection
  step**, per-module trust consent for the git/gh/gitnr/uv tasks, and the multi-layer
  handoff shape (base first, then python `run_after`). Note the base is always the
  identity root.
- [x] T033 [US5] Confirm the Phase-0 slice unblocks 008b (SC-008): with ≥1 real module
  under `templates/`, `just check-modules` is a real gate (not the empty no-op), and the
  `cog.toml pre_bump_hooks` can drop its `|| true`. Note this in the module CHANGELOGs;
  do NOT run the fan-out CI (008b owns it).

**Checkpoint**: lint green; registered; SKILL.md documents the family; 008b unblocked.

---

## Phase 8: Polish

- [x] T034 [P] Optional sanity: `just lint` / `uv run mypy` (docs/config only — not
  required by the plan). Confirm no `jinja2_time` / random filters in either `copier.yml`
  (Constitution V).
- [x] T035 Final review against FR-001..013 + SC-001..008; record any residual ambiguity
  (git-commit scope, gitnr stack threading, lang-python ruff-hook deferral) as inline
  notes in the module READMEs for the implementer.

---

## Dependencies & Execution Order

- **Phase 1 (Setup)**: no deps — start immediately.
- **Phase 2 (Foundational)**: after Setup — BLOCKS US1–US5.
- **US1 (Phase 3)** & **US2 (Phase 4)**: after Foundational. US2 depends on US1's base
  render existing for the *multi-layer* test (T024) but the python template authoring
  (T019–T022) is independent of US1 authoring and may run in parallel.
- **US3 (Phase 5)**: after US1 + US2 (needs a generated `[base, python]` project).
- **US4 (Phase 6)**: after US1 (arch splice) + US2 (pyproject seed-once).
- **US5 (Phase 7)**: after both modules authored; T030 is the final gate.
- **Polish (Phase 8)**: last.

### Parallel opportunities

- T002 / T003 (scaffold both modules) — [P].
- Base authoring (T005–T007) and python authoring (T008–T009) — largely [P] (different
  files) once stubs exist.
- Test-writing tasks marked [P] (T016, T017, T023, T025, T031, T032) run in parallel
  where they touch different files.

## SC → task traceability

| SC | Covered by |
|---|---|
| SC-001 (base scaffold + managed byte-identical; gitnr/gh task-output; AGENTS.md seed-once) | T011, T012, T013, T014, T017, T026 |
| SC-002 (`[base, python]` base-first, threads project_name, lang-python output) | T008, T009, T019, T024 |
| SC-003 (reproduce managed byte-identical; order recomputed) | T026 |
| SC-003a (seed-once not clobbered on re-run) | T014, T020, T029 |
| SC-004 (untrusted refused at exit 3 before tasks) | T018 |
| SC-005 (agent-drafted output replays from frozen answer, no agent) | T012, T028 |
| SC-006 (both modules pass `check-modules`, fan-out-registered) | T004, T010, T030 |
| SC-007 (no `secret:` question; policy lint green) | T005, T031 |
| SC-008 (slice unblocks 008b fan-out e2e) | T030, T033 |

## Notes

- [P] = different files, no dependency. [Story] maps task to spec user story.
- Verify each integration test fails before authoring the template content it asserts
  (Constitution VII / tests-first for the loop tests).
- Commit after each logical group; do NOT run the 008b fan-out CI (out of scope).
- **Residual ambiguities flagged in-doc** (resolve at implementation, do not invent):
  (1) exact base dir list count (20 vs docstring's 21 — T011); (2) `clerk-mod-python`
  full manifest not locally present — ruff pre-commit hook contribution has no Phase-0
  file to append to (T022, plan mapping); (3) git-init commit scope (project-setup's
  git-init `after`-edges every module including later-phase ones — in Phase 0 the commit
  is simply the last base `_task`, which is faithful for a base+python selection).
