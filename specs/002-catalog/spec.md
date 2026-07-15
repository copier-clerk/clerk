# Feature Specification: bailiff catalog — user-owned sources, runtime discovery + injection

**Feature Branch**: `002-catalog`

**Created**: 2026-07-10

**Status**: Draft

**Input**: Roadmap spec 002 (Catalog + runtime injection), governed by the
constitution (I, II, IV, VI) and ADR-0002/0003. Reconciles ADR-0003's
two-template meta-flow (repos-collector + selector copier templates) to the
post-010 skill-bundled model: the catalog is a plain user-owned file managed by
`scripts/bailiff.py`, and template selection is the phase-1 agent's job backed by a
deterministic validation gate — no repos-collector template, no selector template.

## Overview

Spec 001 proved the loop against ONE source the user names inline; spec 010 made
bailiff a skill-bundled copier wrapper (`scripts/bailiff.py` + `SKILL.md`, no console
script). Spec 002 lets a user point bailiff at **their own set of source repos** and
have the skill present the templates those sources offer — without depending on any
first-party hub (ADR-0002).

The catalog is **user-owned configuration**: a plain file listing source repos.
`scripts/bailiff.py` gains `catalog` verbs to create, list, add to, remove from, and
**refresh** (discover + verify) that file. Discovery reuses the existing static
`copier.yml` parser (`src/bailiff/discovery.py`) against each source, so the derived
catalog listing is **deterministic** — same sources at same pins → identical
listing, with no template code executed and no trust required.

Selection — *which* templates the user wants — stays with the **phase-1 agent**
(Constitution II: judgment is the agent's job), which presents the deterministic
listing and collects the user's choice. To neutralize the one real risk (the agent
naming a template that does not exist), `scripts/bailiff.py` provides a
**deterministic validation gate**: any selected full-id is checked against the
discovered catalog and refused with a non-zero exit if unknown. This gives the
guardrail a selector template would provide, without a committed bailiff artifact or
a template whose only job is holding a list.

This spec deliberately does **not** build multi-template execution or dependency
ordering (spec 003) — it produces a *verified catalog* and a *validated selection*,
which 003 consumes to build and drive its DAG.

## Motivating decisions

1. **Catalog = plain user-owned file, managed by `scripts/bailiff.py`** — NOT a
   repos-collector copier template. It lists **sources, not templates**, and holds
   **no pinned refs by default** (the reproduce pin lives in each generated
   project's answers file — ADR-0002); an optional per-source `@ref` is a team
   override, not the model. The agent can create the file if absent and
   add/remove/list sources, so the user never hand-crafts it blind.
   *(Supersedes ADR-0003's "repos-collector template" — see "Reconciliation".)*
2. **Discovery is deterministic and reuses 001's static parser.** `catalog refresh`
   clones each source at its resolved pin and reads `copier.yml` + the file tree
   statically (no Jinja env, no template code, no trust). Same inputs → identical
   listing. copier's "1 template = 1 git repo" rule holds: one catalog source = one
   repo = one template (ADR-0002).
3. **Selection is the agent's job; a deterministic gate validates it.** The skill
   presents the verified listing and collects the user's pick. `scripts/bailiff.py`
   validates each chosen **full-id** against the discovered catalog and refuses an
   unknown id (non-zero exit). No selector copier template — the multiselect →
   grouping → DAG machinery is spec 003 (drive) / spec 007 (the apm module's
   internal multiselect), not this spec.
   *(Supersedes ADR-0003's "selector template" — see "Reconciliation".)*
4. **Full-id namespacing always** (`<catalog>/<template>`). bailiff supports **one or
   more** catalog pointers; a template's identity is namespaced by its catalog so
   the same short name under two catalogs never collides (ADR-0002). No
   unnamespaced first-wins lookup.
5. **`--data catalog=[…]` injection is retained but not exercised here.** ADR-0003's
   verified fact — that a runtime-injected `catalog` value is in copier's render
   scope from question 1 — remains true and is the mechanism a *template* uses when
   it genuinely needs the list in its own `choices` (the apm module's internal
   multiselect, spec 007). Spec 002 needs no template to consume the catalog, so it
   injects nothing into a render; it emits the listing for the agent.
6. **No git submodules, no `catalog.yml` committed into generated projects, no
   catalog-generation CI** (ADR-0002/0003). The catalog is user config read at
   runtime; nothing bailiff-authored lands in a generated project (the 010 invariant
   holds).
7. **Adapter only if forced (C-04).** Discovery stays static-parse-only. If a real
   third-party source needs `!include`/inheritance resolution that static parsing
   cannot do, the contained `Template`/`Worker` adapter + drift test are introduced
   THEN, with that evidence — not preemptively (roadmap Q3).

## User Scenarios & Testing

### US1 — Point bailiff at my own sources and see the templates (Priority: P1)

A developer supplies one or more source repos and gets a verified list of the
templates available, with no dependency on any first-party hub.

**Why this priority**: this is the feature — decentralized, user-owned templates.

**Independent Test**: with a catalog file naming ≥1 local git template fixture,
run `scripts/bailiff.py catalog list`; assert the output enumerates each source's
template with its full-id, description, and usable versions, and that a source with
no PEP 440 tag or no answers-file `.jinja` is reported as unusable (not silently
included).

**Acceptance Scenarios**:
1. **Given** a catalog with two valid sources, **When** the user refreshes/lists,
   **Then** both templates appear with full-ids `<catalog>/<template>` and static
   metadata (questions summary, versions, `has_tasks`, `reproducible`).
2. **Given** a source with no usable PEP 440 tag, **When** listing, **Then** it is
   reported as unusable with a clear reason, and the other sources still list.

### US2 — Manage the catalog through the skill (Priority: P1)

A developer (via the agent) creates the catalog if it does not exist, and
adds/removes/lists sources — without hand-editing the file blind.

**Why this priority**: your explicit requirement — the agent manages the catalog.

**Independent Test**: on a machine with no catalog file, run `scripts/bailiff.py
catalog add <src>`; assert the file is created with that source; `catalog list`
shows it; `catalog remove <src>` removes it; operations are idempotent and preserve
unrelated entries/comments where feasible.

**Acceptance Scenarios**:
1. **Given** no catalog file, **When** `catalog add <src>`, **Then** the file is
   created (at the documented user-config path or an explicit `--catalog PATH`) with
   that source and nothing else.
2. **Given** a source already present, **When** `catalog add` it again, **Then** it
   is a no-op (idempotent), not a duplicate.
3. **Given** a catalog with two sources, **When** `catalog remove <one>`, **Then**
   only that source is gone; the other and any file comments/structure survive.

### US3 — Selection is validated deterministically (Priority: P1)

A selected template id is checked against the discovered catalog; an id that is not
in the catalog is refused before anything else happens.

**Why this priority**: this is the determinism guarantee that makes agent-driven
selection safe — the concern that motivated choosing a gate over a selector
template.

**Independent Test**: with a known catalog, run the selection-validation entry with
(a) a valid full-id → accepted; (b) an unknown/misspelled full-id → non-zero exit
with a message listing valid ids; (c) an ambiguous bare name that exists under two
catalogs → refused, requiring the full-id. Assert the check reads only the
discovered catalog (no network beyond the static discovery it already did, no
template code).

**Acceptance Scenarios**:
1. **Given** catalog full-id `demo/base` exists, **When** validating `demo/base`,
   **Then** accepted (exit 0).
2. **Given** no `demo/typo` exists, **When** validating it, **Then** refused
   (non-zero) naming the valid ids.
3. **Given** `a/base` and `b/base` both exist, **When** validating bare `base`,
   **Then** refused as ambiguous, requiring a full-id.

### Edge Cases

- **No catalog file and no `--catalog`**: `catalog list`/`refresh` reports the
  absence with the exact `catalog add`/`init` remediation, not a stack trace.
- **Malformed catalog file**: refuse with a clear parse error; never silently
  clobber it on a subsequent `add`.
- **Duplicate source across two catalog pointers**: both surface under their own
  namespace (full-id disambiguates); this is not an error.
- **Source unreachable at refresh** (network/auth): reported per-source as unusable
  with the reason; other sources still list (one bad source ≠ whole-catalog
  failure).
- **`@ref` override on a source**: honored for discovery display; it does NOT become
  a reproduce pin (that remains the per-project answers file — ADR-0002).
- **A repo using a templated `_subdirectory`** is still ONE catalog entry (variant
  is a question answer, not a separate template — ADR-0002).

## Requirements

### Functional Requirements

- **FR-001**: The catalog MUST be a **plain user-owned file** listing source repos
  (locator `gituser/gitrepo`, optional `@ref` override), NOT a copier template and
  NOT committed into any generated project. Its default location MUST follow the
  same user-config resolution bailiff already uses (mirroring `trust.py`'s
  `platformdirs`/env approach) and MUST be overridable with an explicit
  `--catalog PATH`.
- **FR-002**: `scripts/bailiff.py` MUST provide catalog-management verbs to **create
  (if absent), list, add, and remove** sources. `add`/`remove` MUST be idempotent
  and MUST NOT destroy unrelated entries.
- **FR-003**: `scripts/bailiff.py catalog refresh`/`list` MUST derive the available
  templates by **statically** discovering each source (reusing
  `discovery.discover`), executing no template code and requiring no trust, and MUST
  emit each template's full-id, static metadata, usable versions, and reproducible
  flag. Same sources at same pins MUST produce an identical listing.
- **FR-004**: Templates MUST be identified by **full-id `<catalog>/<template>`**.
  bailiff MUST support one or more catalog pointers and MUST NOT provide an
  unnamespaced first-wins lookup; an ambiguous bare name MUST be refused.
- **FR-005**: A source that is unusable (no PEP 440 tag, no answers-file `.jinja`,
  unreachable, bad `copier.yml`) MUST be reported per-source with a clear reason and
  MUST NOT silently appear as usable; other sources MUST still list (one bad source
  does not fail the whole catalog).
- **FR-006**: `scripts/bailiff.py` MUST provide a **deterministic selection-validation
  gate**: given one or more chosen full-ids, it accepts only ids present in the
  discovered catalog and refuses an unknown or ambiguous id with a non-zero exit and
  a message listing valid ids. This gate MUST contain no LLM judgment.
- **FR-007**: The catalog MUST hold **sources, not mandatory pinned refs** (ADR-0002);
  an optional per-source `@ref` is a display/standardization override only and MUST
  NOT be written as a reproduce pin into a generated project.
- **FR-008**: This spec MUST NOT build a repos-collector template, a selector
  template, multi-template execution, or dependency ordering (spec 003). It produces
  a verified catalog listing and a validated selection only.
- **FR-009**: The `SKILL.md` MUST document the catalog-management + selection flow:
  discover sources → present the verified listing → collect the user's pick → pass
  validated full-id(s) to init. Selection remains phase-1 (agent) judgment; the
  mechanical discovery + validation remain LLM-free.

### Key Entities

- **Catalog file**: user-owned config; a set of named catalog pointers, each listing
  source locators (`gituser/gitrepo` [`@ref`]). No template metadata (that is read
  live from each source's `copier.yml`), no reproduce pins.
- **Catalog source**: one git repo = one template (ADR-0002); resolved + statically
  discovered at refresh.
- **Catalog listing**: the deterministic derived view — per template: full-id,
  description, versions, `has_tasks`, `reproducible`, questions summary. Emitted for
  the agent; not persisted into any project.
- **Selection**: one or more validated full-ids the agent hands to init.

## Success Criteria

- **SC-001**: A user with zero first-party dependencies can list templates from
  their own sources: given a catalog of local git fixtures, `catalog list` enumerates
  every usable template with full-id + versions, and every unusable source with a
  reason.
- **SC-002**: `catalog list` is deterministic — repeated runs against the same
  sources at the same pins produce byte-identical listings.
- **SC-003**: The agent can fully manage the catalog: create-if-absent, add, remove,
  list — idempotently, without destroying unrelated entries.
- **SC-004**: Selection is safe — a valid full-id validates (exit 0); an unknown or
  ambiguous id is refused (non-zero) naming the valid ids; the check runs without
  template code or LLM judgment.
- **SC-005**: No bailiff-specific artifact is written into any generated project and
  no template code runs during catalog operations (the 010 + discovery-safety
  invariants hold).

## Reconciliation (ADR-0003 superseded in part)

ADR-0003 (2026-07-09, pre-010) specified a **two-template meta-flow**: a
*repos-collector* copier template persisting sources in its `.copier-answers.yml`,
and a *selector* copier template with `choices: "{{ catalog }}"` injected via
`--data`. Spec 010 reshaped bailiff to skill-bundled with **no committed bailiff
artifacts** and the agent authoring inputs. This spec therefore supersedes those two
mechanisms:

- **repos-collector template → plain user-owned catalog file** managed by
  `scripts/bailiff.py` (FR-001/FR-002). No template whose only job is holding a list;
  no `.copier-answers.yml` acting as a catalog store.
- **selector template → agent presentation + deterministic validation gate**
  (FR-006). The multiselect/grouping machinery ADR-0003 described is explicitly
  *"internal to the apm module template"* (spec 007) and the DAG is spec 003 — not
  built here.

**Retained from ADR-0003, unchanged**: the source-verified fact that a
runtime-injected `catalog` value is in copier's render scope from question 1
(`--data catalog=[…]`) — the mechanism spec 007's apm module uses for its own
`choices`. Dependency edges remain hidden `when:false` answers in each source's
`copier.yml`, statically read (already implemented in `discovery.py`), consumed by
spec 003. ADR-0002 (catalog = user-owned sources, answers carry state, full-id
collisions, no submodules) is honored in full, not superseded. This reconciliation
is recorded in ADR-0003 and the roadmap in the same PR.

## Out of scope

- Dependency ordering / multi-template execution / the DAG (spec 003 — consumes
  this spec's validated selection).
- The apm module's internal skills/mcp/bundles multiselect (spec 007).
- Global per-template defaults (004), secrets (005), upgrade (006).
- Catalog publishing / generation CI and the `catalog.json` index derived from the
  authoring monorepo (spec 008 — a *producer* of a catalog; this spec is a
  *consumer* of user-supplied sources).
- Any `Template`/`Worker` adapter unless a real source forces it (C-04 / Q3).

## Open Questions

- **Q-002a — Catalog file format**: TOML (idiomatic config, matches `pyproject.toml`,
  toolchain-defaults leans modern) vs YAML (matches copier's ecosystem). Lean: TOML
  for the bailiff-owned config; resolve at planning. Either way it is plain,
  hand-editable, and agent-manageable.
- **Q-002b — Catalog pointer form**: is a "catalog pointer" a local file path only,
  or also a remote URL (fetched) for shared team catalogs? Lean: local file(s) for
  002 (a remote/shared catalog is an 008 authoring-plane concern); support multiple
  local pointers now. Resolve at planning.
- **Q-002c — Namespace derivation**: how is `<catalog>` in the full-id derived —
  explicit per-pointer name, or the file/source basename? Lean: an explicit name per
  catalog pointer, defaulting to a sanitized basename. Resolve at planning.

## Governing constitution & ADRs

- Constitution I (skills + templates + minimal glue), II (two-phase; agent judges,
  helpers execute), IV (prefer CLI + static config; adapter only if forced), VI
  (template-author contract enforced at discovery), VII (per-step hardening).
- ADR-0002 (user-owned catalog of sources; answers carry state; full-id collisions;
  no submodules), ADR-0003 (runtime `catalog` injection fact retained; two-template
  meta-flow superseded here), ADR-0001 (copier is the engine).
- Constraints: C-01, C-04, C-06, C-11 (glue only where copier cannot). Delivery
  shape from spec 010 (skill-bundled `scripts/bailiff.py`, no committed bailiff artifact).
