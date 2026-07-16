# Implementation Plan: De-opinionated bailiff-mod-* module family + new modules (spec 011)

**Branch**: `009-phase-1-3-module-port` (spec dir `011-deopinionated-module-family`) |
**Date**: 2026-07-14 | **Spec**: [spec.md](./spec.md)

**Input**: [spec.md](./spec.md) + the ratified decision ledger
(`$CLAUDE_JOB_DIR/tmp/009-deopinionation-decisions.md`, job 6548a828). Governed by the
constitution (amended to **v2.3.0** by this plan — see FR-019) and ADR-0002/0003/0006 + the
new ADR-0007 (native-command scaffolding). Reopens spec 007 (apm fold-in).

## Summary

Deliver the de-opinionated bailiff-mod-* family: revise 2 built modules, fold apm into a new
agentic module, and author ~14 new/ported modules — each offering finite `choices:` for the
tooling decisions teams differ on, scaffolding via native tool commands under `mise`, and
staying pure template content (no new `src/bailiff/` code — C-11). Two governance deliverables
land in this plan phase before any module is released: **(a)** a Constitution III amendment +
**ADR-0007** recording that native-tool-generated manifests are process-deterministic
task-output (FR-019); **(b)** a spec-007 reconciliation (apm FRs migrate to `bailiff-mod-agentic`).
Publishing (mirrors, releases, the apm tombstone) is a maintainer-confirmed batch, never
unattended (FR-020/FR-023/SC-009).

## Technical Context

**Language/Version**: No application code. Deliverables are copier YAML + Jinja templates +
shell `_tasks` + governance docs (constitution/ADR/spec-007 amendment). Existing
`scripts/check_modules.py` (Python 3.11+) is the lint; **no new `src/bailiff/` module, no new
`scripts/bailiff.py` verb** (C-11 / FR-011).

**Primary Dependencies**: copier `>=9.16,<10` (render/reproduce engine, pinned); `mise` (default
tool/version manager for generated projects — new cross-cutting dependency, FR-006); native
per-tool CLIs invoked by tasks (`uv`, `bun`/`pnpm`/`npm`, `cargo`, `go`, `gh`, `gitnr`, `cdk`,
`terraform`/`tofu`, `cfn-lint`, `uvx --from apm-cli`); the spec-003 `init_many` engine (threads
prior-layer answers via its accumulator — verified, no change needed).

**Storage**: N/A — files rendered/generated into the project tree; state in each layer's
`.copier-answers.yml` (`_src_path` + `_commit`, ADR-0002).

**Testing**: `pytest` init+reproduce loop tests under `tests/loop/` reusing
`build_template_repo`/`multi_template_set`/`_copy_module_with_stub_tasks` (tasks stubbed to
deterministic offline no-ops — the native-command tasks stub to marker writes so the suite stays
hermetic). `just check-modules` is the contract gate; the spec-005 secrets-policy lint must stay
green.

**Target Platform**: developer/CI shells (macOS/Linux/WSL); copier CLI + `settings.yml` trust.

**Project Type**: copier template family authored in a monorepo, fanned out per-repo by 008b
(ADR-0006); consumed as multi-template layers (ADR-0003).

**Constraints**: reproduce is faithful + agent-free (Constitution III, amended); **managed**
renders config-consistent; **seed-once** files via `_skip_if_exists`; **task-output** (native-tool
manifests, `.gitignore`/gitnr, `LICENSE`/gh, `.terraform.lock.hcl`, apm lock) process-
deterministic and version-pinned via `mise`; NO `jinja2_time` (Constitution V); NO `secret:`
questions (Constitution VI). No new `src/bailiff/` code (C-11).

**Scale/Scope**: ~18 modules total (post-critique) — revise `bailiff-mod-{base,python}` (bump to MAJOR
v1.0.0, clean break, M2); NEW `bailiff-mod-agentic` (apm folded in); build
`bailiff-mod-{ts,go,rust,precommit,quality,justfile,readme,stack-adr,github-repo,package-add}`; NEW CI
as TWO modules `bailiff-mod-ci-github` + `bailiff-mod-ci-gitlab` (5 models each, R3 split); NEW IaC trio
`bailiff-mod-{terraform,cdk,cloudformation}`. Drop `worktree`/`env`; **`org-policy` dropped** (R1, inert
until org-source-fetch). `bailiff-mod-speckit` separate (out of this build set).

## Constitution Check

*GATE: evaluated before Phase 0; re-checked after design. Constitution amended to v2.3.0 by
this plan (FR-019) — the check below is against the amended text.*

| Principle | Verdict | How spec 011 satisfies it |
|---|---|---|
| **I — Skills + Templates + Minimal Glue (C-11)** | PASS | Pure template content under `templates/bailiff-mod-*/`. No new `src/bailiff/` module or `scripts/bailiff.py` verb. `mise`/native-commands/multi-model-CI/agentic-rollup are all copier questions + rendered files + trust-gated tasks — no copier gap requiring glue (FR-011). |
| **II — Two-Phase; skill conducts, helpers execute** | PASS | Agent-tier decisions (CI model, stack facts, arch facts, plugin/target lists) are phase-1 judgment frozen as `--data` answers (FR-010); reproduce replays them, no agent in the reproduce path. |
| **III — Reproduce is faithful + agent-free** | PASS (amended) | **Managed** renders config-consistent. **Seed-once** via `_skip_if_exists`. **Task-output** now explicitly includes native-tool-generated manifests (FR-019 amendment + ADR-0007) — process-deterministic, `mise`-pinned, extending the existing LICENSE/gitnr/apm-lock precedent already in III. Order recomputed from committed answers. |
| **IV — copier CLI + static config** | PASS | Edges are `when:false` hidden answers statically read; no Template/Worker adapter introduced. |
| **V — Determinism via pinning; trust by source** | PASS | Native-command + network tasks are trust-gated; tool versions pinned via `mise .mise.toml`; `today` injected, no `jinja2_time`; no irreversible cloud action at scaffold time (FR-009). |
| **VI — Template-author contract** | PASS | Every module ships the answers-file `.jinja`, `when:false` edges, clean tags via cocogitto; **NO `secret:` questions** — tokens read from ambient env by tasks (FR-005). |
| **VII — Hardening is per-step** | PASS | Each module lands init+reproduce loop tests + `check_modules.py`; grill verdicts already applied per module (FR-021/FR-022). |
| **VIII — Documented, dry-run-validated handoff** | PASS | Frozen inputs are copier answers documented in SKILL.md; validation reuses copier's dry run + answer validation. |

**No unjustified violations.** The single principle *touched* is III, amended in-scope per its own
governance rule (amend the principle in the same change that relies on it) — recorded in the Sync
Impact report + ADR-0007. Complexity Tracking is therefore empty except the noted governance amendment.

## Project Structure

### Documentation (this feature)

```text
specs/011-deopinionated-module-family/
├── spec.md              # the spec (source of truth)
├── plan.md              # this file
├── research.md          # Phase 0 — consolidated grill/research findings
├── data-model.md        # Phase 1 — cross-cutting choice axes + module entities
├── contracts/           # Phase 1 — per-module + cross-cutting contracts
│   ├── _cross-cutting.md      # choice-axis keys, mise pattern, native-command pattern,
│   │                          #   hook_manager threading, agent-frozen --data facts
│   ├── bailiff-mod-base.md
│   ├── bailiff-mod-python.md
│   ├── bailiff-mod-agentic.md   # apm folded in
│   ├── ci-github-gitlab.md    # bailiff-mod-ci-github + bailiff-mod-ci-gitlab (2 modules, 5 models each)
│   ├── languages.md           # ts / go / rust (shared shape)
│   ├── quality-tooling.md     # precommit / quality / justfile
│   ├── docs-integration.md    # readme / stack-adr / github-repo / package-add (org-policy dropped, R1)
│   └── iac.md                 # terraform / cdk / cloudformation
├── quickstart.md        # Phase 1 — how to validate the family end to end
└── tasks.md             # Phase 2 (/speckit.tasks — NOT created here)
```

### Authored template content (repository root)

```text
templates/
├── bailiff-mod-base/            # REVISED — thinned scaffold + de-opinionation questions
├── bailiff-mod-python/          # REVISED — PM/version/ruff/layout choices; native uv init
├── bailiff-mod-agentic/         # NEW — agentic config rollup (apm folded in)
├── bailiff-mod-ts/              # NEW
├── bailiff-mod-go/              # NEW
├── bailiff-mod-rust/            # NEW
├── bailiff-mod-precommit/       # NEW — owns the hook_manager threading contract
├── bailiff-mod-quality/         # NEW
├── bailiff-mod-justfile/        # NEW
├── bailiff-mod-readme/          # NEW
├── bailiff-mod-stack-adr/       # NEW
├── bailiff-mod-github-repo/     # NEW
├── bailiff-mod-package-add/     # NEW
├── bailiff-mod-ci-github/       # NEW — 5 models (org-policy DROPPED per R1)
├── bailiff-mod-ci-gitlab/       # NEW — 5 models (host split per R3)
├── bailiff-mod-terraform/       # NEW
├── bailiff-mod-cdk/             # NEW
└── bailiff-mod-cloudformation/  # NEW
# bailiff-mod-apm/ is REMOVED from templates/ (folded into agentic); its released mirror is
# tombstoned in the confirmed publish batch (FR-020), not by this authoring work.

# Governance (edited by this plan phase — FR-019 / spec-007 reconciliation):
.specify/memory/constitution.md   # III amended → v2.3.0
docs/decisions/0007-native-command-scaffolding.md   # NEW ADR
specs/007-agentic-module/spec.md  # amended: apm FRs migrate to bailiff-mod-agentic

# Registration (per module, by `just new-module` + verified by check_modules.py):
cog.toml · catalog-sources.toml · skills/bailiff/SKILL.md
```

**Structure Decision**: mirror the proven `bailiff-mod-python` shape (`_subdirectory: template`,
answers-file `.jinja`, `when:false` edges, trust-gated `_tasks`). Each module authored in-monorepo;
008b fans each out to `bailiff-io/bailiff-mod-<name>`. `bailiff-mod-apm` is deleted from `templates/`
and its cog/catalog registration migrates to `bailiff-mod-agentic`.

## Cross-cutting design (Phase 1 detail → contracts/_cross-cutting.md)

1. **Choice-axis consistency (FR-002)**: shared keys/choices across modules — `python_pkg_manager
   [uv,pdm]=uv`, `js_pkg_manager [bun,pnpm,npm]=bun`, `hook_manager [pre-commit,lefthook,none]=
   pre-commit`, `python_layout [flat,src]=src`, `ts_linter [biome,eslint-prettier]=biome`, plus
   version lists (FR-004). Authored once in `_cross-cutting.md`; each module references it.
2. **mise integration (FR-006)**: each language/tool module contributes `[tools]` entries to a
   `.mise.toml` (managed render from frozen version answers); preflight `_task` = `mise install`
   (or a mise-aware presence check) instead of per-tool `command -v`. `.mise.toml` is the single
   pin surface that makes native-command output deterministic.
3. **Native-command scaffold pattern (FR-007 / ADR-0007)**: initial manifest via the tool's own
   init (`uv init`, `bun init`, `cargo new`, `go mod init`, `cdk init`) as a trust-gated `_task`
   with an idempotency guard (skip if the manifest already exists — the LICENSE-guard pattern);
   the manifest is task-output (process-deterministic), then seed-once/project-owned. Adding
   deps later = native `add` command (package-add). Config bailiff owns (tsconfig, `.tflint.hcl`,
   ruff-beyond-init, CI files) stays managed render.
4. **hook_manager threading contract (precommit owns it)**: `bailiff-mod-precommit` owns
   `.pre-commit-config.yaml` (or `lefthook.yml`); each language module threads
   `hook_manager` via `default: "{{ hook_manager }}"` and contributes its hook block, exactly as
   `gitignore_stack` is threaded today — single writer, no double-append.
5. **Agent-frozen `--data` facts (FR-010)**: `bailiff-mod-ci` and `bailiff-mod-stack-adr` sort
   before language layers (alphabetical basename tie-break) so they CANNOT read run-order answers;
   the phase-1 agent injects `ci_languages`/per-language facts/`ci_model` and the stack facts as
   frozen `--data`. Documented as the required pattern.

## How each governance deliverable is realized

- **FR-019 — Constitution III amendment + ADR-0007**: III already carves out "process-deterministic,
  tasks touch external state"; the amendment adds native-tool-generated manifests (via `mise`-pinned
  native init) as an explicit member of that task-output category, and ADR-0007 records the tradeoff
  (authentic new-project setup + mise pinning vs strict config-consistency) and the boundary (config bailiff
  owns stays config-consistent). Constitution bumps 2.2.0→2.3.0 (MINOR — materially expanded guidance).
  **Gate: no 011 module is released until this lands** (SC-008).
- **Spec-007 reconciliation (FR-016/FR-020)**: amend 007's Q1/OQ-007-b/f/D-007-4 to record the hybrid
  resolution (agentic rollup + apm folded + speckit separate); 007's apm-specific FRs (apm.yml/install/
  lockfile/empty-set-refusal) migrate to `bailiff-mod-agentic`'s feature set, with the empty-set refusal
  DROPPED (agentic renders clean with no features). The released apm mirror tombstone (FR-020) is a
  confirmed public action, not authoring.

## Module contract summary (detail in contracts/*)

| Module | Kind | Key questions (choices/default) | Native task | Notable |
|---|---|---|---|---|
| base | revise | layout, license(13/apache-2.0), docs_subdirs(on→arch/decisions/runbooks), extra_dirs, branch_strategy, copyright_name, run_git_init, github_host | gitnr, gh LICENSE, git init | thinned: agent/iac/ci/specs dirs moved out; archive/assets dropped |
| python | revise | python_pkg_manager[uv,pdm], python_version[3.11-3.14]=3.13, python_layout[flat,src]=src, ruff_* , test opt-in(pytest) | `uv init` | pyproject → task-output; ruff config managed |
| agentic | NEW | agentic_targets[claude,codex,opencode,kiro] (no default), kiro_cli_agents, mcp_config, native_marketplace, install_via_apm(off) | apm install, plugin install | apm folded in; renders clean empty; MCP per-target |
| ts | NEW | js_pkg_manager[bun,pnpm,npm]=bun, ts_linter[biome,eslint-prettier]=biome, test_runner(none), node_version, framework | `bun/pnpm init` | nuxi pinned, sst gitignore fix |
| go | NEW | go_version, app_kind[cli,service,library]=cli, test_runner[go-test,gotestsum]=go-test, use_vendor_mode | `go mod init` | golangci-lint seed-once |
| rust | NEW | rust_channel=stable, rust_edition[2024,2021,2018]=2024, test_runner[cargo-test,nextest]=nextest, rustfmt_heuristics=Max, clippy_stage=pre-push | `cargo new`(+--lib fix) | |
| precommit | NEW | hook_manager[pre-commit,lefthook,none]=pre-commit, enforce_conventional_commits, enable_typo_check | pre-commit install | OWNS hook_manager threading |
| quality | NEW | quality_languages(yaml open list) | — | single writer `.agents/hooks/quality-languages`; empty→no file |
| justfile | NEW | thread js_pkg_manager+hook_manager, language[py,ts,go,rust,""] | — | seed-once justfile |
| readme | NEW | readme_style[static-skeleton,agent-draft]=agent-draft, confirm_readme_draft | — | seed-once; agent draft frozen via --data |
| stack-adr | NEW | format[simple,adr]=simple (opt-in), adr_dir=docs/decisions | — | SEED-ONCE, agent-frozen facts, initial-only |
| github-repo | NEW | visibility[private,public,internal]=private, remote_protocol, push_after_create, team | gh repo create | public keeps hard abort-without-consent |
| package-add | NEW | native add per PM | pnpm/bun/uv/cargo/go add | scaffolds pkg dir; tool writes workspace manifest |
| ci-github | NEW | ci_model[minimal,standard,optimized,monorepo-affected,merge-queue]=minimal, ci_cache(on), ci_concurrency_cancel(on), ci_os_matrix/versions(single), ci_oidc_provider(none), merge_queue_org_confirmed | none (pure render) | agent-frozen ci_languages+facts; fail-loud on empty (R4); artifact majors match |
| ci-gitlab | NEW | same + gitlab_tier[free,premium_ultimate]=free | none (pure render) | no gate/deploy job; optional:true needs; pinned images; merge-queue+free=fallback |
| ~~org-policy~~ | DROPPED (R1) | — | — | inert until org-source-fetch; ships in future org-governance spec |
| terraform | NEW | tf_flavor[terraform,opentofu]=terraform, placement_dir=infrastructure | `terraform/tofu init` | versions.tf managed, main/backend seed-once, lock task-output; tflint+trivy |
| cdk | NEW | cdk_language[typescript,python,go,java,csharp]=typescript, placement_dir, cdk_version, include_cdk_nag, include_synth_validate | `cdk init` | never bootstrap/deploy; cdk.context.json committed |
| cloudformation | NEW | mode[raw,sam]=raw, stack_description, environment_names([dev,prod]), cfnlint_version, cfnlint_ignore_rules, aws_validate(off) | opt-in aws validate | YAML render; seed-once template + params; cfnlintrc managed |

## Build / test / release sequencing

1. **Governance first (FR-019 gate)**: amend Constitution III → v2.3.0, write ADR-0007, amend spec 007.
   No module releases until done (SC-008).
2. **Slice A — deterministic core**: base(revise→v1.0.0), python(revise→v1.0.0), ts, go, rust, precommit
   (owns hook_manager/hook_blocks freeze — do early), quality, justfile. Each: `just new-module` (if new)
   → author → loop tests → `just check-modules` green. base/python are a clean-break MAJOR (M2): no
   `_migrations`, no update path, no break docs.
3. **Slice B — agent-tier + agentic + CI**: readme, stack-adr, bailiff-mod-agentic (apm fold-in),
   bailiff-mod-ci-github + bailiff-mod-ci-gitlab (two modules, R3). MI-1 pin auto-updater lands with/before
   the second CI host.
4. **Slice C — integration + IaC + monorepo**: github-repo, package-add, terraform, cdk, cloudformation.
   (org-policy dropped — R1.)
5. **Verify all green locally** (`just check-modules`, `just test` targeted, `just lint`, `just vendor &&
   just check-vendor` if vendored sources touched — none expected under C-11).
6. **Confirmed publish batch (FR-020/FR-023, SC-009)**: pre-create each mirror by hand; merge to main fires
   the armed 008b pipeline; tombstone the old apm mirror. All maintainer-confirmed, never unattended.

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| Constitution III amendment (v2.3.0) | Native-command scaffolding makes manifests process-deterministic, not config-consistent (FR-007/FR-019) | Rendering config-consistently was the Phase-0 model; maintainer chose native+mise (more authentic) and to keep it bundled (critique M4 — decouple option declined). In-scope per III's own governance rule. |
| base/python MAJOR bump, no update path | 011 reshapes released v0.1.0 incompatibly (M2) | `_migrations` across managed→seed-once + moved dirs is fiddly + low-value at near-zero consumers; clean break is honest (greenfield). No user-facing break docs (maintainer). |

## Critique resolutions (2026-07-14) — folded into spec/plan/contracts
- **M1**: accreting files (`mise_tools`, `hook_manager`+`hook_blocks`, `quality_languages`) are
  agent-frozen unions → single writer (the `gitignore_stack` pattern), NOT runtime accumulation.
  Cross-cutting §2/§4/§5 rewritten; languages/quality/precommit contracts updated.
- **M2**: base/python clean-break MAJOR (FR-012).
- **M3**: preflight + native-init tasks init-only-guarded; reproduce over committed tree needs no
  toolchain/network (FR-012a).
- **M4**: keep native+mise+III bundled (maintainer decision).
- **R1**: org-policy DROPPED. **R2**: agentic keeps refusal for `install_via_apm && apm_packages==[]`.
  **R3**: CI split into `bailiff-mod-ci-github` + `bailiff-mod-ci-gitlab` (both built). **R4**: CI fails
  loud on empty ci_languages + no monorepo_tool. **R5**: SC-002/quickstart assert presence not
  regeneration. **R6**: catalog regen sequenced with apm tombstone.

No unjustified violations remain.
