# bailiff-mod-editorconfig

Editor whitespace defaults micro-module (spec 012 / FR-006, spec 014 rewrite). Renders a managed
`.editorconfig` whose language sections derive from the project's frozen language facts — deliberately
NOT part of `bailiff-mod-base` (keeps base thin, ratified).

## Outputs

| File | Lifecycle | Notes |
|---|---|---|
| `.editorconfig` | **managed** | config-consistent on reproduce |

## Design

- **Universal defaults section always present**: `charset = utf-8`, `end_of_line = lf`,
  `insert_final_newline = true`, `trim_trailing_whitespace = true`.
- **TS/JS section** renders when `ts_linter` is set (biome and eslint-prettier both follow the
  2-space indent convention).
- **Python section** renders when `python_linter` is set (PEP 8 / ruff convention: 4-space indent,
  `max_line_length` from `ruff_line_length`).
- **INVARIANT**: indentation derives from the linter's convention ONLY, never from line-width facts.
- **No language facts present** → universal defaults only; no sections invented.
- **Zero `_tasks`**: pure render; reproduce needs no toolchain or network.

## Cross-module facts (`_external_data`)

`ts_linter` is read from `bailiff-mod-ts` via the `_external_data` alias (spec 014 FR-004):

```yaml
_external_data:
  ts: .copier-answers.bailiff-mod-ts.yml
```

This makes `bailiff-mod-ts` a **hard dependency**: if ts is absent from the stack, bailiff raises
a loud `OrderingError` at preflight (FR-006). Python facts (`python_linter`, `ruff_line_length`)
are injected by bailiff via `--data`.

## Questions

| Key | Type | Default | Notes |
|---|---|---|---|
| `ts_linter` | str | `{{ _external_data.ts.ts_linter }}` | read from bailiff-mod-ts; empty = no TS section |
| `python_linter` | str | `""` | frozen fact (e.g. `ruff`); empty = no Python section |
| `ruff_line_length` | str | `"88"` | feeds Python `max_line_length` only |

## Dependency edge

`depends_on: [bailiff-mod-ts]` — ts must be applied before editorconfig (the `_external_data` read
is the ordering constraint, spec 014 FR-019/R7).

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-editorconfig.git <destination>
```
