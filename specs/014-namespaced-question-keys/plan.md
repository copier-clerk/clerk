# Implementation Plan: Private-by-default answer threading, `_external_data` facts, and the universal fragment/merge model (spec 014)

**Branch**: `014-namespaced-question-keys` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)

**Input**: [spec.md](./spec.md) (FR-001..020, SC-001..008) + the ratified
[decisions-ledger.md](./decisions-ledger.md) (§RATIFIED R1–R10 + FR-006 inversion; all
NEEDS-CLARIFICATION closed, dependency model redesigned via the 2026-07-16 grill + engineering
critique). Governed by the constitution (v3.0.0) and ADRs 0001–0008. Amends the 011 cross-cutting
contract (`specs/011-.../contracts/_cross-cutting.md`) per FR-018; also supersedes 011's edge
vocabulary (`run_after`/`run_before` → single `depends_on` + phases).

## Summary

Kill a whole CLASS of cross-module answer-poisoning bugs (the shipped `framework` collision;
the latent `test_runner` one) with five coordinated moves:

1. **Engine — private-by-default threading**: `init_many` stops accreting every prior layer's
   answers into the next layer's `data=` (`_merge_layer_answers`, runner.py:532/484); `accumulated`
   stays `{today}` (seeded runner.py:430; NO run-level `--data` channel exists — cli.py:286). A
   module's questions become layer-local and *cannot* leak. Reproduce gets the same isolation.
2. **Cross-module facts via `_external_data`, ENFORCED as hard data-deps** (no vendor prefix): the
   ratified fact set — **base** (`project_name`, `layout`, `description`,
   `default_branch`-NEW) + **precommit** (`hook_manager`) + **ts** (`js_pkg_manager`, `ts_linter`) +
   **moon** (`monorepo_tool`, `monorepo_packages`) — read via consumer aliases. bailiff statically
   parses the aliases and REQUIRES each producer present + ordered-before (FR-006 inverted: absent →
   loud error, not silent fallback). `default_branch` NEW to base (fixes a latent bug); `github_host`
   is NOT a fact — R12/FR-022 deletes it from base (see move 6).
3. **Dependency model** — single `depends_on` edge (drop `run_after`/`run_before`); pre/normal/post
   stratified DAG with edge-legality validation (`base`=pre, family=normal, `post` reserved).
   Side-effect deps use `depends_on`; data deps use `_external_data` — both hard-enforced + ordering.
4. **Universal fragment/merge model** — every cross-module "union" deleted. Each module writes its
   OWN fragment to a `.d/` directory; combined by the tool's NATIVE drop-in (mise) or the merged-file
   owner (pre-commit: one vendored Python bundler in `bailiff-mod-precommit`, highest-pin-wins+warn on
   rev-pin conflict; gitignore: idempotent inline concat). Engine does ZERO merging.
5. **Migration gate** — `_bailiff_schema: 014` marker + refuse-on-mismatch in `reproduce_many` (copier
   silently ignores stale keys, so bailiff must produce the loud error SC-006 requires).
6. **Forge metadata cleanup (R12 / FR-022..024)** — base stops emitting forge-specific files: the
   `{% if github_host %}.github{% endif %}/` tree (CODEOWNERS, ISSUE_TEMPLATE, PULL_REQUEST_TEMPLATE)
   MOVES to `bailiff-mod-github-repo`; a `.gitlab/` equivalent is ADDED to `bailiff-mod-gitlab-repo`.
   `github_host` is DELETED from base (not replaced by any selector — nothing forge-specific remains in
   base). `bailiff-mod-dep-updates` self-defaults `dep_update_tool` (was reading `github_host`).
   `github-repo`/`gitlab-repo` gain `create_remote: bool` (default false) — creation is now conditional;
   `create_remote=false` still renders the metadata (adopt-existing-repo path). No new module; no import
   of live remote state. This is a module-structure change, so `check_modules` and the collision check
   must stay green through the file moves.

Plus non-code deliverables: FR-018 module-authoring doc rewrite, a documented migration BREAK (no
shim), and a full 27-mirror re-fanout. LARGE multi-agent job, spec-011 shape: worktree-isolated
parallel module rewrites over a settled contract.

## Technical Context

**Language/Version**: Python 3.11+ for the engine changes — `src/bailiff/runner.py` (threading +
`_external_data` validation + `_bailiff_schema` gate), `src/bailiff/ordering.py` (single-edge +
stratified DAG), `src/bailiff/discovery.py` (static `_external_data` parse + path lint) — plus the
vendored pre-commit bundler shipped as template content. Everything else is copier YAML + Jinja
templates + shell `_tasks` + governance/docs prose. `scripts/check_modules.py` is the lint gate.

**Primary Dependencies**: copier `>=9.16,<10` — specifically its `_external_data` mechanism
(verified 2026-07-16: namespaced, opt-in cross-template reads via `_external_data.<alias>.<key>`,
does not pollute the consumer's answers file) and its default template isolation (one answers
file per template). `mise` — its `.mise/conf.d/*.toml` drop-in merge (verified against mise
source `config_root.rs`: `.mise/conf.d` is a config root, merged at runtime). The spec-003
`init_many`/`reproduce_many` engine (the threading paths being changed). `gitnr` (pinned 0.3.0),
`gh`, `git` as before. The pre-commit bundler needs only Python + PyYAML (already present).

**Storage**: N/A — files rendered/generated into the project tree; per-layer state in each
`.copier-answers.<module-basename>.yml` (`ordering.py:answers_file_name`, the deterministic name
`_external_data` aliases point at). No new persistent state.

**Testing**: `pytest` init+reproduce loop tests under `tests/loop/` + the combination integration
suite under `tests/integration/` (33 tests, 5 stacks). New: a negative **isolation** test (two layers,
same bare key, disjoint domains → no bleed, SC-001/SC-007); an `_external_data` fact test
(present-producer resolves; **absent-producer → loud error**, SC-002); a mise conf.d merge test
(SC-003); an order-independent pre-commit merge test incl. **rev-pin highest-wins+warn** (SC-004); a
dependency-model test (single `depends_on`; forward cross-phase edge rejected; `_bailiff_schema` gate
refuses a pre-014 tree — SC-008). `just check-modules` stays the contract gate.

**Target Platform**: developer/CI shells (macOS/Linux/WSL); copier CLI + `settings.yml` trust.

**Project Type**: copier template family authored in a monorepo, fanned out per-repo (ADR-0006);
consumed as multi-template layers (ADR-0003). One packaged CLI (`bailiff` on PyPI); 014 touches its
engine across runner/ordering/discovery (all under the 013 C-11 exception).

**Performance Goals**: N/A (scaffold-time tooling; no hot path).

**Constraints**: reproduce is faithful + agent-free (Constitution III); the guarantee is relaxed
from **byte-identical** to **config-consistent** for merged artifacts (a YAML re-emit / append
cannot be byte-identical) — single-module MANAGED renders stay deterministic. NO `jinja2_time`
(V); NO `secret:` questions (VI). The engine footprint (13 exception) spans runner.py (threading +
`_external_data` validation + schema gate), ordering.py (single-edge + stratified DAG), discovery.py
(static `_external_data` parse + path lint). No `bailiff merge` CLI — fragment merging is owner-side
vendored/inline so a generated project never depends on the bailiff CLI at render/reproduce time.

**Scale/Scope**: engine changes across 3 modules (runner/ordering/discovery) + base gains
`default_branch` and loses `mise_tools`/`gitignore_stack` unions + ~all 27 modules touched:
tool-contributors → `.mise/conf.d/` drop-ins (~10); hook-contributors → `.pre-commit.d/` fragments +
precommit gains the bundler; gitignore contributors → `.gitignore.d/` + the concat; fact-consumers →
`_external_data` aliases (~19 for `project_name`, +7 for `hook_manager`, etc.); ~25 modules migrate
`run_after: base` → `depends_on: base` + gain a `phase`. Plus FR-018 doc rewrite + migration break +
27-mirror re-fanout.

## Constitution Check

*GATE: evaluated before Phase 0; re-checked after design. No amendment required (engine change
is the 013-established C-11 exception; the byte→config invariant reframe already landed as prose
on main, `498315f`).*

| Principle | Verdict | How spec 014 satisfies it |
|---|---|---|
| **I — Skills + Templates + Minimal Glue (C-11)** | PASS (larger footprint, justified) | The threading change is a *removal* of glue (deletes the bespoke cross-layer bleed, delegates reads to copier-native `_external_data`). The ADDED engine surface — `_external_data` static-parse + validation, the single-edge + stratified-DAG rewrite of `ordering.py`, the `_bailiff_schema` gate — is coordination logic copier cannot do (validating cross-template data-deps, ordering, migration safety), which is exactly the C-11-sanctioned glue category, not a copier re-implementation. No `bailiff merge` CLI (owner-side vendored merging). 013 governs the engine touch; Complexity Tracking records the widened footprint. |
| **II — Two-Phase; skill conducts, helpers execute** | PASS | Agent-tier facts (stack facts, CI facts) stay phase-1 `--data` answers; the reproduce path stays agent-free. `_external_data` resolution is copier-deterministic. The pre-commit bundler runs as a deterministic `_post_task` (bailiff-run, after the render loop), no LLM. |
| **III — Reproduce is faithful + agent-free** | PASS | Managed single-module renders stay byte-identical; merged artifacts are **config-consistent** (same tools/hooks/ignore rules) — the invariant reframe already ratified + prose-swept (main `498315f`). Reproduce accumulator gets the SAME private isolation (FR-003) so it reconstructs per-layer, not a flattened namespace. |
| **IV — copier CLI + static config** | PASS | `_external_data` is copier's supported public mechanism; edges stay `when:false` hidden answers statically read; no Template/Worker adapter. |
| **V — Determinism via pinning; trust by source** | PASS | conf.d/fragment/merge tasks are trust-gated + init-only-guarded as today; tool versions pinned via mise; `today`/facts injected, no `jinja2_time`. |
| **VI — Template-author contract** | PASS | Every module keeps its answers-file `.jinja`, `when:false` edges, clean tags. NO `secret:` questions. The `_external_data` alias is a new *authoring* pattern documented in FR-018, not a contract violation. |
| **VII — Hardening is per-step** | PASS | 014 lands its own determinism + isolation tests (SC-001..008), incl. the negative isolation test, the absent-producer loud-error test, the rev-pin highest-wins+warn test, and the dependency-model tests (single edge, forward-cross-phase rejection, `_bailiff_schema` gate), before the re-fanout. |
| **VIII — Documented, dry-run-validated handoff** | PASS | Handoff stays copier answers documented in SKILL.md; `_external_data` aliases are declared in `copier.yml` and validated by copier's dry run. FR-018 documents the new authoring format. |

**No unjustified violations.** No constitution amendment is needed: the byte→config invariant
relaxation already landed as ratified prose on main; the engine touch is 013's standing exception.
Complexity Tracking notes the deliberate migration break only.

## Project Structure

### Documentation (this feature)

```text
specs/014-namespaced-question-keys/
├── spec.md              # the spec (source of truth) — RATIFIED
├── decisions-ledger.md  # ratified research + R1–R10 decisions (+ FR-006 inversion) — RATIFIED
├── plan.md              # this file
├── research.md          # Phase 0 — consolidated copier/mise verification + cross-module fact audit
├── data-model.md        # Phase 1 — fact set, .d/ directory contracts, fragment shapes
├── contracts/           # Phase 1 — the rewritten cross-cutting contract + per-surface contracts
│   ├── _threading.md          # private-by-default engine contract + _external_data alias pattern
│   ├── _fragment-merge.md     # the universal .d/-dir + owner-side-merge contract (mise/precommit/gitignore)
│   └── _facts.md              # the ratified first-party fact set + producer/consumer wiring
├── quickstart.md        # Phase 1 — validate isolation + facts + merges end to end
└── tasks.md             # Phase 2 (/speckit.tasks — NOT created here)
```

### Changed source + template content (repository root)

```text
# Engine (C-11 013 exception — spans runner + ordering + discovery):
src/bailiff/runner.py            # private-by-default threading; _external_data validation; _post_tasks collect+run (init+reproduce); _bailiff_schema write+gate
src/bailiff/ordering.py          # single depends_on edge (drop run_after/run_before); pre/normal/post stratified DAG + edge-legality validation
src/bailiff/discovery.py         # static _external_data parse + path lint (FR-006a); _post_tasks parse
tests/loop/test_*isolation*.py   # NEW negative isolation test (SC-001/SC-007)
tests/loop/test_external_data*.py# NEW fact-resolution + absent-producer-error test (SC-002)
tests/loop/test_ordering*.py     # NEW single-edge + stratified-DAG + schema-gate tests (SC-008)

# Base — gains default_branch fact, loses the two unions AND github_host + .github/ (R12):
templates/bailiff-mod-base/copier.yml            # +default_branch; −mise_tools; −gitignore_stack union; −github_host (R12)
templates/bailiff-mod-base/template/...          # .mise.toml removed; base contributes .mise/conf.d/ + .gitignore.d/; {% if github_host %}.github{% endif %}/ tree REMOVED (moves to github-repo, R12)

# Forge metadata cleanup (R12 / FR-022..024):
templates/bailiff-mod-github-repo/               # +.github/ managed files (CODEOWNERS, ISSUE_TEMPLATE, PULL_REQUEST_TEMPLATE) moved from base; +create_remote question; gh tasks gated on create_remote
templates/bailiff-mod-gitlab-repo/               # +.gitlab/ equivalent (CODEOWNERS + MR/issue templates); +create_remote question; glab tasks gated on create_remote
templates/bailiff-mod-dep-updates/copier.yml     # −github_host read; dep_update_tool self-defaults to renovate

# mise drop-in (union dissolution — ~10 tool-contributing modules):
templates/bailiff-mod-{python,ts,go,rust,cocogitto,moon,api,cdk,terraform,...}/
    template/.mise/conf.d/<vendor>-<module>.toml.jinja   # per-module drop-in; NO module writes .mise.toml
templates/bailiff-mod-devcontainer/...           # postCreateCommand → bare `mise install`

# pre-commit fragments + one vendored bundler:
templates/bailiff-mod-precommit/template/scripts/_merge_precommit.py.jinja  # the owner-side bundler (rev-pin highest-wins+warn)
templates/bailiff-mod-precommit/copier.yml       # merge as _post_tasks (not inline); hook_blocks union deleted
templates/bailiff-mod-*/template/.pre-commit.d/<vendor>-<module>.yaml.jinja # per-contributor fragment

# gitignore fragments + one idempotent concat:
templates/bailiff-mod-*/template/.gitignore.d/<vendor>-<module>.jinja       # per-contributor fragment
templates/bailiff-mod-base/copier.yml            # concat task (delimited blocks, idempotent)

# _external_data fact consumers (~19 for project_name; layout/description/default_branch; moon facts):
templates/bailiff-mod-*/copier.yml               # _external_data: {base: .copier-answers.bailiff-mod-base.yml} etc.

# FR-018 module-authoring documentation:
specs/011-deopinionated-module-family/contracts/_cross-cutting.md  # frozen-union sections REPLACED
skills/bailiff/SKILL.md                          # "how to write a module" steps updated
_meta/module-template/                           # scaffold copier.yml + README demonstrate conf.d + _external_data
templates/*/README.md                            # prose referencing the old union model
docs/... (authoring guide)                       # concrete guide: private-by-default, _external_data, fragments, config-consistency

# Registration / regen (per touched module):
cog.toml · catalog-sources.toml (regen) · check_modules.py (single-merger lint, optional)
```

**Structure Decision**: keep the proven `bailiff-mod-*` shape. The novelty is purely the `.d/`
directory convention (mise `.mise/conf.d/`, pre-commit `.pre-commit.d/`, gitignore `.gitignore.d/`)
+ the `_external_data` alias block in `copier.yml`. Each module is rewritten in-monorepo; the
armed fan-out publishes each to `bailiff-io/bailiff-mod-<name>`.

## Cross-cutting design (Phase 1 detail → contracts/)

1. **Private-by-default threading (FR-001..003) — `contracts/_threading.md`.** In `init_many`
   (runner.py:454-485) the per-layer `data = {**accumulated, **layer_answers}` (line 457) currently
   grows `accumulated` after every layer via `_merge_layer_answers` (line 484). The change: STOP
   accreting private answers — `accumulated` stays `{today}` (seeded runner.py:430; there is NO
   run-level `--data` channel — the multi-run-spec exposes only per-layer `answers`, cli.py:286). A
   layer renders with its own per-layer answers + builtins/`today` + any `_external_data` facts.
   `_merge_layer_answers` is neutered/removed at its call site. The reproduce path (`reproduce_many`,
   line 554+) applies the SAME rule (FR-003). Cross-module VALUES travel via `_external_data` (below),
   which copier resolves by reading the producer's answers file directly.

2. **`_external_data` fact reads, ENFORCED (FR-004..007, FR-006a) — `contracts/_facts.md`.** A consumer
   declares a local alias at the producer's deterministic answers file:
   ```yaml
   _external_data:
     base: .copier-answers.bailiff-mod-base.yml     # literal path (FR-006a lint)
   project_name:
     type: str
     default: "{{ _external_data.base.project_name }}"   # base is a HARD dependency (FR-006)
   ```
   No vendor prefix; no shared-key lint (FR-007). bailiff statically parses the aliases and REQUIRES
   each producer present + ordered-before; ABSENT producer → loud error (FR-006 inverted — copier's own
   missing-file behavior is `warn + {}` → empty render, which SC-006 forbids). The ratified fact set
   (producers = base + precommit + ts + moon):
   - **base** (`base`): `project_name`, `layout`, `description`, **`default_branch` (NEW)**. (`github_host`
     is NOT a fact — deleted from base by R12/FR-022; see move 6.)
   - **precommit** (`precommit`): `hook_manager` (consumers: python, ts, api, go, rust, terraform, justfile).
   - **ts** (`ts`): `js_pkg_manager` (justfile, package-add), `ts_linter` (editorconfig).
   - **moon** (`moon`): `monorepo_tool`, `monorepo_packages` — proves non-base producers.
   - **bare-private (NOT facts)**: `org`/`copyright_name`/`branch_strategy`; exclusive siblings
     (`visibility`/`remote_protocol`/`push_after_create`/`team`, `ci_*`, `placement_dir`).
   - **collision-class (stay private)**: `test_runner` (go/rust/ts disjoint domains).

3. **Dependency model (FR-019/020) — `contracts/_threading.md`.** Single `depends_on` edge (side-effect
   deps: X needs Y's tool/file); `run_after`/`run_before` DROPPED from `ordering.py`; ~25 modules migrate
   `run_after: base` → `depends_on: base` + gain a `phase`. pre/normal/post stratified DAG: sort =
   (phase) → (`depends_on` DAG) → (basename); edge legality validated at discovery (pre→pre, normal→
   pre+normal, post→anything; forward cross-phase edge rejected). base=pre, family=normal, post reserved.
   Data-deps (item 2) and side-effect-deps are distinct but both required-present + ordered.

4. **Universal fragment/merge — `contracts/_fragment-merge.md`.** The engine does ZERO merging;
   the `.d/` directory IS the cross-module interface. Per surface:
   - **mise (native)**: each tool module renders `.mise/conf.d/<vendor>-<module>.toml`; mise merges
     natively at `mise install`. NO `.mise.toml`, NO merge task, NO `mise_tools` union. devcontainer
     runs bare `mise install`. The 013 collision check passes (distinct paths).
   - **pre-commit (owner-side vendored bundler, run as a POST-TASK)**: each hook module renders
     `.pre-commit.d/<vendor>-<module>.yaml` (its block only). `bailiff-mod-precommit` vendors ONE
     Python bundler (`scripts/_merge_precommit.py`) run as a **`_post_task`** (FR-021, R11) — NOT inline,
     because precommit is ordered FIRST (languages read `hook_manager` from it), so an inline task would
     see no fragments. bailiff runs it after the render loop: reads ALL fragments, dedups repos, emits
     `.pre-commit-config.yaml` deterministically (order-independent), and on a rev-pin conflict picks the
     **highest rev + WARNS** (R2 revised — a hard error would let a lagging third-party module veto a
     valid stack). Inert when precommit absent / `hook_manager=none`. Per-contributor merging forbidden.
   - **gitignore (owner-side concat, also a POST-TASK)**: per-module `.gitignore.d/<vendor>-<module>`
     fragments (gitnr-produced OR literal static lines); the gitignore owner runs ONE idempotent
     ordered-concat as a `_post_task` (delimited blocks so reproduce does not duplicate). No
     `gitignore_stack` fact, no vendored script (concat is trivial).

5. **Post-tasks (FR-021 / R11).** A module declares `_post_tasks` (a `when:false` hidden list); bailiff
   collects them across modules and runs them AFTER the render loop, in `depends_on` order, on init AND
   reproduce. Distinct from the module `phase` (which orders renders). Resolves the precommit
   merge-ordering contradiction (render early as a `hook_manager` producer; merge late). Enabled by
   bailiff driving copier as a library. NO `_pre_tasks` (ordering + a first-module `_task` covers it).

6. **Migration gate (FR-014 / R10).** bailiff WRITES `_bailiff_schema: 014` into each answers file
   post-render (it can't be a copier answer — `_`-keys/non-questions are filtered, hidden questions
   omitted); `reproduce_many` REFUSES (loud error + re-init) on a missing/older marker. copier silently
   ignores unknown recorded keys, so this positive-allowlist gate is what makes the break loud.

7. **Config-consistency invariant.** Merged artifacts are config-equivalent, not byte-identical;
   the reproduce byte-assertions on merged files are dropped surgically (the in-flight byte-drop
   worktree) while single-module managed renders keep their byte assertions. This is what makes the
   merge model sound and is already reframed in prose on main.

## Migration & re-fanout (FR-014)

- **Documented BREAK + re-init, NO shim (R3).** Pre-014 committed trees record old bare keys
  (`mise_tools`, bare `project_name`, `framework`) and the dissolved unions. Justified by near-zero
  real population (greenfield, no external users, 27 mirrors freshly published 2026-07-16 and
  re-fannable). Reproduce over a pre-014 tree MUST produce a CLEAR documented error, never a silent
  mis-render (SC-006). A short migration note documents the break + re-init recommendation.
- **27-mirror re-fanout**: after all modules are rewritten + green locally, the armed fan-out
  republishes each `bailiff-mod-<name>` mirror. Maintainer-confirmed batch, never unattended (011
  precedent). Sequence catalog regen with the re-fanout.

## Build / test / release sequencing

The task DAG (Phase 2) is built on this ordering; slices A–B/B2 fan out with worktree isolation.

1. **Engine + contract first (the gate).** Land in `src/bailiff/`: private-by-default threading
   (`runner.py`, init + reproduce); `_external_data` static-parse + validation + FR-006 loud-error
   (`discovery.py` parse + `runner.py` preflight); single-`depends_on` + pre/normal/post stratified DAG
   + edge-legality validation (`ordering.py`); the `_bailiff_schema: 014` gate (`reproduce_many`). Land
   the tests: negative isolation, absent-producer error, dependency-model, schema-gate. Rewrite the 011
   cross-cutting contract (FR-018a) + author `contracts/`. Nothing downstream until the contract is
   frozen. NOTE: the byte-drop already merged to main (`30a982a`) — test files are settled. **base gains
   `default_branch`** + all producers (base/precommit/ts/moon) write their facts before consumers wire.
2. **Slice A — mise conf.d dissolution** (parallel, worktree-isolated per module): the ~10
   tool-contributing modules → `.mise/conf.d/` drop-ins; base drops `.mise.toml`; devcontainer →
   bare `mise install`. Migrate each module's `run_after: base` → `depends_on: base` + set `phase`.
   Each: rewrite → loop test → `check_modules` green.
3. **Slice B — fragment/merge + facts** (parallel per module): pre-commit bundler + `.pre-commit.d/`
   fragments across hook contributors; `.gitignore.d/` fragments + base concat; `_external_data` alias
   wiring — `project_name` (~19), `layout`/`description`/`default_branch` (base);
   **`hook_manager` (precommit → python/ts/api/go/rust/terraform/justfile)**; **`js_pkg_manager`/
   `ts_linter` (ts → justfile/package-add/editorconfig)**; moon facts (ci-github, ci-gitlab, cocogitto).
4. **Slice B2 — forge metadata cleanup (R12 / FR-022..024)** (small, mostly serial — touches base +
   the two repo modules + dep-updates): move base's `{% if github_host %}.github{% endif %}/` tree
   (CODEOWNERS, ISSUE_TEMPLATE, PULL_REQUEST_TEMPLATE) into `github-repo` as managed files; add the
   `.gitlab/` equivalent to `gitlab-repo`; DELETE `github_host` from base; add `create_remote: bool`
   (default false) to both repo modules + gate their `gh`/`glab` tasks on it; drop `github_host` from
   dep-updates and self-default `dep_update_tool`. Verify: collision check stays green through the file
   moves; each module loop-tests; `check_modules` green.
5. **Slice C — FR-018 docs**: SKILL.md authoring steps, `_meta/module-template/` scaffold (demonstrate
   a conf.d fragment + an `_external_data` alias), per-module README prose, the concrete authoring
   guide (private-by-default, fact reads, fragment contribution, config-consistency). A module author
   must be able to write a correct module without reverse-engineering an existing one.
6. **Verify all green locally**: `uv run pytest tests/ -q -m "not network"`, `tests/integration/`
   (esp. the Python+TS `framework` stack now passing on isolation ALONE), `just check-modules` →
   "ok — 27 module(s)", `uvx bailiff doctor`.
7. **Confirmed re-fanout batch (maintainer)**: republish 27 mirrors; regen catalog; publish engine
   release (release-please). Write the migration note. Never unattended.

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| Documented migration BREAK + `_bailiff_schema` gate, no shim (R3/R10) | Dissolving recorded keys breaks reproduce over pre-014 trees; copier ignores stale keys silently | An alias/migration shim is fiddly and low-value at near-zero population. A clean break is honest — but "clear error" needs the schema marker + refuse-on-mismatch, else reproduce mis-renders silently (SC-006). |
| Rev-pin HIGHEST-WINS + WARN, not hard error (R2 revised) | Two modules pinning one hook repo at different revs must not make a stack un-generatable | A hard error collides with the open-ecosystem premise: a lagging THIRD-PARTY hook module would veto valid first-party stacks. Highest-wins is a safe default; the warning surfaces it for reconciliation. |
| Vendored pre-commit bundler (not a `bailiff merge` CLI) | pre-commit has no native drop-in; the combine needs a real script | An in-binary `bailiff merge` would make every generated project depend on the bailiff CLI at render/reproduce time (no module task does today) and can't be extended by third-party modules. Vendored = open-ecosystem + engine-free. |
| Widened engine footprint (runner + ordering + discovery), not one function | The dependency model (data-dep validation, single-edge + stratified DAG, schema gate) needs coordination copier lacks | The original "one threading tweak" scope could not enforce fact-producer presence, ordering, edge-legality, or migration safety — all cross-template coordination, the C-11-sanctioned glue category. Doing it in templates alone is impossible (copier has no cross-template validation hook). Still under 013's engine exception. |
| pre/normal/post stratified DAG built now (no `post` module exists yet) | A single `depends_on` cannot express "run last" without the last-mover enumerating N edges | Deferring leaves no structural "run last"; building it now is near-zero marginal cost (ordering.py + all 27 copier.yml already being rewritten) and avoids a second re-fanout later. `post` reserved until a finalizer appears. |
| Forge metadata restructure in-scope (R12: `.github/` base→forge modules, delete `github_host`) | base (host-agnostic) silently emitted GitHub-only files with no GitLab equivalent and no guard against `github_host=true` + `gitlab-repo` — same "unenforced cross-module assumption" class 014 targets | Deferring to a later spec means the module family gets re-fanned out once for 014 and AGAIN for the forge fix. Since 014 already rewrites every `copier.yml` and re-fans all mirrors, folding it in is near-zero marginal cost and fixes the contradiction now. Merging the two repo modules into one `git` module was the bigger alternative — deferred (keeps exclusive-sibling pattern, avoids cascade into ci-github/ci-gitlab). |

**Through-line note**: 014 explicitly REVERSES spec 011's M1 critique resolution ("agent-frozen
unions → single writer, the `gitignore_stack` pattern"). 011 made unions single-writer to satisfy
013's collision rule; 014 recognizes the union itself was the anti-pattern and replaces N-writers-of-
one-file with N-writers-of-N-files + one owner-side merge. The 011 cross-cutting contract §2/§4/§5/§6
sections are the exact prose being rewritten under FR-018.

No unjustified violations remain.
