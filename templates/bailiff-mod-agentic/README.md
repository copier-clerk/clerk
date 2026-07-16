# bailiff-mod-agentic

Agentic-config rollup (spec 011). One copier template that wires agentic tool
configuration into a generated project, folding in the APM install path from
the superseded `bailiff-mod-apm`.

Supports four targets — **claude**, **codex**, **opencode**, **kiro** — on
deliberately disjoint paths so any combination can be selected without collision.
Empty selection (no targets) is a clean no-op.

Requires **bailiff-mod-base** (declared via `depends_on`). Reads `project_name`
from the base answers file via `_external_data.base` (spec 014 / FR-004).

## What it produces

| Output | Target | Lifecycle | Condition |
|--------|--------|-----------|-----------|
| `AGENTIC.md` | all | **managed** | always |
| `.claude/settings.json` | claude | **managed** | `claude` selected |
| `.mcp.json` | claude | **managed** | `claude` + `mcp_config=true` |
| `.codex/config.toml` | codex | **managed** | `codex` selected |
| `.agents/plugins/marketplace.json` | codex | **managed** | `codex` + `native_marketplace=true` |
| `opencode.json` | opencode | **managed** | `opencode` selected |
| `.kiro/settings/mcp.json` | kiro | **managed** | `kiro` + `mcp_config=true` |
| `.kiro/steering/project.md` | kiro | **seed-once** | `kiro` selected |
| `.kiro/agents/agents.json` | kiro | **managed** | `kiro` + `kiro_cli_agents=true` |
| `apm.lock.yaml` | — | **task-output** | `install_via_apm=true` + non-empty `apm_packages` |

## Target selection

`agentic_targets` is a **multiselect with no default**. The phase-1 agent picks
targets by context and injects via `--data agentic_targets=[...]`. Empty list =
clean no-op (only `.copier-answers.yml` written, no refusal).

## APM install path (R2)

`install_via_apm=true` + `apm_packages==[]` is **refused** with a validator
message — that combination is a phase-1 mistake. The module-level empty
selection (no targets) is a different, legitimate no-op.

## MCP server configuration

`mcp_servers` is a canonical list injected via `--data`. Env values MUST use
`${VAR}` refs — never literal secrets (Constitution VI / FR-005).

## Prerequisites

Trust-gated `_tasks`:

- **mise** — <https://mise.jdx.dev> (preflight, always)
- **uv / uvx** — <https://docs.astral.sh/uv/getting-started/installation/> (when `install_via_apm=true`)

## Usage

```sh
uvx bailiff init --run-spec <run-spec.(json|yml)>
```

Copier-only (single layer):

```sh
copier copy --trust \
  --data 'agentic_targets=["claude","codex"]' \
  https://github.com/bailiff-io/bailiff-mod-agentic.git <destination>
```
