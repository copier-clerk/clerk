# bailiff-mod-ts

TypeScript/JavaScript language overlay for the bailiff copier framework.

Depends on `bailiff-mod-base` (`depends_on: [bailiff-mod-base]`, `phase: normal`).
Seeds a `package.json` via the chosen package manager's native init (task-output, then seed-once).
Ships managed byte-identical configs: `tsconfig.json`, biome or eslint+prettier config, and vitest/playwright config per `test_runner`.

## Questions

| Key | Choices | Default | Notes |
|-----|---------|---------|-------|
| `js_pkg_manager` | `bun`, `pnpm`, `npm` | `bun` | yarn DEAD; fact for `ts` alias |
| `ts_linter` | `biome`, `eslint-prettier` | `biome` | fact for `ts` alias |
| `test_runner` | `none`, `vitest-node`, `vitest-browser`, `vitest+playwright`, `bun-test`, `playwright-only` | `none` | jest DEAD; private (collision class) |
| `node_version` | finite modern list | `22` | |
| `ts_framework` | `plain`, `nuxt`, `vite`, `sst` | `plain` | `vite_template` asked when `ts_framework=vite` |
| `ui_kit` | `none`, `shadcn` | `none` | |

## Fragment contributions (spec 014)

| Surface | Path | Notes |
|---------|------|-------|
| mise tools | `.mise/conf.d/bailiff-mod-ts.toml` | `node = "<node_version>"`; mise merges natively |
| pre-commit hooks | `.pre-commit.d/bailiff-mod-ts.yaml` | biome or eslint+prettier hooks; bundled by precommit's post-task |
| gitignore lines | `.gitignore.d/bailiff-mod-ts` | Node/TS ignore patterns; concatenated by base's post-task |

## Facts produced (alias `ts`)

Consumers wire `_external_data: {ts: .copier-answers.bailiff-mod-ts.yml}` and read:

| fact | consumers |
|------|-----------|
| `js_pkg_manager` | justfile, package-add |
| `ts_linter` | editorconfig |

## Bug fixes included

- `nuxi`/`create-vite` pinned (no `@latest`)
- SST `.gitignore` entries added
- Cache keys use `bun.lock` (Bun 1.2 text lockfile, not `bun.lockb`)
- biome branch retains an md/yaml-scoped prettier hook

## Usage

```bash
bailiff init --modules bailiff-mod-base bailiff-mod-ts
```
