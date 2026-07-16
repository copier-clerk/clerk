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

## 2. mise integration pattern (FR-006) — agent-frozen union → single writer (CRITIQUE M1)

**CRITICAL**: shared accreting files are NOT built by runtime accumulation across layers. With the
ordering tie-break = lexicographic basename (`ordering.py:11`) and every layer `run_after:
[bailiff-mod-base]`, a later-sorting layer CANNOT reliably read an earlier one's answer via the
`init_many` accumulator, and two managed writers to one file overwrite (not append). The proven,
buildable pattern is the existing `gitignore_stack` (base `copier.yml:124-188`, help: "bailiff
**injects** this"): the **phase-1 agent freezes a UNION answer** and injects it via `--data`, and a
**single designated module writes the file**.

- **`mise_tools`** is a frozen union answer (yaml, default `[]`): the phase-1 agent, knowing the whole
  selection, injects the full `[tools]` set (e.g. `{python: "3.13", node: "22", ...}`) via `--data`.
- **`bailiff-mod-base` is the single writer** of `.mise.toml` (**managed** render from `mise_tools`).
  Language/tool modules do NOT each write `.mise.toml`; they merely contribute their token to the
  frozen `mise_tools` union the agent assembles (exactly as they contribute to `gitignore_stack`).
- The module's FIRST `_task` is the preflight: `command -v mise >/dev/null || { echo "install mise:
  https://mise.jdx.dev"; exit 1; }` then `mise install`. **Init-only-guarded (FR-012a)** via a
  committed sentinel so reproduce over a populated tree does not re-shell.
- Because `mise install` pins versions, native-init output below is task-output (ADR-0007).
- Ubiquitous tools not in the mise registry (`git`, `gh`, `gitnr`) stay a `command -v` check in base's
  preflight — mise is the pin surface for language/build toolchains, not literally every binary.

## 3. Native-command scaffold pattern (FR-007 / ADR-0007)

- Initial manifest = the tool's own init as a trust-gated `_task`, **init-only-guarded** (FR-012a):
  `test -f <manifest> || <tool> init …`. The manifest is **task-output** (process-deterministic),
  then **seed-once** (`_skip_if_exists`) so a populated-tree re-run never clobbers project edits.
  **Reproduce note (critique R5):** over the normal committed tree the guard + `_skip_if_exists` mean
  the committed manifest is used verbatim (config-consistent, NOT regenerated, no toolchain needed); the
  native tool only runs on a genuinely empty tree. Loop tests assert manifest *presence/structure* on
  reproduce, never regeneration.
- Per language: `uv init` (python), `bun init`/`pnpm init` (ts, per `js_pkg_manager`), `cargo new`
  (rust, `--lib` when lib), `go mod init` (go), `cdk init app --language=` (cdk). Adding deps later
  (package-add) = native `add` command, never manifest edits.
- Config bailiff owns and the tool does NOT generate stays a **managed** config-consistent render
  (`.tflint.hcl`, `.cfnlintrc.yaml`, CI files, ruff config beyond init, `.mise.toml`).
- NEVER an irreversible action at scaffold (no `cdk bootstrap`/`deploy`, `terraform apply`,
  `sam deploy`; `gh repo create` only behind the public-repo consent gate).

## 4. hook_manager threading contract — agent-frozen union → single writer (CRITIQUE M1)

Same fix as §2 — NOT runtime accumulation (the circular case: precommit needs languages'
`hook_blocks`, languages need precommit's `hook_manager`; unresolvable at runtime with basename
ordering). Resolved by freezing both up front:

- **`hook_manager`** (str, `[pre-commit,lefthook,none]=pre-commit`) and **`hook_blocks`** (yaml union,
  default `[]`) are BOTH frozen by the phase-1 agent and injected via `--data`. The agent knows the
  whole selection, so it assembles the union of language hook blocks and the chosen manager up front.
- **`bailiff-mod-precommit` is the single writer** of the hook config file: `.pre-commit-config.yaml`
  (pre-commit), `lefthook.yml` (lefthook), or nothing (`none`) — rendered from `hook_manager` +
  `hook_blocks` + its own base hooks. Language modules do NOT write the hook file; they contribute
  their block to the frozen `hook_blocks` union.
- `bailiff-mod-justfile`'s `lint` recipe reads the frozen `hook_manager` to emit the right invocation.
- When `hook_manager=none`, no hook file is written and `hook_blocks` is inert.
- `install_hooks` task is **init-only-guarded** (FR-012a).

## 5. quality_languages threading contract — agent-frozen union → single writer (CRITIQUE M1)

Same fix as §2 and §4:

- **`quality_languages`** (yaml, default `[]`) is a frozen union answer injected by the phase-1 agent via
  `--data`. The agent assembles the set of active language identifiers (e.g. `["python", "typescript"]`)
  from the full module selection.
- **`bailiff-mod-quality` is the single writer** of `.agents/hooks/quality-languages` — a **managed** render
  from `quality_languages`. Language modules do NOT each write this file; they contribute their language
  token to the frozen `quality_languages` union the agent assembles.
- When `quality_languages` is empty (no language modules selected), the file is omitted.

## 6. Agent-frozen `--data` facts (FR-010)

- `bailiff-mod-ci` and `bailiff-mod-stack-adr` sort BEFORE language layers (alphabetical basename
  tie-break), so they CANNOT read language answers via the run-order accumulator. The phase-1 agent
  MUST inject their sizing facts directly as frozen `--data` answers: `ci_languages` + per-language
  facts (manager, version, image, test command) + `ci_model` for CI; stack pins/framework/rationale
  for stack-adr. Reproduce replays the frozen answers; no agent in the reproduce path.
- Everything a module CAN get from an upstream layer it already ran after uses copier
  `default: "{{ upstream_answer }}"` threading via the `init_many` accumulator (verified available).
- **Accreting-file unions are frozen, not accumulated (M1):** `gitignore_stack`, `mise_tools`,
  `hook_manager`+`hook_blocks`, and `quality_languages` are ALL agent-frozen union answers injected via
  `--data` to a single designated writer — NEVER built by later layers reading earlier layers at
  runtime (basename ordering + persisted-only accumulator make that unreliable/circular). This is the
  established `gitignore_stack` contract, applied uniformly. Single writers: base → `.gitignore`,
  base → `.mise.toml`, precommit → hook config file, quality → `.agents/hooks/quality-languages`.

## 7. Determinism / trust / secrets (unchanged constitution rules)

- No `jinja2_time`; `today` injected as an answer (Constitution V). No `secret:` questions; tokens
  from ambient env in tasks (Constitution VI / FR-005). Code/network steps are trust-gated `_tasks`
  with the preflight ordered first (FR-009). Tool versions pinned via `.mise.toml`.

## 8. Contract-lint + test shape (every module — FR-021/FR-022)

- Ships `template/{{ _copier_conf.answers_file }}.jinja`, README, CHANGELOG (with `- - -`),
  three-way registration parity. `_subdirectory: template`.
- Loop test: hermetic init + reproduce, native/network tasks stubbed to offline marker writes (the
  `_copy_module_with_stub_tasks` pattern in `tests/conftest.py`). Byte-assert **managed** renders;
  presence/structure-assert **task-output**; `_skip_if_exists`-assert **seed-once**.
