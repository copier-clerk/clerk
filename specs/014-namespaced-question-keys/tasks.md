---
description: "Task list — spec 014: private-by-default threading, _external_data facts, universal fragment/merge, forge cleanup"
---

# Tasks: Private-by-default answer threading, `_external_data` facts, fragment/merge model, forge cleanup (spec 014)

**Input**: `specs/014-namespaced-question-keys/` — spec.md (FR-001..024, SC-001..009), plan.md,
decisions-ledger.md (R1–R12), data-model.md, contracts/ (`_threading.md`, `_facts.md`,
`_fragment-merge.md`), quickstart.md.

**Prerequisites**: on branch `014-namespaced-question-keys`; origin/main green; the ledger + spec +
plan + contracts are RATIFIED and consistent (HEAD `11b55d0`). The `framework` point-fix and the
byte→config prose reframe already merged to main.

**Tests**: This spec explicitly requests tests (SC-001..009 name specific loop/integration tests).
Test tasks are INCLUDED and, per the engine gate, written to FAIL before the engine change lands.

**Organization**: Phases follow plan.md "Build/test/release sequencing". Phase 2 (engine + contract)
is the blocking gate; user-story phases (US1..US5 + forge cleanup) fan out per-module with worktree
isolation after the gate is frozen. Phase order = plan slices: Engine → Slice A (mise) →
Slice B (fragment/merge + facts) → Slice B2 (forge) → Slice C (docs) → verify → re-fanout.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no incomplete-task dependency)
- **[Story]**: US1..US5 (spec user stories) or FORGE (R12); Setup/Foundational/Polish carry none
- Exact repo paths included. Module dirs are `templates/bailiff-mod-<name>/`.

## Path conventions

- Engine: `src/bailiff/{runner,ordering,discovery}.py`; tests under `tests/loop/`, `tests/integration/`.
- Modules: `templates/bailiff-mod-<name>/copier.yml` + `templates/bailiff-mod-<name>/template/…`.
- Lint gate: `scripts/check_modules.py`; contracts under `specs/014-namespaced-question-keys/contracts/`.

---

## Phase 1: Setup (baseline + worktree hygiene)

**Purpose**: confirm a green starting point and the isolation harness before any change.

- [ ] T001 Confirm branch `014-namespaced-question-keys` at HEAD `11b55d0`; run the full non-network baseline DETACHED (`nohup uv run pytest tests/ -q -m "not network" > /tmp/014-baseline.log 2>&1 &`) and record pass/fail count from `/tmp/014-baseline.log`.
- [ ] T002 Run `uv run python scripts/check_modules.py` → confirm "ok — 27 module(s)" as the pre-change module-parity baseline.
- [ ] T003 [P] Read `tests/loop/` harness (`build_template_repo` / `multi_template_set` fixtures) and note the exact helper signatures the new isolation/external-data/ordering tests will call (no code change).

---

## Phase 2: Foundational — engine + contract gate (BLOCKS all module work)

**Purpose**: land the engine changes + the frozen contract. Per plan.md move 1–5 + R11. Nothing in
Phases 3+ may start until this phase is green and the contract is frozen.

**⚠️ CRITICAL**: All module rewrites (Slices A/B/B2) depend on this phase. Tests here are written to
FAIL first (engine still bleeds), then pass after the change.

### Tests first (write, ensure they FAIL against current engine)

- [ ] T004 [P] Write negative isolation loop test in `tests/loop/test_threading_isolation.py`: two layers with same bare key `q`, disjoint domains → no `InvalidRunSpecError`, each answers file records only its own `q` (SC-001/SC-005/SC-007). MUST fail on current bleed.
- [ ] T005 [P] Write `_external_data` fact-resolution test in `tests/loop/test_external_data.py`: present producer resolves; ABSENT producer → loud `OrderingError` naming the alias (SC-002, FR-006 inverted); non-base producer (moon) resolves.
- [ ] T006 [P] Write dependency-model + schema-gate tests in `tests/loop/test_ordering_phases.py`: single `depends_on` edge orders + dangling→error; forward cross-phase edge (`normal`→`post`) rejected at discovery (FR-020); pre-014 answers file (no `_bailiff_schema`) makes `reproduce_many` refuse (SC-008/FR-014).
- [ ] T007 [P] Write `_post_tasks` collection test in `tests/loop/test_post_tasks.py`: a module declaring `_post_tasks` has it run AFTER the render loop, in `depends_on` order, on BOTH init and reproduce (FR-021/R11).

### Engine implementation (src/bailiff/)

- [ ] T008 In `src/bailiff/runner.py` neuter private-answer accretion: at the `_merge_layer_answers` call site (~line 484) STOP growing `accumulated`; `accumulated` stays `{today}` for the whole run (seeded ~line 430). Remove/neutralize `_merge_layer_answers` (~line 532). Init path (FR-001/FR-002).
- [ ] T009 In `src/bailiff/runner.py` apply the SAME isolation to `reproduce_many` (~line 554+): reconstruct per-layer, no flattened namespace (FR-003).
- [ ] T010 In `src/bailiff/discovery.py` add static `_external_data` parse: map each alias → producer basename; path lint rejecting non-literal / non-`.copier-answers.<basename>.yml` values for first-party modules (FR-006a/R9). Also statically read `_post_tasks` like edges (R11).
- [ ] T011 In `src/bailiff/runner.py` (preflight) enforce data-dependency: producer ABSENT → loud `OrderingError` naming the alias; PRESENT → ordered before consumer (FR-006 inverted). Reuse the 013 preflight/collision surface.
- [ ] T012 In `src/bailiff/ordering.py` collapse edges to single `depends_on`: drop `run_after`/`run_before` handling; treat absent target as loud `OrderingError` (dangling-edge, explicit) (FR-019/R7).
- [ ] T013 In `src/bailiff/ordering.py` add pre/normal/post stratified sort = (phase) → (`depends_on` DAG) → (basename); validate edge legality at discovery (pre→pre, normal→pre+normal, post→anything; forward cross-phase rejected) (FR-020/R8).
- [ ] T014 In `src/bailiff/runner.py` add `_post_tasks` collection + execution: gather across all selected modules, run AFTER the render loop in `depends_on` order, on BOTH `init_many` and `reproduce_many`, trust-gated/init-guarded as normal tasks (FR-021/R11).
- [ ] T015 In `src/bailiff/runner.py` add the `_bailiff_schema: 014` migration gate: APPEND the marker to each `.copier-answers.<basename>.yml` post-render (positive allowlist, mirroring copier's `_commit`/`_src_path` write); `reproduce_many` REFUSES (loud error + re-init guidance) when a recorded answers file lacks the marker or carries an older schema (FR-014/R10).
- [ ] T016 Make T004–T007 pass; run `uv run pytest tests/loop/test_threading_isolation.py tests/loop/test_external_data.py tests/loop/test_ordering_phases.py tests/loop/test_post_tasks.py -q` green.

### Contract freeze

- [ ] T017 [P] Confirm `specs/014-namespaced-question-keys/contracts/` (`_threading.md`, `_facts.md`, `_fragment-merge.md`) match the landed engine behavior; fix any residual drift (contracts are the authoring source of truth). No code change.

**Checkpoint**: engine is private-by-default with enforced facts, single-edge + stratified DAG,
`_post_tasks`, and the schema gate; the four new test files pass; contract frozen. Module work may begin.

---

## Phase 3: US3 (P1) — mise tools compose via drop-in, no union [Slice A]

**Goal**: dissolve the `mise_tools` union into per-module `.mise/conf.d/*.toml` drop-ins; mise merges
natively. Migrate each touched module's edge/phase.

**Independent Test**: init base + cocogitto + moon → three `.mise/conf.d/*.toml`, no `.mise.toml`,
collision check passes, `mise install` (bare) installs the union (quickstart Scenario 3, SC-003).

- [ ] T018 [P] [US3] Write mise conf.d loop test in `tests/loop/test_mise_confd.py`: N tool modules → N distinct `.mise/conf.d/<vendor>-<module>.toml`, NO `.mise.toml`, collision check passes; single-module reproduce byte-identical (SC-003).
- [ ] T019 [US3] `templates/bailiff-mod-base/`: remove `mise_tools` from `copier.yml`; delete `template/.mise.toml.jinja`; add base's own `template/.mise/conf.d/bailiff-mod-base.toml.jinja`; migrate `run_after`→`depends_on` (base=phase `pre`). (Base is the union's origin — do first; other tool modules depend on the pattern.)
- [ ] T020 [P] [US3] `templates/bailiff-mod-python/`: render `template/.mise/conf.d/bailiff-mod-python.toml.jinja` (own tools only); drop `.mise.toml`; `run_after: base`→`depends_on: base` + `phase: normal`.
- [ ] T021 [P] [US3] `templates/bailiff-mod-ts/`: same conf.d drop-in + edge/phase migration.
- [ ] T022 [P] [US3] `templates/bailiff-mod-go/`: same.
- [ ] T023 [P] [US3] `templates/bailiff-mod-rust/`: same.
- [ ] T024 [P] [US3] `templates/bailiff-mod-cocogitto/`: same.
- [ ] T025 [P] [US3] `templates/bailiff-mod-moon/`: same.
- [ ] T026 [P] [US3] `templates/bailiff-mod-api/`: same.
- [ ] T027 [P] [US3] `templates/bailiff-mod-mkdocs/`: same.
- [ ] T028 [P] [US3] `templates/bailiff-mod-terraform/`: same.
- [ ] T029 [P] [US3] `templates/bailiff-mod-devcontainer/`: change `postCreateCommand` to bare `mise install` (no explicit tool list); migrate edge/phase (FR-009). (No conf.d authored unless it contributes tools.)
- [ ] T030 [US3] Verify no residual `.mise.toml` writer and no `mise_tools` reference remains: `rg -l "mise_tools|\.mise\.toml" templates/` returns nothing; run `tests/loop/test_mise_confd.py` + `tests/loop/test_devcontainer*` + `scripts/check_modules.py` green.

**Checkpoint**: mise union dissolved; SC-003 passes.

---

## Phase 4: US2 (P1) — cross-module facts via `_external_data` aliases [Slice B, facts]

**Goal**: wire every consumer to read producer facts via `_external_data` aliases; add `default_branch`
to base; producers write their facts as normal bare questions.

**Independent Test**: present producer resolves; absent producer → loud error naming the alias
(quickstart Scenario 2, SC-002).

### Producers write their facts (do before consumers wire)

- [ ] T031 [US2] `templates/bailiff-mod-base/copier.yml`: ADD `default_branch` as a base question (fixes the phantom-producer latent bug); confirm `project_name`, `layout`, `description` are plain bare questions in base's answers file. (`github_host` handled in Phase 6 — do NOT add a forge fact here.)
- [ ] T032 [P] [US2] `templates/bailiff-mod-precommit/copier.yml`: confirm `hook_manager` is a normal bare question written to precommit's answers file (producer for the `precommit` alias).
- [ ] T033 [P] [US2] `templates/bailiff-mod-ts/copier.yml`: confirm `js_pkg_manager` + `ts_linter` are bare questions in ts's answers file (producer for the `ts` alias).
- [ ] T034 [P] [US2] `templates/bailiff-mod-moon/copier.yml`: confirm `monorepo_tool` + `monorepo_packages` are bare questions in moon's answers file (producer for the `moon` alias).

### Consumers wire aliases (parallel per module — each edits only its own copier.yml)

- [ ] T035 [P] [US2] `base` fact consumers of `project_name` — add `_external_data: {base: .copier-answers.bailiff-mod-base.yml}` + `default: "{{ _external_data.base.project_name }}"` in each of: agentic, api, apm, cdk, ci-gitlab, cocogitto, devcontainer, go, mkdocs, moon, python, readme, rust, stack-adr, ts, terraform (github-repo/gitlab-repo handled in Phase 6). One task per module is acceptable if conflicts arise; batch where the edit is identical.
- [ ] T036 [P] [US2] `layout` consumers (moon, cocogitto, package-add): wire `_external_data.base.layout`.
- [ ] T037 [P] [US2] `description` consumers (apm, api, mkdocs, python, readme): wire `_external_data.base.description`.
- [ ] T038 [P] [US2] `default_branch` consumers (ci-github, ci-gitlab): replace `default: "{{ default_branch }}"` with `_external_data.base.default_branch` (removes the phantom-producer read).
- [ ] T039 [P] [US2] `hook_manager` consumers (python, ts, api, go, rust, terraform, justfile): wire `_external_data: {precommit: .copier-answers.bailiff-mod-precommit.yml}` + read `_external_data.precommit.hook_manager`.
- [ ] T040 [P] [US2] `js_pkg_manager` consumers (justfile, package-add) + `ts_linter` consumer (editorconfig): wire `_external_data.ts.*`.
- [ ] T041 [P] [US2] `monorepo_tool`/`monorepo_packages` consumers (ci-github, ci-gitlab, cocogitto): wire `_external_data.moon.*`.
- [ ] T042 [US2] Run `tests/loop/test_external_data.py` + `scripts/check_modules.py` green; confirm every `_external_data` value is a literal `.copier-answers.<basename>.yml` (discovery path lint passes, FR-006a).

**Checkpoint**: all facts resolve via aliases; absent-producer errors loud; SC-002 passes.

---

## Phase 5: US4 (P2) — pre-commit fragments + bundler; gitignore fragments + concat [Slice B, merge]

**Goal**: eliminate `hook_blocks`/`gitignore_stack` unions; per-module fragments + owner-side merges
run as `_post_tasks`.

**Independent Test**: precommit + two hook modules → two `.pre-commit.d/*.yaml` + one merged
`.pre-commit-config.yaml`; order-independent; rev-pin highest-wins+warn; inert without precommit
(quickstart Scenario 4, SC-004). gitignore idempotent concat (Scenario 5).

### pre-commit (US4)

- [ ] T043 [US4] Write pre-commit merge loop test in `tests/loop/test_precommit_merge.py`: order-independence, dedup, rev-pin HIGHEST-WINS+WARN (not abort), inert when precommit absent / `hook_manager=none`, config-consistent reproduce (SC-004).
- [ ] T044 [US4] `templates/bailiff-mod-precommit/`: vendor `template/scripts/_merge_precommit.py.jinja` (owner-side bundler — reads all `.pre-commit.d/*.yaml`, dedups repos, deterministic order-independent emit, rev-pin highest-wins+warn; Python+PyYAML only, no bailiff CLI); declare the bundler invocation as a `_post_task` in `copier.yml`; DELETE the `hook_blocks` union.
- [ ] T045 [P] [US4] Hook contributors render `.pre-commit.d/<vendor>-<module>.yaml.jinja` (own block only, MAY be conditional on own answers) + delete `hook_blocks` contribution, in each of: api, cocogitto, go, python, rust, terraform, ts. (Distinct paths → collision-free.)
- [ ] T046 [US4] Run `tests/loop/test_precommit_merge.py` + `scripts/check_modules.py` (single-merger invariant) green; `rg -l hook_blocks templates/` returns nothing.

### gitignore (US4)

- [ ] T047 [US4] Write gitignore concat loop test in `tests/loop/test_gitignore_concat.py`: base + two contributors → `.gitignore.d/*` fragments folded into `.gitignore` via delimited blocks; reproduce twice → no duplicates (FR-013, Scenario 5).
- [ ] T048 [US4] `templates/bailiff-mod-base/`: add the idempotent ordered-concat as a `_post_task` (delimited blocks folding `.gitignore.d/*` → `.gitignore`); DELETE `gitignore_stack` union.
- [ ] T049 [P] [US4] gitignore contributors render `.gitignore.d/<vendor>-<module>.jinja` (gitnr-produced OR literal static lines) + delete `gitignore_stack` contribution, in each of: apm, go, python, quality, rust, terraform, ts.
- [ ] T050 [US4] Run `tests/loop/test_gitignore_concat.py` green; `rg -l gitignore_stack templates/` returns nothing.

**Checkpoint**: zero cross-module answer unions remain; SC-004 + gitignore idempotency pass.

---

## Phase 6: FORGE (P2) — forge metadata leaves base; delete github_host; conditional creation [Slice B2, R12]

**Goal**: base emits zero forge-specific files; `.github/` moves to github-repo, `.gitlab/` added to
gitlab-repo; `github_host` deleted; `create_remote` toggle; dep-updates self-defaults.

**Independent Test**: base has no `.github/` and no `github_host`; github-repo renders `.github/`,
gitlab-repo renders `.gitlab/`, neither leaks the other; `create_remote=false` renders metadata but
runs no `gh`/`glab` create; dep-updates renders with no `github_host` input (SC-009).

- [ ] T051 [FORGE] Write forge-cleanup loop test in `tests/loop/test_forge_metadata.py`: base emits no `.github/`; github-repo renders CODEOWNERS/ISSUE_TEMPLATE/PULL_REQUEST_TEMPLATE; gitlab-repo renders the `.gitlab/` equivalent; `create_remote=false` → metadata present, no create task run; no cross-forge leakage (SC-009).
- [ ] T052 [FORGE] `templates/bailiff-mod-base/`: DELETE the `{% if github_host %}.github{% endif %}/` template tree; remove the `github_host` question from `copier.yml`. (Base now forge-free.)
- [ ] T053 [FORGE] `templates/bailiff-mod-github-repo/`: ADD the moved `.github/` managed files (CODEOWNERS, ISSUE_TEMPLATE/, PULL_REQUEST_TEMPLATE/) under `template/`; ADD `create_remote: bool` (default false) question; gate the existing `gh` `_tasks` on `{{ create_remote }}`; wire `_external_data.base.project_name` (deferred from T035); migrate edge/phase. Update the module's "pure side-effect / writes no files" header comment.
- [ ] T054 [FORGE] `templates/bailiff-mod-gitlab-repo/`: ADD a `.gitlab/` equivalent (CODEOWNERS + MR/issue templates) under `template/`; ADD `create_remote: bool` (default false); gate the `glab` `_tasks` on it; wire `_external_data.base.project_name`; migrate edge/phase; update header comment.
- [ ] T055 [FORGE] `templates/bailiff-mod-dep-updates/copier.yml`: remove the `github_host` read; `dep_update_tool` defaults to `renovate` (agent/user overridable); confirm `dependabot.yml` output stays gated on `dep_update_tool` (not forge).
- [ ] T056 [FORGE] Run `tests/loop/test_forge_metadata.py` + `scripts/check_modules.py` green; `rg -l github_host templates/` returns nothing.

**Checkpoint**: base is forge-agnostic; SC-009 passes; the github_host/`.github`-in-base contradiction is gone.

---

## Phase 7: US1 + US5 (P1) — isolation regression + reproduce/migration proof

**Goal**: prove the motivating bug is fixed and migration behaves (these are cross-cutting verifications
over the rewritten modules).

**Independent Test**: Python+TS `framework` stack inits on isolation ALONE; pre-014 tree reproduce →
documented error (quickstart Scenarios 1 + 6, SC-001/SC-006).

- [ ] T057 [US1] Extend `tests/integration/` (or a fixture) so the real Python+TS monorepo stack (both historically defined `framework`) inits successfully on ISOLATION ALONE — temporarily reuse the bare `framework` key in two layers or revert the point-fix in-fixture (SC-001).
- [ ] T058 [P] [US5] Write migration-break test in `tests/loop/test_migration_gate.py`: a pre-014 committed tree (bare `project_name`, `mise_tools`, `framework` recorded; no `_bailiff_schema`) → `reproduce_many` refuses with a clear re-init message, never a silent mis-render (SC-006).
- [ ] T059 [US5] Author the short migration note (documented BREAK + re-init recommendation) in `docs/` (or the module-authoring guide) referencing the `_bailiff_schema` gate (R3/R10/FR-014).

**Checkpoint**: SC-001 + SC-006 pass; isolation alone prevents the shipped regression.

---

## Phase 8: FR-018 documentation rewrite [Slice C]

**Purpose**: teach the new model so a module author needs no reverse-engineering.

- [ ] T060 [P] Rewrite `specs/011-deopinionated-module-family/contracts/_cross-cutting.md` §2/§4/§5/§6: replace frozen-union single-writer prose with the fragment/merge pattern + `_external_data` fact-read pattern + single-`depends_on`/phase model (FR-018a).
- [ ] T061 [P] Update `skills/bailiff/SKILL.md` "how to write a module" steps: private-by-default questions, `_external_data` alias reads, `.d/` fragment contribution, `_post_tasks`, config-consistency.
- [ ] T062 [P] Update `_meta/module-template/` scaffold `copier.yml` + README: demonstrate a `.mise/conf.d/` fragment + an `_external_data` alias (NOT a union contribution) + `depends_on`/`phase`.
- [ ] T063 [P] Sweep `templates/*/README.md` for old union-model prose (`mise_tools`/`hook_blocks`/`gitignore_stack`/threaded-answer language) and update to the fragment/fact model.
- [ ] T064 [P] Write the concrete authoring guide in `docs/`: private-by-default, when/how to read a fact via `_external_data`, fragment contribution per surface (mise/pre-commit/gitignore), the config-consistency (not byte-identity) reproduce guarantee, and the forge-module convention (R12).

---

## Phase 9: Verify all green locally (before re-fanout)

- [ ] T065 Run the FULL non-network suite DETACHED (`nohup uv run pytest tests/ -q -m "not network" > /tmp/014-full.log 2>&1 &`) and poll `/tmp/014-full.log` — all green (the suite is ~24min; do NOT foreground).
- [ ] T066 Run `uv run pytest tests/integration/ -q` — 33 combination tests incl. the Python+TS `framework` stack now passing on isolation alone.
- [ ] T067 Run `uv run python scripts/check_modules.py` → "ok — 27 module(s)"; run `uvx bailiff doctor` → exit 0.
- [ ] T068 Confirm SC-001..009 each map to a passing test (isolation, external-data absent-error, mise conf.d, precommit rev-pin, dependency-model/schema-gate, migration break, integration suite, forge cleanup).

**Checkpoint**: everything green locally; ready for the maintainer-confirmed batch.

---

## Phase 10: Confirmed re-fanout + release (maintainer, never unattended)

- [ ] T069 Regenerate catalog (`catalog-sources.toml` → `catalog.json`) reflecting the rewritten modules.
- [ ] T070 Maintainer-confirmed 27-mirror re-fanout: republish each `bailiff-mod-<name>` to `bailiff-io/bailiff-mod-<name>` (armed fan-out, never unattended; 011 precedent).
- [ ] T071 Publish the engine release via release-please (tag → OIDC PyPI publish; bumps apm.yml + marketplace skill versions in lockstep). Push via `dgit push`.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no deps.
- **Phase 2 (Engine gate)**: depends on Phase 1. **BLOCKS Phases 3–8** — no module rewrite until the engine is private-by-default, facts are enforced, `_post_tasks` works, and the contract is frozen.
- **Phase 3 (US3 mise)**: after Phase 2. T019 (base) before T020–T029 (pattern origin).
- **Phase 4 (US2 facts)**: after Phase 2. Producers (T031–T034) before consumers (T035–T041).
- **Phase 5 (US4 merges)**: after Phase 2; independent of Phase 4 but touches some same module files (python/ts/go/rust/terraform/api) — see conflict note.
- **Phase 6 (FORGE)**: after Phase 2; T052 (base delete) before/independent of T053–T055; wires deferred `project_name` consumers (github-repo/gitlab-repo).
- **Phase 7 (US1/US5)**: after Phases 3–6 (verifies the rewritten modules).
- **Phase 8 (docs)**: after the model is stable (Phases 2–6); parallelizable.
- **Phase 9 (verify)**: after Phases 3–8.
- **Phase 10 (re-fanout)**: after Phase 9 green; maintainer-gated.

### Same-file conflict note (worktree isolation)

Several modules are touched by MULTIPLE phases on the SAME `copier.yml`: **python, ts, go, rust,
terraform, api** appear in Slice A (mise), Slice B facts (hook_manager/project_name), AND Slice B merge
(pre-commit fragment). **moon, cocogitto** appear in mise + facts. **base** is touched by mise + facts
(default_branch) + gitignore concat + forge delete. To avoid worktree collisions, either:
(a) sequence all edits to one module in a single worktree/agent (recommended — one agent owns
`templates/bailiff-mod-<name>/` end-to-end across slices), OR
(b) run slices as ordered barriers (A → B-facts → B-merge → B2) so no two writers touch one module dir
concurrently. Do NOT fan out two agents onto the same module dir in parallel.

### Parallel opportunities

- Phase 2 tests T004–T007 in parallel (distinct files).
- Within a slice, `[P]` module tasks that touch DISJOINT module dirs run in parallel with worktree isolation.
- Phase 8 docs (T060–T064) fully parallel.

---

## Implementation Strategy

### MVP / gate

Phase 2 is the true gate and the highest-value increment: private-by-default threading ALONE fixes the
motivating `framework` poisoning class (SC-001/SC-005) even before any module is restructured. Land and
verify Phase 2 first.

### Incremental delivery (per plan slices)

1. Phase 1 + 2 → engine green, contract frozen (fixes the bug class).
2. Slice A (Phase 3) → mise union dissolved.
3. Slice B (Phases 4–5) → facts wired + fragment merges.
4. Slice B2 (Phase 6) → forge cleanup.
5. Slice C (Phase 8) → docs.
6. Phase 9 verify → Phase 10 maintainer-gated re-fanout.

### Recommended agent model

One agent per module dir owning ALL slices for that module (avoids same-file conflict), coordinated by
a parent that lands Phase 2 first, then fans out module-owning agents in worktrees, then runs the
detached full suite before the maintainer-gated re-fanout.

---

## Notes

- `[P]` = disjoint files, no incomplete-task dependency. The same-file conflict note overrides `[P]` for the multi-slice modules.
- Tests are written to FAIL before the Phase-2 engine change (per the spec's explicit SC test requests).
- The pytest suite is ~24min full — always run detached and poll the log (never foreground; bash caps at 2min).
- Never `git checkout main` in this checkout — use a throwaway worktree for any main-branch verify/push. Push via `dgit push`.
- Commit after each logical group; reference the 014 issue in the PR body for auto-close.
