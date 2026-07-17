# bailiff-mod-editorconfig

Editor whitespace defaults micro-module (spec 012 / FR-006, spec 014 rewrite). Renders a managed
`.editorconfig` whose language sections derive from frozen language facts — deliberately NOT part
of `bailiff-mod-base` (keeps base thin, ratified).

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
- **No language facts frozen** → universal defaults only; no sections invented.
- **Zero `_tasks`**: pure render; reproduce needs no toolchain or network.

## Questions

All three language-fact questions are injected by the phase-1 agent via `--data`. They are empty
when the corresponding language module is absent from the stack.

| Key | Type | Default | Notes |
|---|---|---|---|
| `ts_linter` | str | `"{{ ts_linter }}"` | agent-frozen `--data` fact; empty = no TS section |
| `python_linter` | str | `""` | agent-frozen `--data` fact (e.g. `ruff`); empty = no Python section |
| `ruff_line_length` | str | `"88"` | feeds Python `max_line_length` only |

This module has no `_external_data` reads and no hard producer dependency. It works standalone.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-editorconfig.git <destination>
```
