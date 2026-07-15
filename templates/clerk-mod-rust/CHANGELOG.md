# Changelog

All notable changes to `clerk-mod-rust` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial Rust language overlay (spec 011):
  - questions: `rust_channel` [stable,beta,nightly,esp]=stable,
    `rust_edition` [2024,2021,2018]=2024, `crate_kind` [bin,lib]=bin,
    `test_runner` [cargo-test,nextest]=nextest,
    `rustfmt_heuristics` [Default,Max,Off]=Max,
    `clippy_stage` [pre-push,pre-commit]=pre-push,
    `precommit_rust_rev` (injectable);
  - `run_after: [clerk-mod-base]` edge; threads `project_name` and `hook_manager`;
  - managed `rust-toolchain.toml` (channel pin) and `rustfmt.toml` (max_width=100);
  - init-only-guarded `cargo new` task (FIX: passes `--lib` when `crate_kind=lib`);
  - Cargo.toml and src/*.rs seed-once (`_skip_if_exists`);
  - contributes `gitignore_stack`, `mise_tools`, `hook_blocks` tokens for the
    agent-frozen union (M1 — single writers: base, base, precommit respectively).

- - -
## clerk-mod-rust-v0.1.0 - 2026-07-15
#### Features
- (**011**) implement clerk-mod-rust - (a6a6d2a) - Sjors Robroek
#### Bug Fixes
- (**011**) cargo init not new (non-empty dir), gitnr token casing (E2E) - (330c08a) - Sjors Robroek

- - -


