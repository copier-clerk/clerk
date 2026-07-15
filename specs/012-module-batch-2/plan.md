# Implementation Plan: Module batch 2 — dev-environment, release, dependency-hygiene, monorepo, docs, GitLab-parity, and API modules (spec 012)

**Branch**: `012-module-batch-2` (spec dir `specs/012-module-batch-2/`) |
**Date**: 2026-07-14 | **Spec**: [spec.md](./spec.md)

**Input**: [spec.md](./spec.md) + `decisions-ledger.md` (MUST be vendored before plan
execution — see T000; does not exist yet). Governed by Constitution v2.3.0 unchanged
(C-11 holds for 012; spec 013 owns any relaxation). Extends spec 011 without reopening its
decisions, with two sanctioned 011-artifact amendments: the FR-009 base dependabot removal
(already merged, commit a68295e) and the FR-010a CI moon branch.

## Summary

Deliver eight new `bailiff-mod-*` templates plus amendments to `bailiff-mod-ci-github` and
`bailiff-mod-ci-gitlab` (FR-010a). `bailiff-mod-base` FR-009 is already done (commit a68295e —
no template work remains; only 011 spec-artifact annotations needed). Every new module is
pure template content: copier questions + rendered files + trust-gated tasks — no new
`src/bailiff/` code (C-11 / FR-003). One new cross-cutting axis: `dep_update_tool`
`[renovate, dependabot]` (FR-004). Publishing remains a maintainer-confirmed batch via
the 008b pipeline.

## Technical Context

**Language/Version**: No application code. Deliverables are copier YAML + Jinja templates +
shell `_tasks` + two 011-artifact amendments. `scripts/check_modules.py` (`just
check-modules`) is the contract gate; no new `src/bailiff/` module or verb (C-11).

**Primary Dependencies**: copier `>=9.16,<10`; mise; all 19 existing 011 templates
(`templates/`); `tests/conftest.py` `_copy_module_with_stub_tasks` fixture (extend only if
a new command class is missing for glab, cog, moon, mkdocs, spectral).

**Testing**: pytest loop tests under `tests/loop/test_<name>_loop.py`, reusing
`_copy_module_with_stub_tasks`. `just check-modules` + `tests/loop/test_secrets_policy.py`
are the gates.

**Constraints**: Constitution v2.3.0 unchanged. All patterns from
`specs/011-deopinionated-module-family/contracts/_cross-cutting.md` apply unchanged.
Reproduce over a committed tree must succeed without toolchain or network (011 FR-012a / M3).

## New axis introduced by 012

`dep_update_tool [renovate, dependabot]` (FR-004). Default is host-derived:
`dependabot` when `github_host=true`, `renovate` otherwise — expressed as
`default: "{{ 'dependabot' if github_host else 'renovate' }}"` (the FR-002 threading
pattern), explicitly overridable. Must be added to
`specs/011-deopinionated-module-family/data-model.md` axis table.

## Constitution Check

C-11 holds unchanged. All eight modules are pure template content. The two sanctioned
011-artifact amendments are pre-v1.0.0 edits that do not require a Constitution change.
No new complexity item beyond what 011's check already covers.

## NEEDS CLARIFICATION items (RESOLVED — maintainer-ratified 2026-07-15)

All five items are resolved in `decisions-ledger.md` (§ NEEDS CLARIFICATION resolutions).
No task is blocked. Summary:

- **FR-005 (devcontainer)**: fixed default image
  `mcr.microsoft.com/devcontainers/base:ubuntu`; no `devcontainer_image` question. (T003)
- **FR-007 (cocogitto)**: leave CI untouched — CI modules own workflow files. (T005)
- **FR-010 (moon)**: warn-and-render on single-package layouts. (T007)
- **FR-011 (mkdocs)**: pin via `mise_tools` contribution regardless of python
  co-selection. (T008)
- **FR-013 (api)**: root `openapi.yaml`, OpenAPI 3.1. (T010)

## Project Structure

### Spec-dir documentation

```text
specs/012-module-batch-2/
├── spec.md               # source of truth
├── decisions-ledger.md   # MUST be vendored before any task beyond T000 (does not exist yet)
├── plan.md               # this file
└── tasks.md
```

### Authored template content

```text
templates/
├── bailiff-mod-devcontainer/   # NEW — P1
├── bailiff-mod-editorconfig/   # NEW — P1
├── bailiff-mod-cocogitto/      # NEW — P1
├── bailiff-mod-dep-updates/    # NEW — P1
├── bailiff-mod-moon/           # NEW — P2
├── bailiff-mod-mkdocs/         # NEW — P2
├── bailiff-mod-gitlab-repo/    # NEW — P2
└── bailiff-mod-api/            # NEW — P3

# Amended (existing 011 modules):
templates/bailiff-mod-base/        # FR-009 DONE (a68295e) — no template work remaining
templates/bailiff-mod-ci-github/   # FR-010a — add moon branch to monorepo-affected
templates/bailiff-mod-ci-gitlab/   # FR-010a — add moon branch to monorepo-affected

# 011 spec artifacts requiring annotation:
specs/011-deopinionated-module-family/contracts/bailiff-mod-base.md  # strike dependabot row
specs/011-deopinionated-module-family/tasks.md (T004)              # strike dependabot render req
specs/011-deopinionated-module-family/contracts/ci-github-gitlab.md  # add moon to monorepo_tool

# 011 data-model requiring axis row:
specs/011-deopinionated-module-family/data-model.md   # add dep_update_tool axis row

# Registration (per new module, via `just new-module` + check_modules.py):
cog.toml · catalog-sources.toml · skills/bailiff/SKILL.md
```

## How each module maps to implementation

### P1 modules

**bailiff-mod-devcontainer** (FR-005): Pure managed render. Zero `_tasks`. Consumes the
agent-frozen `mise_tools` union (does not write `.mise.toml`) and emits
`.devcontainer/devcontainer.json` referencing the mise devcontainer feature with the same
pinned tool/version set. Renders a minimal valid file when `mise_tools` is empty. No
questions of its own beyond frozen facts. Edge: `run_after: [bailiff-mod-base]`.
[NEEDS CLARIFICATION on base image — FR-005]

**bailiff-mod-editorconfig** (FR-006): Pure managed render. Zero `_tasks`. Reads frozen
language facts (`ts_linter`, Python linter identity, `ruff_line_length`) to emit
language-specific sections; a universal defaults section (charset/newline/trailing-
whitespace) is always present. Indentation derives from the linter's convention, never from
line width. No questions of its own. The phase-1 agent must freeze `ts_linter` and
`ruff_line_length` via `--data` (FR-006). Edge: `run_after: [bailiff-mod-base]`.

**bailiff-mod-cocogitto** (FR-007): Renders managed `cog.toml` sized to project shape
(single vs monorepo from threaded `layout` fact). Contributes `cog` token to `mise_tools`
union and a commit-message-lint block to `hook_blocks` union (written by
`bailiff-mod-precommit` only). Trust-gated `_task`: mise preflight + cog availability check,
init-only-guarded. No `cog bump`, no tag creation, no changelog write at scaffold time.
Edge: `run_after: [bailiff-mod-base]`. [NEEDS CLARIFICATION on CI job seeding — FR-007]

**bailiff-mod-dep-updates** (FR-008): One module with `dep_update_tool [renovate, dependabot]`
axis (isomorphic family — FR-001). Default derived from `github_host` (FR-004). Renovate
branch → managed `renovate.json` sized from frozen language facts; dependabot branch →
managed `.github/dependabot.yml` sized from frozen language facts. Neither branch deletes
the other tool's file. `dep_update_tool=dependabot` + `github_host=false` → file still
rendered but with a warning comment and README note (warn-and-render). Zero `_tasks`. Edge:
`run_after: [bailiff-mod-base]`.

**FR-009 base amendment**: Already merged (commit a68295e). Template and loop test already
patched. Remaining work: annotate `specs/011-deopinionated-module-family/contracts/bailiff-mod-base.md`
(strike dependabot from `github_host` row) and `specs/011-deopinionated-module-family/tasks.md`
T004 (strike dependabot render requirement) per FR-009. These are spec-doc annotations, not
code changes. See T001-annotate.

**FR-010a CI amendment**: Amend the `monorepo_tool` help text in both
`templates/bailiff-mod-ci-github/copier.yml` and `templates/bailiff-mod-ci-gitlab/copier.yml`
to include `moon`. Amend the `monorepo-affected` model render in each to invoke moon's
affected-detection command (not a hardcoded turborepo assumption) when
`monorepo_tool == 'moon'`. Add loop-test coverage for the moon branch in both modules.
Update `specs/011-deopinionated-module-family/contracts/ci-github-gitlab.md` to add `moon`
to `monorepo_tool`'s value list. See T002.

### P2 modules

**bailiff-mod-moon** (FR-010): Renders moon's workspace config (managed) wired to base's
package-dirs layout (threaded from frozen `layout`/`monorepo_packages` facts). Contributes
`moon` token to `mise_tools` union. Setting `monorepo_tool=moon` as a frozen answer closes
the dangling CI read. Trust-gated `_task`: mise preflight, init-only-guarded. Edge:
`run_after: [bailiff-mod-base]`; consumed by CI via frozen `--data`. [NEEDS CLARIFICATION on
single-package behavior — FR-010; must be resolved before T007]

**bailiff-mod-mkdocs** (FR-011): Renders managed `mkdocs.yml` wired to base's `docs/` dir.
Seed-once starter pages (`docs/index.md` and nav siblings via `_skip_if_exists`). Contributes
`mkdocs-material` (and `mkdocs`) token to `mise_tools` union. No build/deploy action at
scaffold time. Zero `_tasks`. Edge: `run_after: [bailiff-mod-base]`. [NEEDS CLARIFICATION on
Python co-selection pin strategy — FR-011]

**bailiff-mod-gitlab-repo** (FR-012): Exact semantic port of `bailiff-mod-github-repo` to
`glab`. Pure side-effect module (no file output, `reconcile=false`). Same question shape as
github-repo (`visibility`, `remote_protocol`, `push_after_create`, `team`). Trust-gated
`_task` chain: (1) `glab` presence check — non-fatal exit 0 if missing; (2) public consent
gate — exit 1 on `visibility=public` without explicit consent; (3) `glab repo create` —
non-fatal on creation failure; (4) optional push. Token from ambient env; no `secret:`
questions. Init-only-guarded. Edge: `run_after: [bailiff-mod-base]`.

### P3 module

**bailiff-mod-api** (FR-013): Seed-once OpenAPI skeleton document (`_skip_if_exists`) plus
managed spectral config (`.spectral.yaml`, byte-identical on reproduce). Contributes
`spectral` token to `mise_tools` union and a spectral-lint block to `hook_blocks` union
(written by `bailiff-mod-precommit` only; inert when `hook_manager=none`). No codegen; no
server scaffold. Zero `_tasks`. Edge: `run_after: [bailiff-mod-base]`. [NEEDS CLARIFICATION
on OpenAPI document path and version — FR-013]

## Phase breakdown and sequencing

```
T000  Pre-plan: vendor decisions-ledger.md              [HARD GATE — nothing else starts without it]
  └─> Phase 1: Baseline verification (T_baseline)
        └─> Phase 2: Amendments (T001-annotate FR-009, T002 FR-010a + axis) [serial pair]
              └─> Phase 3 Slice A: {T003 devcontainer, T004 editorconfig,
                                    T005 cocogitto, T006 dep-updates} [P — all parallel]
                    └─> Phase 4 Slice B: {T007 moon, T008 mkdocs, T009 gitlab-repo,
                                          T010 api} [P — all parallel]
                          └─> Phase 6 Polish: T011 whole-family gate
                                └─> Phase 7 Publish: T012 → T013 → T014 → T015 [serial, gated]
```

### Intra-phase ordering rationale

- **Amendments before new modules**: FR-010a must land before `bailiff-mod-moon` is authored
  so that `monorepo_tool=moon` is a valid CI input from the moment moon exists.
- **Slice A before B**: moon (Slice B) contributes `monorepo_tool=moon`; the CI modules
  must already accept it (FR-010a, Phase 2). All Slice A modules are independent of moon.
- **api runs in Slice B** (decisions-ledger 2026-07-15 amendment): T010 has no
  inter-module dependency — it joins the Slice B parallel set rather than occupying a
  serial slice of its own. Its P3 priority label is unchanged.
- **Phase 7 strictly serial**: mirror pre-creation must precede merge; each step is
  irreversible.

### Parallel opportunities

- Slice A: T003–T006 — four independent workstreams (disjoint `templates/` dirs, disjoint
  loop-test files).
- Slice B: T007–T010 — four independent workstreams (api included per the ledger
  amendment).

## Module contract summary

| Module | Kind | Key questions | Tasks | Notable |
|---|---|---|---|---|
| devcontainer | NEW P1 | consumes `mise_tools` (frozen) | none | pure managed render; minimal valid file on empty mise_tools; image [NC FR-005] |
| editorconfig | NEW P1 | consumes `ts_linter`, `ruff_line_length` (frozen) | none | universal defaults always present; language sections from linter conventions |
| cocogitto | NEW P1 | `layout` (threaded) | mise preflight (init-only-guarded) | cog→mise_tools, commit-msg-lint→hook_blocks; NO release actions; CI seeding [NC FR-007] |
| dep-updates | NEW P1 | `dep_update_tool [renovate,dependabot]` default host-derived; `github_host` threaded | none | isomorphic axis; warn-and-render for dependabot+non-github |
| moon | NEW P2 | `layout`/package dirs (threaded) | mise preflight (init-only-guarded) | moon→mise_tools; single-package behavior [NC FR-010] |
| mkdocs | NEW P2 | `docs_dir` (threaded from base) | none | managed mkdocs.yml; seed-once starter pages; pin strategy [NC FR-011] |
| gitlab-repo | NEW P2 | `visibility [private,public,internal]=private`, `remote_protocol`, `push_after_create`, `team` | glab check (non-fatal), public gate (exit 1), glab create (non-fatal) | semantic port of github-repo |
| api | NEW P3 | `hook_manager` (threaded) | none | seed-once openapi.yaml; managed .spectral.yaml; path/version [NC FR-013] |
| ci-github | AMEND FR-010a | `monorepo_tool` help+render adds moon | none | moon affected-detection branch in monorepo-affected model |
| ci-gitlab | AMEND FR-010a | same | none | same |

## Risk assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| decisions-ledger.md not vendored before work starts | Medium (file doesn't exist yet) | T000 is the hard gate; nothing proceeds without it |
| FR-009 races 011 Phase 7 publish | Eliminated (a68295e already merged) | Loop test already asserts absence; spec annotations (T001-annotate) are the only remaining action |
| FR-010a lands after bailiff-mod-moon | Low | FR-010a is Phase 2 (before any Phase 3+ module) |
| NEEDS CLARIFICATION items block a task | Medium for FR-010/FR-013 | Each task states its NC dependency; coder must not start until NC is resolved |
| conftest.py missing stub coverage for glab, cog, moon, spectral | Low | Checked and extended in Phase 1 baseline if needed |
| dep_update_tool default expression produces unexpected value | Low | Loop tests cover both github_host=true and false explicitly |

## Complexity Tracking

No new complexity items. All patterns are established 011 conventions. The single new
axis (`dep_update_tool`) follows the existing FR-002 threading pattern.
