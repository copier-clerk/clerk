# E2E Campaign — agent-driven validation + fuzzing

An orchestrating agent spawns multiple parallel test agents, each running a
category of real-world `clerk init` scenarios using `tests/e2e/harness.py`.
The harness uses REAL native tools (mise, uv, bun, cargo, go, gitnr, gh) —
NOT the stubbed loop tests. It is a live integration test, not a unit test.

## Prerequisites

```bash
export GITHUB_TOKEN=$(gh auth token)    # mise attestation + gh rate limits
# All tools installed: mise, uv, bun, pnpm, cargo, go, gitnr, gh, just, pre-commit, terraform, cdk
```

## Harness entry point

```python
from tests.e2e.harness import (
    run_scenario, expect_failure, check, runner, ClerkError
)
```

- `run_scenario(name, [(module, answers), ...])` → `Path` to the dest
- `expect_failure(name, [(module, answers), ...], match="")` → `(bool, str)`
- `check(condition, message, failures_list)` → prints PASS/FAIL, appends on fail

Each agent MUST set a unique `CLERK_E2E_ROOT` env var (e.g.
`/tmp/clerk-e2e-<agent-id>`) to avoid collision on the trust store / project dirs.

## Known answer-shape quirks

- `mise_tools`: list of single-key maps (`[{"python": "3.13"}]`), not a flat dict
- `gitignore_stack`: capitalized gitnr codes (`Python`, `Node`, `Go`, `Rust`)
- `hook_blocks` / `quality_languages`: agent-frozen union lists, default `[]`
- `ci_languages` / `ci_lang_facts`: agent-frozen data, per-language sizing facts
- Modules in ordered dependency chains (`run_after` edges); base always first
- `hook_manager` and `js_pkg_manager` are THREADED via `default: "{{ key }}"` when
  a module is used downstream — when invoked standalone, pass the value explicitly

## Campaign categories (one agent each, run in parallel)

### 1. VALID-MATRIX — all language overlays with various options

For each language (python, ts, go, rust), iterate combinations:
- python: uv/pdm × flat/src × 3.13/3.12 × ruff standard/strict
- ts: bun/pnpm × biome/eslint-prettier × none/vitest-node test-runner
- go: cli/service/library × go-test/gotestsum × vendor on/off
- rust: bin/lib × stable/nightly × cargo-test/nextest

Assert: init succeeds, correct manifest exists, managed configs render correctly,
reproduce preserves manifests verbatim.

### 2. FULL-STACK — multi-module realistic stacks

Compose 4-6 modules per project as a real-world team would:
- Python web service: base + precommit + python + quality + ci-github + agentic
- TS monorepo: base + precommit + ts + justfile + ci-github
- Go CLI: base + precommit + go + quality + justfile + github-repo
- Rust service: base + precommit + rust + ci-gitlab + terraform

Assert: all modules' outputs co-exist without file collision, threading works
(hook_blocks from multiple languages render in precommit), reproduce replays all.

### 3. IaC — infrastructure-as-code family

- Terraform: terraform/opentofu × each placement_dir
- CDK: typescript/python × include_cdk_nag on/off × include_synth_validate on/off
- CloudFormation: raw/sam × 1/3 environments × cfnlint_version set/unset

Assert: no cloud action ever runs (never terraform apply, cdk bootstrap, sam deploy),
managed configs byte-identical on reproduce, seed-once files survive edits.

### 4. BROKEN — deliberately invalid inputs that SHOULD fail loudly

- package-add: path-traversal inputs (`../`, `.`, `\\`, empty) → exit 1 zero side effects
- package-add: layout != monorepo → no-op exit 0
- agentic: `install_via_apm=true` + `apm_packages=[]` → validator refusal (R2)
- ci-github: `ci_languages=[]` + `monorepo_tool=none` → loud warning render
- github-repo: `visibility=public` without consent flag → hard abort exit 1
- base: no `secret:` questions in any module (verified by: check copier.yml)
- any module with an answer value not in `choices:` → copier validation error

Use `expect_failure()` for all of these. Also assert no partial writes for
abort cases (dest should be empty or contain only prior layers).

### 5. FUZZ — random valid answer generation

Programmatically enumerate each module's `copier.yml` questions: read choices,
types, defaults. Generate random valid values for each question and run init
with randomized stacks (2-4 modules, random selection). Run N=20 iterations.

Assert: every run either succeeds cleanly OR raises ClerkError with a message
(never an unhandled exception, never a Jinja UndefinedError, never a partial
render that leaves no error). Capture any crash as a finding with full answers.

## Reporting format

Each agent returns a structured report:

```
CATEGORY: <category-name>
SCENARIOS_RUN: <int>
PASSED: <int>
FAILED: <int>
FINDINGS:
  - scenario: <name>
    answers: <compact JSON>
    error: <traceback or assertion text, first 500 chars>
    classification: bug | design-gap | documentation | infra
```

## How to continue

1. Read `tests/e2e/harness.py` for the exact API.
2. Read `templates/clerk-mod-*/copier.yml` for each module's question schema.
3. Set unique `CLERK_E2E_ROOT`, run scenarios, report findings.
4. For any bug found: create a targeted reproducer (minimal answers), note the
   root cause (template logic, answer shape, init_many ordering), suggest fix.
