# bailiff-mod-cocogitto

Conventional-commit + [cocogitto](https://docs.cocogitto.io/) release
discipline — the same setup bailiff itself dogfoods. Renders a managed
`cog.toml` sized to the project shape; **no release action occurs at scaffold
time** (no `cog bump`, no tag, no changelog write, no network) — release
actions are the project's to run.

release-please is a ratified later **sibling** module (per-tool split under
FR-001), not an axis of this module.

## Outputs

| File | Lifecycle | Notes |
|---|---|---|
| `cog.toml` | **managed** | config-consistent on reproduce; single vs monorepo shape from `layout` |
| `.mise/conf.d/bailiff-mod-cocogitto.toml` | **managed** | contributes `cog = "latest"` to the mise conf.d drop-in |
| `.pre-commit.d/bailiff-mod-cocogitto.yaml` | **managed** | commit-msg-lint hook fragment; consumed by bailiff-mod-precommit's bundler |

## Cross-module facts read

| Source | Key | How supplied |
|---|---|---|
| `_external_data.base` (`bailiff-mod-base`) | `project_name`, `layout` | answers file — always-present hard dep (FR-006) |
| agent-fed `--data` | `monorepo_packages` | list of package paths; defaults to `[]` when moon is absent |

`bailiff-mod-base` is a hard dependency. `monorepo_packages` is agent-fed
(standing rule R13 GENERALIZED): moon is sometimes-absent (non-monorepo stacks
omit it), so the orchestrating agent passes this list via `--data` rather than
reading it from moon's answers file.

## CI

Deliberately untouched (ledger, FR-007): CI modules are the single owners of
workflow/pipeline files. A cog-driven release job is a CI-model decision, not
release-tool-module scope.

## Dependency edges

- `depends_on: [bailiff-mod-base]`
- `phase: normal`

Tasks: a single trust-gated mise preflight, init-only-guarded via the committed
`.bailiff-cocogitto-preflight` sentinel — reproduce over a committed tree never
re-shells.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-cocogitto.git <destination>
```
