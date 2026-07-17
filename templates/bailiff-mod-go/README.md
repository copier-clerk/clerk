# bailiff-mod-go

The Go **language overlay** — adds Go tooling (go mod, golangci-lint) as a
copier layer (spec 014). Reads `project_name` from
[`bailiff-mod-base`](https://github.com/bailiff-io/bailiff-mod-base) and
`hook_manager` from
[`bailiff-mod-precommit`](https://github.com/bailiff-io/bailiff-mod-precommit)
via `_external_data` aliases.

## What it produces

| Output | Lifecycle | Notes |
|---|---|---|
| `go.mod` | **task-output → seed-once** (`_skip_if_exists`) | Native `go mod init` on a fresh tree; `_skip_if_exists` preserves edits on reproduce. |
| `.golangci.yml` | **seed-once** (`_skip_if_exists`) | Sensible golangci-lint v2 defaults; user-tunable after init. |
| `cmd/<name>/main.go` | **seed-once** (`_skip_if_exists`) | Stub entry point for cli/service. **Omitted for library** (`_exclude` on cmd/). |
| `.mise/conf.d/bailiff-mod-go.toml` | **managed** | Go toolchain version fragment; mise merges all `conf.d/*.toml` natively. |
| `.pre-commit.d/bailiff-mod-go.yaml` | **managed** | golangci-lint hook block; bundled into `.pre-commit-config.yaml` by `bailiff-mod-precommit`'s `_post_task`. Omitted when `golangci_hook_rev` is empty. |
| `.gitignore.d/bailiff-mod-go` | **managed** | Go gitignore lines (binaries, test outputs, optionally `vendor/`); folded into `.gitignore` by `bailiff-mod-base`'s `_post_task`. |

## Questions

| Key | Choices / default | Notes |
|---|---|---|
| `go_version` | `1.23` / `1.22` / `1.21` (default `1.23`) | Pinned in `.mise/conf.d/bailiff-mod-go.toml` and `go.mod`. |
| `app_kind` | `cli` / `service` / `library` (default `cli`) | `library` drops `cmd/` entirely. |
| `test_runner` | `go-test` / `gotestsum` (default `go-test`) | Private — collision-class key (FR-007). `gotestsum` adds a mise tool entry. |
| `use_vendor_mode` | bool (default `false`) | When `true`, adds `vendor/` to the gitignore fragment. |
| `golangci_hook_rev` | str (default `""`) | Rev for the golangci-lint pre-commit hook block. Empty → hook block omitted from fragment. |

## Ordering & facts

- `depends_on: [bailiff-mod-base]` — base applies first (`_bailiff_phase: pre`); this module is `normal` phase.
- `project_name` read from base via `_external_data.base.project_name` (FR-004).
- `test_runner` is **bare-private** — collision-class across go/rust/ts; never threaded or aliased.
- No `hook_manager` dependency (R13): `.pre-commit.d/bailiff-mod-go.yaml` renders unconditionally; `bailiff-mod-precommit`'s bundler merges it when present.

## Prerequisites (FR-007b)

This template runs a trust-gated preflight `_task`; the source must be
trusted before it renders. The preflight checks:

- **go** — <https://go.dev/doc/install> (or `mise install go`)

## Usage

Prefer bailiff (multi-layer, in dependency order):

```sh
uvx bailiff init --run-spec <run-spec with [bailiff-mod-base, bailiff-mod-go]>
```

Copier-only (standalone; renders with defaults):

```sh
copier copy --trust https://github.com/bailiff-io/bailiff-mod-go.git <destination>
```
