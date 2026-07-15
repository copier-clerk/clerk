# Changelog

All notable changes to `bailiff-mod-github-repo` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial implementation of bailiff-mod-github-repo (spec 011 T018):
  - `visibility [private, public, internal]=private` replaces legacy `public:bool`;
  - hard exit-1 gate on `visibility=public` (no consent question, intentional);
  - tool-missing / creation-failure is non-fatal `exit 0` (warn-and-continue);
  - `remote_protocol [https, ssh]=https`, `push_after_create=false`, `team=""`;
  - plain `gh repo create` only — dropped legacy `gh-api.py` wrapper;
  - token from ambient `GITHUB_TOKEN`; no `secret:` questions;
  - `default_enabled=false`, `run_after: [bailiff-mod-base]`, `reconcile=false`.

- - -
## bailiff-mod-github-repo-v0.1.0 - 2026-07-15
#### Features
- (**011**) implement bailiff-mod-github-repo (T018) - (86c77bc) - Sjors Robroek
#### Bug Fixes
- (**011**) T018 address review findings - (6f25385) - Sjors Robroek

- - -

