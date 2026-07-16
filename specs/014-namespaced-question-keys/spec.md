# Feature Specification: Namespaced question keys, private-by-default answer threading, and the drop-in/union split (spec 014)

**Feature Branch**: `014-namespaced-question-keys`

**Created**: 2026-07-16

**Status**: Draft — research-first. This spec RATIFIES the model; plan.md + tasks.md are a
separate pass after the decisions-ledger is accepted. Authored after a real cross-module
bug (`framework` collision) surfaced by the spec-013 integration tests.

**Input**: The integration-test finding of 2026-07-16 (three modules — python, ts, stack-adr
— defined a copier question named `framework` with incompatible value domains, and
`init_many`'s answer threading poisoned any stack selecting both python and ts), plus the
copier + mise capability research recorded in `decisions-ledger.md`. Governed by the
constitution (v3.0.0) and ADRs 0001–0008. Extends the 011 cross-cutting contract; does not
reopen 011/012/013 module behavior except where a key is renamed for namespacing.

---

## Overview

bailiff composes a project from independent `bailiff-mod-*` copier templates applied as
layers. Today `init_many` threads **every** non-`_`-prefixed answer from each rendered layer
into the `data=` dict of the next layer (`_merge_layer_answers`, runner.py:532). This blanket
bleed is a bailiff invention — **stock copier isolates templates** (one answers file per
template; no shared answer namespace) and offers `_external_data` for *explicit, namespaced*
cross-template reads.

The blanket bleed causes **answer poisoning**: when two modules define a question with the
same key but different value domains, the first layer's answer flows into the second layer,
which validates the inherited value against its own choices and hard-fails. This is not
hypothetical — it shipped. `bailiff-mod-python` (`framework ∈ {none,fastapi,django,flask}`)
and `bailiff-mod-ts` (`framework ∈ {plain,nuxt,vite,sst}`) break every Python+TS stack.

Spec 014 makes **privacy the default** (a module's questions stay in its own layer unless
explicitly shared), aligns cross-module sharing with copier-native mechanisms, and eliminates
the largest "union" entirely by using mise's native drop-in config. The philosophy is
inherited directly from spec 013: **enforce structure, don't trust author discipline** — a
private key must be *unable* to leak, not merely *conventionally* named to avoid collision.

This spec covers **engine threading behavior + a small set of key renames + the universal
fragment/merge model that eliminates cross-module answer unions entirely**. It does NOT
introduce new module features. C-11 relaxation from 013 applies (engine changes are the
governed exception; this spec touches `src/bailiff/runner.py`).

---

## The universal fragment/merge pattern (the core model)

The governing insight (ratified 2026-07-16): **a cross-module "union" is an anti-pattern that
exists only because a single output file was assumed to have a single writer.** Replace every
such union with the same universal shape:

> **Each module renders ONLY its own fragment into its own path. The combined artifact is
> produced by a merge — either the target tool's NATIVE drop-in merge, or, where the tool has
> none, a single bailiff post-install merge task that folds all fragments into the one file
> the tool expects.**

This turns N-writers-of-one-file (a collision, forbidden by 013) into N-writers-of-N-files
(no collision) plus one deterministic merge. It applies to EVERYTHING that is otherwise a
single-file union:

| Surface | Native drop-in? | Model under 014 |
|---|---|---|
| `mise_tools` → `.mise.toml` | ✅ `.mise/conf.d/*.toml` | Per-module drop-in; **mise merges natively** at `mise install`. No merge task. |
| `hook_blocks` → `.pre-commit-config.yaml` | ❌ pre-commit has none | Per-module `.pre-commit.d/<module>.yaml` fragments; **one bailiff post-install merge task** folds them into `.pre-commit-config.yaml`. |
| `gitignore_stack` → `.gitignore` | ❌ (git composes by precedence, not committed-file merge) | Per-module `.gitignore.d/<module>` fragments — produced by gitnr OR as literal static lines — **one bailiff merge task** concatenates into `.gitignore`. Supports non-gitnr / static-list packages. |
| `quality_languages` | n/a | NOT shared — single module declares AND consumes it. No change. |

**Consequence: there are ZERO cross-module answer unions after 014.** No module contributes to
another module's answer list; no key like `mise_tools` / `hook_blocks` / `gitignore_stack` is
threaded across layers at all. What remains is (a) per-module fragments, (b) native or task
merges, and (c) cross-module *facts* (single values like `project_name`) read via copier
`_external_data` aliases — see below.

### Cross-module facts via `_external_data` aliases — no prefix (ratified)

A module that needs a value another module produced reads it through copier's `_external_data`,
which maps a **local alias** to the producer's answers file. bailiff's per-layer answers-file
name is deterministic (`.copier-answers.<module-basename>.yml`, verified in
`ordering.py:answers_file_name`), so a consumer can point an alias at any producer:

```yaml
# consumer module copier.yml
_external_data:
  base: .copier-answers.bailiff-mod-base.yml
project_name:
  type: str
  default: "{{ _external_data.base.project_name }}"   # base is a HARD dependency (FR-006, inverted)
```

The borrowed value lives under the **alias namespace** (`_external_data.base.project_name`) —
copier isolates it structurally; it never enters the consumer's own question namespace and
never lands in the consumer's answers file. **No vendor prefix is needed** (an earlier
`bailiff__<name>` scheme is REJECTED — copier's alias namespacing already isolates cross-module
reads, works across vendors since each producer's answers file is a distinct alias, and adds no
convention to lint). Most facts are base-produced (`project_name`, `layout`, `github_host`,
`default_branch`); the few that aren't (e.g. `monorepo_tool` produced by moon, read by CI) use
the same mechanism with a different alias (`_external_data.moon.monorepo_tool`).

### Config-consistency, not byte-identity (invariant relaxation)

A merged artifact (`.pre-commit-config.yaml` folded from fragments, `.gitignore` appended from
tokens) cannot be byte-identical on reproduce — a YAML re-emit or an append reorders/reformats.
bailiff's reproduce guarantee is therefore relaxed from **byte-identical** to
**config-consistent**: a reproduced file expresses the SAME configuration (same tools, same
hooks, same ignore rules), not necessarily the same bytes. Managed single-module renders remain
deterministic; the merge outputs are config-equivalent. This is the invariant that makes the
universal fragment/merge pattern sound.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A private question never poisons another module (Priority: P1)

A user (or the phase-1 agent) composes a stack containing two modules that each define a
question with the same bare key but different, incompatible value domains. `bailiff init`
renders both layers correctly: each module's private question is answered from its OWN default
or the run-spec's per-layer answers, and neither layer sees the other's value.

**Why this priority**: This is the bug that motivated the spec. Answer poisoning is a
correctness failure that breaks real stacks (Python+TS today) and will recur for any future
key collision as the module family grows.

**Independent Test**: Build a two-layer selection where layer A defines `q ∈ {x,y}` and layer
B defines `q ∈ {m,n}`. Init the stack → A renders with its `q`, B renders with its `q`, no
`InvalidRunSpecError`; each layer's answers file records only its own `q`.

**Acceptance Scenarios**:

1. **Given** two selected modules with the same private question key and disjoint choice sets,
   **When** `init_many` runs, **Then** neither layer's answer for that key appears in the
   other layer's `data=`, and both render successfully.
2. **Given** the Python+TS regression case specifically (`framework` in both), **When** a
   monorepo stack selecting both is inited, **Then** it succeeds (this is the exact failure
   the spec-013 integration test caught).
3. **Given** a single-module stack, **When** inited, **Then** behavior is byte-identical to
   pre-014 (isolation changes nothing when there is only one layer).

### User Story 2 — A module reads a cross-module fact via `_external_data` alias (Priority: P1)

A module that needs a value produced by another module (e.g. a language overlay needing base's
`project_name` or `layout`) reads it through copier's `_external_data` mechanism: it declares a
local alias pointing at the producer's deterministic answers file
(`.copier-answers.<producer-basename>.yml`) and reads `{{ _external_data.<alias>.<key> }}`. No
ambient bleed; no vendor prefix. The value is isolated under the alias namespace by copier and
never enters the consumer's own question space.

**Why this priority**: Cross-module facts are real and necessary (base produces `project_name`;
overlays read it). Reading them through `_external_data` aliases is copier-native, needs no
naming convention or lint, and works across vendors because each producer's answers file is a
distinct alias.

**Independent Test**: A consumer declares `_external_data: {base: .copier-answers.bailiff-mod-base.yml}`
and reads `{{ _external_data.base.project_name }}`; with base in the stack it resolves base's
value; WITHOUT base, bailiff raises a loud preflight error naming the missing producer (the read is
a hard data-dependency — FR-006 inverted).

**Acceptance Scenarios**:

1. **Given** base (producer) writing `project_name` to its answers file and a consumer aliasing
   base as external data, **When** both are in a stack, **Then** the consumer renders base's
   `project_name` (and base is ordered before the consumer).
2. **Given** the same consumer with NO producer in the stack, **When** inited alone, **Then**
   bailiff raises a LOUD preflight error naming the `_external_data.base` alias's missing producer —
   NOT a silent empty render (copier's own behavior would return `{}` → empty string; bailiff
   produces the error copier will not).
3. **Given** a non-base producer (e.g. moon writing `monorepo_tool`), **When** a CI module
   aliases moon and reads `_external_data.moon.monorepo_tool`, **Then** it resolves — the
   mechanism is not base-specific.
4. **Given** the producer's answers-file name, **When** the consumer aliases it, **Then** the
   name is the deterministic `.copier-answers.<module-basename>.yml` (verified in
   `ordering.py`), so the alias path is knowable at authoring time.

### User Story 3 — mise tools compose via drop-in files, no union (Priority: P1)

A user selects base + several tool-contributing modules (cocogitto, moon, api…). Each module
renders its OWN `.mise/conf.d/<vendor>-<module>.toml` containing only the tools it needs. mise
merges all drop-in files at runtime; `mise install` installs the union of every tool. No
module combines a list; no single module owns `.mise.toml`.

**Why this priority**: `mise_tools` is the largest and most-contributed union (10 modules). It
exists only because `.mise.toml` was assumed to be one file with one writer — which is exactly
a file-collision under 013's rules. mise's `.mise/conf.d/` drop-in directory (verified in
mise source `config_root.rs`) eliminates the constraint entirely.

**Independent Test**: Init base + cocogitto + moon → three files under `.mise/conf.d/`, each
with its own `[tools]`; `mise cfg` shows all three merged; the set of installed tools equals
the union. Reproduce re-renders each drop-in file byte-identically (each is a normal managed
render of a single module — no cross-layer dependency).

**Acceptance Scenarios**:

1. **Given** N tool-contributing modules, **When** inited, **Then** each writes a distinct
   `.mise/conf.d/<vendor>-<module>.toml` and NONE writes `.mise.toml`; no file collision
   occurs (013 collision check passes).
2. **Given** a devcontainer in the stack, **When** inited, **Then** its `postCreateCommand`
   runs `mise install` with NO explicit tool list (it reads the merged conf.d), and the
   container installs exactly the configured tools.
3. **Given** any tool module alone, **When** reproduced over a committed tree, **Then** its
   drop-in file re-renders config-consistently with no toolchain or network (a single-module
   managed render stays deterministic).
4. **Given** a stack with zero tool modules beyond base, **When** inited, **Then** base's own
   drop-in (or a minimal valid config) is present and `mise install` is a valid no-op.

### User Story 4 — pre-commit config composes via fragments + one merge task (Priority: P2)

Modules that contribute pre-commit hooks each render their OWN fragment
(`.pre-commit.d/<vendor>-<module>.yaml`) containing only their hook block. Because pre-commit
has no native drop-in, a single bailiff post-install merge task folds all fragments into the
one `.pre-commit-config.yaml` pre-commit expects — deterministically ordered and deduplicated.
The merged file is config-consistent on reproduce (same hooks; not necessarily identical
bytes).

**Why this priority**: pre-commit is the canonical "no native drop-in" case — it proves the
universal fragment/merge pattern for tools that lack conf.d. It is NOT an answer union: no
module contributes to a shared `hook_blocks` answer; each writes a file, and a task merges.
P2 because it depends on the fragment/merge mechanism and the shared-fact model (US2) being
settled first.

**Independent Test**: Init precommit + two hook-contributing modules → two
`.pre-commit.d/*.yaml` fragments + a merge task producing `.pre-commit-config.yaml` with both
hooks; reproduce yields a config-equivalent file; the same two modules in the other selection
order yield the SAME merged config (order-independent merge).

**Acceptance Scenarios**:

1. **Given** N modules contributing hook fragments + precommit, **When** inited, **Then** each
   contributor writes a distinct `.pre-commit.d/<vendor>-<module>.yaml` (no collision), and the
   precommit merge task produces one `.pre-commit-config.yaml` containing all N hooks, sorted
   deterministically.
2. **Given** the same set in a different layer order, **When** inited, **Then** the merged
   config is equivalent (merge is order-independent).
3. **Given** a hook contributor but NO precommit module (or `hook_manager=none`), **When**
   inited, **Then** the fragments may exist but no merge runs — the hook file is not produced
   (contribution inert without the merger).
4. **Given** a populated committed tree, **When** reproduced, **Then** `.pre-commit-config.yaml`
   comes back config-consistent (same hooks) with no drift.

### User Story 5 — Reproduce and update survive the key renames (Priority: P1)

Projects generated before 014 have `.copier-answers*.yml` files recording the OLD key names
(bare `project_name`, `mise_tools`, `framework`). The spec MUST define what happens to those
trees: either a migration/alias path or an explicit, documented break scoped to the near-zero
population of pre-014 scaffolded projects.

**Why this priority**: Constitution III / spec 013 SC-008 require reproduce to be faithful.
Renaming recorded question keys breaks reproduce over committed trees unless handled. This
must be resolved before any rename ships.

**Independent Test**: Take a tree scaffolded by a pre-014 module (recorded bare keys) and run
`reproduce` after the rename lands → either it succeeds via alias/migration, or the break is
detected and reported with a documented remediation (never a silent wrong render).

**Acceptance Scenarios**:

1. **Given** a pre-014 committed tree with bare recorded keys, **When** reproduced post-rename,
   **Then** the defined disposition occurs (migration, alias, or a clear documented error —
   NOT a silent mis-render).
2. **Given** the near-zero real population (greenfield; 27 mirrors just published; no external
   users), **When** the disposition is chosen, **Then** the decision records the population
   argument and the chosen cost.

### Edge Cases

- **A private key that a module WANTS to expose later**: no rename needed — the producer already
  writes it to its answers file as a normal bare question; a consumer opts in by declaring an
  `_external_data` alias at the producer's answers file and reading `{{ _external_data.<alias>.<key> }}`.
  There is no implicit promotion and no shared-key namespace to reserve.
- **A shared fact whose producer is absent from the stack**: LOUD preflight error naming the alias's
  missing producer — the read is a hard data-dependency (FR-006 inverted; US2 AS2), never a silent
  fallback (copier's own missing-file behavior returns `{}` → empty render, which SC-006 forbids).
- **mise conf.d on a system without mise**: the drop-in files are inert config; `mise install`
  is the only step that needs mise, and it is init-only-guarded per the existing task
  contract.
- **pre-commit merge when fragments disagree on a rev pin**: deterministic resolution rule
  required (the merge is first-party-authored; a rule such as "highest pin wins" or "explicit
  conflict error" is a plan-phase decision).
- **gitignore per-module vs frozen fact**: if per-module fragment/append is chosen, the merge
  MUST be idempotent (delimited stack blocks) so reproduce does not duplicate; if frozen-fact
  is kept, base remains the single gitnr caller. Plan-phase decision. Either way the guarantee
  is config-consistency (same ignore rules), not byte-identity.
- **Reproduce/update never re-thread**: the private-by-default change applies to init AND the
  reproduce/update accumulator (which also reads answers files) — reproduce must reconstruct
  the SAME per-layer isolation, not a flattened namespace.

## Requirements *(mandatory)*

### Functional Requirements — private-by-default threading

- **FR-001** *(no blanket bleed)*: `init_many` MUST NOT thread a layer's private answers into
  subsequent layers' `data=`. A question key is PRIVATE unless it is explicitly declared
  shared (FR-004). `_merge_layer_answers` (runner.py:532) MUST be changed from "merge all
  non-`_` keys" to "merge only declared-shared keys."
- **FR-002** *(isolation is the default)*: Each layer renders with its own per-layer answers
  plus copier/bailiff builtins (`_copier_conf`, `today`, run-ordering keys) plus any facts it
  reads via `_external_data` (FR-004) — never another module's private answers threaded through
  `data=`. NOTE (verified): `accumulated` is seeded ONLY with `today` (runner.py:430); there is
  NO run-level `--data` channel in the input model (the multi-run-spec exposes only per-layer
  `answers`, cli.py:286). Private-by-default = `accumulated` stays `{today}` and never accretes.
- **FR-003** *(reproduce/update parity)*: The reproduce and update accumulators MUST apply the
  same isolation rule (FR-012 of 013 keeps capability/collision out of those paths; this spec
  keeps private-answer bleed out of them too). A committed tree reproduces per-layer, not from
  a flattened namespace.

### Functional Requirements — cross-module facts via `_external_data`

- **FR-004** *(read via `_external_data` alias)*: A module that needs a value another module
  produced MUST read it through copier `_external_data`: declare a local alias pointing at the
  producer's answers file and reference `{{ _external_data.<alias>.<key> }}`. The producer
  simply writes the key to its own answers file as a normal question. NO vendor prefix and NO
  cross-layer threading of the key. The producer set is **base, precommit, ts, moon** (final fact
  set in decisions-ledger R4).
- **FR-005** *(deterministic producer path)*: Consumers rely on the deterministic per-layer
  answers-file name `.copier-answers.<module-basename>.yml` (`ordering.py:answers_file_name`).
  This name is a stable contract; changing the naming scheme is a breaking change gated
  separately.
- **FR-006** *(a fact read is a HARD data-dependency — INVERTED)*: Reading `_external_data.<alias>.<key>`
  makes the aliased producer a HARD dependency. bailiff statically parses the consumer's
  `_external_data` block, maps each alias → producer basename, and at preflight: producer ABSENT →
  LOUD error (reuse `OrderingError`, naming the offending alias); producer PRESENT → ordered before
  the consumer. There is NO graceful fallback (the prior FR-006 is REPLACED): copier's own behavior on
  a missing external-data file is to return `{}` → an unguarded `{{ _external_data.base.project_name }}`
  renders EMPTY STRING, i.e. the silent mis-render SC-006 forbids. bailiff produces the error copier
  will not. See decisions-ledger R6 + "FR-006 INVERTED".
- **FR-006a** *(`_external_data` path lint — discovery)*: For the static alias→producer mapping to
  work, an `_external_data` value MUST be a literal `.copier-answers.<basename>.yml` (no Jinja
  expression, no path traversal, no URL). Discovery rejects non-literal/non-convention paths for
  first-party modules with a clear error (decisions-ledger R9).
- **FR-007** *(no vendor prefix, no shared-key lint)*: The `<vendor>__<name>` prefix scheme and
  its lint are explicitly REJECTED — copier alias namespacing isolates cross-module reads
  structurally and works across vendors without convention. `check_modules.py` gains no
  shared-key naming lint. Every question key stays a normal (bare) key, private by default
  (FR-001), shared only by being read through an alias.

### Functional Requirements — dependency model (single edge + stratified DAG)

- **FR-019** *(single `depends_on` edge)*: The edge vocabulary collapses to ONE edge: `depends_on`
  (target present + ordered-before; ABSENT target → loud `OrderingError`, the existing dangling-edge
  behavior made explicit). `run_after` and `run_before` are DROPPED (`ordering.py` stops handling them;
  the ~23 `run_after: bailiff-mod-base` migrate to `depends_on: bailiff-mod-base`). Rationale: today the
  two are byte-identical in code and only `run_after: base` is used; `run_before` has zero uses and
  doubles DAG cycle surface. `depends_on` expresses SIDE-EFFECT dependencies (X needs a tool Y installed
  or a file Y wrote) — distinct from the DATA dependency FR-006 covers. (decisions-ledger R6/R7.)
- **FR-020** *(pre/normal/post stratified DAG)*: Modules carry a phase — `pre` | `normal` (default) |
  `post`. Sort = (phase) → (`depends_on` DAG) → (basename). Edge legality is VALIDATED at discovery:
  `pre`→pre only; `normal`→pre+normal; `post`→anything; a forward cross-phase edge is rejected with a
  clear error (cycles cannot cross phases). `base = pre`; the module family = `normal`; `post` is
  RESERVED for a future finalizer (none exists today). This gives structural "run first / run last"
  without a last-mover enumerating N edges. (decisions-ledger R8.)

### Functional Requirements — mise drop-in (union dissolution)

- **FR-008** *(mise conf.d)*: The `mise_tools` union MUST be replaced by per-module
  `.mise/conf.d/<vendor>-<module>.toml` drop-in files. Each tool-contributing module renders
  ONLY its own tools into its own file. No module writes `.mise.toml`; no module reads a
  combined `mise_tools` list.
- **FR-009** *(devcontainer reads merged config)*: `bailiff-mod-devcontainer`'s
  `postCreateCommand` MUST run `mise install` with no explicit tool list — it consumes the
  merged conf.d, not a frozen `mise_tools` answer. The devcontainer no longer depends on the
  union.
- **FR-010** *(no collision from drop-ins)*: Because each module owns a distinct
  `.mise/conf.d/*.toml` path, the 013 init-time collision check MUST pass for any combination
  of tool modules (distinct paths, no overlap).

### Functional Requirements — pre-commit fragments + merge task

- **FR-011** *(fragment + merge, not answer union)*: `hook_blocks` as a threaded answer union
  MUST be eliminated. Each contributing module renders its OWN
  `.pre-commit.d/<vendor>-<module>.yaml` fragment (its hook block only; MAY be conditional on
  the module's own answers). `bailiff-mod-precommit` **vendors a single Python bundler**
  (`scripts/_merge_precommit.py`, owner-side — sees all fragments; NOT a `bailiff merge` CLI) run as
  a post-install task that folds all fragments into `.pre-commit-config.yaml`. The merge MUST be
  deterministic and order-independent (same fragment set → equivalent config regardless of layer
  order) and config-consistent on reproduce. On a rev-pin conflict (two fragments pinning the SAME
  hook repo at DIFFERENT revs) the bundler picks the **highest rev and WARNS** — it does NOT abort
  (decisions-ledger R2, revised: a hard error would let one lagging third-party module veto an
  otherwise-valid stack, colliding with the open-ecosystem premise).
- **FR-012** *(single merger, inert without it, no collision)*: Exactly one module (precommit)
  runs the merge. When precommit is absent or `hook_manager=none`, no merge runs and no
  `.pre-commit-config.yaml` is produced (fragments are inert). Because each contributor owns a
  distinct `.pre-commit.d/*.yaml` path, the 013 collision check passes. `check_modules.py` MAY
  lint the single-merger invariant.

### Functional Requirements — gitignore & migration

- **FR-013** *(gitignore disposition — RESOLVED)*: `gitignore_stack` is eliminated as a threaded
  fact. Each contributing module writes a per-module `.gitignore.d/<vendor>-<module>` fragment
  (gitnr-produced OR literal static lines). The gitignore owner runs ONE idempotent ordered-concat
  (an inline shell task, delimited blocks) folding the fragments into `.gitignore`. No `bailiff merge`
  CLI and no vendored script for this surface (concat is trivial). Reproduce MUST NOT duplicate
  entries (config-consistent guarantee via delimited blocks).
- **FR-014** *(rename migration + detection gate)*: A documented BREAK + re-init is ratified (R3;
  near-zero pre-014 population). But "clear error, not silent mis-render" needs a MECHANISM: copier
  silently ignores unknown recorded answer keys (verified: `load_answersfile_data` returns `{}`, never
  errors), so a pre-014 tree with `mise_tools:` recorded would reproduce WITHOUT the tools and WITHOUT
  error. Therefore post-014 modules MUST stamp `_bailiff_schema: 014` into their answers files, and
  `reproduce_many` MUST REFUSE (loud error + re-init guidance) when a recorded answers file lacks the
  marker or carries an older schema. This gives SC-006 real teeth. (decisions-ledger R10.)

### Functional Requirements — governance & scope

- **FR-015** *(no new module features)*: This spec renames keys, changes engine threading, and
  restructures mise/hook/gitignore output — it introduces NO new user-facing module
  capabilities. The 011 cross-cutting contract is amended (single-writer unions → drop-in
  where possible); the amendment is recorded.
- **FR-018** *(module-authoring documentation)*: The module structure/how-to documentation MUST
  be updated to teach the new model, because it changes how every module author works. Scope:
  (a) the 011 cross-cutting contract (`specs/011-.../contracts/_cross-cutting.md`) — replace the
  frozen-union single-writer sections with the fragment/merge pattern and the `_external_data`
  fact-read pattern; (b) `SKILL.md` (the authoring skill) — the "how to write a module" steps;
  (c) the `_meta/module-template/` scaffold that `just new-module` copies — its `copier.yml` and
  README must demonstrate a `.mise/conf.d/` fragment and an `_external_data` alias, not a union
  contribution; (d) `templates/*/README.md` prose where it references the old union model; (e) a
  concrete authoring guide covering: private-by-default questions, when/how to read a
  cross-module fact via `_external_data`, how to contribute a fragment (mise/pre-commit/gitignore),
  and the config-consistency (not byte-identity) reproduce guarantee. A module author reading the
  docs MUST be able to write a correct new module without reverse-engineering an existing one.
- **FR-016** *(decisions ledger prerequisite)*: The ratified `decisions-ledger.md` MUST exist
  and be accepted before the plan phase begins (011/013 precedent).
- **FR-017** *(constitution check)*: Engine changes are within the C-11 relaxation established by
  013 (engine is the governed exception). 014's engine footprint is LARGER than a single threading
  tweak — it spans `runner.py` (neuter `_merge_layer_answers`; `_external_data` validation in the
  preflight; `_bailiff_schema` gate in `reproduce_many`), `ordering.py` (drop `run_after`/`run_before`;
  add the pre/normal/post stratified sort + edge-legality validation), and `discovery.py` (static
  `_external_data` parse + path lint). All fall under the 013 engine exception; no new constitution
  amendment is anticipated (the byte→config invariant reframe already landed). The plan phase confirms.

### Out of scope

- New module features or new modules.
- The `framework` collision point-fix itself (landing separately on
  `fix-framework-collision`; 014 generalizes the CLASS, not that instance).
- Conditional-Jinja contribution expressiveness beyond hook_blocks (if a future union needs
  it).
- Stack presets (013 FR-017, still deferred).

## Success Criteria *(mandatory)*

- **SC-001**: A stack selecting two modules with the same private question key and disjoint
  domains inits successfully; the Python+TS `framework` regression passes without the point-fix
  rename (i.e., isolation alone would have prevented it).
- **SC-002**: Cross-module facts resolve only through declared `_external_data` aliases at a
  producer's answers file; no private answer appears in another layer's render context (verified by
  an isolation test). A consumer whose producer is ABSENT triggers a LOUD preflight error naming the
  alias — never a silent empty render (FR-006, inverted).
- **SC-003**: A multi-tool stack produces per-module `.mise/conf.d/*.toml` files, no
  `.mise.toml`, and `mise install` (bare) installs the union; the 013 collision check passes.
- **SC-004**: the pre-commit fragment merge is order-independent and config-consistent on
  reproduce (same hooks regardless of layer order; no duplicate hooks across re-runs); two fragments
  pinning the same hook repo at different revs resolve to the HIGHEST rev with a warning, not an abort
  (FR-011, R2 revised).
- **SC-008**: The dependency model is proven: `depends_on` is the sole edge; an `_external_data`
  read with its producer absent errors loud (FR-006); a forward cross-phase edge (`normal`→`post`)
  is rejected at discovery (FR-020); a pre-014 answers file (no `_bailiff_schema`) makes reproduce
  refuse (FR-014).
- **SC-005**: The private-by-default engine change is proven by a negative isolation test: two
  layers with the same bare key and disjoint domains render without cross-layer bleed. (No shared-key
  naming lint exists — FR-007 rejects it.)
- **SC-006**: Reproduce/update over a post-014 committed tree is faithful; the pre-014
  disposition (FR-014) behaves as ratified (migrate, alias, or documented error — never silent
  mis-render).
- **SC-007**: The existing loop + integration suites pass; no private-key collision is possible
  by construction (an added negative test proves isolation).

## Assumptions

- copier `_external_data` (verified 2026-07-16 against copier docs) is the sanctioned
  cross-template read mechanism; namespaced, opt-in, does not pollute the consumer's answers
  file.
- mise `.mise/conf.d/*.toml` drop-in merging (verified against mise source `config_root.rs`)
  is stable and merges all drop-in files at runtime.
- `.gitignore` has no committed drop-in merge (git composes by precedence, not by merging
  multiple committed root files); gitignore is task-output (already non-byte-asserted).
- pre-commit has no include/drop-in for `.pre-commit-config.yaml`; a single-file combine is
  irreducible.
- The pre-014 scaffolded-project population is effectively zero (greenfield; no external users;
  the 27 mirrors were published 2026-07-16 and can be re-fanned).
- The 013 engine (init_many pre-check/threading, discovery static parsing, `_external_data`
  availability, collision check, `ClerkError` hierarchy) is consumed as-is and extended.

## Open questions — ALL RESOLVED (2026-07-16; see decisions-ledger.md §RATIFIED R1–R10)

1. **pre-commit merge mechanism** → R1: engine does zero merging; `.d/` dirs are the contract;
   `bailiff-mod-precommit` vendors ONE Python bundler (owner-side, sees all fragments). No `bailiff
   merge` CLI. Rev-pin conflict → R2 (revised): **highest-pin-wins + warn**, not a hard error
   (open-ecosystem: a lagging third-party module must not veto a valid stack).
2. **gitignore disposition** (FR-013) → R1: per-module `.gitignore.d/` fragments + one idempotent
   ordered-concat inline shell task in the gitignore owner. No `gitignore_stack` fact.
3. **Rename migration** (FR-014) → R3 + R10: documented break + re-init AND a `_bailiff_schema: 014`
   marker with refuse-on-mismatch in `reproduce_many` (copier won't error on stale keys; bailiff must).
4. **First-party shared-fact set** (FR-007) → R4 (expanded after exhaustive audit): producers =
   **base** (`project_name`, `layout`, `github_host`, `description`, `default_branch`-new) +
   **precommit** (`hook_manager`) + **ts** (`js_pkg_manager`, `ts_linter`) + **moon** (`monorepo_tool`,
   `monorepo_packages`). Collision-class `test_runner` stays PRIVATE; exclusive-sibling +
   `org`/`copyright_name`/`branch_strategy` stay bare-private.
5. **Vendor-prefix separator** → R5: **MOOT** — dropped for `_external_data` aliases; bare keys only.
6. **Dependency model** (grill 2026-07-16) → R6–R9: a fact read is a HARD data-dependency (FR-006
   inverted — loud error on absent producer, no fallback); single `depends_on` edge, `run_after`/
   `run_before` DROPPED (FR-019); pre/normal/post stratified DAG with edge-legality validation
   (FR-020); `_external_data` path lint (FR-006a).
