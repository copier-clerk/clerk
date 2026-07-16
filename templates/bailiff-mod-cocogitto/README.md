# bailiff-mod-cocogitto

Conventional-commit + [cocogitto](https://docs.cocogitto.io/) release
discipline (spec 012 / FR-007) — the same setup bailiff itself dogfoods.
Renders a managed `cog.toml` sized to the project shape; **no release action
occurs at scaffold time** (no `cog bump`, no tag, no changelog write, no
network) — release actions are the project's to run.

release-please is a ratified later **sibling** module (per-tool split under
FR-001), not an axis of this module.

## Outputs

| File | Lifecycle | Notes |
|---|---|---|
| `cog.toml` | **managed** | config-consistent on reproduce; single vs monorepo shape from `layout` |

## Frozen-union contributions (M1 — tokens only)

| Union | Token | Single writer |
|---|---|---|
| `mise_tools` | `cog` | `bailiff-mod-base` (`.mise.toml`) |
| `hook_blocks` | commit-msg-lint block | `bailiff-mod-precommit` (hook file) |

This module never writes `.mise.toml` or the hook config file itself.

## CI

Deliberately untouched (ledger, FR-007): CI modules are the single owners of
workflow/pipeline files. A cog-driven release job is a CI-model decision, not
release-tool-module scope.

## Questions

| Key | Type | Default | Notes |
|---|---|---|---|
| `project_name` | str | threaded from base | header comment |
| `layout` | str | threaded from base | `single` or `monorepo` — sizes cog.toml |
| `monorepo_packages` | yaml | `[]` | frozen fact; monorepo `[packages]` entries |
| `mise_tools` / `hook_blocks` | yaml | `[]` | frozen unions (declared for threading) |

Tasks: a single trust-gated mise preflight, init-only-guarded via the committed
`.bailiff-cocogitto-preflight` sentinel — reproduce over a committed tree never
re-shells.

Edge: `run_after: [bailiff-mod-base]`.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-cocogitto.git <destination>
```
