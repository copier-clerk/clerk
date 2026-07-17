# bailiff-mod-api

API-first project skeleton (spec 012 / FR-013): a seed-once OpenAPI 3.1
document plus a managed [spectral](https://docs.stoplight.io/docs/spectral)
lint config. No codegen, no server scaffold — the language modules own
runtime code.

## Outputs

| File | Lifecycle | Notes |
|---|---|---|
| `openapi.yaml` (repo root) | **seed-once** | `_skip_if_exists`; OpenAPI 3.1 minimal valid skeleton; project-owned after init |
| `.spectral.yaml` | **managed** | byte-identical on reproduce; `extends: spectral:oas` |
| `.mise/conf.d/bailiff-mod-api.toml` | **managed** | contributes `spectral` to the project's mise tool set |
| `.pre-commit.d/bailiff-mod-api.yaml` | **managed** | spectral-lint hook fragment; merged by `bailiff-mod-precommit` |

Root placement + 3.1 are the ledger-ratified defaults (FR-013): spectral and
editors find a root `openapi.yaml` without configuration, and since the
document is seed-once a project can move it — re-runs never clobber.

## Fragment contributions (spec 014 fragment/merge model)

| Surface | Fragment path | Merge owner |
|---|---|---|
| mise tools | `.mise/conf.d/bailiff-mod-api.toml` | mise native (drop-in) |
| pre-commit hooks | `.pre-commit.d/bailiff-mod-api.yaml` | `bailiff-mod-precommit` bundler |

## Questions

| Key | Type | Source | Notes |
|---|---|---|---|
| `project_name` | str | `_external_data.base` | OpenAPI `info.title` |
| `description` | str | `_external_data.base` | OpenAPI `info.description` |

Facts are read via `_external_data` aliases (spec 014). `bailiff-mod-base` is a hard
data-dependency and must be present in the selection.

Zero `_tasks`; reproduce needs no toolchain or network.

Edge: `depends_on: [bailiff-mod-base]`, `phase: normal`.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-api.git <destination>
```
