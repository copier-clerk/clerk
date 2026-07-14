# Changelog

All notable changes to `clerk-mod-ci-github` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial implementation: GitHub Actions CI workflow module (spec 011).
  Pure managed render (ZERO `_tasks`); five models (minimal, standard, optimized,
  monorepo-affected, merge-queue); all sizing facts AGENT-FROZEN via `--data`;
  fail-loud R4 guard; pinned action majors; upload/download-artifact share v4.

<!--
  cocogitto inserts each released version's section ABOVE the `- - -` separator
  below (spec 008b). The separator MUST be present or `cog bump` fails with
  "cannot find default separator '- - -'". Keep it as the last content line.
-->

- - -
