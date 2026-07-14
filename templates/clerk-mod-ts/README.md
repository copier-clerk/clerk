# clerk-mod-ts

TypeScript/JavaScript language overlay for the clerk copier framework (spec 011).

Applies after `clerk-mod-base` (`run_after: [clerk-mod-base]`), threads `project_name`,
and seeds a `package.json` via the chosen package manager's native init (task-output,
then seed-once). Ships managed byte-identical configs: `tsconfig.json`, biome or
eslint+prettier config, and vitest/playwright config per `test_runner`.

## Questions

| Key | Choices | Default | Notes |
|-----|---------|---------|-------|
| `js_pkg_manager` | `bun`, `pnpm`, `npm` | `bun` | yarn DEAD |
| `ts_linter` | `biome`, `eslint-prettier` | `biome` | |
| `test_runner` | `none`, `vitest-node`, `vitest-browser`, `vitest+playwright`, `bun-test`, `playwright-only` | `none` | jest DEAD |
| `node_version` | finite modern list | `22` | |
| `framework` | `plain`, `nuxt`, `vite`, `sst` | `plain` | `vite_template` asked when `framework=vite` |
| `ui_kit` | `none`, `shadcn` | `none` | |
| `project_name` | — | threaded | from `clerk-mod-base` |
| `hook_manager` | — | threaded | from phase-1 agent |

## Frozen-union contributions (M1)

- Gitignore token → `gitignore_stack` (base writes `.gitignore`)
- Node version entry → `mise_tools` (base writes `.mise.toml`)
- Hook block → `hook_blocks` (precommit writes hook file)

## Bug fixes included

- `nuxi`/`create-vite` pinned (no `@latest`)
- SST `.gitignore` entries added
- Cache keys use `bun.lock` (Bun 1.2 text lockfile, not `bun.lockb`)
- biome branch retains an md/yaml-scoped prettier hook

## Usage

```bash
clerk init --modules clerk-mod-base clerk-mod-ts
```
