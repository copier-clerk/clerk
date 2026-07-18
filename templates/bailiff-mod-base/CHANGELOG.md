# Changelog

All notable changes to `bailiff-mod-base` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Changed

- **v1.0.0 clean break (spec 011)**: thinned scaffold — `.agents/` + `.codex/`
  moved to bailiff-mod-agentic; `infrastructure/` moved to IaC modules;
  `.github/workflows/` moved to bailiff-mod-ci; `specs/` moved to
  bailiff-mod-speckit; `archive/`, `assets/`, and 5 extra docs subdirs dropped
  (available via `extra_dirs`).
- New question axes: `copyright_name`, `branch_strategy`, `docs_subdirs`,
  `github_host`, `extra_dirs`, `run_git_init`, `mise_tools`.
- `.mise.toml` now managed (single writer, agent-frozen `mise_tools` union).
- `.github/` minimal scaffold (issue/PR templates, CODEOWNERS, dependabot)
  gated on `github_host`; no workflows (bailiff-mod-ci).
- Tasks restructured: mise preflight first, init-only-guarded via committed
  sentinel (FR-012a), `copyright_name` replaces `org` in LICENSE substitution.
- No `_migrations` / update path (M2 clean break to v1.0.0).

- - -
## bailiff-mod-base-v0.2.1 - 2026-07-17
#### Bug Fixes
- tree is clean after multi-layer init (initial commit is engine-owned) (#44) - (b9e309d) - Sjors Robroek

- - -

## bailiff-mod-base-v0.1.0 - 2026-07-16
#### Features
- rename project clerk → bailiff (PyPI: bailiff, org: bailiff-io) - (52ac605) - Sjors Robroek
#### Documentation
- (**013**) move template README invocations to uvx bailiff (T013 follow-up) - (d8cf603) - Sjors Robroek

- - -

## bailiff-mod-base-v0.2.0 - 2026-07-15
#### Features
- (**011**) revise bailiff-mod-base to v1.0.0 thinned scaffold - (b813710) - Sjors Robroek
- (**012**) remove dependabot.yml from base template (pre-v1.0.0 amendment) - (a68295e) - Sjors Robroek
#### Bug Fixes
- (**011**) T004 address review findings - (3554e7f) - Sjors Robroek

- - -

## bailiff-mod-base-v0.1.0 - 2026-07-13
#### Features
- add base and Python project templates (#26) - (dd704d2) - Sjors Robroek
#### Bug Fixes
- (**008b**) add cog changelog separator; gate on it in check-modules (#31) - (26a8db7) - Sjors Robroek

- - -
