# Contract — bailiff-mod-python (REVISE)

Python language overlay, de-opinionated + native-command scaffolded. References
[_cross-cutting.md](./_cross-cutting.md). `run_after: [bailiff-mod-base]`.

## Questions
| key | type | choices / default | notes |
|---|---|---|---|
| project_name | str | "{{ project_name }}" | threaded |
| description | str | "" | → pyproject description |
| python_pkg_manager | str | [uv, pdm] / uv | drop poetry/pip/pipenv |
| python_version | str | [3.11,3.12,3.13,3.14] / 3.13 | pins requires-python + ruff target + mise |
| python_layout | str | [flat, src] / src | src = uv init --package layout |
| framework | str | [none, fastapi, django, flask] / none | recorded; no scaffolding branch beyond hints |
| ruff_line_length | str | 79/88/100/119/120 / 88 | managed ruff config |
| ruff_quote_style | str | double/single / double | |
| ruff_rule_profile | str | standard/strict / standard | |
| add_tests | bool | false | opt-in; pytest is the sole runner when on |
| hook_manager | str | "{{ hook_manager }}" | threaded; contributes ruff hook block to precommit |
| ruff_version / pinned_deps / dev_deps | str/yaml | "" / [] | agent-frozen pins if pre-resolved |
| today | str | "" | injected |
| run_after | yaml when:false | [bailiff-mod-base] | (+ bailiff-mod-precommit when it lands, for hook order) |

## Outputs / lifecycle
- **pyproject.toml** — TASK-OUTPUT via `uv init` (or `pdm init`), then seed-once. Native init picks build backend + layout (`--package` for src). requires-python from `python_version`.
- **ruff config** — MANAGED (byte-identical): either the `[tool.ruff]` block appended to pyproject as a managed splice, or `ruff.toml` — whichever the tool does NOT own; line-length/quotes/profile from answers, target-version threaded from `python_version`.
- **`.mise.toml` [tools]** — contributes `python = "{{ python_version }}"` (+ uv) token (managed, shared file).
- **`.gitignore` Python entries** — task-output via base gitnr (`python` token into `gitignore_stack`); python writes NO `.gitignore` itself.
- **ruff pre-commit hook** — contributed to bailiff-mod-precommit via the hook_manager threading contract (single writer); not written here.
- test scaffold (when `add_tests`): a `tests/` example + pytest config (managed config, seed-once example).

## Tasks (order)
1. preflight: mise + `mise install` (python + chosen PM).
2. native init: `test -f pyproject.toml || <uv|pdm> init …` (task-output; guarded).

## Tests
init `[base, python]` `python_pkg_manager=uv python_version=3.13 python_layout=src` → base first (edge), pyproject present (native-init marker in stub), ruff config managed with 88/double/standard, mise token present, gitignore_stack includes python; standalone init renders with defaults; reproduce: managed ruff byte-identical, pyproject regenerated (process-deterministic), edited pyproject preserved on re-run.
