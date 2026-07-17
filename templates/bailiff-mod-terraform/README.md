# bailiff-mod-terraform

Terraform / OpenTofu **IaC overlay** — generic infrastructure skeleton that
works standalone or `depends_on`
[`bailiff-mod-base`](https://github.com/bailiff-io/bailiff-mod-base).
Does NOT ask for `cloud_provider` or `state_backend`; users
configure those via commented examples in `backend.tf`.

## Flavors

| `tf_flavor` | Binary | Lock-file pattern |
|---|---|---|
| `terraform` (default) | `terraform` | DynamoDB comment in `backend.tf` |
| `opentofu` | `tofu` | `use_lockfile=true` comment in `backend.tf` |

## What it produces

| Output | Lifecycle | Notes |
|---|---|---|
| `<placement_dir>/versions.tf` | **MANAGED** | `required_version` + generic provider hint |
| `<placement_dir>/.tflint.hcl` | **MANAGED** | terraform ruleset; cloud rulesets commented |
| `<placement_dir>/.terraform-version` | **MANAGED** | Used by tfenv and compatible managers |
| `<placement_dir>/main.tf` | **SEED-ONCE** | Starter; add provider config + resources |
| `<placement_dir>/variables.tf` | **SEED-ONCE** | Declare input variables here |
| `<placement_dir>/outputs.tf` | **SEED-ONCE** | Declare outputs here |
| `<placement_dir>/backend.tf` | **SEED-ONCE** | Commented local + S3 examples; flavor-conditional |
| `<placement_dir>/terraform.tfvars.example` | **SEED-ONCE** | Copy to `terraform.tfvars`, fill in values |
| `<placement_dir>/.terraform.lock.hcl` | **TASK-OUTPUT** | Written by `terraform/tofu init`; COMMIT this file |
| `.mise/conf.d/bailiff-mod-terraform.toml` | **MANAGED** | IaC binary + tflint pins (mise drop-in) |
| `.pre-commit.d/bailiff-mod-terraform.yaml` | **MANAGED** | antonbabenko/pre-commit-terraform hook fragment |
| `.gitignore.d/bailiff-mod-terraform` | **MANAGED** | Terraform gitignore fragment |

`.terraform/` is gitignored via the `.gitignore.d/bailiff-mod-terraform` fragment (folded into
`.gitignore` by `bailiff-mod-base`'s `_post_task`).
`.terraform.lock.hcl` is **NOT** gitignored — commit it for reproducible provider pins.

## Questions

| Key | Default | Notes |
|---|---|---|
| `tf_flavor` | `terraform` | `terraform` or `opentofu` |
| `terraform_version` | `1.12.2` | Only shown when `tf_flavor=terraform` |
| `opentofu_version` | `1.10.0` | Only shown when `tf_flavor=opentofu` |
| `tflint_version` | `0.57.0` | Pinned in `.mise/conf.d/` drop-in |
| `pre_commit_terraform_rev` | `""` | Rev for antonbabenko/pre-commit-terraform hook |
| `placement_dir` | `infrastructure` | Use `.` for standalone IaC repo |

Facts read from producers via `_external_data` (spec 014 `_facts.md`):

| Fact | Producer | Alias |
|---|---|---|
| `project_name` | `bailiff-mod-base` | `base` |

## Ordering

- `_bailiff_phase: normal`
- `depends_on: [bailiff-mod-base]` (hard data-dependency via `_external_data`)
- Standalone use without base is not supported when `project_name` is needed; copier renders an empty
  string and bailiff produces a loud `OrderingError` when the producer is absent.

## Fragment model (spec 014)

- **mise**: renders `.mise/conf.d/bailiff-mod-terraform.toml` with own tools only; mise merges all
  conf.d entries at runtime — no `.mise.toml` written by this module.
- **pre-commit**: renders `.pre-commit.d/bailiff-mod-terraform.yaml` unconditionally (own block
  only); `bailiff-mod-precommit`'s bundler merges all fragments — inert when precommit is absent.
- **gitignore**: renders `.gitignore.d/bailiff-mod-terraform`; `bailiff-mod-base`'s concat
  `_post_task` folds fragments into `.gitignore`.

## Tooling

- **tflint** — HCL linter; pre-commit hook via `antonbabenko/pre-commit-terraform`
- **trivy** — security scanner (tfsec is DEAD); pre-commit hook via same
- No workspaces (env-per-directory is idiomatic); no Terragrunt (future module)

## Prerequisites (FR-007b)

The template runs trust-gated `_tasks`, so the source must be trusted before it renders.

- **mise** — <https://mise.jdx.dev>
- **terraform** or **tofu** (installed via mise)

## Usage

Prefer bailiff (multi-layer):

```sh
uvx bailiff init --run-spec <run-spec with [bailiff-mod-terraform]>
```

Copier-only (standalone):

```sh
copier copy --trust https://github.com/bailiff-io/bailiff-mod-terraform.git <destination>
```
