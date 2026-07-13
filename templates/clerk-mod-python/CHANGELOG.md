# Changelog

All notable changes to `clerk-mod-python` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial port of the Python language overlay (spec 009 Phase 0), from
  project-setup's `lang-python`:
  - threaded `project_name` (`default: "{{ project_name }}"`) + a fixed-choice
    `python_version` (default 3.13);
  - a `run_after: [clerk-mod-base]` edge so base applies first;
  - the seed-once `pyproject.toml` (uv/ruff/pytest, `requires-python` pinned);
  - a `uv` preflight `_task`.
- With this module under `templates/`, `just check-modules` is a real gate,
  which (with clerk-mod-base) unblocks the spec-008b fan-out pipeline (SC-008).

### Notes / residual (spec 009)

- `lang-python`'s full manifest was not available at authoring time; the
  `pyproject.toml` config and `python_version` choices are inferred from the
  catalog + SKILL.md characterization and flagged `TODO(009)` for reconciliation.
- ruff pre-commit hooks are **deferred**: they belong to the Phase-1
  `precommit-setup` module (absent here), so there is no file to append to.
