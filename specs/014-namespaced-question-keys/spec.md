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
| `hook_blocks` → `.pre-commit-config.yaml` | ❌ pre-commit has none | Per-module `.pre-commit.d/<vendor>-<module>.yaml` fragments; **one bailiff post-install merge task** folds them into `.pre-commit-config.yaml`. |
| `gitignore_stack` → `.gitignore` | ❌ (git composes by precedence, not committed-file merge) | Per-module fragment (or gitnr per-module) + merge/append into `.gitignore`, OR keep as a frozen fact + single gitnr call. Plan-phase pick. |
| `quality_languages` | n/a | NOT shared — single module declares AND consumes it. No change. |

**Consequence: there are ZERO cross-module answer unions after 014.** No module contributes to
another module's answer list; no key like `mise_tools` / `hook_blocks` is threaded across
layers at all. What remains is (a) per-module fragments, (b) native or task merges, and (c)
namespaced shared *facts* (single-value threading like `project_name`) via `_external_data`.

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

### User Story 2 — A module explicitly shares a fact, namespaced by vendor (Priority: P1)

A module that needs a value produced by another module (e.g. a language overlay needing
base's `project_name` or `layout`) reads it through copier's `_external_data` mechanism,
under a **vendor-namespaced key** (`bailiff__project_name`), never via ambient bleed. The
producing module publishes the fact under the same vendor-namespaced key. A third-party
vendor's modules share their own facts under their own prefix (`acme__foo`) with zero
collision risk against first-party or other vendors.

**Why this priority**: Cross-module facts are real and necessary (base sets `project_name`;
everything reads it). The sharing must be explicit and namespaced so it survives a
multi-vendor ecosystem — a centralized first-party allowlist cannot know a third-party
vendor's shared keys.

**Independent Test**: A consumer module declares `_external_data` pointing at the producer's
answers file and reads `{{ _external_data.<ns>.bailiff__project_name }}`; the producer writes
`bailiff__project_name` to its answers file. Rendering the consumer resolves the shared value;
a stack without the producer falls back to the consumer's own default.

**Acceptance Scenarios**:

1. **Given** a producer module writing `bailiff__project_name` and a consumer declaring it as
   external data, **When** both are in a stack, **Then** the consumer renders the producer's
   value.
2. **Given** the same consumer with NO producer in the stack, **When** inited alone, **Then**
   it falls back to its own default (no hard failure on a missing producer).
3. **Given** a third-party module sharing `acme__toolchain` and a first-party module sharing
   `bailiff__mise` context, **When** both are in a merged catalog, **Then** the two vendor
   namespaces never collide.
4. **Given** any shared key, **When** `check_modules.py` runs, **Then** it enforces the
   `<vendor>__<name>` shape for keys declared shared (well-formedness lint).

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

- **A private key that a module WANTS to expose later**: it must explicitly rename it to
  `<vendor>__<name>` and publish it as shared — there is no implicit promotion.
- **Two vendors both prefix `bailiff__`**: forbidden — the `bailiff__` namespace is
  first-party-reserved; third parties MUST use their own vendor prefix (lint-enforced for
  first-party; runtime-warn for third-party, mirroring 013's capability lint split).
- **A shared fact whose producer is absent from the stack**: consumer falls back to its own
  default; never a hard failure (US2 AS2).
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
  plus injected shared facts (FR-004) plus copier/bailiff builtins (`_copier_conf`, today,
  run-ordering keys) — never another module's private answers.
- **FR-003** *(reproduce/update parity)*: The reproduce and update accumulators MUST apply the
  same isolation rule (FR-012 of 013 keeps capability/collision out of those paths; this spec
  keeps private-answer bleed out of them too). A committed tree reproduces per-layer, not from
  a flattened namespace.

### Functional Requirements — vendor-namespaced sharing

- **FR-004** *(explicit shared keys)*: A key that must cross layers MUST be declared shared and
  named `<vendor>__<name>` (double-underscore separator; kebab-or-snake `<name>`). Sharing is
  explicit on BOTH ends: the producer writes the key to its answers file; the consumer reads
  it via copier `_external_data` (the verified copier-native cross-template mechanism) under a
  namespace. bailiff MUST route the shared value so consumers resolve it.
- **FR-005** *(vendor prefix reserves the collision boundary)*: `<vendor>` is the collision
  boundary. `bailiff__` is first-party-reserved. Third-party vendors use their own prefix. No
  bare (unprefixed) key may be declared shared.
- **FR-006** *(shared-key lint)*: `check_modules.py` MUST lint first-party shared-key
  declarations for the `bailiff__<name>` shape and reject bare or wrong-vendor shared keys
  (exit 1, naming module + key). Third-party malformed shared keys are at most runtime warnings
  on ingest (mirrors 013 FR-011 first-party/third-party split).
- **FR-007** *(the shared-fact set)*: The first-party shared facts are exactly those with a
  genuine cross-module producer→consumer relationship, enumerated and ratified in
  `decisions-ledger.md` (candidates: `project_name`, `layout`, `github_host`, `default_branch`,
  `monorepo_tool`, `monorepo_packages`, and the gitnr token list). Every other question is
  private (FR-001).

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
  the module's own answers). `bailiff-mod-precommit` ships a single post-install merge task
  that folds all fragments into `.pre-commit-config.yaml`. The merge MUST be deterministic and
  order-independent (same fragment set → equivalent config regardless of layer order) and
  config-consistent on reproduce. The merge runs as an init-only-guarded task (existing task
  contract).
- **FR-012** *(single merger, inert without it, no collision)*: Exactly one module (precommit)
  runs the merge. When precommit is absent or `hook_manager=none`, no merge runs and no
  `.pre-commit-config.yaml` is produced (fragments are inert). Because each contributor owns a
  distinct `.pre-commit.d/*.yaml` path, the 013 collision check passes. `check_modules.py` MAY
  lint the single-merger invariant.

### Functional Requirements — gitignore & migration

- **FR-013** *(gitignore disposition)*: `gitignore_stack` is a frozen token list (task-output
  via gitnr, already config-consistent not byte-asserted), not a managed-render union. It MUST
  either (a) remain a shared fact (`bailiff__gitignore_stack`) consumed by base's single gitnr
  call, or (b) become per-module fragment + idempotent merge/append. The choice is a plan-phase
  decision; whichever is chosen, reproduce MUST NOT duplicate entries (config-consistent
  guarantee).
- **FR-014** *(rename migration)*: The spec MUST define the disposition for pre-014 committed
  trees whose answers files record old bare keys (US5). Given the near-zero real population
  (greenfield, no external users, 27 mirrors just published), an explicit documented break
  with a re-init recommendation is acceptable IF ratified; otherwise an alias/migration path
  MUST be specified. Silent mis-render is prohibited.

### Functional Requirements — governance & scope

- **FR-015** *(no new module features)*: This spec renames keys, changes engine threading, and
  restructures mise/hook/gitignore output — it introduces NO new user-facing module
  capabilities. The 011 cross-cutting contract is amended (single-writer unions → drop-in
  where possible); the amendment is recorded.
- **FR-016** *(decisions ledger prerequisite)*: The ratified `decisions-ledger.md` MUST exist
  and be accepted before the plan phase begins (011/013 precedent).
- **FR-017** *(constitution check)*: Engine changes to `runner.py` are within the C-11
  relaxation established by 013 (engine is the governed exception). No new constitution
  amendment is anticipated; the plan phase confirms.

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
- **SC-002**: Cross-module facts resolve only through declared `<vendor>__<name>` shared keys;
  no private answer appears in another layer's render context (verified by an isolation test).
- **SC-003**: A multi-tool stack produces per-module `.mise/conf.d/*.toml` files, no
  `.mise.toml`, and `mise install` (bare) installs the union; the 013 collision check passes.
- **SC-004**: the pre-commit fragment merge is order-independent and config-consistent on
  reproduce (same hooks regardless of layer order; no duplicate hooks across re-runs).
- **SC-005**: `check_modules.py` rejects a first-party bare or wrong-vendor shared key.
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

## Open questions (NEEDS CLARIFICATION — resolved in decisions-ledger before plan)

1. **pre-commit merge mechanism**: the merge task lives in precommit and folds
   `.pre-commit.d/*.yaml` fragments — confirm the merge implementation (a pinned bailiff helper
   invoked as a task vs a small vendored script) and the rev-pin conflict rule.
2. **gitignore disposition** (FR-013): shared frozen fact + single gitnr call, vs per-module
   fragment + idempotent merge?
3. **Rename migration** (FR-014): documented break + re-init, vs alias/migration shim?
4. **Exact first-party shared-fact set** (FR-007): ratify the final list.
5. **Vendor-prefix separator**: `bailiff__name` (double underscore) confirmed — reconfirm no
   copier parsing conflict (copier reserves single leading `_`; `bailiff__` has no leading
   underscore, so it is a normal key — verify no tooling assumes `__` semantics).
