# bailiff-mod-justfile

Seeds a `justfile` with idiomatic recipes (default/test/lint/build/dev/clean) for
the selected language. The file is **seed-once** — user edits survive `bailiff reproduce`.

Installs `just` via `.mise/conf.d/bailiff-mod-justfile.toml`.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-justfile.git <destination>
```

## Questions

| Key | Type | Default | Choices | Description |
|-----|------|---------|---------|-------------|
| `language` | str | `""` | `python`, `ts`, `go`, `rust`, `""` | Primary language for recipe bodies. Empty = fail-loud stubs. |
| `js_pkg_manager` | str | threaded / `bun` | `bun`, `pnpm`, `npm` | JS package manager for the `test` recipe. Agent-fed `--data` fact; standalone default `bun`. |
| `hook_manager` | str | threaded / `pre-commit` | `pre-commit`, `lefthook`, `none` | Hook manager for the `lint` recipe. Agent-fed `--data` fact; standalone default `pre-commit`. |

## Agent-fed facts

`hook_manager` and `js_pkg_manager` follow the R13 (sometimes-absent-producer) model:

- The phase-1 agent injects them via `--data` when their producer modules are in the stack.
- When run standalone the `default: "{{ hook_manager }}"` / `default: "{{ js_pkg_manager }}"` expressions resolve to the choice-list first element (`pre-commit` / `bun`).
- **Not** read via `_external_data`. `bailiff-mod-precommit` and `bailiff-mod-ts` are **not** in `depends_on`.

## Lifecycle

- `justfile` — **seed-once** (`_skip_if_exists`): rendered on first init, never overwritten on reproduce.
- `hook_manager=none`: the `lint` recipe falls back to a language-native linter command.
- `language=""`: all recipes emit a fail-loud error stub so missing configuration is obvious.

## Dependency edge

| Key | Value |
|-----|-------|
| `depends_on` | `[bailiff-mod-base]` |
| `_bailiff_phase` | `normal` |

`run_after` and `run_before` are absent (spec 014 R7).
