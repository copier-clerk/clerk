# Phase 1 Data Model — spec 014

bailiff has no application data store; the "entities" that matter for 014 are the *contracts*
between modules: the cross-module fact set, the `.d/` directory conventions, the fragment shapes,
and the per-layer answers-file naming that `_external_data` relies on. Validation rules are the
FR/SC requirements from spec.md.

## Entity 1 — Cross-module Fact

A single VALUE produced by one module and read by others via a copier `_external_data` alias.

| Field | Value |
|---|---|
| `key` | the bare question key (e.g. `project_name`) |
| `producer` | the module that originates + answers it (base, precommit, ts, or moon) |
| `producer_answers_file` | `.copier-answers.<producer-basename>.yml` (deterministic, `ordering.py:answers_file_name`) |
| `alias` | consumer-local `_external_data` alias name (`base`, `precommit`, `ts`, `moon`) |
| `read_expr` | `{{ _external_data.<alias>.<key> }}` |
| `absent_behavior` | **producer is a HARD dependency** — absent → LOUD preflight error, NOT a fallback (FR-006, inverted) |

**The ratified fact set (EXPANDED after exhaustive audit — producers = base + precommit + ts + moon):**

| key | producer | alias | consumers (read via alias) |
|---|---|---|---|
| `project_name` | base | `base` | agentic, api, apm, cdk, ci-gitlab, cocogitto, devcontainer, github-repo, gitlab-repo, go, mkdocs, moon, python, readme, rust, stack-adr, ts, terraform |
| `layout` | base | `base` | moon, cocogitto, package-add |
| `github_host` | base | `base` | dep-updates |
| `description` | base | `base` | apm, api, mkdocs, python, readme |
| `default_branch` **(NEW)** | base | `base` | ci-github, ci-gitlab |
| `hook_manager` **(ADDED)** | precommit | `precommit` | python, ts, api, go, rust, terraform, justfile |
| `js_pkg_manager` **(ADDED)** | ts | `ts` | justfile, package-add |
| `ts_linter` **(ADDED)** | ts | `ts` | editorconfig |
| `monorepo_tool` | moon | `moon` | ci-github, ci-gitlab |
| `monorepo_packages` | moon | `moon` | ci-gitlab, cocogitto |

**Validation rules:**
- FR-004: a fact is read ONLY via an `_external_data` alias; never threaded through `data=`.
- FR-005: the producer path is the deterministic `.copier-answers.<module-basename>.yml`; changing
  the naming scheme is a separately-gated breaking change.
- FR-006 (inverted): reading a fact makes the producer a HARD dependency — absent → loud error, no
  fallback (copier's own missing-file behavior returns `{}` → empty render, which SC-006 forbids).
- FR-006a: `_external_data` values MUST be literal `.copier-answers.<basename>.yml` (static-parseable).
- FR-007: NO vendor prefix, NO shared-key lint. Bare keys, private by default.

**NOT facts (bare-private):** `org`, `copyright_name`, `branch_strategy` (no cross-reader);
`visibility`/`remote_protocol`/`push_after_create`/`team`, the `ci_*` keys, `placement_dir`
(mutually-exclusive siblings — never co-occur). **Collision-class (stay private):** `test_runner`
(go/rust/ts, disjoint domains) — reading it cross-layer IS the bug.

## Entity 2 — `.d/` Fragment Directory (the cross-module interface)

A directory into which each contributing module writes exactly its OWN fragment. Distinct paths
per module ⇒ no file collision (013 check passes). Three instances:

| Surface | Directory | Fragment path | Combined into | Combiner |
|---|---|---|---|---|
| mise | `.mise/conf.d/` | `<vendor>-<module>.toml` | (none — mise merges natively at `mise install`) | mise runtime |
| pre-commit | `.pre-commit.d/` | `<vendor>-<module>.yaml` | `.pre-commit-config.yaml` | vendored bundler in precommit |
| gitignore | `.gitignore.d/` | `<vendor>-<module>` | `.gitignore` | idempotent inline concat in the gitignore owner |

**Validation rules:**
- FR-008/010: each tool module writes exactly one `.mise/conf.d/*.toml`; NO module writes
  `.mise.toml`; NO `mise_tools` union.
- FR-011/012: each hook module writes exactly one `.pre-commit.d/*.yaml`; EXACTLY ONE merger
  (precommit); fragments inert when precommit absent / `hook_manager=none`.
- FR-013: each gitignore contributor writes exactly one `.gitignore.d/*` fragment; the concat is
  idempotent (delimited blocks) so reproduce does not duplicate.

## Entity 3 — pre-commit Bundler (vendored)

The single owner-side merge program, shipped as template content by `bailiff-mod-precommit`.

| Field | Value |
|---|---|
| path | `scripts/_merge_precommit.py` (rendered into the project) |
| input | all `.pre-commit.d/*.yaml` fragments |
| output | `.pre-commit-config.yaml` |
| invocation | post-install `_task` in precommit's `copier.yml`, init-only-guarded |
| ordering | deterministic + order-independent (same fragment set → equivalent config regardless of layer order) |
| dedup | repos deduplicated |
| rev-pin conflict | **HIGHEST-PIN-WINS + WARN** — same repo pinned at two revs → pick max, warn, never abort (R2 revised; open-ecosystem) |
| dependencies | Python + PyYAML only (no bailiff CLI) |
| reproduce | config-consistent (same hooks), NOT byte-identical |

## Entity 4 — Per-layer Answers File (unchanged contract, load-bearing)

`.copier-answers.<module-basename>.yml`, written by copier per layer (`ordering.py:answers_file_name`).
Records `_`-prefixed metadata + the layer's OWN answered questions. Under 014:
- it NO LONGER feeds the next layer's `data=` (private-by-default; `_merge_layer_answers` neutered);
- it IS the target an `_external_data` alias points at (a fact producer writes its fact here as a
  normal answer);
- the name is a stable contract (FR-005) — consumers hard-code the producer basename in their alias.

## State transition — the engine threading change (FR-001..003)

```
BEFORE (runner.py:457/484):
  layer N renders with  data = {**accumulated, **layer_answers_N}
  after layer N:         _merge_layer_answers → accumulated += {non-_ keys of layer N}
  ⇒ every later layer sees every earlier layer's private answers  (poisoning)

AFTER (private-by-default):
  layer N renders with  data = {**accumulated, **layer_answers_N}
    where accumulated stays {today} for the whole run (seeded at runner.py:430, never accreted).
    There is NO run-level --data channel (multi-run-spec has only per-layer answers, cli.py:286).
  after layer N:         no accretion of private answers (_merge_layer_answers neutered)
  cross-module VALUES:   travel via copier _external_data (copier reads the producer answers file),
                         NOT via accumulated
  reproduce_many:        same isolation (FR-003) — reconstructs per-layer, not a flattened namespace
```

**Isolation invariant (SC-001/SC-002/SC-007):** for any two layers A, B with the same bare key `q`
and disjoint domains, A's answer for `q` never enters B's render context. Proven by a negative
isolation loop test.

## Entity 5 — Dependency edge + phase (FR-019, FR-020)

The ordering model. ONE edge type + a phase per module.

| Field | Value |
|---|---|
| `depends_on` | list of module basenames this module requires present + ordered-before (side-effect deps) |
| `phase` | `pre` \| `normal` (default) \| `post` |
| derived data-dep | each `_external_data` alias → its producer basename is ALSO required present + ordered-before (FR-006), validated separately from `depends_on` |
| sort order | (phase) → (`depends_on` DAG, stable) → (basename tie-break) |

**Validation rules:**
- FR-019: `depends_on` is the SOLE edge; `run_after` + `run_before` dropped from `ordering.py`.
  Absent `depends_on` target → loud `OrderingError` (dangling-edge behavior).
- FR-020: edge legality at discovery — `pre`→pre only; `normal`→pre+normal; `post`→anything; a
  forward cross-phase edge is rejected (cycles cannot cross phases). base=`pre`; family=`normal`;
  `post` reserved.

## Entity 6 — Schema marker (migration gate, FR-014 / R10)

| Field | Value |
|---|---|
| key | `_bailiff_schema` (a `_`-prefixed metadata key, stamped into each answers file) |
| value | `014` (the schema generation) |
| enforcement | `reproduce_many` REFUSES (loud error + re-init guidance) when a recorded answers file lacks the marker or carries an older schema |
| rationale | copier silently ignores unknown recorded keys (`load_answersfile_data` → `{}`), so a pre-014 tree would mis-render silently without this gate |
