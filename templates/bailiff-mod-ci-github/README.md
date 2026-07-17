# bailiff-mod-ci-github

GitHub Actions CI workflow overlay — pure managed render (ZERO `_tasks`).
Outputs `.github/workflows/ci.yml`, config-consistent on reproduce.

## Models

| Model | Description |
|---|---|
| `minimal` | Single combined job, no fan-in gate |
| `standard` | Parallel per-language jobs + required fan-in gate |
| `optimized` | standard + dorny/paths-filter + cache + concurrency-cancel |
| `monorepo-affected` | paths-filter per-package (monorepo_tool required) |
| `merge-queue` | GitHub merge queue trigger (requires org/GHEC signal) |

## Output

| File | Lifecycle | Notes |
|---|---|---|
| `.github/workflows/ci.yml` | **managed** | Config-consistent on reproduce; re-render to update |

## Facts read via `_external_data`

| Alias | Source file | Keys read |
|---|---|---|
| `base` | `.copier-answers.bailiff-mod-base.yml` | `default_branch` |
| `moon` | `.copier-answers.bailiff-mod-moon.yml` | `monorepo_tool` |

Both producers must be present in the bailiff selection (FR-006). Absent producer → preflight error naming the alias.

## Fail-loud guard (R4)

When `ci_languages==[]` AND `monorepo_tool==none`, the rendered workflow
emits a warning comment and a no-op job that exits 1. This makes the
misconfiguration visible rather than producing a silent empty file.

## Agent-frozen facts

`ci_languages` and `ci_lang_facts` MUST be injected via `--data` by the
phase-1 agent. They are NOT computed at runtime because this module sorts
before language overlays (alphabetical basename tie-break) and cannot read
their answers via the run-order accumulator.

## Pins

All action refs are pinned to current majors:
- `actions/checkout@v4`
- `actions/setup-python@v5`, `actions/setup-node@v4`, `actions/setup-go@v5`
- `actions/cache@v4`
- `dorny/paths-filter@v3`
- `actions/upload-artifact@v4` / `actions/download-artifact@v4` (same major)
- `dtolnay/rust-toolchain@stable`

## Usage

```sh
copier copy --trust \
  --data ci_languages='["python","typescript"]' \
  --data 'ci_lang_facts={"python":{"manager":"uv","version":"3.13","test_runner":"pytest","image":""},"typescript":{"manager":"bun","version":"22","test_runner":"vitest","image":""}}' \
  https://github.com/bailiff-io/bailiff-mod-ci-github.git <destination>
```
