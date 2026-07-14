# Contract — IaC family: clerk-mod-terraform / -cdk / -cloudformation (NEW)

Three SEPARATE modules (different paradigms, no shared template content). Each a
layout-independent overlay: `placement_dir` default `infrastructure` (`.` for standalone IaC repo);
`run_after: [clerk-mod-base]` optional (works standalone). References [_cross-cutting.md](./_cross-cutting.md).
Generic skeletons — do NOT ask cloud_provider/state_backend (user configures via pseudo-params/comments).

## clerk-mod-terraform
- **Questions**: `tf_flavor [terraform, opentofu]=terraform` (opentofu available); `terraform_version`/`opentofu_version`; `tflint_version`; `placement_dir=infrastructure`.
- **Lifecycle**: MANAGED — `versions.tf` (required_version + generic provider block hint), `.tflint.hcl` (terraform ruleset only; cloud rulesets commented), `.terraform-version`, `.mise.toml` [tools] (opentofu/terraform + tflint), the pre-commit IaC hooks block (contributed to clerk-mod-precommit). SEED-ONCE — `main.tf`, `variables.tf`, `outputs.tf`, `backend.tf` (commented local + S3 examples; OpenTofu `use_lockfile=true` vs Terraform `dynamodb_table` conditional), `terraform.tfvars.example`. TASK-OUTPUT — `.terraform.lock.hcl` (via init; COMMIT it, do NOT gitignore; `.terraform/` gitignored).
- **Task**: preflight (mise + tofu/terraform) → trust-gated `terraform init` / `tofu init` (network, provider download). NEVER apply. Tooling: tflint + trivy (tfsec is DEAD → trivy) via antonbabenko/pre-commit-terraform. NO workspaces (env-per-dir idiomatic), NO Terragrunt (future module).

## clerk-mod-cdk (AWS CDK)
- **Questions**: `cdk_language [typescript, python, go, java, csharp]=typescript`; `placement_dir=infrastructure`; `cdk_version` (2.261.0); `include_cdk_nag` (bool, false); `include_synth_validate` (bool, false); threaded project_name. NO edge to language modules (cdk init self-contained in placement_dir).
- **Lifecycle**: pure TASK module — `template/` renders ~nothing (answers-file + optional README seed); ALL CDK files come from `cdk init` (task-output → then seed-once/user-owned). `cdk.context.json` COMMITTED (not gitignore); `cdk.out/` gitignored.
- **Tasks**: preflight (mise + node + language runtime conditional on cdk_language + cdk reachable) → `cdk init app --language=<cdk_language>` (idempotency guard: skip if placement_dir/cdk.json exists) + pin cdk_version → OPTIONAL `cdk synth` validate (when include_synth_validate; credential-free for empty stack). NEVER `cdk bootstrap`/`deploy`. cdk-nag import spliced when include_cdk_nag. De-opinionation: env via CDK_DEFAULT_ACCOUNT/REGION or no env key — never hardcode account/region; no default VPC/Lambda.

## clerk-mod-cloudformation
- **Questions**: `mode [raw, sam]=raw`; `stack_description`; `environment_names` (yaml, [dev, prod]); `cfnlint_version` (str, "" = no pin); `cfnlint_ignore_rules` (yaml, []); `aws_validate` (bool, false); `placement_dir=infrastructure`.
- **Lifecycle**: RENDER-oriented (CFN is declarative YAML). SEED-ONCE — `template.yaml` (AWSTemplateFormatVersion + Description + Parameters(Environment) + Resources placeholder + Outputs; SAM mode adds Transform: AWS::Serverless-2016-10-31 + commented Globals via `{% if mode=='sam' %}`), `parameters/<env>.json` per environment_names. MANAGED — `.cfnlintrc.yaml` (ignore_checks from cfnlint_ignore_rules; version pin as pre-commit rev). YAML only (JSON CFN dead). No `sam init` (interactive, mixes app code).
- **Tasks**: OPT-IN trust-gated `aws cloudformation validate-template` (network + creds) when `aws_validate`. cfn-lint 1.53.0 (pre-commit + local; ships bundled schema, no hard network dep). cfn-guard 3.2.0 / rain = opt-in comments only (don't scaffold guard rules — org-specific). Don't-hardcode region/account/stackname → AWS pseudo-params (AWS::Region etc.).

## Tests (each)
terraform: init `tf_flavor=terraform` → HCL skeleton, .tflint.hcl managed, main/backend seed-once, init task stubbed → .terraform.lock.hcl present; opentofu flavor swaps binary + backend pattern. cdk: `cdk_language=python` → cdk init task stubbed produces marker in placement_dir, never bootstrap/deploy, cdk.context.json committed. cloudformation: raw vs sam template render (Transform present only in sam), per-env param files, .cfnlintrc managed, aws_validate opt-in stubbed. All reproduce: managed byte-identical, task-output present, seed-once preserved. No secret questions.
