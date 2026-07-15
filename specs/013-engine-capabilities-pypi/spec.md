# Feature Specification: bailiff engine — PyPI packaging, multi-catalog, listing cache, collision check, capability tags (spec 013)

**Feature Branch**: `013-engine-capabilities-pypi`

**Created**: 2026-07-14

**Status**: Draft — authored from the ratified 2026-07-14 decision session and reshaped by the
maintainer adjudication of the same date, which DROPPED the originally drafted capability
policy system (central vocabulary, policy kinds, init-time policy validator, escape hatch,
`bailiff capabilities` verb) in favor of a slim warn-only design. All design decisions below are
maintainer-ratified fixed inputs; only the items explicitly marked NEEDS CLARIFICATION remain
open.

**Input**: Maintainer-ratified decisions of 2026-07-14 (as adjudicated): publish `src/bailiff/`
to PyPI as a real CLI tool; add slim, informational capability tags with a warn-only conflict
signal; add a fact-based init-time file-collision check as the hard backstop; give the ordered
catalog-pointer list a defined bare-name precedence plus a persisted listing cache; optionally
add stack presets as catalog data; and perform the constitution amendment that the packaging
work requires (Constitution I / C-11 currently forbid exactly this — the amendment follows the
FR-019/ADR-0007 governance pattern established by spec 011).

---

## Overview

bailiff today is deliberately *not* a published application. Constitution I (v2.3.0) states there
is "no `[project.scripts] bailiff` console entry, no `uvx bailiff` PyPI tool", and C-11
(`.specify/memory/roadmap.md:110-113`) permits new deterministic code only for a capability
copier lacks. Spec 011 honors that boundary (its FR-011 is a hard no-new-glue gate) and
continues to honor it retroactively — nothing in 011 changes.

Spec 013 is the deliberate, governed exception: the maintainer has ratified repositioning
**bailiff as the tool** (installed via `uvx`, published to PyPI) and **`bailiff-mod-*` as the
modules** consumed via the catalog. Three forces make this the right moment:

1. **There is no init-time conflict detection at all today.** `init_many` renders every layer
   with `run_copy(..., overwrite=True)` (runner.py:275, 329), so two modules writing the same
   file silently last-write-wins. The only existing conflict scan — `_scan_conflicts`
   (runner.py:520) — is a **post-update** merge-marker/`.rej` scanner on the `update` path; it
   never runs at init and backstops nothing at selection time. Spec 013 adds the missing
   fact-based backstop: a pre-render file-collision check that hard-stops when two selected
   modules would write the same managed path. Alongside it, informational **capability tags**
   give the selecting agent visible grouping of alternatives, with a warn-only conflict
   signal. The maintainer's ratified rationale for dropping the drafted policy system: **rely
   on module authors and the selecting agent; enforce facts (file collisions), not claims
   (capability labels)**.
2. **The engine is now a genuine non-agent consumer.** Constitution VIII forbids typed
   models/JSON Schemas "until a genuine non-agent program consumes the handoff" — the packaged
   CLI, the collision check, and the capability-tag warning computation are exactly such
   consumers, so VIII contains its own unlock clause for this spec.
3. **Platform teams need layered catalogs.** An organization wants to overlay an internal
   catalog pointer (forked/private modules, internal stack presets) on the public one without
   renaming modules. The catalog is ALREADY an ordered list of named pointers — the existing
   `CatalogPointer` model over `catalog.toml`'s `[[catalog]]` tables (catalog.py:75-87,
   111-138). What 013 adds is a defined **bare-name resolution precedence** (first-listed
   pointer wins, replacing today's ambiguity error) plus a persisted listing cache so listing
   and selection reads stop shallow-cloning every source on every call.

Scope is **engine work only**: packaging/publication of `src/bailiff` as a CLI, informational
capability tags with the warn-only conflict signal, the init-time file-collision check,
bare-name precedence across catalog pointers, the persisted listing cache, optional stack
presets, and the constitution amendment. No module content is authored here (that is 012);
MI-1 (version auto-updater) remains a separate future spec, though it is noted below as a
future consumer of the packaged engine.

**Sequencing**: 012 and 013 are DECOUPLED (ratified in the adjudication). Capability tags are
inert informational metadata on any pre-013 engine, and the collision check is fact-based, so
neither spec gates the other; there is no cross-spec landing-order requirement.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A conflicting selection produces a loud warning, never a block (Priority: P1)

A user (or the phase-1 agent) composes a selection that includes two modules providing the same
capability where any provider in the merged listing has declared that capability exclusive —
e.g. two monorepo-tool modules, or two docs-site engines. `bailiff init` emits a LOUD WARNING
that names the capability and the conflicting members, then proceeds. There is no hard error,
no block, and therefore no escape hatch to learn. The warning also fires on incremental adds:
initing an additional module into a destination that already contains
`.copier-answers.*.yml` layers considers the already-installed modules' capabilities too.

**Why this priority**: This is the entire behavioral payoff of capability tags — the selecting
agent (or human) is told, before the render output is inspected, that the selection contains
alternatives that are normally pick-one. It is deliberately advisory: labels are claims, and
bailiff does not enforce claims. (Upgrading warn→error later is a trivial change if real-world
misuse demands it — noted as a deliberate design property, not scope.)

**Independent Test**: Build a selection of two test templates that both declare
`_bailiff_provides: [monorepo-tool]`, one of which also declares `_bailiff_exclusive: true` →
`bailiff init --run-spec` prints a loud warning naming `monorepo-tool` and both members, exits
with the normal success code, and renders both layers; re-run initing only the second module
into a destination already carrying the first module's `.copier-answers.*.yml` → the same
warning fires from the incremental-add path.

**Acceptance Scenarios**:

1. **Given** a selection containing two providers of capability `C`, where at least one
   provider of `C` anywhere in the merged listing declares `_bailiff_exclusive: true`, **When**
   `bailiff init --run-spec` runs, **Then** a loud warning is emitted before rendering, naming
   the capability and every conflicting member, and the run proceeds normally (exit code
   unchanged by the warning).
2. **Given** the same conflict where the two SELECTED modules did not themselves declare
   `_bailiff_exclusive` but a third provider of the same capability in the merged listing did,
   **When** init runs, **Then** the warning STILL fires — exclusivity infects the whole
   capability group (ratified: err on the side of caution).
3. **Given** a destination directory already containing `.copier-answers.*.yml` layers,
   **When** an additional module is inited into it and its capabilities conflict with an
   already-installed module's capabilities (read from the existing answers files / their
   recorded sources), **Then** the same warning fires.
4. **Given** a selection of modules that declare no capabilities at all, **When** init runs,
   **Then** no warning is emitted and behavior is byte-identical to a pre-013 engine.
5. **Given** two providers of a capability that NO provider in the merged listing declares
   exclusive, **When** init runs, **Then** no warning is emitted (multiple providers are fine
   by default).

---

### User Story 2 — A module author declares what their module provides (Priority: P1)

A module author adds an optional key — `_bailiff_provides: [<capability>, …]` — to their module's
`copier.yml`. The declaration is a LIST (a module may provide multiple capabilities), purely
informational, with NO closed vocabulary: any kebab-case string is a valid capability name. The
catalog regeneration pipeline scrapes it into `catalog.json` automatically; the author writes
nothing anywhere else. An author whose module is a pick-one alternative additionally declares
`_bailiff_exclusive: true` — a self-referential statement ("my capability is a pick-one slot")
that never names sibling modules. First-party CI (`check_modules.py`) lints only
well-formedness (list of kebab-case strings; `_bailiff_exclusive` boolean) and flags MIXED
exclusivity declarations within one first-party capability group.

**Why this priority**: Declaration is the foundation the warning and the listing tags consume;
without it there is nothing to group or warn about. It is deliberately optional and
low-ceremony so the 011/012 module family can adopt it incrementally.

**Independent Test**: Using a fixture module scoped inside a `templates/`-shaped tree (passed
to `check_modules(templates_dir=…)`), add `_bailiff_provides: [hook-manager]` to its
`copier.yml` → `bailiff discover` on that template reports the capability list;
`scripts/generate_catalog.py` emits it in the module's `catalog.json` entry; change the value
to a non-list or a non-kebab-case string → `scripts/check_modules.py` exits non-zero naming
the offending module and value; give two fixture siblings the same capability with only one
declaring `_bailiff_exclusive: true` → `check_modules.py` flags the mixed group.

**Acceptance Scenarios**:

1. **Given** a module whose `copier.yml` contains `_bailiff_provides: [<capability>, …]`,
   **When** the module is discovered, **Then** the capability list appears in the discovery
   output (and therefore in `bailiff discover`'s dict) without executing any template code.
2. **Given** the same module, **When** the repo catalog is regenerated, **Then** its
   `catalog.json` entry carries the capability list (and `_bailiff_exclusive` when declared)
   alongside name/description/source/tags.
3. **Given** a first-party module whose `_bailiff_provides` is not a list of kebab-case strings
   (or whose `_bailiff_exclusive` is not a boolean), **When** `check_modules.py` runs, **Then**
   it fails naming the module and the malformed value. No vocabulary check exists — any
   well-formed name is valid.
4. **Given** two first-party modules sharing a capability where only one declares
   `_bailiff_exclusive: true`, **When** `check_modules.py` runs, **Then** the mixed group is
   flagged as an author-time error (all siblings of a pick-one family should declare it).
5. **Given** a module with no `_bailiff_provides` key, **When** discovered/validated, **Then**
   it is treated as unconstrained (no group membership, no warnings).

---

### User Story 3 — Install and run bailiff via uvx (Priority: P1)

A user with no bailiff checkout runs `uvx <dist-name> init …` (or installs the package and runs
`bailiff init` / `bailiff reproduce`). They get the full CLI — every verb the bundled script offers
today — with correct declared dependencies, a version that matches the release tag, and the
same exit-code contract the script has always had.

**Why this priority**: This is the repositioning itself — bailiff as the tool. It is also the
scope that requires the constitution amendment, so it is the release gate for the whole spec.

**Independent Test**: `uv build` the wheel, install it into a clean venv → the `bailiff` console
command exists, `bailiff --version` matches `pyproject.toml`, `bailiff doctor` passes, and a
declared-dependency audit (`importlib.metadata.requires` / deptry-style) confirms every
directly imported third-party package — including `platformdirs` — is a declared dependency.

**Acceptance Scenarios**:

1. **Given** the built wheel installed in a clean environment, **When** the user runs the
   console command with any existing verb (`discover`, `init`, `reproduce`, `catalog`, `trust`,
   `update`, `doctor`), **Then** each behaves identically to the repo script today (same
   flags, same exit codes 0/1/2/3/4).
2. **Given** the installed package, **When** `--version` is queried, **Then** it reports the
   single-sourced version that matches the `pyproject.toml` release version (no drift between
   `pyproject.toml` and `bailiff.__version__`).
3. **Given** the repo checkout WITHOUT an installed distribution (the bundled
   `scripts/bailiff.py` path), **When** `--version` is queried, **Then** `bailiff.__version__`
   still resolves (the single-sourcing mechanism must not depend on installed dist metadata
   being present).
4. **Given** a release of the engine, **When** the release pipeline runs, **Then** the PyPI
   publish step is maintainer-confirmed (never unattended) and only runs after the
   constitution amendment gate (FR-018) has landed.

---

### User Story 4 — Two selected modules writing the same file hard-stop before any render (Priority: P1)

A user composes a selection in which two modules would write the same managed path — whether or
not either declares any capability. `bailiff init` detects the overlap BEFORE any file is written
and refuses with a typed, deterministic error naming the colliding path(s) and both modules.
This is the fact-based hard backstop: it fires on what modules actually do, not on what they
claim.

**Why this priority**: Today nothing prevents silent last-write-wins at init
(`run_copy(overwrite=True)`, runner.py:329). This check is the enforcement story of 013 — the
capability warning (US1) is advisory; the collision check is the hard stop.

**Independent Test**: Build a selection of two test templates that both render the same
destination path → `bailiff init --run-spec` fails with a typed `BailiffError` (exit 1) naming the
path and both modules, and the destination directory is verifiably untouched; a selection with
disjoint outputs proceeds normally.

**Acceptance Scenarios**:

1. **Given** two selected modules that would each write the same managed destination path,
   **When** `bailiff init --run-spec` runs, **Then** a typed error in the `BailiffError` hierarchy
   (exit 1) is raised before ANY render, deterministically naming the overlapping path(s) and
   the modules involved, and the destination is left untouched.
2. **Given** a selection whose modules write disjoint paths, **When** init runs, **Then** the
   check passes silently and rendering proceeds unchanged.
3. **Given** a capability-conflict warning (US1) AND a real file collision in the same
   selection, **When** init runs, **Then** the warning is emitted and the collision error still
   hard-stops — two independent signals, the fact-based one binding.

---

### User Story 5 — A platform team layers an internal catalog pointer over the public one (Priority: P2)

A platform team configures `catalog.toml` with their internal pointer first and the public
bailiff pointer second (the existing ordered `[[catalog]]` tables). Their internal fork of
`bailiff-mod-python` (same module name) resolves first for bare-name selection — deliberately,
with a loud shadow warning naming both sources so nobody is surprised. The shadowed public
entry remains fully addressable by full-id (`public/bailiff-mod-python`) and remains visible in
listings, marked shadowed. Existing single-pointer users notice nothing.

**Why this priority**: This is the organizational adoption path and the reason bare-name
resolution is first-listed-wins rather than an error. P2 because single-pointer behavior (the
default) must be proven first.

**Independent Test**: Configure two pointers where both contain a module named
`bailiff-mod-python` → selecting the bare name `bailiff-mod-python` resolves to the first pointer's
entry with a loud shadow warning naming the shadowed source (today this raises the ambiguity
`CatalogError`, catalog.py:455-466); `bailiff catalog list` shows BOTH entries with the second
marked shadowed; selecting the shadowed full-id works; a pre-013 single-pointer `catalog.toml`
loads and behaves unchanged.

**Acceptance Scenarios**:

1. **Given** two pointers in order `[internal, public]` both listing module `X`, **When** the
   bare name `X` is selected, **Then** internal's `X` wins, a loud shadow warning is emitted
   naming both sources, and no content-based dedup is attempted (name precedence only).
2. **Given** the same configuration, **When** the full-id `public/X` is selected, **Then** the
   shadowed entry resolves normally — full-ids are always individually addressable.
3. **Given** the same configuration, **When** `bailiff catalog list` runs, **Then** BOTH entries
   appear, the shadowed one explicitly marked as shadowed (shadowing hides nothing from
   listings; it only decides bare-name resolution).
4. **Given** an existing single-pointer `catalog.toml` written by a pre-013 bailiff, **When**
   any verb runs, **Then** behavior is unchanged — no migration step.
5. **Given** stack presets defined in both pointers (optional scope), **When** listed, **Then**
   each preset is namespaced by its pointer name with `/` (e.g. `internal/python-service`,
   matching full-id form) and no collision is possible.

---

### User Story 6 — Listing reads are fast and offline via a persisted cache (Priority: P2)

A user (or agent) runs `bailiff catalog refresh` once; bailiff builds the full listing (this is the
step that clones/discovers every source) and persists it. Subsequent `bailiff catalog list`
calls, selection validation, and capability-tag reads consume the persisted listing — fast, and
with no per-source network traffic. When no cache exists, bailiff instructs the user to refresh
(or builds it once automatically). Staleness is user-controlled: the listing changes only when
the user refreshes.

**Why this priority**: `build_listing` today shallow-clones/discovers every source on EVERY
call (catalog.py:336-397 via `discovery.discover`) — the earlier draft's "works offline from
the already-built listing" claims were phantom; no persisted listing exists. The cache makes
listing-backed reads honest and cheap. P2 because correctness does not depend on it.

**Independent Test**: Run `bailiff catalog refresh` → a listing file appears under the
platformdirs cache dir; run `bailiff catalog list` twice → byte-identical output with zero
network/git traffic; delete the cache → `bailiff catalog list` either instructs the user to run
refresh or transparently builds the cache once (single defined behavior, see FR-016).

**Acceptance Scenarios**:

1. **Given** a configured catalog, **When** `bailiff catalog refresh` runs, **Then** the full
   listing (templates, unusable bucket, capability tags, shadow marks) is built and persisted
   in the platformdirs cache location.
2. **Given** a persisted listing, **When** `bailiff catalog list` (including `--json`) or
   selection validation runs, **Then** it reads the cache and performs no per-source
   clone/discovery traffic; two consecutive runs are byte-identical.
3. **Given** no persisted listing, **When** a listing-consuming verb runs, **Then** the defined
   fallback occurs (explicit instruction to refresh, or a one-time automatic build) — never a
   silent per-call re-clone regime.
4. **Given** a source that was unreachable at refresh time, **When** the listing is read,
   **Then** the source appears in the existing `unusable` bucket style (never an abort of the
   whole listing).

---

### Edge Cases

- **Any capability name is valid**: there is no vocabulary, closed or open. First-party CI
  lints well-formedness only (list of kebab-case strings); a novel name is simply a new group.
- **Malformed declaration in a third-party catalog** (non-list, non-string members,
  non-kebab-case): warn on catalog ingest and treat the declaration as absent — never a hard
  failure for third-party content.
- **Mixed exclusivity in a third-party capability group**: runtime warning only; the
  group-infection rule (any exclusive declaration makes the whole capability a select-1 group)
  means the conflict warning still fires correctly. Mixed declarations are a hard author-time
  error only in first-party CI.
- **Wrong label, missed conflict**: two modules that *should* conflict but neither is labeled —
  no warning fires; the init-time file-collision check (FR-012) remains the fact-based
  backstop, and where files do not collide, last-write-wins concerns do not arise. Benign by
  design (ratified: enforce facts, not claims).
- **Wrong label, false conflict**: the warning fires and the run proceeds — a false positive
  costs one warning line, which is exactly why conflicts warn instead of block.
- **Module description naming a sibling** ("use this instead of bailiff-mod-X"): forbidden
  authoring practice — `_bailiff_exclusive` is self-referential precisely so descriptions never
  go stale against the sibling set.
- **Incremental add into a non-bailiff directory** (no `.copier-answers.*.yml` present): the
  incremental branch of the warning has nothing to read; only the current selection is
  considered.
- **Shadowing module provides different capabilities than the shadowed one**: bare-name
  resolution takes the first-listed entry entirely — its capabilities (or absence thereof) are
  the truth for that bare name; the shadowed entry keeps its own tags in the listing.
- **Existing multi-pointer configs**: behavior changes ONLY where they previously hit the
  bare-name ambiguity error — see FR-014's explicit break statement.
- **`bailiff catalog list` with an empty catalog**: prints an empty listing, exit 0 (existing
  behavior, unchanged).
- **Reproduce/update over a tree whose modules now carry conflicting tags**: never warned,
  never blocked — capability signals are init-time only; reproduce fidelity is untouched.
- **Stale cache after a catalog edit**: `catalog add`/`remove` MAY invalidate or update the
  cache; regardless, `refresh` always rebuilds. Staleness is user-controlled by design.
- **PyPI name `bailiff` is taken** (verified 2026-07-14: an existing unrelated `bailiff 0.1.0`
  package occupies it): plain `uvx bailiff` is impossible; the distribution name decision is
  flagged below.

## Requirements *(mandatory)*

### Functional Requirements — PyPI packaging & CLI

- **FR-001** *(console entry point)*: The CLI currently living in `scripts/bailiff.py` MUST be
  available from the installed package: its verb dispatch moves (or is re-exported) into
  `src/bailiff/` (e.g. `bailiff/cli.py`) and `pyproject.toml` gains a `[project.scripts]` entry
  mapping the console command to it. The installed CLI MUST offer every existing verb
  (`discover`, `init`, `reproduce`, `catalog`, `trust`, `update`, `doctor`, `-V/--version`),
  with the existing exit-code contract preserved (0 ok, 1 `BailiffError`, 2 usage, 3
  `UntrustedSourceError`, 4 preflight failure / `MergeConflictError`). The dual-mode
  `sys.path` shim and PEP 723 header of the script MUST NOT be carried into the packaged
  entry point.
- **FR-002** *(dependency correctness)*: `platformdirs` — imported directly by
  `src/bailiff/catalog.py`, `src/bailiff/trust.py`, and `src/bailiff/defaults.py` but today only
  transitively available via copier — MUST be declared as an explicit runtime dependency. Any
  surviving PEP 723 script MUST have its inline deps brought into agreement with the
  package's declared deps.
- **FR-003** *(single-source version)*: The version MUST be single-sourced: `pyproject.toml`'s
  `version` and `bailiff.__version__` MUST NOT be independently maintained duplicates; the
  release flow (cog-tagged) MUST keep the published version, the tag, and `--version` output
  in agreement. The mechanism MUST keep `bailiff.__version__` resolvable WITHOUT installed
  distribution metadata (e.g. a guarded `importlib.metadata` lookup with a fallback, or hatch
  dynamic versioning reading from the source) — the bundled `scripts/bailiff.py` path (FR-006)
  imports `bailiff.__version__` from a bare checkout and MUST keep working.
- **FR-004** *(publish automation)*: The release workflow MUST gain a build + PyPI publish
  step (trusted-publisher/OIDC preferred over long-lived tokens). Publishing is an
  irreversible public action: the FIRST publish, and any publish that claims a new
  distribution name, MUST be maintainer-confirmed, never unattended. No publish may occur
  before the FR-018 governance gate lands.
- **FR-005** *(distribution name)*: The PyPI name `bailiff` is TAKEN (verified 2026-07-14
  against pypi.org: an unrelated `bailiff 0.1.0` exists); `bailiff-io` (the current
  `pyproject.toml` name) and `bailiff-scaffold` were both available at verification time. The
  spec REQUIRES: (a) the console command is `bailiff` regardless of distribution name; (b) the
  distribution name is re-verified as available immediately before first publish (an explicit
  early task); (c) the final choice of distribution name is
  [NEEDS CLARIFICATION: `bailiff-io` (status quo, invoked `uvx --from bailiff-io bailiff`)
  vs `bailiff-scaffold` (closer to `uvx bailiff-…` ergonomics) — maintainer decision].
- **FR-006** *(bundled-script disposition)*: The skill-bundled `scripts/bailiff.py` invocation
  path (`./scripts/bailiff.py` / `uv run scripts/bailiff.py`) MUST keep working for the bailiff repo
  and skill during the transition (the skill procedure references it). Its end-state —
  permanent thin re-export shim vs deprecation once the PyPI tool is the documented path — is
  [NEEDS CLARIFICATION: maintainer preference; affects Constitution I's amended wording, which
  currently defines the glue as "bundled with the skill as a single script"].

### Functional Requirements — capability tags (informational, warn-only)

- **FR-007** *(declaration)*: A module MAY declare `_bailiff_provides: [<capability>, …]` in its
  `copier.yml` — LIST-VALUED (a module may provide multiple capabilities), each entry a
  kebab-case string. The declaration is OPTIONAL INFORMATIONAL metadata: its purpose is
  visible grouping of alternatives for the selecting agent. There is NO closed vocabulary and
  NO enforcement of semantic truth (ratified rationale: rely on module authors + the
  selecting agent; enforce facts, not claims). An absent key means unconstrained — no group
  membership, no warnings, no behavior change (backward compatible with every existing
  module).
- **FR-008** *(exclusivity declaration)*: A module MAY additionally declare
  `_bailiff_exclusive: true` — a SELF-REFERENTIAL statement meaning "my capability is a
  pick-one slot". Module descriptions MUST NOT name sibling modules (sibling lists go stale;
  self-reference cannot). GROUP-INFECTION SEMANTICS (ratified): if ANY module in the merged
  catalog listing declares exclusive for a capability, the ENTIRE capability is treated as a
  select-1 group — a selection containing >1 provider of that capability triggers the FR-010
  warning even if the specific selected modules did not themselves declare exclusive (err on
  the side of caution).
- **FR-009** *(aggregation)*: Discovery MUST parse the declarations statically (never
  executing template code, mirroring how hidden `when:false` dependency edges are already
  extracted) and expose them on the `Discovery` object and its dict form. Both catalog
  artifacts MUST carry them: the repo-published `catalog.json` (scraped by
  `scripts/generate_catalog.py` at regen, which already reads each module's `copier.yml`) and
  the user-catalog listing built for the cache (FR-016). `bailiff catalog list` output MUST show
  each module's capability tags (and exclusivity) — this listing view is the read surface for
  the selecting agent; there is NO standalone capabilities verb.
- **FR-010** *(conflict warning — never a block)*: At `init_many` selection time, when the
  selection contains more than one provider of a capability that is a select-1 group under
  FR-008's group-infection rule, bailiff MUST emit a LOUD WARNING naming the capability and the
  conflicting members — and MUST then proceed. There is no hard error and no escape-hatch
  flag (nothing to escape). The warning computation MUST also cover INCREMENTAL ADDS: when
  initing into a destination that already carries `.copier-answers.*.yml` layers, the
  already-installed modules' capabilities (read from the existing answers files / their
  recorded sources) participate in the conflict computation. Design note (ratified): the
  warn→error upgrade is deliberately trivial if real-world misuse ever demands it.
- **FR-011** *(first-party CI lint)*: `scripts/check_modules.py` MUST lint capability
  declarations for WELL-FORMEDNESS ONLY: `_bailiff_provides` is a list of kebab-case strings,
  `_bailiff_exclusive` is a boolean. It MUST additionally flag MIXED exclusivity declarations
  within one first-party capability group in the monorepo (all siblings of a pick-one family
  should declare it; inconsistency is an author-time error in first-party CI). For
  third-party catalogs, both conditions are at most runtime warnings on ingest — never hard
  failures. No vocabulary validation exists anywhere.
- **FR-012** *(signal scope)*: Capability warnings apply to `init_many` selection time ONLY.
  `reproduce`, `reproduce_many`, and `update` paths MUST NOT consult capability data (a
  committed tree always reproduces; tag changes never affect existing projects).

### Functional Requirements — init-time file-collision check

- **FR-013** *(pre-render overlap scan — the hard backstop)*: `init_many` MUST perform a
  pre-render overlap scan across the selected modules: if two selected modules would write the
  same managed destination path, init MUST fail with a typed error in the `BailiffError`
  hierarchy (exit 1) — deterministically naming the overlapping path(s) and the modules
  involved — BEFORE any render, leaving the destination untouched. This is fact-based
  enforcement and fires regardless of capability declarations. The exact mechanism
  (pretend-render manifest diffing, template-tree overlap scan, or equivalent) is a plan-phase
  decision; the requirement is the behavior. **Correction (binding)**: the existing
  `_scan_conflicts` (runner.py:520) is a POST-UPDATE merge-conflict scanner on the `update`
  path and does NOT run at init — it is NOT a backstop for init-time collisions; this FR
  introduces the only init-time collision gate.

### Functional Requirements — multi-catalog precedence

- **FR-014** *(bare-name precedence + compat)*: "Catalog" here means the EXISTING
  `CatalogPointer` model — `catalog.toml`'s ordered `[[catalog]]` tables (catalog.py:75-87);
  no new configuration model is introduced. First-listed-wins applies to BARE-NAME RESOLUTION
  ONLY: where a bare module name matches entries under multiple pointers, resolution takes
  the FIRST-listed pointer's entry with a loud shadow warning — replacing today's ambiguity
  `CatalogError` (catalog.py:455-466). Full-ids (`internal/bailiff-mod-x`) remain individually
  addressable, always. **Migration/compat note (binding)**: existing single-pointer configs
  are unchanged in every respect. Existing multi-pointer configs change behavior ONLY where
  they previously received the bare-name ambiguity error — those selections now resolve by
  precedence with a warning instead of failing. This is an explicit, deliberate behavioral
  break for exactly that error path and nothing else.
- **FR-015** *(shadowed entries stay visible)*: On bare-name shadowing, the shadow warning
  MUST name both the winning and the shadowed sources. Shadowed entries MUST remain in
  `bailiff catalog list` output, explicitly marked as shadowed — shadowing affects bare-name
  resolution, never listing visibility. There is NO content-based dedup — name precedence
  only.

### Functional Requirements — listing cache

- **FR-016** *(persisted listing + refresh)*: A new `bailiff catalog refresh` action MUST build
  the full listing (templates, unusable bucket, capability tags, shadow marks) and persist it
  under the platformdirs cache directory. `bailiff catalog list`, selection validation, and
  capability-tag reads MUST consume the persisted listing instead of re-discovering every
  source per call (today `build_listing` shallow-clones/discovers per invocation,
  catalog.py:336-397 — the pre-reshape draft's "offline from the already-built listing"
  claims described a listing that did not exist). When no cache is present, the engine MUST
  either instruct the user to run refresh or auto-build the cache once (plan phase picks one;
  either way the per-call re-clone regime ends). Staleness is user-controlled via refresh.

### Functional Requirements — stack presets (optional scope)

- **FR-017** *(stack presets)*: Stack presets are catalog DATA: named module lists (e.g.
  `python-service = [base, python, precommit, quality, ci-github]`), namespaced per catalog
  pointer with `/` matching the full-id form (`internal/python-service` — NOT `:`), the
  namespace being the existing pointer name. If shipped in 013, a preset expands to its
  module list before the FR-010 warning computation and the FR-013 collision check (presets
  get no special bypass).
  [NEEDS CLARIFICATION: presets in the first 013 release or deferred to a follow-up — ratified
  as "optional scope for 013"; maintainer to pick the release boundary].

### Functional Requirements — governance & invariants

- **FR-018** *(constitution amendment — release gate)*: Before ANY PyPI publish under this
  spec, the plan phase MUST, in one change and following the exact FR-019/ADR-0007 precedent
  from spec 011: (1) amend Constitution I (which verbatim forbids a `[project.scripts] bailiff`
  console entry and a `uvx bailiff` PyPI tool) to permit the published engine, with a
  sync-impact report; (2) amend C-11 in `.specify/memory/roadmap.md` (and its cross-cutting
  restatement) to scope — not delete — the glue-only rule; (3) write the governing ADR
  recording the repositioning (bailiff = the tool, bailiff-mod-* = the modules) and the tradeoff;
  (4) reconcile dependent text so spec 011's FR-011 remains honored retroactively for 011's
  own scope (C-11 stays binding for module-authoring specs; 013 is the governed engine
  exception). The amendment is likely a MAJOR constitution version bump (redefinition of a
  principle, unlike 011's MINOR expansion) — the plan phase confirms the bump class.
- **FR-019** *(Constitution VIII unlock)*: The typed/JSON outputs touched here (capability
  fields in catalog artifacts, `catalog list --json`) are sanctioned by Constitution VIII's
  own unlock clause — genuine non-agent programs (the packaged CLI, the collision check, the
  warning computation) now consume the handoff. The amendment (FR-018) MUST record this
  scoping so VIII's prohibition remains in force everywhere a real non-agent consumer does
  not exist.
- **FR-020** *(engine invariants preserved)*: All existing constitution invariants remain
  binding on the new code: `runner.py` stays copier-public-API-only and subprocess-free (all
  git stays in discovery); discovery never executes template code (capability parsing is
  static YAML reading); trust remains read-only in the deterministic core; no agent appears
  in any reproduce path; the deterministic phase never writes trust or secrets.
- **FR-021** *(decisions ledger — pre-plan prerequisite)*: The ratified decision ledger for
  this spec MUST be vendored as `specs/013-engine-capabilities-pypi/decisions-ledger.md`
  (following the spec 011 precedent) BEFORE the plan phase begins, so the adjudicated
  dispositions are versioned with the spec rather than living only in session records.
- **FR-022** *(MI-1 note — non-scope)*: MI-1 (the version auto-updater) remains a separate
  future spec and is NOT folded into 013. It is noted as a future consumer of the packaged
  engine (a scheduled job importing/invoking the published tool rather than a repo checkout);
  nothing in 013 may preclude that.

### Key Entities

- **Capability declaration**: the optional `_bailiff_provides: [<capability>, …]` list in a
  module's `copier.yml` — module-owned, module-versioned, statically parsed, informational.
- **Capability**: a free-form kebab-case name identifying what a module provides (e.g.
  `monorepo-tool`); no vocabulary, no policy — grouping only.
- **Exclusivity flag**: the optional `_bailiff_exclusive: true` self-referential declaration;
  under group-infection semantics, one declaration makes the whole capability a select-1
  group for warning purposes.
- **Merged catalog listing**: the ordered read over all configured catalog pointers —
  bare-name precedence resolved (first pointer wins), shadowed entries retained and marked —
  the single input to the conflict warning and `catalog list`.
- **Persisted listing cache**: the `bailiff catalog refresh` artifact under the platformdirs
  cache dir; the read source for list/selection/tag operations.
- **Collision error**: the new typed error in the `BailiffError` hierarchy (exit 1) raised by
  the pre-render overlap scan when two selected modules write the same managed path.
- **Stack preset**: catalog data naming a module list, namespaced per pointer with `/`
  (`internal/python-service`); expands before the warning and collision checks.
- **Console entry point**: the `[project.scripts]` mapping making the packaged `src/bailiff`
  CLI installable/runnable via `uvx`/`pip`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Installing the built wheel into a clean environment yields a working `bailiff`
  console command: every existing verb runs with the documented exit-code contract,
  `bailiff --version` matches the `pyproject.toml` version, and a declared-dependency audit
  (`importlib.metadata.requires` on the installed dist, or a deptry-style check) shows every
  directly imported third-party package — including `platformdirs` — declared as a runtime
  dependency (no reliance on transitive availability).
- **SC-002**: A selection containing two providers of a select-1 capability (group-infection
  rule applied) emits the loud warning naming capability and members, and the run completes
  with the same exit code and rendered output as a warning-free run; the same warning fires
  when the second provider is already installed in the destination (incremental add).
- **SC-003**: A selection of only declaration-free modules produces behavior byte-identical to
  the pre-013 engine (no new warnings, no new prompts, same outputs) — verified by the
  existing loop tests passing unmodified.
- **SC-004**: A selection in which two modules write the same managed path fails before any
  render with the typed collision error (exit 1), naming path(s) and modules, with the
  destination verifiably untouched; a disjoint selection passes the scan silently.
- **SC-005**: `generate_catalog.py` output for a declaring module carries its capability list
  (and exclusivity flag); `check_modules.py` exits non-zero for a first-party module with a
  malformed declaration (non-list / non-kebab-case / non-boolean exclusive) or a mixed
  first-party exclusivity group, reporting module + value; `bailiff catalog list` shows the
  capability tags.
- **SC-006**: With two catalog pointers configured in order, a bare name colliding across
  pointers resolves to the first-listed pointer's entry with a shadow warning naming both
  sources (where a pre-013 engine raised the ambiguity error); the shadowed full-id remains
  selectable; the shadowed entry appears in listings marked shadowed; a pre-013
  single-pointer `catalog.toml` operates with zero behavior change.
- **SC-007**: After `bailiff catalog refresh`, `bailiff catalog list` and selection validation
  complete with zero per-source clone/discovery traffic and byte-identical output across
  consecutive runs; with no cache present, the defined fallback (refresh instruction or
  one-time auto-build) occurs — never silent per-call re-cloning.
- **SC-008**: `reproduce` and `update` over a committed tree succeed regardless of capability
  declarations — no reproduce/update path consults capability data or the collision scan.
- **SC-009**: The Constitution I amendment, the C-11 roadmap amendment, the sync-impact
  report, and the governing ADR all land BEFORE the first PyPI publish; spec 011's FR-011
  gate remains textually intact and honored for 011's scope; the vendored
  `decisions-ledger.md` exists in the spec directory before plan phase.
- **SC-010**: No irreversible public action (first PyPI publish, distribution-name claim)
  occurs without explicit maintainer confirmation; the name-availability check is re-run and
  recorded immediately before first publish.

## Assumptions

- The ratified 2026-07-14 decision session, as adjudicated in the maintainer dispositions and
  vendored per FR-021, is the authoritative record; where this spec is silent, those
  decisions govern; where both are silent, the item is out of scope for 013.
- PyPI name availability as verified 2026-07-14: `bailiff` taken (unrelated `bailiff 0.1.0`
  exists), `bailiff-io` and `bailiff-scaffold` available. Availability is rechecked at
  publish time (FR-005/SC-010); squatting risk between now and publish is accepted.
- The existing engine surface (`init_many`'s pre-check pattern, discovery's static
  `copier.yml` parsing and hidden-edge extraction, the `CatalogPointer`/`build_listing`
  model and its unusable-bucket behavior, `generate_catalog.py`'s copier.yml reading, the
  `BailiffError` hierarchy, the 0/1/2/3/4 exit contract) is consumed as-is; 013 extends these
  patterns rather than introducing parallel mechanisms.
- Capability tags are advisory by ratified design: the maintainer relies on module authors
  and the selecting agent, and enforces facts (the FR-013 collision scan) rather than claims.
  The warn→error upgrade path exists but is explicitly not scope.
- 012 and 013 are decoupled: 012's modules MAY ship `_bailiff_provides`/`_bailiff_exclusive`
  declarations as they are authored; the declarations are inert on pre-013 engines, and no
  release-ordering constraint exists between the two specs.
- The constitution amendment (FR-018) is a plan-phase deliverable of THIS spec, following the
  011 FR-019/ADR-0007 pattern exactly; no interim engine code merges to a release under the
  unamended constitution.
- MI-1 stays out of scope; the packaged engine merely must not preclude it (FR-022).

## Open questions (NEEDS CLARIFICATION — maintainer decisions)

1. **Distribution name** (FR-005): `bailiff-io` (status quo; `uvx --from bailiff-io bailiff`)
   vs `bailiff-scaffold` — plain `bailiff` is taken on PyPI (verified 2026-07-14). The console
   command is `bailiff` either way.
2. **Bundled-script end-state** (FR-006): does `scripts/bailiff.py` remain permanently as a thin
   re-export shim for the skill-bundled path, or is it deprecated once the PyPI tool is the
   documented invocation? This shapes the amended Constitution I wording.
3. **Stack presets release boundary** (FR-017): in the first 013 release or deferred —
   ratified only as "optional scope for 013".
