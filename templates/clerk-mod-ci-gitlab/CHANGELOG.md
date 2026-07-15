# Changelog

All notable changes to `clerk-mod-ci-gitlab` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial implementation of the GitLab CI module (spec 011 T017): renders a
  `.gitlab-ci.yml` managed file from 5 ci_models (minimal, standard, optimized,
  monorepo-affected, merge-queue) with full grill-fix compliance:
  - `workflow:rules` duplicate-pipeline guard on all models;
  - `{job: x, optional: true}` needs on change-gated jobs (pipeline-creation safe);
  - coupled `interruptible` + `workflow:auto_cancel:on_new_commit` as one unit;
  - `rules:changes` with `compare_to` on branch arm, omitted on MR arm;
  - `fallback_keys` on caches; pinned images via `ci_lang_facts`;
  - `bun.lock` (not `bun.lockb`) cache key;
  - `gitlab_tier=free` merge-queue fallback with header warning;
  - fail-loud guard: empty `ci_languages` + `monorepo_tool=none` → warning no-op job.

- - -
## clerk-mod-ci-gitlab-v0.1.0 - 2026-07-15
#### Features
- (**011**) implement clerk-mod-ci-gitlab (T017) - (029bf78) - Sjors Robroek
#### Bug Fixes
- (**011**) T017 address review findings - (94b82b3) - Sjors Robroek

- - -

