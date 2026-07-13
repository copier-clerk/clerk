# clerk-mod-python

The Python **language overlay** — ports project-setup's `lang-python` (add
Python tooling: uv, ruff, pytest) as a copier layer that `run_after`
[`clerk-mod-base`](https://github.com/copier-clerk/clerk-mod-base) (spec 009
Phase 0). Threads `project_name` from base and pins the Python version.

## Source

Reconciled against the real `lang-python` manifest at tag **`lang-python-v1.3.0`**
(`srobroek/project-setup`: `module.toml` + `module.py`). The inputs
(`project_name`, `description`, `python_version` — a free-text string defaulting
to `3.13`, `framework`, and the agent-resolved `pinned_deps` / `dev_deps` /
`ruff_version`), the ordering, and the ruff config match that manifest. Three
clerk-model adaptations are noted inline where they occur (see `copier.yml` and
`template/pyproject.toml.jinja`):

- ruff `target-version` is threaded from `python_version` (upstream hardcodes `py313`);
- the Python `.gitignore` block is contributed as a gitnr stack token instead of
  a literal append (single `.gitignore` writer — see `clerk-mod-base`);
- the ruff pre-commit hooks are deferred to Phase 1 (no `.pre-commit-config.yaml`
  exists in Phase 0 to append to).

## What it produces

| Output | Lifecycle | Notes |
|---|---|---|
| `pyproject.toml` | **seed-once** (`_skip_if_exists`) | uv/ruff config; `requires-python` pinned from `python_version`; `[project].name` from `project_name`, `[project].description` from `description`; runtime/dev deps rendered from `pinned_deps`/`dev_deps` (empty by default). Seeded once, then project-owned. |
| Python `.gitignore` entries | **task-output** (via base gitnr) | Contributed through `clerk-mod-base`'s shared `gitignore_stack` answer — this overlay writes NO `.gitignore` of its own (single writer, idempotent reproduce). |

## Not produced in Phase 0

- **ruff pre-commit hooks**: `lang-python` appends its ruff hook block
  (`astral-sh/ruff-pre-commit` `rev: v0.6.9`, `ruff --fix` + `ruff-format`) to a
  `.pre-commit-config.yaml` **owned by** the `precommit-setup` module — a Phase-1
  module absent in Phase 0. With no file to append to, this overlay deliberately
  does not fabricate a standalone pre-commit file. The block (rev pinned from
  `ruff_version`) moves here when `clerk-mod-precommit` lands.
- **installable src-package layout**: `lang-python` runs
  `uv init --name <project> --package`, producing `src/<snake_name>/__init__.py`
  with `[build-system]` + `[project.scripts]`. That is a uv-driven task (uv picks
  the build backend and entrypoint), not a static render, so Phase 0 seeds a flat
  manifest instead. Add a uv-init task if installable packaging is required.

## Ordering & threading

- `run_after: [clerk-mod-base]` (a `when:false` hidden answer) — the spec-003
  engine sequences base fully before this overlay. Upstream `lang-python` orders
  `after = ["gitignore-generate", "precommit-setup"]`; in Phase 0 gitignore-generate
  is collapsed inside `clerk-mod-base` and precommit-setup does not exist yet, so
  the single edge is `clerk-mod-base`. Add `clerk-mod-precommit` to `run_after`
  when it lands.
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
