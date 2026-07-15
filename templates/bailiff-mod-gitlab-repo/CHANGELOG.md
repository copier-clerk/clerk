# Changelog

All notable changes to `bailiff-mod-gitlab-repo` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial implementation (spec 012 / FR-012): exact semantic port of
  bailiff-mod-github-repo to glab — pure side-effect (no file output,
  reconcile=false); glab-missing warn+exit 0; public-without-consent hard
  exit 1 before creation; creation failure non-fatal; optional push; token
  from ambient GITLAB_TOKEN (no secret: questions).

<!--
  cocogitto inserts each released version's section ABOVE the `- - -` separator
  below (spec 008b). The separator MUST be present or `cog bump` fails with
  "cannot find default separator '- - -'". Keep it as the last content line.
-->

- - -
