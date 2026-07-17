# Changelog

All notable changes to `bailiff-mod-precommit` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

#### Changes
- Drop `lefthook` from `hook_manager` choices; module now owns only `.pre-commit-config.yaml`. Lefthook support is deferred to `bailiff-mod-lefthook` (spec 015).

<!--
  cocogitto inserts each released version's section ABOVE the `- - -
## bailiff-mod-precommit-v0.1.0 - 2026-07-15
#### Features
- rename project clerk → bailiff (PyPI: bailiff, org: bailiff-io) - (52ac605) - Sjors Robroek

- - -

## bailiff-mod-precommit-v0.1.0 - 2026-07-15
#### Features
- (**011**) implement bailiff-mod-precommit (T005) - (943bc89) - Sjors Robroek
#### Bug Fixes
- (**011**) T005 address review findings - (e897cf4) - Sjors Robroek

- - -
` separator
  below (spec 008b). The separator MUST be present or `cog bump` fails with
  "cannot find default separator '- - -'". Keep it as the last content line.
-->

- - -
