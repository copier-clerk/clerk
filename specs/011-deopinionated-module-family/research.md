# Research — spec 011 (de-opinionated module family)

All Phase-0 unknowns for spec 011 were resolved during the 2026-07-14 decision session by
adversarial grilling + live-doc research workflows. This file consolidates the decisions; the
authoritative source is the ledger (`$CLAUDE_JOB_DIR/tmp/009-deopinionation-decisions.md`).
There are **no open NEEDS CLARIFICATION** items.

## Decision log (Decision / Rationale / Alternatives)

### R1 — Tool/version management: mise
- **Decision**: `mise` is the default tool/version manager across modules; `.mise.toml` pins tools+versions; preflight = `mise install`.
- **Rationale**: solves "is every tool present at the right version" generically across a multi-language project; makes native-command output deterministic via pinning; lets the agent resolve available versions.
- **Alternatives**: per-tool `command -v` preflight (leaves multi-tool install unsolved); asdf/tool-specific version files (mise supersedes, reads them anyway).

### R2 — Scaffolding: native tool commands
- **Decision**: scaffold via `uv init`/`bun init`/`cargo new`/`go mod init`/`cdk init` as trust-gated tasks; manifests are process-deterministic task-output; deps added via native `add`.
- **Rationale**: authentic idiomatic output owned by the tool author; far less Jinja branching for de-opinionation; correctness (e.g. pnpm workspace format) is the tool's job. bailiff targets new-project setup so tool presence at scaffold is acceptable.
- **Alternatives**: render manifests byte-identically (Phase-0 model — reimplements each PM's format, drifts, fights de-opinionation); native-init-then-freeze-bytes (goes stale). Recorded in ADR-0007. Requires the Constitution III amendment (FR-019).

### R3 — Cross-cutting choice axes (de-opinionation)
- **Decision**: shared keys/choices with sane defaults, dead options dropped — Python PM `[uv,pdm]=uv`; JS PM `[bun,pnpm,npm]=bun`; hook manager `[pre-commit,lefthook,none]=pre-commit`; Python layout `[flat,src]=src`; TS linter `[biome,eslint-prettier]=biome`; ruff line-length 88 / quotes double / profile standard; version lists finite with modern defaults.
- **Rationale**: FR-014 de-opinionation; consistency lets multi-layer selections read coherently.
- **Alternatives**: keep upstream single opinions (rejected — the whole point of 011); offer dead options like pip/yarn/jest/husky (rejected — noise).

### R4 — Agentic module boundary (resolves spec 007 OQ-007-b/f)
- **Decision**: one `bailiff-mod-agentic` rollup for coding-agent config (Claude/Codex/OpenCode/Kiro) + MCP + native marketplace + APM install folded in; `bailiff-mod-speckit` stays separate; apm module retired.
- **Rationale**: agentic config is one cohesive concern; matches the "rolls up unless large enough" rule; apm is *another install mechanism* for the same job. Verified against microsoft/apm targets-matrix: APM installs to kiro/opencode/cursor/etc. (which have NO marketplace); marketplace-native only for claude/codex.
- **Alternatives**: keep apm separate (re-splits the install-mechanism concern; rejected by maintainer); separate per-target modules (fragmentation).

### R5 — Kiro modeling
- **Decision**: one `kiro` slug + `kiro_cli_agents` sub-toggle (IDE + CLI share `.kiro/`).
- **Rationale**: shared config surface; one writer avoids collision; simpler selection.
- **Alternatives**: two slugs kiro-ide/kiro-cli (double-write risk on shared `.kiro/`; a distinction most users don't make).

### R6 — CI: multi-model, two hosts
- **Decision**: 5 models `[minimal,standard,optimized,monorepo-affected,merge-queue]` default `minimal`; matrix is a toggle not a model; `ci_host [github,gitlab]` same menu, host-specific render; pure managed render sized from agent-frozen `--data`. `gitlab_tier` governs merge-queue fallback.
- **Rationale**: grilled on both hosts. minimal=one job (the true minimal); standard/optimized differ by gate + change-filtering; matrix duplicated a model for zero gain. GitLab: pipeline-level "Pipelines must succeed" is the gate (no status-shim); merge-trains Premium-only.
- **Alternatives**: 6 models with matrix (split decision surface); default standard (over-engineered for solo standalone); ci_harden_runner (new supply-chain capability — dropped, FR-011).

### R7 — IaC: three separate modules
- **Decision**: `bailiff-mod-terraform` (`tf_flavor [terraform,opentofu]=terraform`), `bailiff-mod-cdk` (AWS CDK, `cdk_language` choice), `bailiff-mod-cloudformation` (`mode [raw,sam]=raw`). Pulumi/CDKTF/Ansible out of scope.
- **Rationale**: three different paradigms sharing no template content — separate modules per the "warrants its own module" rule. Terraform+OpenTofu share HCL → one module with a flavor choice. CDK is imperative code; CFN is declarative YAML.
- **Alternatives**: one bailiff-mod-iac branching all paradigms (conditional explosion); include Pulumi (diverges on every axis — future module).

### R8 — Thin base
- **Decision**: base always-on = `docs/` (+ lean `docs_subdirs`: architecture/decisions/runbooks) + `scripts/` + `tests/` + minimal `.github/` (gated on `github_host`). Move out `.agents/`+`.codex/`→agentic, `infrastructure/`→IaC, `.github/workflows/`→ci, `specs/`→speckit. Drop archive/assets. Add extra_dirs/branch_strategy/copyright_name/run_git_init.
- **Rationale**: base is always-on; its over-opinionation propagates everywhere. Each concern belongs to its owning module.
- **Alternatives**: keep all dirs always-on (over-opinionated); a giant toggle set (extra_dirs + per-group toggles is enough).

### R9 — Reproduce-model reconciliation (FR-019)
- **Decision**: amend Constitution III → v2.3.0 + write ADR-0007; gate all 011 releases on it landing.
- **Rationale**: native-command manifests are process-deterministic, softening III's byte-identical form for those files; III already carved out task side-effects, so this is a clarifying MINOR amendment.
- **Alternatives**: don't formalize (leaves constitution/behavior gap); keep byte-identical renders (reverses R2).

## Cross-cutting facts consumed unchanged (no research needed)
- spec-003 `init_many` threads all prior-layer answers via its accumulator (`data = {**accumulated, **layer_answers}` then `_merge_layer_answers`) — verified at `src/bailiff/runner.py:307–352`; cross-module answer forwarding needs no new engine code.
- CI/stack-adr sort before language layers (alphabetical basename tie-break, ordering.md) → they cannot read run-order answers → must consume agent-frozen `--data` facts (FR-010).
- 008b pipeline (`just new-module`, `check_modules.py`, cog.toml, catalog-sources.toml) is the authoring/lint/fan-out surface; each new module's mirror is pre-created by hand (App token can't create org repos).

## Current tool versions (from live-doc research, mid-2026 — pin via mise / bump at authoring)
- OpenTofu 1.12.0 · Terraform (BSL) · tflint 0.63.1 · trivy (replaces tfsec) · aws-cdk-lib/CLI 2.261.0 · cfn-lint 1.53.0 · cfn-guard 3.2.0 · apm-cli 0.25.0.
- CI action majors (github): checkout@v7, setup-uv@v8, setup-python@v6, setup-node@v6, pnpm/action-setup@v6, setup-bun@v2, setup-go@v6, golangci-lint-action@v9, rust-toolchain@stable, rust-cache@v2, upload/download-artifact must share major. (Reconcile the design's v7/v8 artifact mismatch — grill finding.)
- GitLab: workflow:auto_cancel requires 16.8+; CI Components 17.0+; merge trains Premium/Ultimate only.
