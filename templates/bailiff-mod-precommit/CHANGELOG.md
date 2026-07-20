# Changelog

All notable changes to `bailiff-mod-precommit` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

#### Breaking Changes
- Remove `hook_manager` question entirely (spec 014 R13). Selecting `bailiff-mod-precommit` IS choosing pre-commit; the question was redundant with module selection. Lefthook is a separate module (`bailiff-mod-lefthook`, spec 015).

#### Changes
- Drop `lefthook` from `hook_manager` choices; module now owns only `.pre-commit-config.yaml`. Lefthook support is deferred to `bailiff-mod-lefthook` (spec 015).

<!--
  cocogitto inserts each released version's section ABOVE the `- - -
## bailiff-mod-precommit-v0.3.1 - 2026-07-20
#### Bug Fixes
- fail with install guidance when a module's required tool is missing (#52) - (adcf599) - Sjors Robroek

- - -

## bailiff-mod-precommit-v0.3.0 - 2026-07-20
#### Features
- agent-projected capabilities (cross-format hooks, agentic editorconfig) (#47) - (453464e) - Sjors Robroek

- - -

## bailiff-mod-precommit-v0.2.0 - 2026-07-17
#### Features
- (**014**) T032/T044/T043 — precommit fragment/merge model - (e1f75cb) - Sjors Robroek
- (**014/n-precommit-lefthook**) strip lefthook from bailiff-mod-precommit - (d86267e) - Sjors Robroek
#### Bug Fixes
- (**bundler**) reject non-dict fragments with a clear error - (6d3665d) - Sjors Robroek

- - -

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
