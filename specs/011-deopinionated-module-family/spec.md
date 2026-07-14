# Feature Specification: De-opinionated clerk-mod-* module family + new modules (spec 011)

**Feature Branch**: `009-phase-1-3-module-port` (spec dir `011-deopinionated-module-family`; the
011 work continues on the existing 009 branch by maintainer choice)

**Created**: 2026-07-14

**Status**: Draft — authored from the ratified 2026-07-14 decision session. Supersedes the
faithful-translation lean of spec 009 Phases 1–3.

**Input**: The authoritative decision ledger at
`$CLAUDE_JOB_DIR/tmp/009-deopinionation-decisions.md` (job 6548a828), produced by a full
decision session on 2026-07-14 in which every module (built + to-build) and every new module
design (CI models, agentic rollup, IaC family) was adversarially **grilled** for opinionation
and each choice ratified by the maintainer. Governed by the constitution v2.2.0 (Principles
I–VIII), ADR-0002/0003/0006, and spec 009 (Clarifications 2026-07-14, FR-011 relaxed,
FR-014/FR-015). Depends on specs 002/003/006/008/010; **reopens spec 007** (apm folds into a
new agentic module).

---

## Overview

Spec 009 re-homed the `project-setup` capability as copier templates under a *faithful
translation* charter (FR-011: "no capability beyond the ancestor"). On 2026-07-14 the
maintainer redirected the work: the ported modules must be **generic** — they must offer the
user sane, finite choices for the decisions competent teams genuinely differ on (package
manager, linter, formatter, test runner, hook manager, layout, tool versions) rather than
baking in one opinion — while dropping genuinely dead options (bare `pip`, `yarn`, `jest`,
`husky`). Spec 009 already relaxed FR-011 and added FR-014 (de-opinionation) and FR-015
(multi-model CI) to sanction this. Spec 011 is the full, planned expression of that redirect:
it is large enough (a re-architected base, ~13 revised/ported modules, 5 new modules, and a
reproduce-model change that touches the constitution) that it warrants its own spec rather than
further amendment of 009.

The work is **still template content, not tool code** (Constitution I / C-11): every choice is
a copier question, a rendered file, a `when:`/`when:false` edge, or a trust-gated `_task`. The
only exception surfaced during grilling is a **reproduce-model shift** (see FR-019): adopting
`mise` as the default tool manager and using **native tool commands** (`uv init`, `bun init`,
`cargo new`, `go mod init`, `cdk init`) to scaffold projects makes language manifests
**process-deterministic task-output** rather than byte-identical renders. This softens
Constitution III for those files and MUST be reconciled by a constitution amendment + an ADR
during the plan phase.

This spec covers **authoring/revision only**. Publishing the resulting module mirrors +
releases, and the `clerk-mod-apm` → `clerk-mod-agentic` mirror tombstone, are irreversible
public actions that MUST be a maintainer-confirmed batch, never performed unattended.

---

## Working method (already executed)

Every module and every new-module design was adversarially **grilled** for opinionation by
background analysis workflows before ratification (16-module grill; CI-models research + GitHub
and GitLab design grills; IaC/CDK/CloudFormation research; agentic-config design). The ledger
records each ratified decision. Spec 011 encodes those decisions as requirements. Any decision
not in the ledger is out of scope for this spec.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Scaffold a language project with my own tooling choices (Priority: P1)

A developer selects a language overlay (e.g. `clerk-mod-python` or `clerk-mod-ts`) and is
offered sane, finite choices for the tooling that teams differ on — the package manager, linter,
formatter, layout, and language version — each with a modern default. The generated project uses
their chosen tools, scaffolded via the tool's own native command, and records the choices so the
project reproduces.

**Why this priority**: This is the core de-opinionation outcome — a generic module family that
adapts to the team instead of imposing one stack. It is the reason spec 011 exists.

**Independent Test**: Init `clerk-mod-python` with `python_pkg_manager=pdm` and `python_layout=src`
→ the project is scaffolded with pdm + a `src/` layout; the answers file records both; a second
person reproduces the same choices.

**Acceptance Scenarios**:

1. **Given** `clerk-mod-python` with `python_pkg_manager=uv`, `ruff_line_length=88`, **When** init,
   **Then** the project is scaffolded via `uv init` and its ruff config uses line-length 88, and the
   choices are persisted to the answers file.
2. **Given** `clerk-mod-ts` with `js_pkg_manager=pnpm`, `ts_linter=biome`, **When** init, **Then**
   the project uses pnpm (`pnpm-workspace.yaml` where relevant) and biome, not npm/eslint.
3. **Given** any language module, **When** the user is offered a tooling choice, **Then** dead
   options (bare `pip`, `yarn`, `jest`, `husky`) are NOT offered; only maintained options appear.

### User Story 2 — Reproduce a project whose manifests were tool-generated (Priority: P1)

A developer reproduces a project on a fresh machine. Files clerk renders (config it owns) come back
byte-identical; language manifests that were generated by a native tool command come back
**process-deterministically** (equivalent, tool-version-pinned, not asserted byte-for-byte);
seed-once/living files that the project has edited are not clobbered.

**Why this priority**: Reproduce is clerk's headline guarantee. The native-commands decision changes
what "faithful" means for manifests, and that change must be correct and tested, not incidental.

**Independent Test**: Generate a `[base, python]` project, reproduce onto a fresh checkout → managed
config re-renders byte-identically; `pyproject.toml` is regenerated by the pinned tool; an edited
`AGENTS.md` on a re-run is preserved.

**Acceptance Scenarios**:

1. **Given** a generated project, **When** reproduce onto a fresh checkout, **Then** clerk-managed
   config files are byte-identical and tool-generated manifests are regenerated by the version-pinned
   tool (process-deterministic, not asserted byte-identical) — consistent with the amended Constitution III.
2. **Given** a project whose seed-once files (`AGENTS.md`, tool-owned manifests) were edited after init,
   **When** a re-run/update over the populated tree, **Then** those edits are preserved (`_skip_if_exists`).
3. **Given** any module that runs a tool, **When** the required tool is absent, **Then** a preflight
   task fails first with explicit install guidance (via `mise`), before any consequential task runs.

### User Story 3 — Wire the agentic ecosystem in one module (Priority: P1)

A developer opts into `clerk-mod-agentic` and selects which coding agents to configure (Claude, Codex,
OpenCode, Kiro) plus features (MCP config, native marketplace, APM package install). The module writes
each agent's native config and, when requested, installs agentic packages via the agent's native
marketplace and/or APM.

**Why this priority**: This resolves spec 007's parked monolith-vs-split question and delivers the
distinctive agentic wiring as one coherent module. It also folds in the released `clerk-mod-apm`.

**Independent Test**: Init `clerk-mod-agentic` with `agentic_targets=[claude, kiro]`, `mcp_config=true`
→ `.claude/` + `.kiro/` config and an MCP config per target are rendered; no target is assumed by default.

**Acceptance Scenarios**:

1. **Given** `agentic_targets=[claude, codex]` and `native_marketplace=true`, **When** init, **Then**
   `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` are rendered and enabled
   plugins installed via a trust-gated task from the frozen plugin list.
2. **Given** a target with no marketplace (kiro/opencode) and `install_via_apm=true`, **When** init,
   **Then** APM is used to install agentic packages into that target's directory.
3. **Given** the module selected with no targets and all features off, **When** init, **Then** it renders
   cleanly (no hard refusal) — a valid no-op layer.

### User Story 4 — Add CI sized to my project, at the right optimization level (Priority: P1)

A developer's project gets a CI workflow whose optimization model (serial / parallel+gate / change-filtered /
monorepo-affected / merge-queue) is selected by the phase-1 agent from the project's shape, targeting either
GitHub Actions or GitLab CI, sized to the active language stack.

**Why this priority**: FR-015; CI is high-value and the multi-model design is a headline of the redirect.

**Independent Test**: Init `clerk-mod-ci` with `ci_host=github`, `ci_model=standard`, two active languages →
a `.github/workflows/ci.yml` with parallel per-language jobs + a fan-in gate; switch `ci_host=gitlab` → an
equivalent `.gitlab-ci.yml`.

**Acceptance Scenarios**:

1. **Given** `ci_model=minimal`, **When** init, **Then** a single-job sequential workflow is rendered with
   NO fan-in gate (regardless of `ci_required_gate`).
2. **Given** `ci_host=gitlab`, `ci_model=merge-queue`, `gitlab_tier=free`, **When** init, **Then** the
   merge-when-pipeline-succeeds fallback is rendered with a header warning (no hard error).
3. **Given** action/image version pins, **When** rendered, **Then** no `:latest`/`:lts`/unpinned refs appear;
   upload/download-artifact majors match.

### User Story 5 — Add infrastructure-as-code in my chosen paradigm (Priority: P2)

A developer adds IaC via the module matching their paradigm — `clerk-mod-terraform` (Terraform or OpenTofu),
`clerk-mod-cdk` (AWS CDK in their language), or `clerk-mod-cloudformation` (raw CFN or SAM) — as a
layout-independent overlay placed under a configurable directory.

**Why this priority**: Restores IaC capability that base wrongly hardcoded, but as a de-opinionated, correctly
separated family. P2 because it follows the language/agentic/CI core.

**Independent Test**: Init `clerk-mod-terraform` with `tf_flavor=opentofu`, `placement_dir=infrastructure` →
an HCL root module under `infrastructure/` with versions.tf managed, backend seeded commented, `.terraform.lock.hcl`
produced by a trust-gated `tofu init`.

**Acceptance Scenarios**:

1. **Given** `clerk-mod-terraform` `tf_flavor=terraform`, **When** init, **Then** the HCL skeleton + `.tflint.hcl`
   (managed) + seed-once `main.tf`/`backend.tf` are written and `terraform init` runs trust-gated.
2. **Given** `clerk-mod-cdk` `cdk_language=python`, **When** init, **Then** `cdk init app --language=python` runs
   as a trust-gated task into `placement_dir`, never `cdk bootstrap`/`deploy`.
3. **Given** `clerk-mod-cloudformation` `mode=sam`, **When** init, **Then** the seed template carries the SAM
   Transform + Globals; raw mode omits them.

### User Story 6 — Get a thin, unopinionated base scaffold (Priority: P1)

A developer selecting `clerk-mod-base` gets a minimal universal skeleton (`docs/`, `scripts/`, `tests/`,
optional lean `docs/` subdirs, a minimal `.github/` only if they use GitHub) plus identity/license, without
being forced into an IaC tree, agent dirs, a CI workflow dir, or a `specs/` dir — those come from their owning
modules only when selected.

**Why this priority**: Base is the always-on root; its over-opinionation propagates to every project. Thinning
it is foundational to the whole family being generic.

**Independent Test**: Init `clerk-mod-base` alone → contains `docs/`+`scripts/`+`tests/`, no `infrastructure/`,
no `.agents/`/`.codex/`, no `.github/workflows/`, no `specs/`, no `archive/`/`assets/`; `extra_dirs` and
`branch_strategy`/`copyright_name`/`run_git_init` questions are honored.

**Acceptance Scenarios**:

1. **Given** `clerk-mod-base` with defaults, **When** init, **Then** the always-on dirs are created and the
   moved-out/dropped dirs are absent.
2. **Given** `github_host=false`, **When** init, **Then** no `.github/` directory is created.
3. **Given** `docs_subdirs=true` (default), **When** init, **Then** only the lean core subdirs
   (`architecture`, `decisions`, `runbooks`) are created, not the former eight.

### User Story 7 — Every module is fan-out-ready (Priority: P1)

Each revised/new module passes `just check-modules` (answers-file `.jinja`, README, CHANGELOG with the
`- - -` separator, three-way registration parity) and ships init+reproduce integration tests, so the 008b
pipeline can fan it out.

**Why this priority**: Without this, nothing can be released; it is the gate the whole family must clear.

**Independent Test**: Run `just check-modules` on the finished `templates/` → `ok`; run the targeted loop tests → green.

**Acceptance Scenarios**:

1. **Given** all authored modules, **When** `just check-modules`, **Then** it reports `ok`.
2. **Given** each module, **When** its loop tests run, **Then** init + reproduce pass and no `secret:` question exists.

### Edge Cases

- **Reproduce of a tool-generated manifest across tool versions**: pinned via `mise`; process-deterministic, not
  byte-identical — the amended Constitution III governs (FR-019). If the tool is absent, preflight fails loudly.
- **A module selected with an empty/none feature set** (e.g. `clerk-mod-agentic` with no targets): renders cleanly,
  no hard refusal (contrast the old apm empty-set refusal).
- **CI `minimal` + `ci_required_gate=true`**: the gate is suppressed for `minimal` (no parallel siblings to gate).
- **GitLab `needs:` on a change-gated job**: MUST use `optional: true` or the pipeline fails to create on
  source-only changes.
- **Multi-crate Rust under `minimal` CI**: one `cargo test --workspace` job — within-language parallelism is the
  tool's, not per-crate CI jobs (that is `standard`/`monorepo-affected`).
- **Native command needs a tool the user lacks**: `mise install` in preflight provides it; if `mise` itself is
  absent, preflight fails with mise install guidance.
- **`clerk-mod-apm` consumers after the rename**: the old mirror is tombstoned with a deprecation pointer to
  `clerk-mod-agentic`; this is a confirmed public action, not automatic.

## Requirements *(mandatory)*

### Functional Requirements — de-opinionation (cross-cutting)

- **FR-001**: Each module MUST expose consequential tooling/config decisions (package manager, linter, formatter,
  test runner, hook manager, layout, tool versions) as copier questions with finite static `choices:` and a sane
  modern default, UNLESS there is a single clear best answer (may stay hardcoded) or the alternatives are dead
  (dropped). (Governed by 009 FR-014.)
- **FR-002**: Cross-cutting choice axes MUST use a consistent key/choices shape across modules. Ratified sets:
  Python package manager `[uv, pdm]` default `uv` (drop `poetry`, `pip`, `pipenv`); JS package manager
  `[bun, pnpm, npm]` default `bun` (drop `yarn`); hook manager `[pre-commit, lefthook, none]` default `pre-commit`
  (drop `husky`, `simple-git-hooks`); Python layout `[flat, src]` default `src`; TS linter `[biome, eslint-prettier]`
  default `biome`.
- **FR-003**: Ruff configuration MUST be de-opinionated: `ruff_line_length` default `88` (offered `[79, 88, 100, 119, 120]`),
  `ruff_quote_style` `[double, single]` default `double`, `ruff_rule_profile` `[standard, strict]` default `standard`.
- **FR-004**: Language version lists MUST be finite `choices:` with a modern default: Python `[3.11, 3.12, 3.13, 3.14]`
  default `3.13`; Rust channel `[stable, beta, nightly, esp]` default `stable`, edition `[2024, 2021, 2018]` default `2024`
  (drop `2015`); Go and Node versions offered as maintained sets. Version lists are subject to the meta-item auto-updater
  (out of module scope, see below).
- **FR-005**: No shipped module MAY declare a `secret:` question; credentials are read from the ambient environment by a
  task (Constitution VI). (Unchanged from 009.)

### Functional Requirements — tooling & reproduce model

- **FR-006** *(mise default)*: Modules MUST use `mise` as the default tool/version manager: each language/tool module
  writes a `.mise.toml` (or contributes its `[tools]` entries) pinning its tools + versions, and the preflight `_task`
  becomes `mise install` (or a mise-aware presence check) rather than per-tool `command -v` checks.
- **FR-007** *(native commands)*: Modules MUST scaffold projects via the tool's own native command
  (`uv init`/`bun init`/`pnpm`/`cargo new`/`go mod init`/`cdk init`) as trust-gated `_tasks`, rather than hand-rendering
  the tool-owned manifest. `mise` guarantees the tool is present. Adding dependencies/packages later (e.g. `package-add`)
  MUST likewise use native `add` commands, not manifest edits.
- **FR-008** *(lifecycle)*: Each module MUST classify each output as **managed** (clerk owns; re-rendered byte-identically),
  **seed-once/living** (`_skip_if_exists`; scaffolded once then project-owned), or **task-output** (process-deterministic,
  produced by a native/network task). Tool-owned manifests are task-output; clerk-owned config (e.g. `.tflint.hcl`,
  `.cfnlintrc.yaml`, CI workflow files) is managed; `AGENTS.md`, tool manifests, and living docs are seed-once.
- **FR-009** *(trust-gated tasks)*: Every code-executing or network-touching action MUST be a trust-gated `_task` with a
  preflight ordered first; version pins in the task command where determinism allows. No task may perform an irreversible
  cloud action at scaffold time (never `cdk bootstrap`/`deploy`, `terraform apply`, `sam deploy`).
- **FR-010** *(agent-tier frozen answers)*: Agent-tier decisions (CI model, stack facts, architecture facts) MUST be
  produced in phase 1 and frozen as `--data` answers; the template renders deterministically; no agent is in the reproduce
  path. Modules that must read facts from sibling layers (CI, stack-adr) MUST receive them as agent-frozen `--data`
  answers (they sort before language layers and cannot read run-order answers).
- **FR-011**: No new `src/clerk/` code or `scripts/clerk.py` verb is introduced (Constitution I / C-11); all behavior is
  copier questions, rendered files, `when:`/`when:false` edges, and trust-gated tasks.

### Functional Requirements — module set

- **FR-012** *(revise built modules)*: `clerk-mod-base`, `clerk-mod-python` MUST be revised to satisfy FR-001…FR-010.
  `clerk-mod-apm` MUST be folded into `clerk-mod-agentic` (FR-016) rather than revised in place. **Migration (critique M2):**
  the 011 reshape of base/python is incompatible with their released v0.1.0 (moved-out dirs; `pyproject.toml`
  managed-render → task-output/seed-once). They MUST bump to a new MAJOR (`v1.0.0`) as a **clean break with NO `copier
  update` path and NO `_migrations`** — justified as greenfield (near-zero consumers). No user-facing break/migration docs
  are written (maintainer decision); the major bump is the only signal.
- **FR-012a** *(reproduce is not coupled to the toolchain — critique M3)*: Every preflight (`mise install`) and native-init
  `_task` MUST be **init-only-guarded** (a committed sentinel or a `test -f <manifest>` guard, as `clerk-mod-base`'s LICENSE
  task already does) so that reproduce over an already-populated tree does NOT re-run `mise install` or the native tool.
  Reproduce fidelity is scoped to managed renders; a committed-tree reproduce MUST succeed without the native toolchain or
  network present.
- **FR-013** *(build ported modules)*: The following MUST be authored: `clerk-mod-ts`, `clerk-mod-go`, `clerk-mod-rust`,
  `clerk-mod-precommit`, `clerk-mod-quality`, `clerk-mod-justfile`, `clerk-mod-readme`, `clerk-mod-stack-adr`,
  `clerk-mod-github-repo`, `clerk-mod-package-add`. Each de-opinionated per its grilling verdict.
- **FR-014** *(drop / defer — amended per 2026-07-14 critique)*: `worktreeinclude-write` (`clerk-mod-worktree`) and
  `env-example` (`clerk-mod-env`) MUST NOT be built (dropped: niche/too-opinionated). **`clerk-mod-org-policy` is DROPPED
  from the 011 build set** (critique R1): it is inert until an org-source-fetch module exists (which is not planned here),
  so it ships in a future org-governance spec alongside its only consumer, not as a dead module now. `clerk-mod-speckit`
  remains a SEPARATE module (owns `specs/`), not part of this build set.
- **FR-015** *(thin base)*: `clerk-mod-base` always-on outputs MUST be `docs/` (with a lean `docs_subdirs` toggle default
  on → `architecture`/`decisions`/`runbooks` only), `scripts/`, `tests/`, and a minimal `.github/` gated on a `github_host`
  boolean. It MUST NOT scaffold `.agents/`/`.codex/` (→ agentic), `infrastructure/` (→ IaC modules),
  `.github/workflows/` (→ CI), `specs/` (→ speckit), or `archive/`/`assets/` (dropped). It MUST add questions:
  `extra_dirs` (freeform list), `branch_strategy`, `copyright_name` (default `{{ org }}`), `run_git_init` (default true),
  `docs_subdirs`. It MUST keep the 13-SPDX license set (default `apache-2.0`), single/monorepo layout, gitnr `.gitignore`,
  and the `gh` LICENSE fetch.
- **FR-016** *(clerk-mod-agentic)*: A NEW `clerk-mod-agentic` module MUST roll up agentic config as a copier template:
  targets `agentic_targets` (multiselect `[claude, codex, opencode, kiro]`, no default — agent chooses); a `kiro_cli_agents`
  sub-toggle (Kiro is one slug, IDE+CLI share `.kiro/`); features gated by `when:` toggles — `mcp_config` (per-target native
  MCP file from a canonical injected `mcp_servers` list), `native_marketplace` (Claude/Codex marketplace manifests +
  trust-gated plugin install from a frozen list), `install_via_apm` (default off; the install path for non-marketplace
  targets, trust-gated `uvx --from apm-cli install`). It MUST render cleanly with no targets/features (no refusal). It
  supersedes `clerk-mod-apm` (reopens spec 007; migrates apm's FRs; renames the released mirror — see FR-020).
- **FR-017** *(CI — TWO host modules, amended per critique R3)*: CI is split into TWO separate modules —
  **`clerk-mod-ci-github`** and **`clerk-mod-ci-gitlab`** (they share almost no render; a single host-branched module was
  the "conditional explosion" the IaC split already rejected). BOTH are built in 011. Each offers `ci_model`
  `[minimal, standard, optimized, monorepo-affected, merge-queue]` default `minimal` (matrix is NOT a model — it is the
  `ci_os_matrix`/`ci_matrix_versions` toggle). Orthogonal toggles: `ci_cache` (default on), `ci_concurrency_cancel`
  (default on), `ci_os_matrix`/`ci_matrix_versions` (default single), `ci_oidc_provider` (default none); `ci_harden_runner`
  is NOT offered. `clerk-mod-ci-gitlab` additionally has `gitlab_tier` `[free, premium_ultimate]` default free (merge-queue
  fallback). Each is a pure managed render (zero `_tasks`), sized from agent-frozen `--data` (`ci_languages` + per-language
  facts + `ci_model`), and MUST **fail loud** (rendered warning or preflight error) when selected with empty `ci_languages`
  and `monorepo_tool==none` (critique R4 — no silent empty workflow). Each MUST apply its grill-identified render fixes:
  github — gate suppressed on minimal, status-shim on change-filtered, pinned actions (upload/download-artifact SAME major);
  gitlab — no gate/deploy job, `optional:true` needs on change-gated jobs, pinned images (no `:latest`), coupled
  interruptible+auto_cancel, literal `compare_to`, canonical `workflow:rules` duplicate guard, `fallback_keys`. The pin
  auto-updater (MI-1) SHOULD land before/with the second host to bound the rotating-pin maintenance surface.
- **FR-018** *(IaC family — three modules)*: Three NEW separate modules MUST be authored (different paradigms, no shared
  template content): `clerk-mod-terraform` (`tf_flavor [terraform, opentofu]` default `terraform`; HCL skeleton; managed
  versions.tf/.tflint.hcl; seed-once main/backend; `.terraform.lock.hcl` task-output via trust-gated init; tflint+trivy,
  no tfsec; env-per-dir not workspaces; no Terragrunt); `clerk-mod-cdk` (AWS CDK; `cdk_language` `[typescript, python, go,
  java, csharp]` default typescript; pure `cdk init` task module; no edge to language modules; never bootstrap/deploy;
  cdk.context.json committed, cdk.out/ gitignored; optional `include_cdk_nag`/`include_synth_validate`);
  `clerk-mod-cloudformation` (`mode [raw, sam]` default raw; YAML-only render; seed-once template.yaml + per-env parameter
  files; managed `.cfnlintrc.yaml`; cfn-lint; opt-in `aws_validate` trust-gated; AWS pseudo-params not hardcoded values).
  Each is a layout-independent overlay with `placement_dir` default `infrastructure` (`.` for standalone).

### Functional Requirements — contract, testing, release

- **FR-019** *(reproduce-model reconciliation)*: The plan phase MUST amend Constitution III and write an ADR recording that
  tool-generated manifests (via native init under FR-007) are **process-deterministic task-output**, not byte-identical
  renders — extending the existing LICENSE/gitnr/apm-lock precedent — and the tradeoff (authentic new-project setup +
  mise-pinned determinism vs strict byte-identity). No module may be released under 011 until this reconciliation lands.
- **FR-020** *(apm rename / tombstone)*: Folding `clerk-mod-apm` into `clerk-mod-agentic` MUST create the new module + mirror
  and tombstone the released `copier-clerk/clerk-mod-apm` mirror with a deprecation pointer. This is an irreversible public
  action requiring explicit maintainer confirmation; it MUST NOT be performed unattended. Spec 007 MUST be amended to record
  the hybrid resolution (agentic rollup + apm folded + speckit separate). **Sequencing (critique R6):** the `catalog.json`
  regeneration that drops apm MUST be sequenced WITH the tombstone so there is no window where apm is un-discoverable in the
  catalog but not yet redirected by the tombstone pointer.
- **FR-021** *(contract lint)*: Every authored/revised module MUST pass `scripts/check_modules.py` (`just check-modules`):
  answers-file `.jinja`, README, CHANGELOG with the `- - -` separator, three-way registration parity
  (`templates/` == `cog.toml [monorepo.packages]` == `catalog-sources.toml`), published-label immutability.
- **FR-022** *(testing)*: Every module MUST ship init + reproduce integration tests under `tests/loop/` (hermetic, tasks
  stubbed offline) and MUST keep the spec-005 secrets-policy lint green (no `secret:` questions).
- **FR-023** *(release batch)*: Publishing the module mirrors + releases via the 008b pipeline is a maintainer-confirmed
  batch (each new module's mirror pre-created by hand per the runbook). No fan-out or release is performed unattended.

### Out-of-module meta-items (flagged, NOT built as modules here)

- **MI-1** *(version auto-updater)*: A CI-driven job in the clerk repo that checks upstream releases and bumps the version
  `choices:`/defaults across modules. Clerk-repo tooling, scoped separately; not a `clerk-mod-*` module. Flagged for its own
  small spec.
- **MI-2** *(apm mirror tombstone)*: The public tombstone of the old apm mirror (see FR-020) — a reconfirm-gated action, not
  authoring work.

### Key Entities

- **clerk-mod-\* template**: one module — copier template under `templates/clerk-mod-<name>/`, fanned out by 008b.
- **Cross-cutting choice axis**: a tooling decision (pkg-manager, linter, …) expressed with a consistent key/choices shape
  across modules (FR-002).
- **Agent-frozen answer**: a phase-1 decision (CI model, stack facts, plugin list) persisted as a `--data` answer — the
  reproduce state for agent-tier behavior.
- **Trust-gated `_task`**: a copier task carrying a native/network action (tool init, install, `gh`/`tofu`/`cdk` calls).
- **mise `.mise.toml`**: the per-project tool+version pin file that makes native-command scaffolding deterministic.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every consequential tooling decision a competent team differs on is a choice with a sane default; a spot-check
  of any module surfaces no forced opinion outside the ratified "keep hardcoded" set, and no dead option (pip/yarn/jest/husky)
  is offered.
- **SC-002** *(reworded per critique R5)*: A generated project reproduces with clerk-managed files byte-identical and
  tool-generated manifests **present and structurally intact** (the committed manifest is used verbatim — the native-init
  task is init-only-guarded and `_skip_if_exists` protects the file, so reproduce over the committed tree does NOT
  re-shell or regenerate); no reproduce path invokes an agent, and reproduce over a committed tree does not require the
  native toolchain to re-run. What the native-command model changes is *init-time cross-machine byte consistency* of
  manifests (never a strict clerk guarantee for task-output), not reproduce fidelity.
- **SC-003**: `clerk-mod-agentic` produces working config for any subset of `[claude, codex, opencode, kiro]` and installs
  packages via native marketplace and/or APM; the empty selection renders with no error.
- **SC-004**: `clerk-mod-ci` renders a valid, correctly-gated workflow for each of the 5 models on both GitHub and GitLab,
  sized to the active languages, with all pins non-mutable and the grill-identified footguns absent.
- **SC-005**: Each IaC module scaffolds an idiomatic project in its paradigm under a configurable directory, runs no
  irreversible cloud action, and reproduces.
- **SC-006**: `clerk-mod-base` generates only the thinned always-on set at defaults; moved-out and dropped directories are
  absent; the new questions are honored.
- **SC-007**: Every authored/revised module passes `just check-modules` and its init+reproduce loop tests; the secrets-policy
  lint stays green.
- **SC-008**: Constitution III is amended and an ADR recorded (FR-019) before any 011 module is released.
- **SC-009**: No irreversible public action (mirror creation, release, apm tombstone) occurs without explicit maintainer
  confirmation.

## Assumptions

- The decision ledger at `$CLAUDE_JOB_DIR/tmp/009-deopinionation-decisions.md` (job 6548a828) is the authoritative,
  complete record of ratified decisions; where this spec is silent, the ledger governs, and where the ledger is silent,
  the item is out of scope.
- Specs 002/003/006/008/010 machinery is consumed unchanged; the spec-003 engine already threads all prior-layer answers via
  the `init_many` accumulator (verified), so cross-module answer forwarding needs no new engine code.
- The 008b authoring/fan-out pipeline (`just new-module`, `check_modules.py`, `cog.toml`, `catalog-sources.toml`) is the
  sanctioned way to create, lint, and release every module.
- `mise` is available (or installable) in the environments where generated projects are scaffolded; requiring the tool at
  scaffold time is acceptable because clerk is focused on new-project setup.
- Spec 007 is reopened by this spec (apm fold-in); its apm-specific FRs migrate to `clerk-mod-agentic`.
- Every module was already adversarially grilled for opinionation before authoring (the working method above); this spec
  encodes those verdicts rather than re-deriving them.
