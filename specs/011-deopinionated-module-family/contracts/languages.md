# Contract — language overlays: clerk-mod-ts / -go / -rust (NEW)

Shared shape (mirror clerk-mod-python + [_cross-cutting.md](./_cross-cutting.md)). Each
`run_after: [clerk-mod-base]`, threads `project_name`. Each contributes its token to the
AGENT-FROZEN UNION answers (NOT runtime accumulation — M1): its `.gitignore` token to
`gitignore_stack`, its `[tools]` token to `mise_tools` (base writes `.mise.toml`), and its hook
block to `hook_blocks` (precommit writes the hook file). Initial manifest = native init
(task-output, seed-once), init-only-guarded (FR-012a).

## clerk-mod-ts
- **Questions**: `js_pkg_manager [bun,pnpm,npm]=bun` (drop yarn); `ts_linter [biome,eslint-prettier]=biome`; `test_runner [none,vitest-node,vitest-browser,vitest+playwright,bun-test,playwright-only]=none` (drop jest); `node_version`; `framework [plain,nuxt,vite,sst]=plain` (+ `vite_template` when vite); `ui_kit [none,shadcn]=none`; threaded `project_name`, `hook_manager`.
- **Native scaffold**: `bun init` / `pnpm init` per `js_pkg_manager` (task-output → seed-once package.json). pnpm workspace = `pnpm-workspace.yaml`; bun/npm = `package.json workspaces[]` (the tool writes it — package-add uses native add).
- **Managed**: tsconfig (ES2022/strict), biome/eslint config (tool-not-generated part), vitest/playwright config.
- **Fixes** (bug, not choice): pin `nuxi`/`create-vite` (no `@latest`); apply the sst `.gitignore` entries; use `bun.lock` (text, Bun 1.2) not `bun.lockb` for cache keys.
- biome branch keeps an md/yaml-scoped prettier hook.

## clerk-mod-go
- **Questions**: `go_version`; `app_kind [cli,service,library]=cli` (wires the dead upstream input → layout; library drops `cmd/`); `test_runner [go-test,gotestsum]=go-test`; `use_vendor_mode=false`; `golangci_hook_rev` (injectable str); threaded `project_name`, `hook_manager`.
- **Native scaffold**: `go mod init` (task-output → seed-once go.mod); `cmd/<name>/main.go` stub (seed-once) per app_kind.
- **Managed**: `.golangci.yml` (the golangci-lint config set — seed-once actually, since users tune it; classify seed-once). gitignore token `Go` (+ vendor line when use_vendor_mode — conditional append).

## clerk-mod-rust
- **Questions**: `rust_channel [stable,beta,nightly,esp]=stable`; `rust_edition [2024,2021,2018]=2024` (drop 2015); `crate_kind [bin,lib]=bin`; `test_runner [cargo-test,nextest]=nextest`; `rustfmt_heuristics [Default,Max,Off]=Max`; `clippy_stage [pre-push,pre-commit]=pre-push`; `precommit_rust_rev` (injectable); threaded `project_name`, `hook_manager`.
- **Native scaffold**: `cargo new` (task-output → seed-once Cargo.toml); **FIX**: pass `--lib` when `crate_kind=lib` (upstream bug). `rust-toolchain.toml` from channel (managed). max_width=100 kept (rustfmt default). resolver=2.
- nextest: `[tools]` entry + test command `cargo nextest run`; NOT `cargo install` per-run (use mise/pre-baked).

## Shared tests (each language)
init `[base, <lang>]` → base first, native manifest present (stub marker), managed config byte-identical, mise token + gitignore token contributed, hook block threaded to precommit; standalone renders with defaults; reproduce: managed byte-identical, manifest regenerated process-deterministic, edited manifest preserved on re-run. No secret question.
