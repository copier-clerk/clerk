# Decisions Ledger — spec 014 (namespaced keys, private-by-default threading, fragment/merge model)

**Source**: The 2026-07-16 design session triggered by the spec-013 integration tests finding
a real cross-module answer-poisoning bug (`framework` collision across python/ts/stack-adr),
plus copier and mise capability research verified against primary sources the same day. This
file is the in-tree authoritative record: where spec.md is silent, this ledger governs; where
this ledger is silent, the item is out of scope for 014. **Research-first spec** — plan.md and
tasks.md follow after this ledger is accepted.

## Verified research (primary sources, 2026-07-16)

| Finding | Source | Implication |
|---|---|---|
| copier isolates templates by default (one answers file per template; no shared answer namespace) | copier docs "Applying multiple templates" | bailiff's blanket cross-layer answer bleed is a bailiff invention, not a copier requirement — it can be removed. |
| copier `_external_data` provides namespaced, opt-in cross-template reads (`_external_data.<ns>.<key>`), does not pollute the consumer's answers file | copier docs "Template Composition with External Data" | This is the sanctioned mechanism for threaded facts (project_name, layout, …). |
| copier `when: false` computed values render a value without prompting; can be locked into the answers file | copier FAQ "computed value" / "lock a computed value" | A module can render an injected value deterministically for reproduce. |
| copier reserves a single leading `_` for settings/metadata; `_`-prefixed keys cannot be answerable questions | copier config model | A private question CANNOT be named `_framework`; privacy must come from threading control, not the `_` prefix. |
| mise merges all `.mise/conf.d/*.toml` drop-in files at runtime | mise source `config_root.rs` (`.mise/conf.d` is a config root); mise docs config hierarchy | `mise_tools` union dissolves: per-module drop-in files, native merge, no combine. |
| git has NO committed-file merge for `.gitignore` (composes by precedence: root, per-dir, info/exclude, global) | git ignore model | gitignore cannot use a native drop-in; needs a fact or a bailiff merge/append. |
| pre-commit has NO include/drop-in for `.pre-commit-config.yaml` (single file) | pre-commit config model | pre-commit needs a bailiff post-install MERGE task over per-module fragments. |

## The governing decision — universal fragment/merge pattern (ratified)

**A cross-module answer "union" is an anti-pattern.** It exists only because a single output
file was assumed to have a single writer. Every union is replaced by:

> Each module renders ONLY its own fragment into its own path. The combined artifact is
> produced by a merge — the tool's NATIVE drop-in merge where one exists, or a single bailiff
> post-install merge task where it does not.

**Ratified consequence: there are ZERO cross-module answer unions after 014.** No key like
`mise_tools` or `hook_blocks` is threaded across layers. What remains: per-module fragments,
native/task merges, and namespaced shared *facts* (single values) via `_external_data`.

This mechanism is the DEFAULT for anything without native drop-in support (maintainer:
"that mechanism works best for everything that does not support this natively").

## Config-consistency invariant (ratified — supersedes byte-identity)

bailiff's reproduce guarantee is **config-consistency**, not byte-identity: a reproduced or
merged file expresses the SAME configuration (same tools/hooks/ignore rules), not necessarily
the same bytes. A merge (YAML re-emit, append) cannot be byte-identical; it is config-equivalent.
Single-module managed renders remain deterministic and, in practice, byte-identical — but the
CONTRACT-level guarantee across the system is config-consistency. A repo-wide prose sweep
reframes all "byte-identical" invariant language to "config-consistent" (running on branch
`byte-to-config-sweep`; test byte-assertions are NOT auto-weakened — flagged for per-assertion
review).

## Union dispositions (ratified)

| Former union | Disposition |
|---|---|
| `mise_tools` | DELETED as a union. Per-module `.mise/conf.d/<vendor>-<module>.toml`; mise merges natively. No module writes `.mise.toml`. devcontainer runs bare `mise install` (reads merged conf.d), no frozen tool list. |
| `hook_blocks` | DELETED as an answer union. Per-module `.pre-commit.d/<vendor>-<module>.yaml` fragments; precommit runs ONE post-install merge task → `.pre-commit-config.yaml`. Config-consistent. |
| `gitignore_stack` | RESOLVED (see Ratified §pre-commit/gitignore below): becomes per-module `.gitignore.d/<vendor>-<module>` fragments (gitnr-produced OR literal static lines) + one idempotent ordered-concat (inline shell task in the gitignore owner). No `gitignore_stack` fact threaded across layers. |
| `quality_languages` | NOT shared — declared and consumed by the same module (quality). No change. |

## Threading model (ratified — vendor prefix DROPPED, superseded by `_external_data`)

> **Supersession note (2026-07-16, HEAD ba4260b):** the earlier `<vendor>__<name>` double-underscore
> prefix scheme recorded in prior revisions of this section is **REJECTED**. copier `_external_data`
> alias namespacing already isolates cross-module reads structurally, works across vendors (each
> producer's answers file is a distinct alias), and needs no naming convention or lint. This section
> is rewritten to the accepted model; spec.md FR-004..007 govern.

- **Private by default**: `init_many`'s `_merge_layer_answers` stops merging all non-`_` keys;
  a module's questions stay in its own layer. Kills the answer-poisoning class structurally
  (the `framework` collision could not occur under isolation). NOTE: `accumulated` is seeded ONLY
  with `today` (runner.py:430) and grows solely via `_merge_layer_answers` (line 484) — there is NO
  separate "run-level `--data`" channel in the input model (the multi-run-spec exposes only per-layer
  `answers`, cli.py:286). So private-by-default = `accumulated` stays `{today}` and never accretes;
  per-layer answers still flow from the run-spec. `today` remains the one legitimately-threaded value.
- **Cross-module facts via `_external_data` aliases, NO prefix**: a consumer declares a local alias
  pointing at the producer's deterministic answers file (`.copier-answers.<producer-basename>.yml`)
  and reads `{{ _external_data.<alias>.<key> }}`. The producer writes the key as a normal (bare)
  question to its own answers file. See §Dependency model below for how presence + ordering are
  ENFORCED (a fact read is a validated dependency, not a best-effort read).
- **No shared-key naming lint**: `check_modules.py` gains NO shared-key/vendor-prefix lint. Every
  key is a normal bare key, private by default, shared only by being read through an alias. This is
  what makes the model work across an open ecosystem without a central `SHARED_KEYS` registry.

## Dependency model — single `depends_on` edge + `_external_data`-as-validated-dependency (ratified 2026-07-16)

Grill + engineering critique this session redesigned the ordering/dependency model. Prior spec text
(FR-006 "graceful fallback", multi-edge vocabulary) is SUPERSEDED by the rulings below.

### R6 — Two distinct dependency KINDS, both hard-enforced

- **Data dependency** (`_external_data`): a consumer reads a producer's fact. bailiff statically parses
  the consumer's `_external_data` block, maps each alias → producer basename, and ENFORCES it: producer
  ABSENT from the selection → loud preflight error (reuse `OrderingError`); producer PRESENT → ordered
  before the consumer. The `_external_data` declaration is the single source of truth — bailiff
  *validates* it, does NOT silently auto-inject a hidden edge (structure is visible in the file, per the
  013 "enforce structure, don't trust discipline" ethos).
- **Side-effect dependency** (`depends_on`): X needs Y's *side effect* — a tool Y installed, a file Y
  wrote that X modifies — WITHOUT reading any of Y's answers. This is the case `_external_data` cannot
  express. `depends_on` = target present + ordered-before; ABSENT target → loud `OrderingError`
  (dangling-edge behavior already in `ordering.py:99-103`, made explicit).

### R7 — Collapse to a SINGLE edge type; drop `run_after` and `run_before`

Empirical audit: today `depends_on` and `run_after` are byte-identical in code (`ordering.py:90`); the
only edge value in real use is `run_after: [bailiff-mod-base]` (~23 modules); `depends_on` default `[]`
everywhere (0 real uses); `run_before` default `[]` everywhere (0 real uses).
- **Keep ONE edge: `depends_on`** (present + ordered-before). Migrate the ~23 `run_after: base` →
  `depends_on: base`.
- **DROP `run_after`** — no soft "order-if-present, tolerate-absent" case exists in the codebase; soft
  ordering would reintroduce the silent-tolerate-absence risk 014 kills.
- **DROP `run_before`** — 0 uses; it doubles the DAG cycle surface (constraints expressible from two
  sides can contradict). Single-arrow vocabulary minimizes accidental cycles. If an open-ecosystem
  "must precede an unmodifiable third-party module" case ever appears, reintroduce a scoped escape hatch
  then (YAGNI).
- Greenfield: no migration cost for redefining the edge vocabulary (maintainer: "we can refactor
  whatever we want").

### R8 — pre/normal/post stratified DAG (structural "run first / run last")

A single `depends_on` cannot ergonomically express "run last" (the last-mover would need an edge to
every other module). Solve with three PHASES, sorted (phase) → (`depends_on` DAG) → (basename):
- **pre** → may depend ONLY on pre.
- **normal** (default) → may depend on pre + normal.
- **post** → may depend on anything.
Edge legality is VALIDATED at discovery: a forward cross-phase edge (pre→normal, pre→post, normal→post)
is illegal and rejected with a clear error — a whole class of ordering bugs becomes undeclarable, and
cycles cannot cross phases. Mapping: **base = pre**; the 25-module family = **normal**; **post reserved**
for a future finalizer (none exists today — base's initial commit is an intra-module last `_task`, not a
cross-module finalizer). Built into 014 now (ordering.py + all 27 copier.yml already being rewritten).

### R9 — `_external_data` path lint (discovery)

For bailiff to map alias → producer basename, `_external_data` values MUST be a literal
`.copier-answers.<basename>.yml` (no Jinja expression, no path traversal, no URL). A discovery-time lint
rejects non-literal / non-convention paths for first-party modules with a clear error. This is the
static-parse the R6 data-dependency validation depends on.

### R10 — Migration detection: `_bailiff_schema` marker + refuse-on-mismatch (supersedes toothless FR-006/FR-014 prose)

copier SILENTLY IGNORES unknown recorded answer keys (verified: `load_answersfile_data`
`_user_data.py:597-603` returns `{}`/warns, never errors), so a pre-014 tree with `mise_tools:` recorded
reproduces WITHOUT the tools and WITHOUT error — the exact silent mis-render SC-006 forbids. "Clear
documented error" was therefore aspirational. FIX: post-014 modules stamp `_bailiff_schema: 014` into
their answers files; `reproduce_many` REFUSES (loud error + re-init guidance) when a recorded answers
file lacks the marker or carries an older schema. This gives SC-006 real teeth.

### FR-006 INVERTED (ratified)

The original FR-006 ("a consumer reading a fact MUST fall back to its own default when the producer is
absent — never a hard failure") is WRONG and REPLACED. copier's `_external_data` on a missing file
returns `{}` → unguarded `{{ _external_data.base.project_name }}` renders EMPTY STRING (not the
consumer's own default), i.e. a silent mis-render. The new rule (R6): reading a fact makes the producer
a hard dependency; producer absence is a LOUD preflight error, not a fallback. This satisfies SC-006
instead of fighting it. A module that renders `project_name` genuinely needs a `project_name` producer.

## framework collision point-fix (DONE — merged to main)

The specific `framework` collision (python/ts/stack-adr) point-fix (rename to `python_framework` /
`ts_framework` / `stack_framework`) is **merged to main** (`9a22b6c`), which unblocked the
integration suite. 014 generalizes the CLASS; it did not depend on that point-fix and vice versa.
Latent sibling of the same class found but NOT point-fixed (private-by-default fixes it wholesale):
`test_runner` is defined independently in `bailiff-mod-ts` and `bailiff-mod-rust` with disjoint domains.

## RATIFIED (2026-07-16 session — folds into plan.md; closes all 5 NEEDS CLARIFICATION)

The 5 open questions from the research-first draft are all resolved. Prior text preserved in git
history; the accepted answers:

### R1 — Merge mechanism: engine does ZERO merging; `.d/` dirs are the contract; merged-file owner vendors its own bundler (FR-011, FR-013)

- **The `.d/` directory IS the cross-module interface.** A contributing module's entire contract is
  "write one fragment to the correct drop-in dir." It has no merge logic, no awareness of other
  modules, and never calls back into the bailiff binary. Surfaces: `.mise/conf.d/`, `.pre-commit.d/`,
  `.gitignore.d/`.
- **The merged-file OWNER performs the combine — never a per-contributor script.** Exactly one module
  (the one that owns the combined file) runs the merge. Per-contributor merging is REJECTED: N scripts
  racing on one output re-creates the multi-writer collision 014 exists to kill, and no single
  contributor can see all fragments to enforce the rev-pin rule.
- **No `bailiff merge` CLI / in-binary renderer.** REJECTED in favour of vendored/owner-side merging.
  Rationale (consistent with rejecting the `bailiff__` prefix in R1-threading): (a) open ecosystem — a
  third-party module can ship its own bundler without patching bailiff; (b) a generated project must
  NOT depend on the bailiff CLI being installed at render/reproduce time (today no module task calls
  bailiff; base tasks call mise/git/gh/gitnr only). Vendored artifacts are managed renders, so
  `update`/`reproduce` re-sync them — no meaningful drift risk.
- **Per surface (weight-differentiated):**
  - **mise** — native `.mise/conf.d/*.toml` merge at `mise install`. NO script, NO merge task.
  - **gitignore** — per-module `.gitignore.d/<vendor>-<module>` fragments (gitnr-produced OR literal
    static lines) + one **idempotent ordered-concat inline shell task** in the gitignore owner
    (delimited blocks so reproduce does not duplicate). No script file; no `gitignore_stack` fact.
  - **pre-commit** — the only surface needing a real script. `bailiff-mod-precommit` **vendors one
    Python bundler** (e.g. `scripts/_merge_precommit.py`) into the project, run as its post-install
    task. It reads ALL `.pre-commit.d/*.yaml`, dedups repos, emits `.pre-commit-config.yaml`
    deterministically (order-independent), and enforces the rev-pin rule (R2). Inert when precommit
    absent / `hook_manager=none`.

### R2 — Rev-pin conflict rule: HIGHEST-PIN-WINS + WARN (FR-011) — REVISED 2026-07-16

When two fragments pin the SAME hook repo at DIFFERENT revs, the precommit bundler MUST pick the
**highest rev and emit a warning** — never abort. Rationale (revised after the critique surfaced the
open-ecosystem tension): the earlier hard-error rule collides with the open-ecosystem premise — a
THIRD-PARTY hook module pinning a different ruff/prettier rev would hard-fail an otherwise-valid
first-party stack, giving one lagging sibling global veto power. Highest-wins is a safe default (newer
hook revs are backward-compatible in practice); the warning surfaces the disagreement for reconciliation
without making any stack un-generatable. This still requires the single owner-side bundler (sees every
fragment) to compute the max and warn (see R1). *(Supersedes the prior EXPLICIT HARD ERROR ruling.)*

### R3 — Rename migration: DOCUMENTED BREAK + re-init (FR-014)

Documented break + re-init recommendation, NO alias/migration shim. Justified by near-zero pre-014
population: greenfield, no external users, 27 mirrors freshly published (2026-07-16) and re-fannable.
Reproduce over a pre-014 tree must produce a clear documented error, never a silent mis-render.

### R4 — First-party shared-fact set (FR-007) — EXPANDED 2026-07-16 after exhaustive audit

The original audit only grepped `copier.yml` `default:` lines and MISSED three real choice-axis
cross-layer reads. A second EXHAUSTIVE audit (all 27 modules' copier.yml + template/ bodies) fixed the
COMPLETE set. Facts read via `_external_data` aliases (each read is a validated data-dependency, R6):

- **Base-produced** (alias `_external_data.base.*`): `project_name`, `layout`, `github_host`,
  `description`, **`default_branch`** (NEW to base — latent bug: ci-github `copier.yml:80-82` /
  ci-gitlab `:91-93` thread it from a non-existent producer today).
  - `description` KEPT + made a base fact (renders into base AGENTS.md, readme README.md, api
    openapi.yaml, apm apm.yml, mkdocs site_description+index). Consumers: apm, api, mkdocs, python,
    readme.
- **precommit-produced** (alias `_external_data.precommit.*`) — ADDED after critique: **`hook_manager`**.
  Consumers: python, ts, api, go, rust, terraform, justfile. Precommit co-occurs with language overlays
  in the same stack, so `hook_manager` is a genuine non-exclusive cross-layer read — private-by-default
  without this alias would render `hook_manager` EMPTY and silently break lint/hook wiring.
- **ts-produced** (alias `_external_data.ts.*`) — ADDED after critique: **`js_pkg_manager`** (consumers:
  justfile, package-add) and **`ts_linter`** (consumer: editorconfig).
- **moon-produced** (alias `_external_data.moon.*`): `monorepo_tool` (ci-github, ci-gitlab),
  `monorepo_packages` (ci-gitlab, cocogitto). Proves the mechanism is not base-specific.

Producers are therefore **base + precommit + ts + moon** (not base+moon as originally scoped). Reading a
base fact auto-requires base as a dependency; reading `hook_manager` auto-requires precommit; etc. (R6).

- **Stay BARE-PRIVATE (NOT facts):**
  - `org`, `copyright_name`, `branch_strategy` — base-only, no cross-module reader.
  - **Exclusive-sibling keys** — `visibility`/`remote_protocol`/`push_after_create`/`team` (github-repo
    vs gitlab-repo); the `ci_*` keys (ci-github vs ci-gitlab); `placement_dir` (terraform/cdk/
    cloudformation — mutually-exclusive IaC siblings). Never co-occur at runtime.
- **COLLISION-CLASS keys (stay private — reading them cross-layer IS the bug):**
  - `test_runner` — go `{go-test,gotestsum}`, rust `{cargo-test,nextest}`, ts `{none,vitest-*,bun-test,
    playwright-only}`: three DISJOINT domains. Private-by-default fixes this wholesale (each layer-local,
    never read cross-layer). This is the latent second instance of the `framework` class.
  - `framework` — already renamed on-branch to `python_framework`/`ts_framework`/`stack_framework`
    (point-fix merged to main). Under private-by-default the bare name would have been safe too, but the
    rename stands (no reason to revert).
- **Audit result on NEW facts beyond {base 5, precommit 1, ts 2, moon 2}: NONE.** Candidates `stack`
  (readme-only, self-referential), `owner_repo` (a `plugins` loop-var field, not a question),
  `module_name` (template-local token) are NOT cross-layer facts.

### R5 — separator sanity: MOOT

The `__`-separator question is void — the vendor-prefix scheme was dropped entirely (R1-threading).
Bare keys only; copier's single-leading-`_` reservation is not engaged.

## Out of scope for 014

- New module features or new modules.
- The `framework` point-fix itself (separate branch).
- Conditional-Jinja contribution expressiveness beyond what the pre-commit fragment needs.
- Stack presets (013 FR-017, still deferred).
- Constitution amendment (none anticipated; engine changes fall under the 013 C-11 relaxation).
