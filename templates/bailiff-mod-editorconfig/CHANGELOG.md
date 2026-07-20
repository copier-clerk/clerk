# Changelog

All notable changes to `bailiff-mod-editorconfig` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial implementation (spec 012 / FR-006): managed `.editorconfig` with
  always-present universal defaults; TS/JS and Python sections sized from
  frozen linter facts (indent from linter convention, max_line_length from
  ruff_line_length); zero `_tasks`.

<!--
  cocogitto inserts each released version's section ABOVE the `- - -
## bailiff-mod-editorconfig-v0.3.0 - 2026-07-20
#### Features
- agent-projected capabilities (cross-format hooks, agentic editorconfig) (#47) - (453464e) - Sjors Robroek

- - -

## bailiff-mod-editorconfig-v0.2.0 - 2026-07-17
#### Features
- (**014/T040**) wire editorconfig ts_linter via _external_data.ts - (ecd6bae) - Sjors Robroek
#### Bug Fixes
- (**014/T040**) revert editorconfig ts_linter to agent-fed --data (standalone contract) - (115a846) - Sjors Robroek
#### Documentation
- reframe reproduce invariant from byte-identical to config-consistent - (498315f) - Sjors Robroek
- reframe reproduce invariant from byte-identical to config-consistent - (c1d7faf) - Sjors Robroek

- - -

## bailiff-mod-editorconfig-v0.1.0 - 2026-07-16
#### Features
- (**012**) bailiff-mod-editorconfig — managed .editorconfig from frozen linter facts (T004) - (281ea81) - Sjors Robroek
- (**012**) bailiff-mod-devcontainer — managed devcontainer.json from frozen mise_tools (T003) - (1e999b3) - Sjors Robroek

- - -
` separator
  below (spec 008b). The separator MUST be present or `cog bump` fails with
  "cannot find default separator '- - -'". Keep it as the last content line.
-->

- - -
