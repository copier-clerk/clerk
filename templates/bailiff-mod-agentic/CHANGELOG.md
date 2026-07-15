# Changelog

All notable changes to `bailiff-mod-agentic` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial agentic-config rollup module (spec 011, folds in bailiff-mod-apm FRs).
  - `agentic_targets` multiselect [claude, codex, opencode, kiro] — NO default;
    phase-1 agent injects via `--data`.
  - Per-target managed outputs on disjoint paths: `.claude/settings.json`,
    `.mcp.json`, `.codex/config.toml`, `.agents/plugins/marketplace.json`,
    `opencode.json`, `.kiro/settings/mcp.json`, `.kiro/agents/agents.json`.
  - `.kiro/steering/project.md` (seed-once, `_skip_if_exists`).
  - `AGENTIC.md` (managed) — documents non-committable setup steps.
  - `mcp_config` / `native_marketplace` / `install_via_apm` feature flags.
  - `mcp_servers` canonical list fanned per-target; env values as `${VAR}` refs.
  - R2 validator: `install_via_apm=true` + `apm_packages==[]` refused loudly.
  - Empty selection = clean no-op (only `.copier-answers.yml` written).
  - Trust-gated tasks: mise preflight; uvx preflight (when `install_via_apm`);
    claude plugin install (when `native_marketplace` + claude + plugins non-empty);
    `uvx --from apm-cli==<ver> apm install` (when `install_via_apm` + packages).

- - -
## bailiff-mod-agentic-v0.1.0 - 2026-07-15
#### Features
- (**011**) implement bailiff-mod-agentic (T014) - (97e6ddf) - Sjors Robroek

- - -

