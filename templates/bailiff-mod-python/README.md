# bailiff-mod-python

The Python **language overlay** (spec 011 / v1.0.0). Provides structured choice
axes for Python toolchain configuration, native-command scaffold via `uv` or `pdm`
init, and a managed `ruff.toml`. Runs after `bailiff-mod-base` and
`bailiff-mod-precommit`.

## What it produces

| Output | Lifecycle | Notes |
|---|---|---|
| `pyproject.toml` | **task-output** → **seed-once** | Written by `uv init` / `pdm init` (init-only-guarded). Never clobbered on reproduce. |
| `ruff.toml` | **managed** (byte-identical) | Re-rendered on every reproduce from the frozen answers. |
| `.mise.toml` [tools] | **contributed token** | python version + pkg manager token injected by the agent into base's `mise_tools` union; base is the single writer. |
| `.gitignore` Python entries | **contributed token** | `Python` token (gitnr short-code, case-sensitive) injected into base's `gitignore_stack`; base (via gitnr) is the single writer. |
| hook config ruff block | **contributed token** | ruff hook block injected into precommit's `hook_blocks` union; precommit is the single writer. |

## Questions

| Key | Choices / default | Notes |
|---|---|---|
| `python_pkg_manager` | [uv, pdm] / uv | |
| `python_version` | [3.11, 3.12, 3.13, 3.14] / 3.13 | pins requires-python + ruff target + mise |
| `python_layout` | [src, flat] / src | src = `uv init --package` (installable) |
| `framework` | [none, fastapi, django, flask] / none | recorded only; no scaffolding branch |
| `ruff_line_length` | [79, 88, 100, 119, 120] / 88 | |
| `ruff_quote_style` | [double, single] / double | |
| `ruff_rule_profile` | [standard, strict] / standard | strict adds ANN, RUF, PERF, C4, PT |
| `add_tests` | bool / false | adds tests/ scaffold with pytest example |
| `hook_manager` | threaded | single writer: bailiff-mod-precommit |

## Ordering

`run_after: [bailiff-mod-base, bailiff-mod-precommit]` — the spec-003 engine applies
base and precommit before this overlay. `project_name` is threaded via
`default: "{{ project_name }}"` (FR-010).

## Prerequisites (FR-007)

This template runs trust-gated `_tasks`; the source must be trusted before it
renders. Preflight checks:

- **mise** — <https://mise.jdx.dev>
- **uv** (when `python_pkg_manager=uv`) — <https://docs.astral.sh/uv/>
- **pdm** (when `python_pkg_manager=pdm`) — <https://pdm-project.org/>

## Usage

Prefer bailiff (multi-layer):

```sh
uvx bailiff init --run-spec <run-spec with [bailiff-mod-base, bailiff-mod-python]>
```

Copier-only (standalone; renders with defaults):

```sh
copier copy --trust https://github.com/bailiff-io/bailiff-mod-python.git <destination>
```
