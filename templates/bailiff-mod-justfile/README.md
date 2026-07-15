# bailiff-mod-justfile

Seeds a `justfile` with idiomatic recipes (default/test/lint/build/dev/clean) for
the selected language. The file is **seed-once** — user edits survive `bailiff reproduce`.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-justfile.git <destination>
```

## Questions

| Key | Default | Choices | Description |
|-----|---------|---------|-------------|
| `language` | `""` | `python`, `ts`, `go`, `rust`, `""` | Primary language for recipe bodies. Empty = fail-loud stubs. |
| `js_pkg_manager` | threaded / `bun` | `bun`, `pnpm`, `npm` | JS package manager for the `test` recipe (threaded from upstream). |
| `hook_manager` | threaded / `pre-commit` | `pre-commit`, `lefthook`, `none` | Hook manager for the `lint` recipe (threaded from `bailiff-mod-precommit`). |

## Lifecycle

- `justfile` — **SEED-ONCE** (`_skip_if_exists`): rendered on first init, never overwritten on reproduce.
- `hook_manager=none`: the `lint` recipe falls back to a language-native linter command.
- `language=""`: all recipes emit a fail-loud error stub so missing configuration is obvious.

## Run after

`bailiff-mod-base`
