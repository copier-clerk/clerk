# clerk-mod-terraform

Terraform / OpenTofu **IaC overlay** — generic infrastructure skeleton that
works standalone or `run_after` [`clerk-mod-base`](https://github.com/copier-clerk/clerk-mod-base)
(spec 011). Does NOT ask for `cloud_provider` or `state_backend`; users
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

`.terraform/` is gitignored (contributed to the `gitignore_stack` union).
`.terraform.lock.hcl` is **NOT** gitignored — commit it for reproducible provider pins.

## Questions

| Key | Default | Notes |
|---|---|---|
| `tf_flavor` | `terraform` | `terraform` or `opentofu` |
| `terraform_version` | `1.12.2` | Only shown when `tf_flavor=terraform` |
| `opentofu_version` | `1.10.0` | Only shown when `tf_flavor=opentofu` |
| `tflint_version` | `0.57.0` | Pinned via mise_tools union |
| `placement_dir` | `infrastructure` | Use `.` for standalone IaC repo |

## Ordering & threading

- `run_after: [clerk-mod-base]` (when:false hidden answer) — base applies first
  when used together; standalone use is fully supported.
- `project_name` is threaded from base via `default: "{{ project_name }}"` (FR-010).
- `mise_tools` and `hook_blocks` are **agent-frozen union answers** injected by
  the phase-1 agent via `--data`. This module contributes `opentofu` or `terraform`
  + `tflint` tokens; `clerk-mod-base` is the single writer of `.mise.toml` and
  `clerk-mod-precommit` is the single writer of the hook config file (M1).

## Tooling

- **tflint** — HCL linter; pre-commit hook via `antonbabenko/pre-commit-terraform`
- **trivy** — security scanner (tfsec is DEAD); pre-commit hook via same
- No workspaces (env-per-directory is idiomatic); no Terragrunt (future module)

## Prerequisites (FR-007b)

The template runs trust-gated `_tasks`, so the source must be trusted before it renders.

- **mise** — <https://mise.jdx.dev>
- **terraform** or **tofu** (installed via mise)

## Usage

Prefer clerk (multi-layer):

```sh
uv run scripts/clerk.py init --run-spec <run-spec with [clerk-mod-terraform]>
```

Copier-only (standalone):

```sh
copier copy --trust https://github.com/copier-clerk/clerk-mod-terraform.git <destination>
```
