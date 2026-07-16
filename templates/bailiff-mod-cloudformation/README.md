# bailiff-mod-cloudformation

CloudFormation / SAM infrastructure overlay for bailiff (spec 011, `iac.md` contract).

## What this module does

Scaffolds a CloudFormation (or AWS SAM) project under `placement_dir` (default: `infrastructure`):

- **SEED-ONCE** `template.yaml` — complete skeleton with `AWSTemplateFormatVersion`, `Description`, `Parameters(Environment)`, a `Resources` placeholder, and empty `Outputs`. SAM mode adds `Transform: AWS::Serverless-2016-10-31` and commented `Globals`.
- **SEED-ONCE** `parameters/<env>.json` — one parameter file per `environment_names` entry (default: `dev`, `prod`), seeded with the `Environment` parameter value.
- **MANAGED** `.cfnlintrc.yaml` — cfn-lint config; `ignore_checks` comes from `cfnlint_ignore_rules`. Byte-identical on `bailiff reproduce`.

## Questions

| Question | Type | Default | Description |
|---|---|---|---|
| `mode` | str choice | `raw` | `raw` = plain CFN; `sam` = adds SAM Transform |
| `stack_description` | str | `""` | Description line in `template.yaml` |
| `environment_names` | yaml list | `[dev, prod]` | Per-env parameter files to seed |
| `cfnlint_version` | str | `""` | cfn-lint version pin (empty = no pin) |
| `cfnlint_ignore_rules` | yaml list | `[]` | cfn-lint rule IDs to suppress |
| `aws_validate` | bool | `false` | Run `aws cloudformation validate-template` at init |
| `placement_dir` | str | `infrastructure` | Project-root-relative directory for CFN artifacts |

## Design notes

- **YAML only** — JSON CloudFormation is not supported (dead format).
- **No hardcoded region/account/stack-name** — use AWS pseudo-parameters (`AWS::Region`, `AWS::AccountId`, `AWS::StackName`).
- **No `sam init`** — SAM init is interactive and mixes app code; this module seeds a minimal skeleton instead.
- **No `sam deploy`** — never runs irreversible actions at scaffold.
- **cfn-lint** pinned at `1.53.0` in the pre-commit hook block; ships bundled schema, no hard network dependency.
- **cfn-guard / rain** — opt-in comments only; guard rules are org-specific and not scaffolded.

## Lifecycle

```
bailiff init --module bailiff-mod-cloudformation
```

On first run, the `aws cloudformation validate-template` task runs only when `aws_validate=true`. The parameter files are seeded with `test -f` guards so they are never overwritten by a later `bailiff reproduce`.

```
bailiff reproduce
```

`.cfnlintrc.yaml` is re-rendered config-consistently. `template.yaml` and `parameters/` files are skipped (already present).
