# Changelog

All notable changes to `clerk-mod-cdk` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial implementation of the AWS CDK overlay (spec 011 T021): preflight +
  `cdk init app --language=<cdk_language>` (guarded on `cdk.json`), optional
  `cdk synth` validation, cdk-nag splice, de-opinionated env pattern.
- Questions: `cdk_language [typescript,python,go,java,csharp]`, `placement_dir`,
  `cdk_version`, `include_cdk_nag`, `include_synth_validate`, threaded `project_name`.
- NEVER `cdk bootstrap`/`deploy`; `cdk.context.json` committed; `cdk.out/` gitignored.

<!--
  cocogitto inserts each released version's section ABOVE the `- - -
## clerk-mod-cdk-v0.1.0 - 2026-07-15
#### Features
- (**011**) implement clerk-mod-cdk (T021) - (3a93f82) - Sjors Robroek
#### Bug Fixes
- (**011**) E2E campaign fixes -- cdk nag-splice bug, drop version pin, IaC exclusion tags - (ce28f28) - Sjors Robroek
- (**011**) T021 give cdk synth its own init-only sentinel - (365d80f) - Sjors Robroek
- (**011**) T021 init-only guards on cdk pin + synth tasks - (9b6d0d3) - Sjors Robroek
- (**011**) T021 address review findings - (736f1f8) - Sjors Robroek

- - -
` separator
  below (spec 008b). The separator MUST be present or `cog bump` fails with
  "cannot find default separator '- - -'". Keep it as the last content line.
-->

- - -
