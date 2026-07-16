# Quickstart — validating spec 014

How to prove the three moves work end-to-end. Prerequisites: repo checked out on
`014-namespaced-question-keys` (rebased onto post-byte-drop main), `uv` + `mise` + `pre-commit`
available, `uv run pytest` green baseline. All scenarios are hermetic/offline unless marked.

References: [`contracts/_threading.md`](./contracts/_threading.md),
[`contracts/_facts.md`](./contracts/_facts.md),
[`contracts/_fragment-merge.md`](./contracts/_fragment-merge.md),
[data-model.md](./data-model.md).

## Scenario 1 — private isolation (SC-001, SC-007) — the motivating bug

Prove two layers with the same bare key + disjoint domains no longer poison each other.

- Build a two-layer selection where layer A defines `q ∈ {x,y}` and layer B defines `q ∈ {m,n}`
  (the loop-test harness `build_template_repo`/`multi_template_set`).
- Init the stack.
- **Expected**: no `InvalidRunSpecError`; A renders with its own `q`, B with its own `q`;
  `.copier-answers.<A>.yml` records only A's `q`, `.copier-answers.<B>.yml` only B's.
- **Real regression**: a monorepo stack selecting both `bailiff-mod-python` and `bailiff-mod-ts`
  (both historically define `framework`) inits successfully on ISOLATION ALONE — verify by
  temporarily reverting the merged point-fix rename in the test fixture, or by adding a fixture that
  reuses the bare `framework` key in two layers.

Command: `uv run pytest tests/loop/test_*isolation* -q`

## Scenario 2 — `_external_data` fact resolution (SC-002)

- **Present producer**: init a stack with base + a consumer that aliases
  `base: .copier-answers.bailiff-mod-base.yml` and reads `_external_data.base.project_name`.
  Expected: the consumer renders base's `project_name`.
- **Absent producer (HARD dep, FR-006 inverted)**: init the same consumer ALONE (no base). Expected:
  a LOUD preflight error naming the `_external_data.base` alias and its missing producer — NOT a silent
  empty render or a fallback.
- **Non-base producer**: init moon + ci-github; ci-github aliases `moon` and reads
  `_external_data.moon.monorepo_tool`. Expected: resolves moon's value.
- **precommit fact**: init precommit + python; python reads `_external_data.precommit.hook_manager`.
  Expected: resolves precommit's value; python ALONE (no precommit) → loud error.
- **default_branch**: init base + ci-github; ci-github reads `_external_data.base.default_branch`.
  Expected: resolves base's value; no un-rendered `"{{ default_branch }}"` string leaks.

Command: `uv run pytest tests/loop/test_external_data* -q`

## Scenario 3 — mise conf.d union dissolution (SC-003)

- Init base + cocogitto + moon (three tool contributors).
- **Expected**: three files under `.mise/conf.d/` (`bailiff-mod-base.toml`,
  `bailiff-mod-cocogitto.toml`, `bailiff-mod-moon.toml`), each with its own `[tools]`; NO
  `.mise.toml`; the 013 collision check passes.
- With `mise` available: `mise cfg` / `mise install` shows the union of all three tool sets.
- Reproduce: each drop-in re-renders byte-identically (single-module managed render).

Command: `uv run pytest tests/loop/test_*mise* tests/loop/test_devcontainer* -q`

## Scenario 4 — pre-commit fragment merge + rev-pin highest-wins (SC-004)

- Init precommit + two hook-contributing modules.
- **Expected**: two `.pre-commit.d/*.yaml` fragments + the vendored `scripts/_merge_precommit.py`
  producing one `.pre-commit-config.yaml` containing both hooks, deterministically sorted.
- **Order-independence**: the same two modules in the other selection order → equivalent merged
  config.
- **Rev-pin conflict**: two fragments pinning the same hook repo at different revs → the bundler picks
  the HIGHEST rev and emits a warning (does NOT abort); the merged config carries the highest rev.
- **Inert without merger**: a hook contributor with NO precommit (or `hook_manager=none`) → fragments
  may exist but no `.pre-commit-config.yaml` is produced.
- Reproduce: `.pre-commit-config.yaml` returns config-consistent (same hooks), NOT byte-asserted.

Command: `uv run pytest tests/loop/test_precommit* -q`

## Scenario 7 — dependency model + migration gate (SC-008)

- **Single edge**: a module declares `depends_on: [bailiff-mod-base]` (no `run_after`/`run_before`);
  ordering places base first. An absent `depends_on` target → loud `OrderingError`.
- **Stratified DAG**: a `normal`-phase module declaring a `depends_on` on a `post`-phase module (a
  forward cross-phase edge) is REJECTED at discovery with a clear error.
- **Migration gate**: reproduce over a tree whose `.copier-answers.*.yml` lacks `_bailiff_schema: 014`
  → `reproduce_many` refuses with a re-init message (never a silent stale render).

Command: `uv run pytest tests/loop/test_ordering* tests/loop/test_*schema* -q`

## Scenario 5 — gitignore fragment concat (FR-013)

- Init base + two gitignore contributors.
- **Expected**: `.gitignore.d/*` fragments + one `.gitignore` folded via the idempotent concat with
  delimited blocks.
- Reproduce twice: `.gitignore` has NO duplicated entries (idempotent).

## Scenario 6 — migration break (SC-006)

- Take a pre-014 committed tree (bare `project_name`, `mise_tools`, `framework` in answers files).
- Reproduce post-014.
- **Expected**: a CLEAR documented error (not a silent mis-render); the migration note points at
  re-init.

## Full gate (before re-fanout)

```bash
uv run pytest tests/ -q -m "not network"     # full non-network suite
uv run pytest tests/integration/ -q          # 33 combination tests incl. Python+TS framework stack
uv run python scripts/check_modules.py        # → "ok — 27 module(s)"
uvx bailiff doctor                            # exit 0
```
