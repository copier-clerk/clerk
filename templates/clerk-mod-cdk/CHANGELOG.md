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
  cocogitto inserts each released version's section ABOVE the `- - -` separator
  below (spec 008b). The separator MUST be present or `cog bump` fails with
  "cannot find default separator '- - -'". Keep it as the last content line.
-->

- - -
