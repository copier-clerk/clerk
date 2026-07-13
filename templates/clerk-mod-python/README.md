# clerk-mod-python

The Python **language overlay** — ports project-setup's `lang-python` (add
Python tooling: uv, ruff, pytest) as a copier layer that `run_after`
[`clerk-mod-base`](https://github.com/copier-clerk/clerk-mod-base) (spec 009
Phase 0). Threads `project_name` from base and pins the Python version.

## Source caveat (Phase 0)

`lang-python`'s full manifest (`module.toml` + `module.py`) was **not available**
when this overlay was authored. It is built from the addon `catalog.json`
description and the `project-setup` SKILL.md characterization (pins 3.13, uv +
`pyproject.toml`, appends Python `.gitignore` entries + ruff pre-commit hooks).
Every inferred behaviour is flagged with a `# TODO(009): confirm against
lang-python manifest when available` comment in `copier.yml` and
`template/pyproject.toml.jinja` so it can be reconciled later. Nothing is
invented beyond those sources (FR-011).

## What it produces

| Output | Lifecycle | Notes |
|---|---|---|
| `pyproject.toml` | **seed-once** (`_skip_if_exists`) | uv/ruff/pytest config; `requires-python` pinned from `python_version`; `[project].name` threaded from `project_name`. Seeded once, then project-owned. |
| Python `.gitignore` entries | **task-output** (via base gitnr) | Contributed through `clerk-mod-base`'s shared `gitignore_stack` answer — this overlay writes NO `.gitignore` of its own (single writer, idempotent reproduce). |

## Not produced in Phase 0

- **ruff pre-commit hooks**: project-setup's `lang-python` appends ruff hooks to
  a `.pre-commit-config.yaml` owned by the `precommit-setup` module — a Phase-1
  module absent in Phase 0. With no file to append to, this overlay deliberately
  does not fabricate a standalone pre-commit file. Wire it when `precommit-setup`
  lands (`TODO(009)` in `copier.yml`).

## Ordering & threading

- `run_after: [clerk-mod-base]` (a `when:false` hidden answer) — the spec-003
  engine sequences base fully before this overlay.
- `project_name` uses copier's `default: "{{ project_name }}"` threading
  (ADR-0003); clerk threads base's answer via `data=`. It does **not** hardcode
  which upstream layer supplied it (FR-010), and renders standalone with a
  default when no base is present (SC-006-style self-containment).

## Prerequisites (FR-007b)

This template runs a trust-gated preflight `_task`, so the source must be
trusted before it renders. The preflight (ordered first) checks:

- **uv** — <https://docs.astral.sh/uv/getting-started/installation/>

## Usage

Prefer clerk (multi-layer, in dependency order):

```sh
uv run scripts/clerk.py init --run-spec <run-spec with [clerk-mod-base, clerk-mod-python]>
```

Copier-only (standalone; renders with defaults):

```sh
copier copy --trust https://github.com/copier-clerk/clerk-mod-python.git <destination>
```
