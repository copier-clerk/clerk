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
  cocogitto inserts each released version's section ABOVE the `- - -` separator
  below (spec 008b). The separator MUST be present or `cog bump` fails with
  "cannot find default separator '- - -'". Keep it as the last content line.
-->

- - -
