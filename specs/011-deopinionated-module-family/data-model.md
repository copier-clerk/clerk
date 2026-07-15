# Data Model — spec 011

The "data" here is the copier answer surface + the module registry. No database. Entities are
copier questions (answers), file-lifecycle classes, dependency edges, and the fan-out registry.

## Entity: Module

A `bailiff-mod-*` copier template.
- **name** (e.g. `bailiff-mod-python`) — the `templates/<name>/` dir, the fan-out repo stem, the
  cog package key, the catalog-sources stem. Three-way parity enforced by `check_modules.py`.
- **questions** — copier questions (see Choice-axis + per-module contracts).
- **outputs** — each classified: `managed` | `seed-once` | `task-output` (see Lifecycle).
- **edges** — `depends_on` / `run_after` / `run_before` (`when:false` hidden answers).
- **tasks** — ordered trust-gated `_tasks` (preflight first).
- **tests** — an init + reproduce loop test (hermetic; tasks stubbed).
- Required contract files: `copier.yml`, `template/{{ _copier_conf.answers_file }}.jinja`,
  `README.md`, `CHANGELOG.md` (with the `- - -` separator).

## Entity: Choice axis (cross-cutting)

A tooling decision expressed with a consistent key/type/choices/default across every module that
touches it (FR-002). Ratified axes:

| Axis key | Type | Choices | Default | Dropped |
|---|---|---|---|---|
| `python_pkg_manager` | str | uv, pdm | uv | poetry, pip, pipenv |
| `js_pkg_manager` | str | bun, pnpm, npm | bun | yarn |
| `hook_manager` | str | pre-commit, lefthook, none | pre-commit | husky, simple-git-hooks |
| `python_layout` | str | flat, src | src | — |
| `ts_linter` | str | biome, eslint-prettier | biome | — |
| `ruff_line_length` | str | 79, 88, 100, 119, 120 | 88 | — |
| `ruff_quote_style` | str | double, single | double | — |
| `ruff_rule_profile` | str | standard, strict | standard | (minimal folded away) |
| `python_version` | str | 3.11, 3.12, 3.13, 3.14 | 3.13 | 3.8–3.10 |
| `rust_channel` | str | stable, beta, nightly, esp | stable | — |
| `rust_edition` | str | 2024, 2021, 2018 | 2024 | 2015 |
| `test_runner` (rust) | str | cargo-test, nextest | nextest | — |
| `test_runner` (go) | str | go-test, gotestsum | go-test | — |
| `test_runner` (ts) | str | none, vitest-node, vitest-browser, vitest+playwright, bun-test, playwright-only | none | jest |
| test scaffolding (all) | bool/opt | — | OFF (opt-in) | — |

Version lists are subject to the meta-item CI auto-updater (out of module scope).

## Entity: File lifecycle class (per output)

- **managed** — bailiff owns; re-rendered byte-identically from committed answers (Constitution III
  strong form). Examples: dir `.gitkeep`, `.tflint.hcl`, `.cfnlintrc.yaml`, CI workflow files,
  `.mise.toml`, ruff config beyond tool init, `.copier-answers.yml`.
- **seed-once** — scaffolded once then project-owned; `_skip_if_exists`. Examples: `AGENTS.md`,
  tool manifests after native init, `README.md`, `justfile`, seeded IaC source, `STACK.md`/ADR.
- **task-output** — process-deterministic, produced by a native/network task; version-pinned via
  mise; NOT byte-asserted (Constitution III amended + ADR-0007). Examples: `pyproject.toml`/
  `package.json`/`Cargo.toml`/`go.mod` (native init), `.gitignore` (gitnr), `LICENSE` (gh),
  `.terraform.lock.hcl`, apm lock, CDK app files.

## Entity: Dependency edge

`when:false` hidden answers read statically from `copier.yml` (ADR-0003). Cross-module ordering is
recomputed at reproduce; tie-break alphabetical by basename. Key edges:
- language/quality/tooling/docs/agentic/iac modules → `run_after: [bailiff-mod-base]` (base is root).
- `bailiff-mod-precommit` owns the hook file; the phase-1 agent freezes `hook_manager` + the
  `hook_blocks` union up front and injects via `--data` (single writer — the `gitignore_stack`
  pattern; NOT runtime accumulation, which is circular/order-accidental — critique M1).
- `bailiff-mod-base` owns `.mise.toml`, written from the frozen `mise_tools` union (M1).
- `bailiff-mod-quality` owns `.agents/hooks/quality-languages` from the frozen `quality_languages`
  union (M1).
- `bailiff-mod-ci-github`/`bailiff-mod-ci-gitlab`, `bailiff-mod-stack-adr` sort before language layers →
  they DON'T read run-order answers; they consume agent-frozen `--data` facts instead.
- IaC modules: layout-independent overlay, `run_after: [bailiff-mod-base]` optional (also standalone).

## Entity: Agent-frozen fact / union

A phase-1 decision persisted as a `--data` answer (FR-010), the reproduce state for agent-tier
behavior. Two flavors:
- **single facts**: `ci_model` + `ci_languages` + per-language CI facts (ci modules);
  `architecture_md` + globs (base); stack facts/pins (stack-adr); `readme_body` when
  `readme_style=agent-draft`; `agentic_targets` + `mcp_servers` + `agentic_plugins` (agentic).
- **frozen unions (critique M1)** — accreting-file inputs the agent assembles across the whole
  selection and injects to a single writer, NEVER runtime-accumulated: `gitignore_stack` (base
  writes `.gitignore`/gitnr), `mise_tools` (base writes `.mise.toml`), `hook_manager`+`hook_blocks`
  (precommit writes the hook file), `quality_languages` (quality writes the hooks list).

## Entity: Fan-out registration (008b)

Per module, three-way parity: `templates/<name>/` dir == `cog.toml [monorepo.packages.<name>]` ==
`catalog-sources.toml [[sources]]` url stem. `just new-module` creates all three; `check_modules.py`
verifies. Mirror `bailiff-io/bailiff-mod-<name>` pre-created by hand (confirmed public action).
`bailiff-mod-apm` registration is REMOVED and migrated to `bailiff-mod-agentic` (catalog regen sequenced
WITH the apm tombstone — R6). `bailiff-mod-org-policy` is NOT registered (dropped — R1). CI registers as
two entries: `bailiff-mod-ci-github` + `bailiff-mod-ci-gitlab` (R3).

## Validation rules (from requirements)
- No `secret:` question on any module (FR-005 / Constitution VI); secrets-policy lint stays green.
- Every module passes `check_modules.py` (FR-021) and ships an init+reproduce loop test (FR-022).
- No new `src/bailiff/` code (FR-011 / C-11).
- No irreversible cloud action at scaffold time (FR-009).
- No 011 module released until Constitution III amended + ADR-0007 landed (FR-019/SC-008).
