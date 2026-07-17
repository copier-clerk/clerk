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
| `gitignore_stack` | RESOLVED (see Ratified §pre-commit/gitignore below): becomes per-module `.gitignore.d/<vendor>-<module>` fragments (gitnr-produced OR literal static lines) + one idempotent ordered-concat in the gitignore owner, run as a `_post_task` (R11). No `gitignore_stack` fact threaded across layers. |
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
documented error" was therefore aspirational. FIX: post-014 answers files carry `_bailiff_schema: 014`;
`reproduce_many` REFUSES (loud error + re-init guidance) when a recorded answers file lacks the marker
or carries an older schema. This gives SC-006 real teeth.

**Write path — bailiff writes it, NOT the template (verified against copier source).** The marker
CANNOT be a copier answer:
- A `when:false` hidden question is explicitly OMITTED from the answers file (`_main.py:613-616`:
  `answers.hide()` → "Omit its answer from the answers file"; writer filter drops `answers.hidden` at
  `_main.py:375`) — the very mechanism our `depends_on` edges use to stay OUT of the file. Wrong: we
  need it PRESENT.
- An askable question is written WITHOUT a leading `_` (→ `bailiff_schema:`), pollutes every module's
  question namespace, needs 27 declarations, and is user-overridable.
- `--data _bailiff_schema=014` is dropped by the `not k.startswith("_")` filter (`_main.py:374`).
So bailiff APPENDS `_bailiff_schema: 014` to each `.copier-answers.<basename>.yml` post-render (one
engine site — it already reads answers files at `runner.py:540`), the same pattern copier itself uses
to write its own `_commit`/`_src_path` metadata (special-cased before the filter, `_main.py:367-369`).
Chosen (Option A, POSITIVE allowlist) over negative dissolved-key detection: a pre-014 tree CANNOT
have the marker, and every future schema-affecting spec just bumps the number — the gate generalizes.

### R11 — Post-tasks: deferred work bailiff runs AFTER the render loop (resolves the precommit merge-ordering contradiction)

The re-critique found a load-bearing contradiction: FR-006 makes `hook_manager` a hard data-dep, so
precommit is ordered BEFORE every language module; but the pre-commit fragment merge must run AFTER
every language writes its `.pre-commit.d/*.yaml`. copier runs each layer's `_tasks` INLINE at that
layer's `run_copy` (`runner.py:461`) — no global post-pass — so a merge in precommit's `_tasks` (precommit
first) would see NO language fragments → empty `.pre-commit-config.yaml`. FR-020's `post` phase is
reserved-not-built, so it doesn't rescue this.

FIX (enabled by bailiff driving copier as a LIBRARY, not a subprocess — `runner.py:33`
`from copier import run_copy...`): a module declares **`_post_tasks`** in its `copier.yml` (a `when:false`
hidden list, statically read like edges). bailiff COLLECTS `_post_tasks` across all selected modules and
runs them AFTER the whole render loop, in `depends_on` order (reuse the module DAG + basename tie-break),
on BOTH `init_many` AND `reproduce_many` (copier `_tasks` run on reproduce too, so the merge must too).
- precommit renders NORMAL (produces `hook_manager`, ordered first via the data-dep) AND contributes the
  merge as a `_post_task` (runs last, sees every fragment). The contradiction dissolves — one module acts
  in two stages.
- The pre-commit vendored bundler and the gitignore concat both move from inline `_tasks` to `_post_tasks`.
- **NO `_pre_tasks`**: "run before everything" is already expressible (be the first-ordered module — base —
  and use a normal `_task`; base's mise/gh preflight already does this). Post fills a gap copier CANNOT
  express (run after modules ordered before you); pre has no such gap. YAGNI until a real case appears.
- The pre/normal/post MODULE phase (R8/FR-020) stays for whole-module ORDERING (base=pre, family=normal,
  post reserved); `_post_tasks` is the orthogonal DEFERRED-WORK mechanism. The sub-render "each phase is a
  separate copier render + answers file" model was considered and REJECTED: the merge is a file-folding
  script either way, so a post sub-render would just wrap the same script at the cost of 3× answers files,
  phase-leaking alias paths, and a 3-pass engine — machinery with no current use case.

### R12 — Forge metadata leaves base; `github_host` DELETED; conditional remote creation (ratified 2026-07-16)

**The smell (found this session):** base — the host-AGNOSTIC foundation — scaffolds GitHub-specific
forge metadata: `{% if github_host %}.github{% endif %}/` (CODEOWNERS, ISSUE_TEMPLATE,
PULL_REQUEST_TEMPLATE), gated on a base bool `github_host`. There is NO GitLab equivalent and NO guard
against `github_host=true` co-occurring with a `gitlab-repo` selection — a silent contradiction
(`.github/` files land in a GitLab project). `github_host` conflates two unrelated jobs: "which forge?"
(a fact) and "emit `.github/` files" (forge-specific output).

**Ruling — NO "forge" fact is introduced; the problem DISSOLVES once base stops emitting the files.**
The forge selector only existed to gate files base should never have owned. Move the files out and the
selector has nothing left to control:
- **`.github/` metadata MOVES base → `github-repo`** (CODEOWNERS, ISSUE_TEMPLATE, PULL_REQUEST_TEMPLATE,
  as MANAGED files that reconcile normally). A `.gitlab/` equivalent (CODEOWNERS + MR/issue templates)
  is ADDED to `gitlab-repo`. base emits ZERO forge-specific files.
- **`github_host` is DELETED from base** and is NOT replaced by any selector/enum. Nothing forge-specific
  remains in base, so no selector is needed. `github_host` is therefore REMOVED from the R4 fact set
  (it was listed as a base fact — that row is struck; see R4 amendment below).
- **`bailiff-mod-dep-updates` self-defaults.** It stops reading `github_host`; `dep_update_tool` simply
  defaults to `renovate` (agent/user overridable). `github_host` was only ever setting its default; the
  module keeps its own axis question and its `dependabot.yml` (gated on `dep_update_tool`, not forge).
- **Conditional remote creation.** `github-repo`/`gitlab-repo` gain `create_remote: bool` (default
  false). `create_remote=true` runs `gh`/`glab repo create` (existing init-only, non-fatal tasks);
  `create_remote=false` SKIPS creation but STILL renders the metadata files — this is how a user adopts
  an EXISTING repo and still gets CODEOWNERS/issue/PR templates. There is NO import of live remote state
  (that would break the deterministic, agent-free reproduce guarantee — a separate future feature).
- **Behavior changes (accepted):** (a) issue/PR templates become OPT-IN via selecting the forge module
  (were default-on via base `github_host=true`); (b) `github-repo`/`gitlab-repo` stop being "pure
  side-effect, writes no files" — they now carry MANAGED metadata files (reconcile on reproduce)
  alongside init-only `gh`/`glab` tasks. (`reconcile` is prose convention, not an engine field — grep
  finds it only in comments — so mixing managed files with init-only tasks in one module is mechanically
  fine.)
- **Merging the two repo modules into one `git` module was CONSIDERED and DEFERRED.** Keeping
  `github-repo`/`gitlab-repo` as exclusive siblings preserves the established one-module-per-exclusive-
  choice pattern (same as the terraform/cdk/cloudformation IaC siblings) and avoids a cascade into
  merging ci-github/ci-gitlab. No new module is added by 014.

**Scope note:** R12 makes 014 touch module STRUCTURE (moving files between modules + new questions),
which the original "no new module features / no new modules" scope excluded. The Out-of-scope section is
amended accordingly: R12's forge cleanup is IN scope; NEW modules and net-new user-facing capabilities
remain out.

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
    static lines) + one **idempotent ordered-concat** in the gitignore owner (delimited blocks so
    reproduce does not duplicate), run as a `_post_task` (R11 — after the render loop). No script file;
    no `gitignore_stack` fact.
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

- **Base-produced** (alias `_external_data.base.*`): `project_name`, `layout`,
  `description`, **`default_branch`** (NEW to base — latent bug: ci-github `copier.yml:80-82` /
  ci-gitlab `:91-93` thread it from a non-existent producer today).
  - **`github_host` STRUCK from this set (R12).** It was listed as a base fact (consumer: dep-updates),
    but R12 deletes `github_host` from base entirely (forge metadata moved to the forge modules).
    dep-updates now self-defaults `dep_update_tool` instead of reading a base fact — so there is no
    `github_host` alias to wire. This drops the base fact count from 5 to 4.
  - `description` KEPT + made a base fact (renders into base AGENTS.md, readme README.md, api
    openapi.yaml, apm apm.yml, mkdocs site_description+index). Consumers: apm, api, mkdocs, python,
    readme.
- **precommit-produced** (alias `_external_data.precommit.*`) — ~~`hook_manager`~~ **STRUCK by R13
  (2026-07-17): `hook_manager` is NOT a cross-module fact.** No language module RENDERS `hook_manager`
  (grep-verified across python/ts/api/go/rust/terraform template bodies) — in the old model it only
  gated whether to CONTRIBUTE a hook block, which under the fragment/merge model (R1/R11) is the
  precommit bundler's job, not the language's. Making it a fact forced precommit as a HARD dependency of
  every language (FR-006), breaking `[base + language]` standalone stacks. Ruling (A): languages
  contribute an UNCONDITIONAL `.pre-commit.d/*.yaml` fragment and do NOT read `hook_manager`; ONLY
  precommit reads its own `hook_manager` (not cross-module). Consumers list voided. See R13.
- **ts-produced** (alias `_external_data.ts.*`) — ADDED after critique: **`js_pkg_manager`** (consumers:
  justfile, package-add) and **`ts_linter`** (consumer: editorconfig).
- **moon-produced** (alias `_external_data.moon.*`): `monorepo_tool` (ci-github, ci-gitlab),
  `monorepo_packages` (ci-gitlab, cocogitto). Proves the mechanism is not base-specific.

Producers after the R12/R13 corrections are **base + ts + moon** (precommit is NO LONGER a cross-module
producer — its only reader was itself; R13). Reading a base fact auto-requires base as a dependency; etc. (R6).
Final base facts: `project_name`, `layout`, `description`, `default_branch`, **`org`** (added by R12 —
forge modules read `_external_data.base.org` for CODEOWNERS; see below).

- **Stay BARE-PRIVATE (NOT facts):**
  - ~~`org`~~ `copyright_name`, `branch_strategy` — base-only, no cross-module reader. **`org` MOVED to
    base facts (R12 correction, 2026-07-17):** the forge modules (github-repo/gitlab-repo) read
    `_external_data.base.org` for CODEOWNERS ownership lines — a legitimate cross-reader. `org` is now a
    base-produced fact with identical status to `project_name`. (Verified: `org` is a bare question in
    base copier.yml:28, so the read is mechanically sound; the hard `depends_on: base` already orders it.)
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

### R13 — `hook_manager` NOT a fact (ruling A); cross-format capability translation deferred to spec 015 (ratified 2026-07-17)

**Trigger:** the fan-out revealed the `.pre-commit.d/` fragment model is pre-commit-FORMAT-specific. With
`hook_manager=lefthook`, language hooks (ruff/biome/clippy/golangci) silently VANISH — the bundler emits
only `.pre-commit-config.yaml`; nothing projects the fragments into `lefthook.yml`. Pre-014, `lefthook.yml`
looped over the `hook_blocks` union, so lefthook DID get language hooks. So the fragment model as built is a
regression for the non-default hook manager.

**Ruling A (maintainer, 2026-07-17):** DROP `hook_manager` as a cross-module fact.
- No language module reads `hook_manager` (grep-verified: no language template body renders it). Languages
  contribute an UNCONDITIONAL `.pre-commit.d/*.yaml` fragment; only precommit reads its OWN `hook_manager`.
- This keeps `[base + language]` stacks generatable WITHOUT precommit (FR-006 hard-dep avoided). python's
  implementation is the reference; go/rust/api/terraform DROP their `_external_data.precommit` alias +
  `depends_on: [bailiff-mod-precommit]` (keep the unconditional fragment). justfile keeps its graceful
  raw-tool `lint` recipe (never hard-reads the fact).
- **precommit phase is UNCHANGED: `_bailiff_phase: normal` + merge as a `_post_task` (R11).** It does NOT
  move to `post` phase — phase controls render/ordering (precommit renders early), `_post_tasks` gives the
  merge its "run last". These are orthogonal; only the merge runs post-loop, not the module.
- **014 SHIPS the pre-commit path (works, verified).** lefthook is a DOCUMENTED KNOWN LIMITATION for 014:
  with `hook_manager=lefthook`, language-contributed hooks are NOT wired (must warn/omit, NOT silently
  drop). The general fix is spec 015 below.

**Spec 015 (ratified DIRECTION — normalized project-wide agent-projected capability contract):** the real
problem is generic-intent → tool-specific-config translation, and it is NOT hooks-specific — it applies to
EVERY capability with pluggable backends (hooks: pre-commit/lefthook; CI; formatters; future third-party).
Design principles ratified for 015:
1. **Contributor declares capability INTENT into a neutral drop-dir, manager-agnostic** (generalize the
   `.mise/conf.d/` inversion): the contributor NEVER depends on or imports the consumer/manager. It drops a
   fragment; whichever manager module is selected scans the dir. None selected → inert. This is why the
   contributor needs NO `depends_on` on "precommit-or-lefthook-or-…" (the messy N-managers coupling the
   maintainer rejected).
2. **Translation tiering — escalate only when the lower tier can't express it:** native drop-in merge (mise)
   > mechanical same-format merge (single-manager pre-commit, gitignore) > **agent-mediated translation**
   (cross-format: pre-commit vs lefthook vs third-party). A static neutral schema was REJECTED — it can't
   cover unknown third-party managers and becomes a leaky superset of every backend's config.
3. **Cross-format translation is done by the phase-1 AGENT and FROZEN as a recorded answer** — identical in
   class to how `bailiff-mod-dep-updates` already maps package managers into the chosen tool's vocabulary
   (dependabot ids vs renovate managers) and freezes it. Reproduce replays the frozen config → deterministic,
   agent-free (Constitution III preserved).
4. **NORMALIZE + MAKE MACHINE-READABLE:** today "the agent fills this" exists ONLY as scattered free-text
   `copier.yml` comments + narrative in `_cross-cutting.md`/`013 spec`/`SKILL.md` — there is NO uniform
   marker a tool (or author, or third party) can rely on. 015 MUST define a normalized, machine-readable
   marker for "this output is agent-projected from the selected stack" and DOCUMENT the one canonical pattern
   (FR-018 authoring guide + cross-cutting contract) so every module — first- or third-party — follows the
   same shape. The agent MUST check/redo the projection based on the actual module SELECTION, for ALL
   capabilities, not just hooks.

## Out of scope for 014

- NEW modules and net-new user-facing module CAPABILITIES. (NOTE: R12's forge cleanup — moving `.github/`
  metadata out of base into the forge modules, deleting `github_host`, adding a `create_remote` toggle —
  IS in scope; it restructures existing modules and fixes a latent contradiction, it does not add a new
  module or a new capability.)
- IMPORTING live remote state (reading an existing repo's config back into answers) — would break the
  deterministic, agent-free reproduce guarantee; a separate future feature if ever wanted (R12).
- The `framework` point-fix itself (separate branch).
- Conditional-Jinja contribution expressiveness beyond what the pre-commit fragment needs.
- Stack presets (013 FR-017, still deferred).
- **Cross-format capability translation / lefthook language-hook wiring → SPEC 015** (R13): the normalized
  agent-projected capability contract (neutral drop-dir + machine-readable agent-projected marker +
  agent-does-cross-format-translation-and-freezes + documentation). 014 ships pre-commit-path-only with
  lefthook as a documented known limitation.
- Constitution amendment (none anticipated; engine changes fall under the 013 C-11 relaxation).
