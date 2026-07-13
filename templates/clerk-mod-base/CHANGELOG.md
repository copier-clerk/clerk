# Changelog

All notable changes to `clerk-mod-base` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial port of the collapsed clerk base scaffold (spec 009 Phase 0). Ports
  the six always-on project-setup base modules (core-identity, dirs-scaffold,
  gitignore-generate, license-write, agents-md, git-init) into one reproducible
  copier template:
  - identity + choice questions (`project_name`, `org`, `description`, `layout`,
    the 13-SPDX `license`);
  - the managed directory scaffold (20 base dirs; +15 monorepo targets on
    `layout=monorepo`);
  - the seed-once `AGENTS.md` (single/monorepo body + frozen-fact architecture
    splice gated on `write_architecture`);
  - trust-gated tasks: tool preflight, `gitnr` `.gitignore`, `gh` LICENSE,
    `git init`, and an `initial_commit`-gated commit.
- With this module under `templates/`, `just check-modules` is now a real gate
  (no longer the empty no-op), which unblocks the spec-008b fan-out pipeline
  (SC-008). `cog.toml` `pre_bump_hooks` can drop its `|| true` guard.

- - -
## clerk-mod-base-v0.1.0 - 2026-07-13
#### Features
- add base and Python project templates (#26) - (dd704d2) - Sjors Robroek
#### Bug Fixes
- (**008b**) add cog changelog separator; gate on it in check-modules (#31) - (26a8db7) - Sjors Robroek

- - -

