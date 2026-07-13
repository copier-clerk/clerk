# Changelog

All notable changes to `clerk-mod-python` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial port of the Python language overlay (spec 009 Phase 0), reconciled
  against the real `lang-python` manifest at tag `lang-python-v1.3.0`:
  - threaded `project_name` (`default: "{{ project_name }}"`), `description`,
    a free-text `python_version` (string, default 3.13 — not a fixed-choice
    list), `framework`, and the agent-resolved `pinned_deps` / `dev_deps` /
    `ruff_version` inputs;
  - a `run_after: [clerk-mod-base]` edge so base applies first;
  - the seed-once `pyproject.toml`: the byte-faithful lang-python ruff config
    (`line-length = 100`, `select = ["E","F","I","N","W","UP","B","SIM","TCH"]`,
    `quote-style = "double"`), `requires-python` pinned, deps rendered from the
    pin answers;
  - a `uv` preflight `_task`.
- With this module under `templates/`, `just check-modules` is a real gate,
  which (with clerk-mod-base) unblocks the spec-008b fan-out pipeline (SC-008).

### Notes / residual (spec 009)

- ruff `target-version` is threaded from `python_version` (upstream hardcodes
  `py313`); the rest of the ruff block is byte-faithful to `lang-python-v1.3.0`.
- ruff pre-commit hooks are **deferred**: `lang-python` appends them to a
  `.pre-commit-config.yaml` owned by the Phase-1 `precommit-setup` module
  (absent here), so there is no file to append to. The hook block (rev pinned
  from `ruff_version`) lands when `clerk-mod-precommit` does.
- installable src-package layout (`uv init --package`) is **flagged, not
  ported**: it is a uv-driven task, not a static render; Phase 0 seeds a flat
  manifest.

- - -
