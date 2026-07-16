# bailiff-mod-rust

The Rust **language overlay** — a copier layer that `depends_on`
[`bailiff-mod-base`](https://github.com/bailiff-io/bailiff-mod-base) (spec 014).
Reads `project_name` from base and `hook_manager` from precommit via `_external_data`
aliases; seeds a Cargo crate via `cargo init` (task-output → seed-once); manages
`rust-toolchain.toml` (channel pin) and `rustfmt.toml` (max_width=100).

## What it produces

| Output | Lifecycle | Notes |
|---|---|---|
| `rust-toolchain.toml` | **managed** (config-consistent) | Pins `rust_channel`; reproduced every run. |
| `rustfmt.toml` | **managed** (config-consistent) | max_width=100; `use_small_heuristics` from `rustfmt_heuristics`. |
| `.mise/conf.d/bailiff-mod-rust.toml` | **managed** | rust + optional cargo-nextest; merged natively by mise (FR-008). |
| `.pre-commit.d/bailiff-mod-rust.yaml` | **managed** | clippy hook fragment; bundled by bailiff-mod-precommit's `_post_task`. |
| `.gitignore.d/bailiff-mod-rust` | **managed** | `/target`, `Cargo.lock`; folded by bailiff-mod-base's `_post_task`. |
| `Cargo.toml` | **task-output → seed-once** | Written by `cargo init`; `_skip_if_exists` protects project edits on reproduce. |
| `src/main.rs` or `src/lib.rs` | **task-output → seed-once** | Written by `cargo init`; `_skip_if_exists` protects on reproduce. |

## FIX: upstream bug

Passes `--lib` to `cargo init` when `crate_kind=lib`. Upstream omitted this flag.

## Ordering & facts

- `depends_on: [bailiff-mod-base]` (hidden `when:false` answer); `phase: normal`.
- `project_name` reads `_external_data.base.project_name` (FR-004 / spec 014).
- `hook_manager` reads `_external_data.precommit.hook_manager` (from the `.pre-commit.d/` fragment template).
- `test_runner` is a bare-private question — `{cargo-test, nextest}` domains are disjoint from other modules (collision-class, no cross-layer alias).

## Fragment contributions (spec 014 model)

This module contributes to three surfaces via drop-in fragments; it DOES NOT write
the merged files directly:

- **`.mise/conf.d/bailiff-mod-rust.toml`** — rust toolchain + optional cargo-nextest.
  mise merges all `conf.d/*.toml` at runtime (FR-008/010). No `.mise.toml` is written.
- **`.pre-commit.d/bailiff-mod-rust.yaml`** — clippy hook block at `clippy_stage`.
  `bailiff-mod-precommit`'s `_post_task` bundler merges all `.pre-commit.d/*.yaml`.
- **`.gitignore.d/bailiff-mod-rust`** — `/target` + `Cargo.lock` static lines.
  `bailiff-mod-base`'s `_post_task` folds all `.gitignore.d/*` into `.gitignore`.

## nextest

When `test_runner=nextest`, the mise conf.d fragment adds `cargo-nextest = "latest"`.
nextest is installed via mise, NOT via `cargo install` per-run.

## Prerequisites

This template runs a trust-gated preflight `_task`:

- **cargo / rustup** — <https://rustup.rs/>

## Usage

```sh
# Multi-layer (preferred — via bailiff):
uvx bailiff init --run-spec <run-spec with [bailiff-mod-base, bailiff-mod-rust]>

# Standalone (renders with defaults; cargo must be on PATH):
copier copy --trust https://github.com/bailiff-io/bailiff-mod-rust.git <destination>
```
