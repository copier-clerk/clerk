# Quickstart — validating spec 011

How to prove the de-opinionated family works end to end. Not implementation — a run/validation
guide. Detail lives in [contracts/](./contracts/) and [data-model.md](./data-model.md).

## Prerequisites
- The bailiff repo on the `009-phase-1-3-module-port` branch (spec dir `011-deopinionated-module-family`).
- `uv` (test runner), `copier>=9.16,<10`, `just`, `mise` available.
- **Governance gate (FR-019) landed**: Constitution III at v2.3.0 + `docs/decisions/0007-native-command-scaffolding.md` present. No module release before this. Verify: `grep 'Version.*2.3.0' .specify/memory/constitution.md && test -f docs/decisions/0007-native-command-scaffolding.md`.

## 1. Contract lint (FR-021)
```
just check-modules
```
Expected: `ok — N module(s) checked` once modules are authored. Fails loudly on missing answers-file
`.jinja`, README, CHANGELOG `- - -` separator, or three-way registration drift.

## 2. Secrets policy (FR-005 / Constitution VI)
```
uv run pytest tests/loop/test_secrets_policy.py -q
```
Expected: green — no module declares a `secret:` question.

## 3. De-opinionation spot-check (SC-001)
For any authored module, confirm its consequential tooling axes are `choices:` with the ratified
defaults and NO dead options:
```
uv run python -c "import yaml,sys; d=yaml.safe_load(open('templates/bailiff-mod-ts/copier.yml')); \
print(d['js_pkg_manager']['choices'], d['js_pkg_manager']['default'])"
# expect ['bun','pnpm','npm'] bun ; and no 'yarn'
```

## 4. Language overlay init + reproduce (US1/US2, SC-002)
Run the targeted loop tests (hermetic; native/network tasks stubbed offline):
```
uv run pytest tests/loop/test_python_overlay.py tests/loop/test_ts_overlay.py -q
```
Expected: base renders before the overlay (edge order), the native-init manifest marker is present
(task-output), managed config (ruff/tsconfig) is config-consistent, the frozen `mise_tools` + gitignore
tokens are present. Reproduce over the committed tree: managed re-renders config-consistently and the
committed manifest is used **verbatim** (init-only guard + `_skip_if_exists` → NOT regenerated, no
toolchain/network needed — critique R5/M3). Assert manifest *presence/structure*, never regeneration.
An edited manifest on a re-run is preserved.

## 5. Agentic rollup (US3, SC-003)
```
uv run pytest tests/loop/test_agentic_*.py -q
```
Expected: any subset of `[claude, codex, opencode, kiro]` renders disjoint per-target config; empty
selection is a clean no-op (no refusal); `install_via_apm` + a non-marketplace target uses the APM
path; MCP env values render as `${VAR}` refs (no secret question).

## 6. Multi-model CI (US4, SC-004) — two modules
```
uv run pytest tests/loop/test_ci_github_*.py tests/loop/test_ci_gitlab_*.py -q
```
Expected: for EACH of `bailiff-mod-ci-github` and `bailiff-mod-ci-gitlab`, all 5 models render valid,
host-lint-clean (actionlint / gitlab-ci lint — valid YAML ≠ valid workflow) CI sized to a 2-language
`ci_languages` fact — minimal no gate, standard gate, optimized change-filters; no `:latest`/unpinned
refs; GitHub artifact majors match; GitLab change-gated `needs:` use `optional: true`; `merge-queue` +
`gitlab_tier=free` → fallback + warning; empty `ci_languages` + `monorepo_tool==none` → loud warning,
not silent (R4). Pure render → reproduce config-consistent.

## 7. IaC trio (US5, SC-005)
```
uv run pytest tests/loop/test_terraform.py tests/loop/test_cdk.py tests/loop/test_cloudformation.py -q
```
Expected: terraform seeds HCL under `placement_dir` with managed versions.tf + seed-once main/backend
and a stubbed `init` producing the lock; cdk runs a stubbed `cdk init` (never bootstrap/deploy),
commits `cdk.context.json`; cloudformation renders raw vs sam templates (Transform only in sam) + per-env
params. No irreversible cloud action.

## 8. Thin base (US6, SC-006)
```
uv run pytest tests/loop/test_base_render.py -q
```
Expected: only the thinned always-on set (`docs/`+lean subdirs, `scripts/`, `tests/`, minimal `.github/`
when `github_host`); `.agents/`/`.codex/`/`infrastructure/`/`.github/workflows/`/`specs/`/`archive/`/`assets/`
ABSENT; `extra_dirs`/`branch_strategy`/`copyright_name`/`run_git_init` honored.

## 9. Full suite + types + lint (US7, SC-007)
```
just test && just lint
```
Expected: green. (No `just vendor`/`check-vendor` needed — C-11 holds, no vendored source touched.)

## 10. Release (SC-009 — CONFIRMED, not part of validation)
Publishing mirrors + releases + the apm tombstone (FR-020/FR-023) is a maintainer-confirmed batch,
never run unattended. Do NOT run the 008b fan-out as part of validating this spec.
