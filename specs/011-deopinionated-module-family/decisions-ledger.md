# Spec 009 de-opinionation — decisions ledger (working scratch)

Branch: 009-phase-1-3-module-port. Captured live during the 2026-07-14 decision rounds.
This is the authoritative running record until folded into spec 009 + a new sub-spec.

## Module set (reconciled)

### Built (need REVISION for de-opinionation)
- clerk-mod-base — thinned (see Base below)
- clerk-mod-python — add PM/version/ruff/layout/test choices
- clerk-mod-apm — **FOLDS INTO clerk-mod-agentic** (rename/tombstone released v0.1.0 mirror)

### New / to-build
- clerk-mod-ts, clerk-mod-go, clerk-mod-rust (language overlays)
- clerk-mod-precommit, clerk-mod-quality (quality — quality stays SEPARATE per user)
- clerk-mod-justfile (tooling)
- clerk-mod-env, clerk-mod-readme, clerk-mod-stack-adr (agent-tier docs/tooling)
- clerk-mod-ci (multi-model, GitHub Actions + GitLab CI) — owns .github/workflows OR .gitlab-ci.yml
- clerk-mod-github-repo, clerk-mod-package-add (integration/monorepo)
- clerk-mod-org-policy (last; no-op until org-source-fetch exists)
- clerk-mod-agentic (NEW rollup: Claude/Codex/OpenCode/Kiro-IDE/Kiro-CLI config + MCP + native marketplace + APM install; owns .agents/ + .codex/)
- clerk-mod-iac (NEW: terraform/opentofu/pulumi/cdk/cfn/ansible; owns infrastructure/; layout-independent overlay) — GRILL+RESEARCH pending
- clerk-mod-speckit (SEPARATE; owns specs/)

### Dropped
- worktreeinclude-write (clerk-mod-worktree) — niche, deferred indefinitely

## Cross-cutting choices (ratified)
- Python PM: [uv, pdm] default uv (drop poetry, pip, pipenv). CASCADE into package-add + stack-adr (uv+pdm everywhere).
- JS PM: [bun, pnpm, npm] default bun (drop yarn).
- Hook manager: [pre-commit, lefthook, none] default pre-commit (drop husky, simple-git-hooks). Threaded cross-module like gitignore_stack; precommit module owns the contract.
- Python layout: [flat, src] default src.
- Ruff line-length default 88 (was 100); quotes [double,single] default double; rule profile [standard, strict] default standard.
- Python versions: [3.11, 3.12, 3.13, 3.14] default 3.13. (+ auto-update-via-CI meta-feature, see below)
- TS linter: [biome, eslint-prettier] default biome.
- Rust: channel [stable,beta,nightly,esp] default stable; edition [2024,2021,2018] default 2024 (drop 2015); rustfmt heuristics Max; clippy pre-push; fix --lib bug.
- **mise = DEFAULT tool/version manager** across modules (writes .mise.toml, preflight = `mise install`, agent resolves versions via mise). Reshapes every preflight.

## Testing (new axis — ratified)
- Test scaffolding: OFFER per-language test_runner, DEFAULT none/off (opt-in).
- Rust: [cargo-test, nextest] default nextest.
- Go: [go-test, gotestsum] default go-test. Python: pytest only. TS: [none, vitest-node, vitest-browser, vitest+playwright, bun-test, playwright-only] default none.
- CI auto-wires the chosen runner + coverage ON (only for languages where test_runner != none).

## Integration / docs (ratified)
- github-repo: visibility [private, public, internal] default private; public keeps hard abort-without-consent gate.
- readme: [static-skeleton, agent-draft] default AGENT-DRAFT.

## clerk-mod-base (thinned — ratified)
- ALWAYS: docs/ (+ 8 subdirs behind docs_subdirs toggle, default on), scripts/, tests/.
- minimal .github/ gated on github_host bool (issue/PR templates, CODEOWNERS, dependabot — NOT workflows).
- MOVED OUT: .agents/ + .codex/ → clerk-mod-agentic; infrastructure/ → clerk-mod-iac; .github/workflows/ → clerk-mod-ci; specs/ → clerk-mod-speckit.
- DROPPED: archive/, assets/.
- ADD questions: extra_dirs (yaml, [] freeform), branch_strategy (default squash-merge), copyright_name (default {{org}}), run_git_init (bool, default true), docs_subdirs (bool, default on), github_host (bool).
- KEEP: 13-SPDX license set default apache-2.0, single/monorepo layout, gitnr .gitignore, gh LICENSE fetch, seed-once AGENTS.md.

## clerk-mod-agentic (NEW — design done, apm folded in)
- Targets set: [claude, codex, opencode, kiro-ide, kiro-cli] (+ APM extends reach to kiro/opencode/cursor/... which have NO marketplace).
- Marketplace-native ONLY: claude (.claude-plugin/marketplace.json), codex (.agents/plugins/marketplace.json). Everything else via APM.
- APM VERIFIED (microsoft/apm targets-matrix): kiro target = .kiro/ (instructions, skills, hooks, mcp); opencode = .opencode/; also cursor/gemini/windsurf/antigravity/copilot/intellij/agent-skills.
- Features (when: toggles): mcp_config (per-target native mcp file), native_marketplace (claude/codex), install_via_apm (trust-gated uvx --from apm-cli==<ver> apm install, DEFAULT OFF), codex_config, kiro_steering.
- MCP: canonical mcp_servers injected list (type yaml) fanned per target; env as ${VAR} refs (no secret: questions). apm-cli pin 0.25.0 (was 0.24.1).
- Mixed render + trust-gated-task module (like base). Empty/none renders clean (no refusal — unlike old apm FR-002b).
- REOPENS spec 007: apm FRs migrate here; resolves OQ-007-b/f as hybrid (agentic rollup + apm folded + speckit separate).

## clerk-mod-ci (multi-model — GitHub design done+grilling; GitLab researching)
- ci_host: [github, gitlab].
- GitHub models: minimal / standard(parallel+fan-in-gate) / matrix / optimized(change-filter+cache+concurrency+status-shim) / monorepo-affected / merge-queue.
- Pure managed render, ZERO _tasks (sizes from agent-frozen --data: ci_languages + per-lang facts + ci_model; NOT from run-order threading — CI sorts before lang layers).
- Owns .github/workflows/ (github) or .gitlab-ci.yml (gitlab), only when selected. (.github/ metadata itself = base, gated on github_host.)
- GRILL SEQUENCE (per user, BOTH hosts): GitHub design → grill (in flight, wf_04a143b8) ; GitLab research (in flight) → GitLab design → **grill GitLab design** → THEN batch 6. Do NOT skip the GitLab grill.

## Batch 7 — agentic (ratified)
- Kiro: ONE `kiro` slug + `kiro_cli_agents` sub-toggle (shared .kiro/, one writer).
- Claude external plugins: INSTALL via trust-gated _task (agent-frozen plugin list → --data → task). Process-deterministic like apm/gh tasks; NOT manual. (Corrected earlier over-caution.)
- install_via_apm default OFF; APM is the install path for non-marketplace targets (kiro/opencode/cursor/...). Marketplace-native (claude/codex) can use either.
- No default agentic_targets — phase-1 agent picks based on which agent/context it runs in.
- codex agent_config_stubs (cursor/windsurf/aider) SUBSUMED into agentic_targets (APM matrix supports them); no separate stub list.

## Smaller-module (ratified batch)
- env-example: DROPPED/deferred — too opinionated, lookup can't cover the space. Not built.
- stack-adr: format [simple, adr] default simple; OPT-IN; adr_dir docs/decisions; facts agent-frozen via --data (not run-order threading); SEED-ONCE (_skip_if_exists) — initial setup only, never re-rendered (docs drift). Drop staleness/CVE agent step.
- docs_subdirs: lean core = architecture/decisions/runbooks (default on); other 5 via extra_dirs opt-in.
- package-add: use NATIVE add commands (pnpm/bun/uv/cargo/go add) as trust-gated tasks — tool writes pnpm-workspace.yaml vs package.json workspaces[] itself. clerk scaffolds new pkg dir + seed.
- Bug-fixes (not choices): rust --lib passed for lib crate; ts nuxi pinned + sst gitignore applied; quality_languages = type:yaml open list auto-pop from selected langs.

## ARCHITECTURAL SHIFT — native commands everywhere (ratified)
- Language modules SCAFFOLD via native tool commands (uv init / bun init / cargo new / go mod init) as trust-gated _tasks, NOT rendered manifests. mise guarantees the tool is present. Project is focused on NEW project setups, so requiring the tool at scaffold is acceptable.
- CONSEQUENCE: language manifests (pyproject/package.json/Cargo.toml/go.mod) become TASK-OUTPUT (process-deterministic), NOT seed-once managed renders. Reproduce re-runs the init command (like the gh LICENSE fetch) — NOT byte-identical. Acceptable under Constitution III (task side-effects process-deterministic) but a DEPARTURE from Phase-0 clerk-mod-python's rendered-seed-once pyproject. clerk-mod-python must be REVISED to this model too.
- Config files clerk owns (tsconfig, .golangci.yml, ruff config beyond what init writes, rustfmt/clippy) stay MANAGED renders where the tool doesn't own them; tool-owned manifests are task-output. Draw the line per file at build.
- Determinism note: pin tool VERSIONS via mise (.mise.toml) so init output is stable across runs; still process-deterministic not byte-identical. Flag in spec reconciliation (touches Constitution III framing + FR-005/FR-005a).

## IaC — THREE SEPARATE MODULES (ratified — different paradigms, no shared template content)
Per user's "warrants its own module" rule: Terraform, AWS CDK, CloudFormation are 3 paradigms → 3 modules. Each layout-independent overlay, placement_dir default 'infrastructure' ('.' for standalone), backend/config = generic skeleton + commented examples (NO cloud_provider/state_backend questions — user configures). Each needs its OWN grill before build.

### clerk-mod-terraform (RESEARCHED — ready to grill+build)
- tf_flavor [terraform, opentofu] default TERRAFORM (opentofu available; only binary name + S3-locking pattern differ). Versions: terraform/opentofu_version, tflint_version.
- Lifecycle: MANAGED (versions.tf, .tflint.hcl, .terraform-version, mise entries, pre-commit IaC block); SEED-ONCE (main.tf, variables.tf, outputs.tf, backend.tf, tfvars.example); TASK-OUTPUT (.terraform.lock.hcl via `tofu/terraform init` — commit, NOT gitignore).
- Native command: `terraform init` / `tofu init` (network, trust-gated task via mise). Tooling: tflint + trivy config (tfsec DEAD→trivy), terraform_fmt via antonbabenko/pre-commit-terraform → contributes to clerk-mod-precommit. NO workspaces (env-per-dir idiomatic), NO Terragrunt (future).
- Generic HCL skeleton (no cloud_provider question — user adds provider block); backend seed = commented local + S3 examples.

### clerk-mod-cdk (AWS CDK — RESEARCHED; needs grill)
- ONE module (NOT per-language). cdk_language [typescript, python, go, java, csharp] default typescript = Q7 choice driving `cdk init app --language=`. NO edge to language modules (cdk init is self-contained in placement_dir/; base→[lang||cdk] parallel).
- Pure task module: template/ renders ~nothing (answers-file + maybe README seed); ALL files come from trust-gated `cdk init` task (task-output → then seed-once/user-owned). Idempotency guard: skip if placement_dir/cdk.json exists (like base LICENSE guard).
- Questions: cdk_language, placement_dir (default infrastructure), cdk_version (2.261.0), include_cdk_nag (bool, false), include_synth_validate (bool, false), project_name threaded.
- Tasks: preflight (node + lang runtime + cdk reachable) → cdk init + pin cdk_version → OPTIONAL cdk synth validate (when include_synth_validate). NEVER cdk bootstrap/deploy (deploy-time). cdk.context.json COMMITTED (not gitignore); cdk.out/ gitignored.
- De-opinionation: env via CDK_DEFAULT_ACCOUNT/REGION env vars or no env key (never hardcode account/region). No default VPC/Lambda/constructs — pure scaffold. cdk_version pinned; aws-cdk-lib 2.261.0.

### clerk-mod-cloudformation (RESEARCHED; needs grill)
- ONE module, mode [raw, sam] default raw (SAM = raw + Transform header + Globals + sam PATH check; 90% overlap, trivial {% if %} gate — NOT a split). YAML only (JSON CFN dead).
- RENDER-oriented (unlike CDK's task): template.yaml (SEED-ONCE), parameters/<env>.json per environment_names (SEED-ONCE, default [dev,prod]), .cfnlintrc.yaml (MANAGED). No `sam init` (interactive, mixes app code).
- Questions: mode, stack_description, environment_names (yaml, [dev,prod]), cfnlint_version (str, "" = no pin), cfnlint_ignore_rules (yaml, []), aws_validate (bool, false).
- Tooling: cfn-lint 1.53.0 (pre-commit rev + local task, ships bundled schema so no hard network dep), cfn-guard 3.2.0 (opt-in, comment only), rain (opt-in mention). Don't scaffold guard rules (org-specific).
- Trust-gated OPT-IN: aws cloudformation validate-template (network + creds) via aws_validate bool. Don't-hardcode: region/account/stackname via AWS pseudo-params (AWS::Region etc).
- clerk-model fit: STRONG (declarative YAML render = the whole product; seed-once like pyproject; no new clerk code).

## clerk-mod-ci (GRILLED — revisions to apply; GitLab design done, needs its own grill)
- GRILL VERDICT: revise 9 things. Menu collapses 6→5: DROP 'matrix' as a model (it's just strategy.matrix on 'standard' when ci_os_matrix>1 / ci_matrix_versions non-empty). Keep: minimal / standard / optimized / monorepo-affected / merge-queue.
- Default ci_model = **minimal** (not standard) — static default fires for standalone/solo; agent overrides via --data for team/multi-lang.
- ci_required_gate: suppress gate job entirely when model=minimal (footgun: self-referential gate).
- 'optimized' = standard topology + ci_paths_filter + ci_cache + ci_concurrency_cancel; status-shim gate REQUIRED when paths_filter on. Make ci_cache / ci_concurrency_cancel independently settable on ANY model (orthogonal toggles).
- Agent-selection heuristic FIXES: merge-queue requires explicit confirmed org/GHEC signal (NOT just high PR volume — else solo repo stalls); solo+single-layout+≤2 langs+low-PR → minimal; team OR moderate+PR → standard.
- Authoring footguns to avoid: (1) Jinja loop for the gate's per-language checks must be OUTSIDE {% raw %} fences; (2) monorepo-affected zero-language guard must emit when monorepo_tool != none even if ci_languages empty.
- upload/download-artifact must be SAME major (design had v7/v8 mismatch). Reconcile all action pins.
- DROP ci_harden_runner (new supply-chain capability, FR-011 fail). ci_oidc_provider keep as default:none (boundary but defensible; adds id-token:write + skeleton).
- Pure render, ZERO _tasks; sizes from agent-frozen --data (ci_languages + per-lang facts + ci_model). CI sorts before lang layers so CANNOT read run-order answers (FACT A/B).
- ci_host [github, gitlab]. GitLab models researched (all 6 mapped): stages/needs/rules; standard uses implicit stage-gate (no explicit gate job); optimized uses rules:changes+compare_to+cache:policy:pull+workflow:auto_cancel; monorepo=parent-child pipelines (strategy:depend) or inline rules:changes; merge-queue=MERGE TRAINS (Premium/Ultimate ONLY — Free fallback merge-when-pipeline-succeeds). GitLab 'Pipelines must succeed' is pipeline-level → skipped-pipeline counts as success (BETTER than GitHub; no shim needed). Always include duplicate-pipeline guard in workflow:rules.
- GITLAB GRILL DONE. Verdict: SAME 5-model menu both hosts, host-specific RENDER, one gating nuance. ci_host does NOT change which models are offered — only how they render.
- GitLab render fixes (from grill): (1) minimal = ONE job multi-command script (research wrongly split into 2 needs-chained jobs); (2) any needs: on a change-gated job MUST be {job:x, optional:true} else PIPELINE-CREATION ERROR (fires on source-only changes); (3) standard emits NO gate job + NO deploy job + NO dead 'gate' stage (stage-order + 'Pipelines must succeed' IS the gate; manual deploy job BLOCKS merge — drop it, it's also an FR-011 deploy-scope violation); (4) PIN images (no :latest/:lts — thread frozen <lang>_image; Constitution III); (5) interruptible + workflow:auto_cancel emitted as ONE coupled unit (driven by ci_concurrency_cancel toggle) or neither; (6) compare_to = literal refs/heads/{{ default_branch }} (NOT hardcoded main, NOT a CI var — GitLab doesn't expand vars there); MR arm omits compare_to; (7) canonical workflow:rules duplicate-guard across ALL models incl merge-queue; (8) cache: add fallback_keys, thread lockfile path, warm/install job for parallel models; (9) monorepo child-pipeline needs a FROZEN monorepo_packages list answer else inline-only; (10) bun.lockb→bun.lock (Bun 1.2 text default), don't `cargo install nextest` per-run (use image/cache), no golangci :latest.
- free_tier_handling: add gitlab_tier [free, premium_ultimate] default free (agent-frozen; render can't detect tier). merge-queue+free → render merge-when-pipeline-succeeds fallback + header warning (NOT hard error; merge-train YAML silently no-ops on free). Agent must have confirmed premium signal before selecting merge-queue (mirrors GitHub org/GHEC requirement).
- OIDC cross-host: ci_oidc_provider renders id_tokens: on GitLab vs id-token:write on GitHub — OR scope GitHub-only. Decide. ci_harden_runner GitHub-only (no GitLab equiv) — and grill said DROP it anyway.

## Batch 6 — CI (RATIFIED, both hosts grilled)
- Menu: 5 models — minimal / standard / optimized / monorepo-affected / merge-queue. 'matrix' DROPPED (→ ci_os_matrix/ci_matrix_versions toggle). Same menu both hosts (ci_host [github, gitlab]); host-specific render only.
- Default ci_model = minimal = ONE job, sequential steps, NO fan-in gate, NO parallel jobs. (Multi-crate Rust = one `cargo test --workspace` job, NOT per-crate jobs — within-language parallelism is Cargo's, not CI's. Per-crate jobs = standard/monorepo model, explicit upgrade.)
- Toggles (all offered, independent of model): ci_cache (default ON), ci_concurrency_cancel (default ON; GH cancel-in-progress / GL workflow:auto_cancel+interruptible coupled unit), ci_os_matrix + ci_matrix_versions (default single = no matrix), ci_oidc_provider (default none; GH id-token:write / GL id_tokens:). ci_harden_runner DROPPED (grill: new supply-chain capability, FR-011 fail).
- gitlab_tier [free, premium_ultimate] default free (agent-frozen). merge-queue+free → render merge-when-pipeline-succeeds fallback + header warning (no hard error). Agent needs confirmed premium (GitLab) / org-GHEC (GitHub) signal before selecting merge-queue.
- Apply all GitHub-grill + GitLab-grill render fixes (see clerk-mod-ci sections above) at build: gate suppressed on minimal; optional:true on needs-to-change-gated-jobs; pinned images; coupled interruptible; literal compare_to; canonical workflow:rules; fallback_keys; zero-lang guard emits when monorepo_tool!=none.

## Meta-features (separate scope, not modules)
- Version auto-update via CI: scheduled job bumping choices:/defaults lists (python/go/rust/node/action pins). Clerk-repo tooling. Flag as its own small spec item.

## Spec reconciliation TODO
- Spec 009: FR-011 relaxed, FR-014/FR-015 added, roadmap 2.2.0 — DONE (commit 4c570b0).
- Spec 007: REOPEN — apm folds into clerk-mod-agentic; amend Q1/OQ-007-b/f/D-007-4; apm FRs migrate.
- New sub-spec (009-generic or 011) for the de-opinionation + new modules (iac, agentic, ci-multi-model) — PENDING.

## Still-open decision batches
- Batch 6: CI models (after CI grill + GitLab research) — default model, required-check strategy, which models ship, orthogonal toggles, ci_host default.
- Batch 7: agentic module — Kiro one-slug vs two, Claude external-plugin activation (doc vs opt-in task), MCP-as-feature confirm, default targets, install_via_apm default.
- clerk-mod-iac: full grill+research (tools, state backend, layout, placement).
- Remaining smaller: env framework lists, stack-adr format/dir, package-add pnpm-workspace fix, codex agent_config_stubs, quality open-list.
