# bailiff-mod-rust

The Rust **language overlay** — a copier layer that `run_after`
[`bailiff-mod-base`](https://github.com/bailiff-io/bailiff-mod-base) (spec 011).
Threads `project_name` from base; seeds a Cargo crate via `cargo new`
(task-output → seed-once); manages `rust-toolchain.toml` (channel pin) and
`rustfmt.toml` (max_width=100).

## What it produces

| Output | Lifecycle | Notes |
|---|---|---|
| `rust-toolchain.toml` | **managed** (byte-identical) | Pins `rust_channel`; reproduced exactly. |
| `rustfmt.toml` | **managed** (byte-identical) | max_width=100; use_small_heuristics from `rustfmt_heuristics`. |
| `Cargo.toml` | **task-output → seed-once** | Written by `cargo new`; `_skip_if_exists` protects project edits on reproduce. |
| `src/main.rs` or `src/lib.rs` | **task-output → seed-once** | Written by `cargo new`; `_skip_if_exists` protects on reproduce. |

## FIX: upstream bug

Passes `--lib` to `cargo new` when `crate_kind=lib`. Upstream omitted this flag.

## Ordering & threading

- `run_after: [bailiff-mod-base]` (hidden `when:false` answer).
- `project_name` and `hook_manager` use `default: "{{ <key> }}"` threading (FR-010).

## Agent-frozen union contributions (M1)

This module does NOT write shared accreting files itself. It contributes tokens
to the frozen unions the phase-1 agent assembles and injects via `--data`:

- **`gitignore_stack`** → `Rust` token; base is the single `.gitignore` writer.
- **`mise_tools`** → `{rust: "<channel>"}` + `{cargo-nextest: "latest"}` when `test_runner=nextest`; base is the single `.mise.toml` writer.
- **`hook_blocks`** → clippy `pre-commit-hooks-rust` block at `clippy_stage`; `bailiff-mod-precommit` is the single hook-config writer.

## nextest

When `test_runner=nextest`, the test command is `cargo nextest run`. nextest is
installed via mise (`mise_tools`), NOT via `cargo install` per-run (avoid re-building
from source at every scaffold).

## Prerequisites

This template runs a trust-gated preflight `_task`:

- **cargo / rustup** — <https://rustup.rs/>

## Usage

```sh
# Multi-layer (preferred — via bailiff):
uv run scripts/bailiff.py init --run-spec <run-spec with [bailiff-mod-base, bailiff-mod-rust]>

# Standalone (renders with defaults; cargo must be on PATH):
copier copy --trust https://github.com/bailiff-io/bailiff-mod-rust.git <destination>
```
