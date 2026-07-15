# bailiff-mod-editorconfig

Editor whitespace defaults micro-module (spec 012 / FR-006). Renders a managed
`.editorconfig` whose language sections are sized from the project's **frozen
language facts** — deliberately NOT part of `bailiff-mod-base` (keeps base
thin, ratified).

## Outputs

| File | Lifecycle | Notes |
|---|---|---|
| `.editorconfig` | **managed** | byte-identical on reproduce |

## Design

- **Universal defaults section always present**: `charset = utf-8`,
  `end_of_line = lf`, `insert_final_newline = true`,
  `trim_trailing_whitespace = true`.
- **Language sections from frozen facts**: a TS/JS section renders when
  `ts_linter` is set (biome and eslint-prettier both follow the 2-space
  convention); a Python section renders when `python_linter` is set (PEP 8 /
  ruff convention: 4-space indent, `max_line_length` from `ruff_line_length`).
- **INVARIANT**: indentation derives from the linter's convention ONLY, never
  from line-width facts.
- **No language facts frozen** → universal defaults only; no sections invented.
- **Zero `_tasks`**: pure render; reproduce needs no toolchain or network.

## Questions

| Key | Type | Default | Notes |
|---|---|---|---|
| `ts_linter` | str | threaded `"{{ ts_linter }}"` | frozen fact; empty = no TS section |
| `python_linter` | str | `""` | frozen fact (e.g. `ruff`); empty = no Python section |
| `ruff_line_length` | str | `"88"` | feeds Python `max_line_length` only |

The phase-1 agent freezes `ts_linter`, the Python linter identity, and
`ruff_line_length` via `--data` (FR-006).

Edge: `run_after: [bailiff-mod-base]`.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-editorconfig.git <destination>
```
