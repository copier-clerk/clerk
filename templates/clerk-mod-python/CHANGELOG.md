# Changelog

All notable changes to `clerk-mod-python` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- **v1.0.0 clean break (spec 011)**: de-opinionated Python overlay with structured
  choice axes, native-command scaffold, and M1 agent-frozen threading contract.
  - Choice questions (C-06 frozen): `python_pkg_manager` [uv, pdm]=uv,
    `python_version` [3.11–3.14]=3.13, `python_layout` [src, flat]=src,
    `framework` [none, fastapi, django, flask]=none,
    `ruff_line_length` [79,88,100,119,120]=88, `ruff_quote_style` [double,single]=double,
    `ruff_rule_profile` [standard,strict]=standard, `add_tests` bool=false.
  - `pyproject.toml` is now TASK-OUTPUT (native `uv`/`pdm` init, init-only-guarded)
    then seed-once; the old rendered template is removed.
  - `ruff.toml` is now a standalone MANAGED (byte-identical) file.
  - `run_after: [clerk-mod-base, clerk-mod-precommit]` edge.
  - `mise install` init-only-guarded preflight (FR-012a sentinel).
  - Contributes tokens only (M1): python version + pkg-manager → mise_tools;
    python → gitignore_stack; ruff hook block → hook_blocks.

### Breaking changes

- Dropped: `pinned_deps`, `dev_deps` questions (no longer seed deps into pyproject).
- Dropped: `pip`, `pipenv`, `poetry` (dead options per FR-002).
- Dropped: `python_version` as free-text string; now a fixed-choice list.
- `pyproject.toml` lifecycle changed from MANAGED seed-once to TASK-OUTPUT seed-once.

- - -
## clerk-mod-python-v0.2.0 - 2026-07-15
#### Features
- (**011**) revise clerk-mod-python to v1.0.0 de-opinionated spec - (cc7d7ea) - Sjors Robroek
#### Bug Fixes
- (**011**) E2E campaign fixes -- cdk nag-splice bug, drop version pin, IaC exclusion tags - (ce28f28) - Sjors Robroek
- (**011**) cargo init not new (non-empty dir), gitnr token casing (E2E) - (330c08a) - Sjors Robroek
- (**011**) T006 address review findings - (d32be2b) - Sjors Robroek

- - -

## clerk-mod-python-v0.1.0 - 2026-07-13
#### Features
- add base and Python project templates (#26) - (dd704d2) - Sjors Robroek
#### Bug Fixes
- (**008b**) add cog changelog separator; gate on it in check-modules (#31) - (26a8db7) - Sjors Robroek
- (**009**) reconcile clerk-mod-python against lang-python-v1.3.0 (#30) - (4ab308d) - Sjors Robroek, *Sjors Robroek*

- - -

