# bailiff-mod-go

The Go **language overlay** — adds Go tooling (go mod, golangci-lint) as a
copier layer that `run_after`
[`bailiff-mod-base`](https://github.com/bailiff-io/bailiff-mod-base) (spec 011).
Threads `project_name` from base; seeds `go.mod` via `go mod init`
(task-output → seed-once); seeds `.golangci.yml` (seed-once) and
`cmd/<name>/main.go` stub for cli/service app kinds.

## What it produces

| Output | Lifecycle | Notes |
|---|---|---|
| `go.mod` | **task-output → seed-once** (`_skip_if_exists`) | Native `go mod init` on a fresh tree; `_skip_if_exists` preserves edits on reproduce. |
| `.golangci.yml` | **seed-once** (`_skip_if_exists`) | Sensible golangci-lint v2 defaults; user-tunable after init. |
| `cmd/<name>/main.go` | **seed-once** (`_skip_if_exists`) | Stub entry point for cli/service. **Omitted for library** (`_exclude` on cmd/). |
| Go `.gitignore` entries | **agent-frozen union** (via base) | Contributed to `gitignore_stack`; base is the single writer of `.gitignore`. |
| go version in `.mise.toml` | **agent-frozen union** (via base) | Contributed to `mise_tools`; base is the single writer of `.mise.toml`. |
| golangci hook block | **agent-frozen union** (via precommit) | Contributed to `hook_blocks`; precommit is the single writer of the hook config file. |

## Questions

| Key | Choices / default | Notes |
|---|---|---|
| `go_version` | `1.23` / `1.22` / `1.21` (default `1.23`) | Pinned in `mise_tools` and `go.mod`. |
| `app_kind` | `cli` / `service` / `library` (default `cli`) | `library` drops `cmd/` entirely. |
| `test_runner` | `go-test` / `gotestsum` (default `go-test`) | `gotestsum` adds a `mise_tools` entry. |
| `use_vendor_mode` | bool (default `false`) | When `true`, adds `vendor/` to the Go gitignore token. |
| `golangci_hook_rev` | str (default `""`) | Rev for the golangci-lint pre-commit hook block. |

## Ordering & threading

- `run_after: [bailiff-mod-base]` — base applies first; `project_name` is
  threaded via `default: "{{ project_name }}"` (ADR-0003, FR-010).
- `gitignore_stack`, `mise_tools`, `hook_blocks` are **agent-frozen union**
  answers injected via `--data` by the phase-1 agent (M1). This module
  contributes its tokens but does NOT write `.gitignore`, `.mise.toml`, or
  the hook config file.

## Prerequisites (FR-007b)

This template runs a trust-gated preflight `_task`; the source must be
trusted before it renders. The preflight checks:

- **go** — <https://go.dev/doc/install> (or `mise install go`)

## Usage

Prefer bailiff (multi-layer, in dependency order):

```sh
uv run scripts/bailiff.py init --run-spec <run-spec with [bailiff-mod-base, bailiff-mod-go]>
```

Copier-only (standalone; renders with defaults):

```sh
copier copy --trust https://github.com/bailiff-io/bailiff-mod-go.git <destination>
```
