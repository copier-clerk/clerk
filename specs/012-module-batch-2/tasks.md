# Tasks: Module batch 2 (012)

**Input**: Design documents from `specs/012-module-batch-2/`

**Prerequisites**: `specs/012-module-batch-2/decisions-ledger.md` MUST exist before any task
beyond T000 is executed (see plan.md). All 19 011 templates present and `just check-modules`
green.

**Branch**: `012-module-batch-2`

> **ORGANIZATION NOTE**: Tasks are per-deliverable (one per new module, one per amendment),
> organized into phases by dependency slice per plan.md. User-story traceability via `[US#]`
> labels. Format matches the 011 precedent.

## Module Definition of Done (applies to every new-module task)

Every module task implicitly includes ALL of the following before it is considered complete:

1. **Shape**: `templates/bailiff-mod-<name>/copier.yml` with `_subdirectory: template`,
   `template/{{ _copier_conf.answers_file }}.jinja`, `README.md`, `CHANGELOG.md`
   (with the `- - -` cocogitto separator). New modules start from
   `just new-module name=bailiff-mod-<name>`; reference shape: `templates/bailiff-mod-github-repo/`
   (for task modules) or any pure-render 011 module (for zero-task modules).
2. **Registration parity**: `just check-modules` green — three-way parity
   `templates/` == `cog.toml [monorepo.packages]` == `catalog-sources.toml`.
3. **Loop test**: hermetic init + reproduce under `tests/loop/test_<name>_loop.py` with ALL
   native/network tasks stubbed via `_copy_module_with_stub_tasks` in `tests/conftest.py`.
   Assertion mapping: **byte-assert** MANAGED renders on init AND reproduce; **presence/
   structure-assert** TASK-OUTPUT; **`_skip_if_exists`-assert** SEED-ONCE.
4. **Determinism/trust**: no `secret:` questions; no `jinja2_time`; trust-gated `_tasks`
   with preflight ordered first; `tests/loop/test_secrets_policy.py` must stay green.
5. **Init-only guards (FR-012a / M3)**: every preflight and native-init `_task` is guarded
   so reproduce over a committed tree never re-shells and requires no toolchain or network.
6. **Frozen-union single-writer (M1)**: contributors add tokens to agent-frozen union
   answers injected via `--data` (`mise_tools`, `hook_blocks`, `gitignore_stack`). Never
   write `.mise.toml`, hook config files, or `.gitignore` directly.
7. **C-11 gate**: no new `src/bailiff/` code; no new `scripts/bailiff.py` verb.

---

## Phase 0: Pre-plan prerequisite

- [x] **T000** Vendor `decisions-ledger.md` into `specs/012-module-batch-2/decisions-ledger.md`.
  This is the in-tree copy of the ratified 2026-07-14 maintainer decisions (same pattern as
  `specs/011-deopinionated-module-family/decisions-ledger.md`). **Hard gate — no task beyond
  T000 may be executed until this file exists at the exact path.** The file must cover the
  eight new modules, the monolith-vs-split governing rule, and the two sanctioned 011
  amendments (FR-009, FR-010a). Once present, verify it matches the spec.md inputs summary.

---

## Phase 1: Baseline

- [x] **T_baseline** Verify the 012 starting baseline: run `just check-modules` (must report
  `ok` over the 19 existing 011 templates); run the existing loop suite targeted at
  `tests/loop/` (all tests green, including `tests/loop/test_secrets_policy.py` and
  `tests/loop/test_base_render.py` which already asserts dependabot.yml absence). Confirm
  that `tests/conftest.py` `_copy_module_with_stub_tasks` covers the new command classes
  needed for 012 modules (glab, cog, moon, mkdocs/mkdocs-material, spectral); if any
  command class is missing, extend the fixture now so all Phase 3-5 tasks have a working
  stub mechanism. Record baseline as the zero-regression reference.

---

## Phase 2: Amendments (both before any new module)

- [x] **T001-template** *(already done — commit a68295e)* Remove `dependabot.yml` from
  `templates/bailiff-mod-base/` and assert its absence in loop tests. Complete.

- [x] **T001-annotate** [US3] Annotate the 011 spec artifacts to record FR-009 as complete
  (spec annotations only, no template code): (a) amend
  `specs/011-deopinionated-module-family/contracts/bailiff-mod-base.md` — strike the
  `dependabot.yml` row from the `github_host` question output list and note "moved to
  bailiff-mod-dep-updates (FR-009, spec 012)"; (b) amend
  `specs/011-deopinionated-module-family/tasks.md` T004 — strike the dependabot render
  requirement and note "dependabot removed pre-v1.0.0 per FR-009 (spec 012, commit a68295e)";
  (c) add the `dep_update_tool [renovate, dependabot]` row to the axis table in
  `specs/011-deopinionated-module-family/data-model.md` with exact key, choices, and the
  host-derived default rule (FR-004). No loop test changes needed. Verify
  `just check-modules` still green after annotation.

- [x] **T002** [US4] FR-010a: amend `bailiff-mod-ci-github` and `bailiff-mod-ci-gitlab` to
  accept `monorepo_tool=moon` and render moon-specific affected-detection. Concrete changes:
  (1) In `templates/bailiff-mod-ci-github/copier.yml` and
  `templates/bailiff-mod-ci-gitlab/copier.yml`, update the `monorepo_tool` help text to
  include `moon` in the accepted values list. (2) In each CI template's `monorepo-affected`
  model render, add a `{% if monorepo_tool == 'moon' %}` branch with moon's
  affected-detection invocation (e.g. `moon run :affected` — verify against moon docs).
  The existing turborepo/nx/pnpm-workspace branches are unchanged. (3) Add loop-test
  coverage for the moon branch in `tests/loop/test_ci_github_loop.py` and
  `tests/loop/test_ci_gitlab_loop.py`: assert the moon invocation appears when
  `monorepo_tool=moon` + `ci_model=monorepo-affected`, and does not appear in other models.
  (4) Amend `specs/011-deopinionated-module-family/contracts/ci-github-gitlab.md` to add
  `moon` to `monorepo_tool`'s value list. Verify `just check-modules` green and amended
  loop tests pass.

---

## Phase 3: Slice A — P1 New Modules (parallel)

- [x] **T003** [US1] NEW module `bailiff-mod-devcontainer` per FR-005; loop test
  `tests/loop/test_devcontainer_loop.py`.
  [NEEDS CLARIFICATION FR-005 — base container image: fixed default vs `devcontainer_image`
  question. Resolve before executing this task.]
  Requirements: (1) Zero `_tasks` — pure managed render. (2) Consumes agent-frozen
  `mise_tools` union via `default: "{{ mise_tools }}"` — does NOT write `.mise.toml`.
  (3) Renders `.devcontainer/devcontainer.json` as MANAGED: references the mise
  devcontainer feature (`ghcr.io/devcontainers-contrib/features/mise`) and lists each
  frozen `mise_tools` entry as a tool to install; when `mise_tools` is empty, renders a
  minimal valid devcontainer.json (valid no-op, never invalid JSON). (4) Base container
  image per NC resolution. (5) `run_after: [bailiff-mod-base]`. (6) Loop tests: init
  `[base, python, devcontainer]` with `mise_tools=[{"python":"3.13"}]` frozen →
  devcontainer.json references mise feature and exact tool set; init with `mise_tools=[]` →
  minimal valid file; byte-assert managed render on init AND reproduce.
  Acceptance: SC-001, US1 AS1-2.

- [x] **T004** [US9] NEW module `bailiff-mod-editorconfig` per FR-006; loop test
  `tests/loop/test_editorconfig_loop.py`.
  Requirements: (1) Zero `_tasks` — pure managed render. (2) Consumes frozen language facts
  via threading: `ts_linter`, `ruff_line_length` (default `"88"`), Python linter identity.
  (3) Renders `.editorconfig` as MANAGED with: always-present universal defaults section
  (`charset=utf-8`, `end_of_line=lf`, `insert_final_newline=true`,
  `trim_trailing_whitespace=true`); language sections sized from frozen facts. INVARIANT:
  indentation derives from the linter's convention ONLY, never from line-width facts.
  (4) `run_after: [bailiff-mod-base]`. (5) Loop tests: init alone → universal-defaults only;
  with `ts_linter=biome` → TypeScript section uses biome's indent convention; with Python
  facts + `ruff_line_length=88` → Python section `max_line_length=88`; byte-assert on
  init AND reproduce.
  Acceptance: SC-001, US9 AS1-3.

- [x] **T005** [US2] NEW module `bailiff-mod-cocogitto` per FR-007; loop test
  `tests/loop/test_cocogitto_loop.py`.
  [NEEDS CLARIFICATION FR-007 — whether to seed a cog-driven release CI job. Conservative
  default: leave CI untouched.]
  Requirements: (1) Renders managed `cog.toml` sized to project shape (single vs monorepo).
  (2) Contributes `cog` to `mise_tools` union. (3) Contributes commit-message-lint block to
  `hook_blocks` union (written by bailiff-mod-precommit only). (4) Trust-gated `_task`: mise
  preflight (init-only-guarded). No cog bump, no tag, no changelog at scaffold time.
  (5) `run_after: [bailiff-mod-base]`; threads `project_name`, `layout`,
  `monorepo_packages`. (6) Loop tests: init single layout → managed cog.toml byte-identical
  on reproduce; init monorepo → `[monorepo]` section present; no tag/changelog; hook_blocks
  contribution present.
  Acceptance: SC-003, US2 AS1-3.

- [x] **T006** [US3] NEW module `bailiff-mod-dep-updates` per FR-008; loop test
  `tests/loop/test_dep_updates_loop.py`.
  Requirements: (1) Zero `_tasks` — pure managed render. (2) Exposes axis `dep_update_tool
  [renovate, dependabot]` with host-derived default
  `"{{ 'dependabot' if github_host else 'renovate' }}"` (FR-004). Threads `github_host`.
  (3) Renovate branch: managed `renovate.json` sized from frozen language facts. (4)
  Dependabot branch: managed `.github/dependabot.yml` with one `updates` entry per active
  ecosystem; when `github_host=false`, adds warning comment + README note. (5) NEVER
  deletes the other tool's file. `run_after: [bailiff-mod-base]`. (6) Loop tests:
  `github_host=true` + default → dependabot.yml present, renovate.json absent;
  `github_host=false` + default → renovate.json present; `dep_update_tool=dependabot` +
  `github_host=false` → dependabot.yml with warning comment; byte-assert on init AND
  reproduce.
  Acceptance: SC-002, US3 AS1-5.

---

## Phase 4: Slice B — P2 New Modules (parallel)

- [x] **T007** [US4] NEW module `bailiff-mod-moon` per FR-010; loop test
  `tests/loop/test_moon_loop.py`.
  [NEEDS CLARIFICATION FR-010 — single-package layout behavior. Must resolve before
  executing.]
  Requirements: (1) Trust-gated `_task`: mise preflight (init-only-guarded). (2) Renders
  managed `.moon/workspace.yml` wired to base's monorepo package-dirs layout. (3)
  Contributes `moon` to `mise_tools` union. (4) Sets `monorepo_tool=moon` as frozen answer
  for CI consumption. (5) Single-package behavior per NC resolution. (6) `run_after:
  [bailiff-mod-base]`; threads `layout`, `monorepo_packages`. (7) Loop tests: init
  `[base(layout=monorepo), moon]` → managed workspace config byte-identical on reproduce;
  confirm CI can consume `monorepo_tool=moon`; single-package behavior tested per NC.
  Acceptance: SC-004, US4 AS1-3.

- [x] **T008** [US5] NEW module `bailiff-mod-mkdocs` per FR-011; loop test
  `tests/loop/test_mkdocs_loop.py`.
  [NEEDS CLARIFICATION FR-011 — mkdocs-material pin strategy. Conservative default:
  mise_tools contribution.]
  Requirements: (1) Zero `_tasks` — pure managed render + seed-once. (2) Managed
  `mkdocs.yml` wired to `docs/` dir. (3) Seed-once starter pages (`docs/index.md` via
  `_skip_if_exists`). (4) Contributes `mkdocs-material` + `mkdocs` to `mise_tools` union.
  (5) No build/deploy at scaffold time. `run_after: [bailiff-mod-base]`. (6) Loop tests:
  managed mkdocs.yml byte-identical on reproduce; seed-once index.md preserved on re-run
  with edited content; no network action.
  Acceptance: SC-006, US5 AS1-3.

- [x] **T009** [US6] NEW module `bailiff-mod-gitlab-repo` per FR-012; loop test
  `tests/loop/test_gitlab_repo_loop.py`.
  Requirements: (1) Pure side-effect (no file output, `reconcile=false`). (2) Same question
  shape as github-repo: `visibility [private,public,internal]=private`, `remote_protocol`,
  `push_after_create`, `team`. (3) Trust-gated `_task` chain, init-only-guarded: (a) glab
  presence check — non-fatal exit 0 if missing; (b) public consent gate — exit 1 without
  consent; (c) `glab repo create` — non-fatal on failure; (d) optional push. (4) No
  `secret:` questions; token from ambient `GITLAB_TOKEN`. (5) `run_after:
  [bailiff-mod-base]`. (6) Loop tests MUST cover all three safety paths: public→exit 1;
  glab missing→exit 0 + complete; private+glab present(stubbed)→creation runs.
  Acceptance: SC-005, US6 AS1-3.

- [x] **T010** [US7] NEW module `bailiff-mod-api` per FR-013; loop test
  `tests/loop/test_api_loop.py`.
  (OpenAPI path/version resolved: root `openapi.yaml`, OpenAPI 3.1 — see decisions-ledger.)
  Requirements: (1) Zero `_tasks` — pure render. (2) Seed-once OpenAPI skeleton
  (`_skip_if_exists`): minimal valid OpenAPI 3.1 skeleton with placeholder info, empty
  paths. (3) Managed spectral config (`.spectral.yaml`): byte-identical on reproduce.
  (4) Contributes `spectral` to `mise_tools` union. (5) Contributes spectral-lint block to
  `hook_blocks` union (inert when `hook_manager=none`). (6) Threads `hook_manager`.
  `run_after: [bailiff-mod-base]`. (7) Loop tests: seed-once openapi.yaml present; managed
  .spectral.yaml byte-identical on reproduce; re-run preserves edited openapi.yaml;
  `hook_manager=none` → module renders files but no hook file written.
  Acceptance: SC-006, US7 AS1-3.

---

## Phase 5: Polish & Integration

- [x] **T011** Full local gate over all 27 modules (19 existing + 8 new):
  `just check-modules` (three-way parity); `just test` (full suite including secrets-policy
  lint). Confirm: (a) no `secret:` in any 012 module; (b) reproduce without toolchain/
  network for every 012 module; (c) FR-009 annotations present in 011 spec artifacts;
  (d) FR-010a loop tests cover moon branch for both CI hosts; (e) all MANAGED renders
  byte-identical on reproduce; (f) all seed-once files respect `_skip_if_exists`;
  (g) no `src/bailiff/` code added (C-11). Fix any deviation.

---

## Phase 7: Publish Batch (MAINTAINER-GATED — never unattended)

- [ ] **T012** [RECONFIRM-GATED] Maintainer creates 8 mirror repos:
  `gh repo create bailiff-io/bailiff-mod-<name> --public` for each new module.

- [ ] **T013** [RECONFIRM-GATED] Push branch, open PR from `012-module-batch-2` to `main`.
  Watch CI green — do not merge on red.

- [ ] **T014** [RECONFIRM-GATED] Maintainer merges PR. The 008b pipeline fans out mirrors +
  releases. Monitor to completion.

- [ ] **T015** [RECONFIRM-GATED] Post-publish verification: `discovery.discover()` against
  published catalog resolves all 8 new modules; smoke-init one project from published
  mirrors; base still has no dependabot.yml.

---

## Dependencies & Execution Order

```
T000 (vendor decisions-ledger.md) [HARD GATE]
  └─> T_baseline (green baseline + conftest stub check)
        └─> T001-annotate + T002 [independent pair, both before Slice A]
              └─> Phase 3: {T003, T004, T005, T006} [parallel]
                    └─> Phase 4: {T007, T008, T009, T010} [parallel — api included per ledger amendment]
                          └─> T011 (full gate)
                                └─> T012 → T013 → T014 → T015 [serial, gated]
```
