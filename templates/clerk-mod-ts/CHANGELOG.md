# Changelog

All notable changes to `clerk-mod-ts` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial TypeScript language overlay (spec 011 T007):
  - `js_pkg_manager [bun,pnpm,npm]=bun`, `ts_linter [biome,eslint-prettier]=biome`,
    `test_runner [none,vitest-node,vitest-browser,vitest+playwright,bun-test,playwright-only]=none`,
    `node_version`, `framework [plain,nuxt,vite,sst]=plain` (+ `vite_template`
    when `framework=vite`), `ui_kit [none,shadcn]=none`;
  - `run_after: [clerk-mod-base]`; threaded `project_name` and `hook_manager`;
  - frozen-union contributions: `gitignore_stack`, `mise_tools`, `hook_blocks`;
  - native scaffold: `bun init` / `pnpm init` (task-output → seed-once `package.json`);
  - managed byte-identical: `tsconfig.json` (ES2022/strict), `biome.json` /
    eslint+prettier config, vitest/playwright config per `test_runner`;
  - bug fixes: pinned `nuxi`/`create-vite` (no `@latest`), SST `.gitignore`
    entries, `bun.lock` cache key (Bun 1.2 text lockfile).

- - -
