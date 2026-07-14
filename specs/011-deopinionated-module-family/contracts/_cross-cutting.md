# Cross-cutting contract — spec 011

Shared design every per-module contract references. Authored once here to keep the choice axes,
tooling patterns, and threading contracts consistent (FR-002).

## 1. Choice-axis keys (FR-002)

Use these EXACT keys/types/choices/defaults wherever a module touches the axis (full table in
[data-model.md](../data-model.md)): `python_pkg_manager [uv,pdm]=uv`, `js_pkg_manager
[bun,pnpm,npm]=bun`, `hook_manager [pre-commit,lefthook,none]=pre-commit`, `python_layout
[flat,src]=src`, `ts_linter [biome,eslint-prettier]=biome`, `ruff_line_length=88`,
`ruff_quote_style=double`, `ruff_rule_profile [standard,strict]=standard`, language version lists
(finite, modern default). Dead options (pip, pipenv, poetry, yarn, jest, husky, simple-git-hooks,
edition 2015, py<3.11) are NOT offered. Threaded axes use `default: "{{ <key> }}"` so a downstream
layer inherits the upstream answer without hardcoding which layer supplied it (FR-010 pattern).

## 2. mise integration pattern (FR-006)

- Each language/tool module contributes a `[tools]` entry for its toolchain to `.mise.toml`
  (**managed** render from the frozen version answer, e.g. `python = "{{ python_version }}"`).
- The module's FIRST `_task` is the preflight: `command -v mise >/dev/null || { echo "install mise:
  https://mise.jdx.dev"; exit 1; }` then `mise install` (installs+pins the toolchain). This replaces
  per-tool `command -v` checks — one preflight covers the module's whole toolchain.
- Because `mise install` pins versions, the native-init output below is deterministic enough to be
  task-output (ADR-0007).
- `.mise.toml` is a single shared file: when multiple language modules are selected, each contributes
  its own `[tools]` line — treat it like `gitignore_stack` (single managed writer keyed off the
  union of frozen tool answers) to avoid multi-writer conflicts. base owns the `.mise.toml` skeleton;
  language modules inject their tool token.

## 3. Native-command scaffold pattern (FR-007 / ADR-0007)

- Initial manifest = the tool's own init as a trust-gated `_task`, idempotency-guarded:
  `test -f <manifest> || <tool> init …`. The manifest is **task-output** (process-deterministic),
  then **seed-once** (`_skip_if_exists`) so a populated-tree re-run never clobbers project edits;
  a fresh-checkout reproduce regenerates it via the pinned tool.
- Per language: `uv init` (python), `bun init`/`pnpm init` (ts, per `js_pkg_manager`), `cargo new`
  (rust, `--lib` when lib), `go mod init` (go), `cdk init app --language=` (cdk). Adding deps later
  (package-add) = native `add` command, never manifest edits.
- Config clerk owns and the tool does NOT generate stays a **managed** byte-identical render
  (`.tflint.hcl`, `.cfnlintrc.yaml`, CI files, ruff config beyond init, `.mise.toml`).
- NEVER an irreversible action at scaffold (no `cdk bootstrap`/`deploy`, `terraform apply`,
  `sam deploy`; `gh repo create` only behind the public-repo consent gate).

## 4. hook_manager threading contract (owned by clerk-mod-precommit)

- `clerk-mod-precommit` owns the hook config file: `.pre-commit-config.yaml` (pre-commit),
  `lefthook.yml` (lefthook), or nothing (`none`). It is the single writer.
- Each language module declares `hook_manager` (`default: "{{ hook_manager }}"`, standalone default
  `pre-commit`) and contributes its language's hook block via the same shared-list mechanism as
  `gitignore_stack`: a `hook_blocks` (or per-manager) answer the precommit module consumes — NOT by
  each language writing the hook file itself (avoids double-append / non-idempotent reproduce).
- `clerk-mod-justfile`'s `lint` recipe reads `hook_manager` to emit the right invocation
  (`pre-commit run --all-files` vs `lefthook run pre-commit`).
- When `hook_manager=none`, no hook file is written and language hook contributions are inert.

## 5. Agent-frozen `--data` facts (FR-010)

- `clerk-mod-ci` and `clerk-mod-stack-adr` sort BEFORE language layers (alphabetical basename
  tie-break), so they CANNOT read language answers via the run-order accumulator. The phase-1 agent
  MUST inject their sizing facts directly as frozen `--data` answers: `ci_languages` + per-language
  facts (manager, version, image, test command) + `ci_model` for CI; stack pins/framework/rationale
  for stack-adr. Reproduce replays the frozen answers; no agent in the reproduce path.
- Everything a module CAN get from an upstream layer it already ran after uses copier
  `default: "{{ upstream_answer }}"` threading via the `init_many` accumulator (verified available).

## 6. Determinism / trust / secrets (unchanged constitution rules)

- No `jinja2_time`; `today` injected as an answer (Constitution V). No `secret:` questions; tokens
  from ambient env in tasks (Constitution VI / FR-005). Code/network steps are trust-gated `_tasks`
  with the preflight ordered first (FR-009). Tool versions pinned via `.mise.toml`.

## 7. Contract-lint + test shape (every module — FR-021/FR-022)

- Ships `template/{{ _copier_conf.answers_file }}.jinja`, README, CHANGELOG (with `- - -`),
  three-way registration parity. `_subdirectory: template`.
- Loop test: hermetic init + reproduce, native/network tasks stubbed to offline marker writes (the
  `_copy_module_with_stub_tasks` pattern in `tests/conftest.py`). Byte-assert **managed** renders;
  presence/structure-assert **task-output**; `_skip_if_exists`-assert **seed-once**.
