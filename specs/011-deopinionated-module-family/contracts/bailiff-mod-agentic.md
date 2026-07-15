# Contract — bailiff-mod-agentic (NEW; folds in bailiff-mod-apm)

Agentic-config rollup. References [_cross-cutting.md](./_cross-cutting.md). Reopens spec 007
(apm FRs migrate here; empty-set refusal DROPPED). Supersedes `bailiff-mod-apm` (mirror tombstoned
in the confirmed publish batch — FR-020).

## Questions
| key | type | choices / default | notes |
|---|---|---|---|
| agentic_targets | str multiselect | [claude, codex, opencode, kiro] / [] | NO default — phase-1 agent picks by context |
| kiro_cli_agents | bool | false | Kiro is one slug; on → CLI-only `.kiro/agents/*.json` |
| mcp_config | bool | false | render per-target native MCP file |
| native_marketplace | bool | false | claude/codex marketplace manifests + plugin install |
| install_via_apm | bool | false | APM install (path for non-marketplace targets) |
| mcp_servers | yaml | [] | canonical injected list, fanned per target; env as ${VAR} refs |
| agentic_plugins | yaml | [] | {marketplace:{name,owner_repo}, plugins:[…], category?} |
| apm_packages | yaml | [] | APM locators (when install_via_apm) — see empty-set rule below |
| apm_cli_version | str | 0.25.0 | pinned uvx --from apm-cli==<ver> |
| project_name / today | str | "{{ project_name }}" / "" | threaded / injected |
| depends_on/run_after/run_before | yaml when:false | [] | ordering declared by consumers |

## Outputs / lifecycle (per selected target — disjoint paths, no collision)
- **claude**: `.claude/settings.json` (managed: extraKnownMarketplaces + enabledPlugins when native_marketplace; enableAllProjectMcpServers when mcp_config), `.mcp.json` (managed, when mcp_config). Plugin activation for external plugins = trust-gated task (see below).
- **codex**: `.codex/config.toml` (managed: [mcp_servers], [plugins] when native_marketplace), `.agents/plugins/marketplace.json` (managed, when native_marketplace).
- **opencode**: `opencode.json` (managed: plugin array + mcp) — npm plugins self-install at agent runtime; pin `name@version`.
- **kiro** (one slug, shared `.kiro/`, OR-guard so it renders once): `.kiro/settings/mcp.json` (managed, when mcp_config), `.kiro/steering/*.md` (seed-once) ; when `kiro_cli_agents`: `.kiro/agents/*.json` (managed). Kiro has NO marketplace → packages via APM.
- **AGENTIC.md** (managed) — documents the two non-committable steps: Claude external-plugin install command + Kiro IDE one-time "enable MCP" toggle.
- `.agents/` + `.codex/` dirs (moved here from base) created when the relevant target selected.
- **task-output**: apm lock (`apm install`, when install_via_apm + non-empty apm_packages); Claude plugin install side-effect.
- **Empty selection renders clean** — no target, no feature → only `.copier-answers.yml`. No refusal.
- **BUT (critique R2): the specific combination `install_via_apm=true` + `apm_packages==[]` MUST refuse
  loudly** (a validator, as old bailiff-mod-apm FR-002b did) — that combination is a phase-1 mistake (the
  APM install path was selected but produced no packages), distinct from the legitimate module-level
  no-op (no targets at all). Two different cases; only the module-level empty is a clean no-op.

## Tasks (order, all trust-gated)
1. preflight: mise + (uvx present when install_via_apm; the agent CLIs are the user's, not required at scaffold).
2. Claude plugin install (when native_marketplace + claude + frozen plugin list): `claude plugin install <plugin>@<mkt> --scope project` (process-deterministic; frozen inputs).
3. apm install (when install_via_apm + apm_packages non-empty): `uvx --from apm-cli=={{ apm_cli_version }} apm install` → apm lock (task-output).

## Marketplace vs APM matrix (verified against microsoft/apm targets-matrix)
- Marketplace-native: claude (`.claude-plugin/marketplace.json`), codex (`.agents/plugins/marketplace.json`).
- APM-only (no marketplace): kiro (`.kiro/`), opencode (`.opencode/`), plus cursor/gemini/windsurf/etc. if targets expand.
- MCP: per-target native file for all; canonical `mcp_servers` list translated per target format.

## spec-007 reconciliation (FR-016/FR-020)
Amend 007 Q1/OQ-007-b/f/D-007-4: hybrid resolution — agentic rollup + apm folded + speckit separate. 007's apm FRs (apm.yml/install/lockfile) migrate here; empty-set refusal (007 FR-002b) DROPPED. Old `copier-bailiff/bailiff-mod-apm` mirror tombstoned (confirmed public action, not authoring).

## Tests
init with each subset of targets renders disjoint config; empty selection = clean no-op; native_marketplace → manifests + (stubbed) plugin install; install_via_apm + kiro → apm path; mcp_config → per-target mcp file with ${VAR} refs (no secret question); reproduce managed byte-identical, apm/plugin tasks re-run idempotent.
