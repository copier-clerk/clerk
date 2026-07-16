# bailiff-mod-api

API-first project skeleton (spec 012 / FR-013): a seed-once OpenAPI 3.1
document plus a managed [spectral](https://docs.stoplight.io/docs/spectral)
lint config. No codegen, no server scaffold — the language modules own
runtime code.

## Outputs

| File | Lifecycle | Notes |
|---|---|---|
| `openapi.yaml` (repo root) | **seed-once** | `_skip_if_exists`; OpenAPI 3.1 minimal valid skeleton; project-owned after init |
| `.spectral.yaml` | **managed** | config-consistent on reproduce; `extends: spectral:oas` |

Root placement + 3.1 are the ledger-ratified defaults (FR-013): spectral and
editors find a root `openapi.yaml` without configuration, and since the
document is seed-once a project can move it — re-runs never clobber.

## Frozen-union contributions (M1 — tokens only)

| Union | Token | Single writer |
|---|---|---|
| `mise_tools` | `spectral` | `bailiff-mod-base` (`.mise.toml`) |
| `hook_blocks` | spectral-lint block | `bailiff-mod-precommit` (hook file) |

When `hook_manager=none` the hook contribution is inert (no hook file is
written by anyone — §4 threading contract).

## Questions

| Key | Type | Default | Notes |
|---|---|---|---|
| `project_name` | str | threaded from base | OpenAPI `info.title` |
| `description` | str | `""` | OpenAPI `info.description` |
| `hook_manager` | str | threaded | `none` = inert hook contribution |
| `mise_tools` / `hook_blocks` | yaml | `[]` | frozen unions (declared for threading) |

Zero `_tasks`; reproduce needs no toolchain or network.

Edge: `run_after: [bailiff-mod-base]`.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-api.git <destination>
```
