# bailiff-mod-package-add

A **monorepo-only** overlay that scaffolds a new package directory and registers
it in the workspace via the native toolchain add command (FR-007).
Runs `run_after: [bailiff-mod-base]`.

## What it produces

| Output | Lifecycle | Notes |
|---|---|---|
| `<dir>/<name>/package.json` (ts) | **task-output → seed-once** | Produced by `bun init` / `pnpm init`; `_skip_if_exists` guards against overwrite. |
| `<dir>/<name>/pyproject.toml` (python) | **task-output → seed-once** | Produced by `uv init` / `pdm init`; `_skip_if_exists` guards against overwrite. |
| `<dir>/<name>/go.mod` (go) | **task-output → seed-once** | Produced by `go mod init`; `_skip_if_exists` guards against overwrite. |
| `<dir>/<name>/Cargo.toml` (rust) | **task-output → seed-once** | Produced by `cargo new`; `_skip_if_exists` guards against overwrite. |

## Security

**SEC-001 / path-traversal guard**: `name` and `dir` are validated before any
`mkdir` runs. Inputs containing `/`, `\`, `..`, `.` (dot-only), or empty string
are rejected immediately with exit 1 and zero side effects.

## Native workspace registration (FR-007)

After the package is scaffolded, the appropriate native add command registers it
in the monorepo workspace:

| Lang | Manager | Command |
|---|---|---|
| ts | pnpm | `pnpm add --workspace <dir>/<name>` |
| ts | bun | `bun add <dir>/<name>` |
| python | uv | `uv add --workspace <dir>/<name>` |
| rust | cargo | `cargo add --path <dir>/<name>` |
| go | go | `go work use <dir>/<name>` |

## Ordering & gating

- `run_after: [bailiff-mod-base]` — base fully applied before this overlay.
- Gated on `layout == 'monorepo'`; all tasks are no-ops on `single` layout.
- `js_pkg_manager` is threaded from bailiff-mod-base via `default: "{{ js_pkg_manager }}"`.

## Prerequisites (FR-007b)

Language-specific tool must be on PATH before applying:

- **ts/bun**: [bun](https://bun.sh/docs/installation)
- **ts/pnpm**: [pnpm](https://pnpm.io/installation)
- **python/uv**: [uv](https://docs.astral.sh/uv/getting-started/installation/)
- **python/pdm**: [pdm](https://pdm-project.org/en/latest/#installation)
- **rust**: [cargo](https://rustup.rs/)
- **go**: [go](https://go.dev/doc/install)

## Usage

```sh
uv run scripts/bailiff.py init --run-spec <run-spec with [bailiff-mod-base, bailiff-mod-package-add]>
```

Or copier-only (monorepo projects only):

```sh
copier copy --trust https://github.com/bailiff-io/bailiff-mod-package-add.git <destination>
```
