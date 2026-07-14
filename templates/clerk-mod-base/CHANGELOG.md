# Changelog

All notable changes to `clerk-mod-base` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Changed

- **v1.0.0 clean break (spec 011)**: thinned scaffold — `.agents/` + `.codex/`
  moved to clerk-mod-agentic; `infrastructure/` moved to IaC modules;
  `.github/workflows/` moved to clerk-mod-ci; `specs/` moved to
  clerk-mod-speckit; `archive/`, `assets/`, and 5 extra docs subdirs dropped
  (available via `extra_dirs`).
- New question axes: `copyright_name`, `branch_strategy`, `docs_subdirs`,
  `github_host`, `extra_dirs`, `run_git_init`, `mise_tools`.
- `.mise.toml` now managed (single writer, agent-frozen `mise_tools` union).
- `.github/` minimal scaffold (issue/PR templates, CODEOWNERS, dependabot)
  gated on `github_host`; no workflows (clerk-mod-ci).
- Tasks restructured: mise preflight first, init-only-guarded via committed
  sentinel (FR-012a), `copyright_name` replaces `org` in LICENSE substitution.
- No `_migrations` / update path (M2 clean break to v1.0.0).

- - -
## clerk-mod-base-v0.1.0 - 2026-07-13
#### Features
- add base and Python project templates (#26) - (dd704d2) - Sjors Robroek
#### Bug Fixes
- (**008b**) add cog changelog separator; gate on it in check-modules (#31) - (26a8db7) - Sjors Robroek

- - -
