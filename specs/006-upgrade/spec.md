# Feature Specification: bailiff upgrade — explicit version upgrade + copier migrations

**Feature Branch**: `006-upgrade`

**Created**: 2026-07-10

**Status**: Draft

**Input**: Roadmap spec 006 (Upgrade + copier migrations), governed by the
constitution (v2.1.0, Principles III and VI) and ADR-0001. Depends on spec 003
(ordering DAG). This is the ONLY place a newer-version dependency or a version-
crossing migration is ever applied; reproduce (spec 003) always stays pinned.

## Overview

Specs 001/010 proved faithful reproduce; spec 003 added multi-layer coordination.
Spec 006 is the intentional escape from the pinned state: an **announced, explicit
upgrade** that moves a project from one template version to another.

Where reproduce replays committed answers at the recorded `_commit` (never
upgrades), upgrade calls copier's **`run_update`** — the smart 3-way merge that
integrates template changes into a project that may have local edits. One `copier
update` per template layer, in dependency order (reusing spec 003's DAG).

Upgrade is also the ONLY place where:
- a dependency added in a **newer template version** is picked up (reproduce stays
  pinned; spec 003 FR-009);
- **`_migrations`** run — copier's version-crossing migration tasks, trust-gated
  identically to `_tasks`.

bailiff's role is the glue copier cannot supply: announce the from→to versions per
layer, drive `run_update` per layer in dependency order, surface migrations and
conflicts, and respect the template-author contract (Constitution VI: new
`_migrations` format only; the deprecated `before`/`after` dict form is rejected).

## Motivating decisions

1. **`run_update` is copier's upgrade path; bailiff does NOT re-implement the merge.**
   copier's 3-way merge handles the diff between template versions against any local
   edits (ADR-0001). bailiff's role is to announce versions, drive the call in
   dependency order, and surface outcomes. New glue is only what copier cannot do
   cross-template (C-11).

2. **Upgrade is the ONLY path that picks up newer-version dependencies.**
   Reproduce re-discovers each layer at its pinned `_commit`; the recomputed DAG
   is therefore identical to init. A dependency added in a newer template version
   cannot appear in the reproduce DAG. Upgrade re-solves the DAG against the
   target versions, so new dependencies ARE picked up (Q-006b open question below).

3. **Multi-layer upgrade uses spec 003's ordering, re-solved against target versions.**
   For each layer the target version is determined (latest unless pinned by the
   user); the edges are re-read at that version; the DAG is rebuilt. Layers are
   then upgraded in that order.

4. **`_migrations` are update-only, trust-gated.** copier runs `_migrations` only
   on `run_update`, never on `run_copy`/`run_recopy` (verified: ADR-0001). They
   execute as code → governed by the same trust surface as `_tasks`. bailiff MUST
   NOT invoke `run_update` on an untrusted source bearing migrations (same
   `UntrustedSourceError` path as `_tasks`).

5. **New `_migrations` format only.** The deprecated per-stage `{"version": …,
   "before": […], "after": […]}` dict form emits `DeprecationWarning` from copier
   and is REJECTED by bailiff discovery at upgrade time (Constitution VI, C-06).
   New format: either a bare command string/list (runs at `after` stage by default),
   or a dict with `command`, optional `version` (version-crossing filter:
   `target_version >= entry_version > from_version`), optional `when` (Jinja
   condition on `_stage`), optional `working_directory`.

6. **conflict=`inline` by default; surface conflicts to the user.**
   When `run_update` writes inline conflict markers (git-merge-style), bailiff
   reports the conflicted paths and exits non-zero. The user resolves and then runs
   upgrade again (or uses copier's `conflict=rej` mode to write `.rej` files
   instead). This is an **open question** (Q-006a) — see below.

7. **Announced from→to.** Before each layer's upgrade, bailiff emits the from-version
   and to-version so the user knows what is happening. For multi-layer upgrades the
   announcement covers all layers before any `run_update` call.

8. **Brownfield adoption (no `.copier-answers.yml`) is OUT of scope.** This spec
   only upgrades projects that were already init-ed with bailiff (have the committed
   answers file(s)). The brownfield rewrite is the deferred spec.

## User Scenarios & Testing

### US1 — Upgrade a single-layer project to a newer template version (Priority: P1)

A developer has a project generated from `bailiff-mod-base v1.0.0`. A new
`v1.1.0` tag is available. They run `scripts/bailiff.py update` targeting
the project; bailiff announces `v1.0.0 → v1.1.0`, calls `run_update`, and reports
success. The committed answers file now records `_commit` at `v1.1.0`.

**Why this priority**: the core upgrade loop; everything else builds on it.

**Independent Test**: a local template fixture at `v1.0.0`; bump to `v1.1.0` adding
one new rendered file. Run `run_update`. Assert: new file present; answers file
records the new `_commit`; old rendered files unchanged where no conflict.

**Acceptance Scenarios**:
1. **Given** a v1.0.0 project, **When** upgrade targeting latest, **Then** the
   project reflects v1.1.0; answers file `_commit` updated.
2. **Given** `--vcs-ref v1.1.0` specified, **When** upgrade, **Then** that exact
   version is targeted (not necessarily latest).
3. **Given** source is untrusted, **When** upgrade, **Then** bailiff refuses with
   `UntrustedSourceError` (exit 3) before calling `run_update`.

### US2 — Upgrade with a version-crossing migration (Priority: P1)

A template adds a `_migrations` entry with `"version": "v1.1.0"` and a migration
command. Upgrading from v1.0.0 → v1.1.0 triggers the migration; upgrading from
v1.1.0 → v1.2.0 (no new migration entry) does not.

**Why this priority**: migrations are this spec's distinctive new capability;
must fire at the right version crossing.

**Independent Test**: a local template with one `_migrations` entry at `v1.1.0`.
Upgrade from v1.0.0 → v1.1.0 → assert migration ran (side effect detectable, e.g.
sentinel file). Upgrade from v1.1.0 → v1.2.0 → assert migration did NOT run.

**Acceptance Scenarios**:
1. **Given** from=v1.0.0, to=v1.1.0, entry with `version: v1.1.0`, **When** upgrade,
   **Then** migration fires (condition: `target >= v1.1.0 > from`).
2. **Given** from=v1.1.0, to=v1.2.0, no entry at v1.2.0, **When** upgrade, **Then**
   no migration runs.
3. **Given** migration in deprecated `{"version": …, "before": …, "after": …}` form,
   **When** upgrade, **Then** bailiff refuses at discovery with a clear error naming
   the template and the deprecated format (exit 1), before calling `run_update`.

### US3 — Multi-layer upgrade in dependency order (Priority: P1)

A project with two layers (A → B via `depends_on`). A has a new version; B has a
new version. Upgrade upgrades A first (dependency order), then B. Per-layer
announcements show both from→to pairs.

**Why this priority**: dependency ordering is the multi-template contract (spec 003
reuse); upgrading out of order could leave the project inconsistent.

**Independent Test**: two fixture templates with a `depends_on` edge. Both have a
v1.1.0. Upgrade a v1.0.0 project. Assert A upgraded before B (per-layer marker or
`_commit` in answers file reflects upgrade order); both answers files updated.

**Acceptance Scenarios**:
1. **Given** B depends_on A, **When** multi-layer upgrade, **Then** A is upgraded
   before B.
2. **Given** B depends_on A (at the TARGET version), **When** multi-layer upgrade
   using DAG re-resolved at target versions, **Then** order reflects the target-
   version edges (see Q-006b on new deps).

### US4 — Upgrade surfaces a merge conflict (Priority: P2)

A template changes a file that the user also edited locally. copier's 3-way merge
produces inline conflict markers. bailiff reports the conflicted paths and exits
non-zero so the user can resolve.

**Why this priority**: conflict handling is the primary risk of an upgrade; the
user must never be left in an unresolvable state silently.

**Independent Test**: a template fixture where `v1.0.0 → v1.1.0` changes a line
in a file; the project also has a local edit on that same line. Run upgrade. Assert
exit non-zero; inline conflict markers present in the file; bailiff names the
conflicted path(s) in its output.

**Acceptance Scenarios**:
1. **Given** a merge conflict, **When** upgrade, **Then** exit 4 (conflict), the
   conflicted file(s) are named in output.
2. **Given** `conflict=rej` mode, **When** upgrade with that option, **Then** `.rej`
   files written instead of inline markers.

### US5 — New dependency appears in upgraded template version (Priority: P2)

Template B at v1.1.0 adds `depends_on: [C]` where C is a new layer. Upgrading a
project that had only B at v1.0.0 surfaces this new dependency. Bailiff alerts the
user that the upgraded template now declares a new dependency and provides the
remediation step (add C to the project, or this is a known open question — Q-006b).

**Why this priority**: upgrading the DAG structure is the spec's novel capability
vs reproduce; must not be silent.

**Independent Test**: fixture template that adds a `depends_on` edge in v1.1.0.
Upgrade a v1.0.0 single-layer project. Assert bailiff surfaces the new dependency
requirement (exit or warning, depending on Q-006b resolution).

**Acceptance Scenarios**:
1. **Given** upgraded template v1.1.0 declares new `depends_on: [C]`, **When**
   upgrade a project that does not have C, **Then** bailiff surfaces this as a
   warning or error (exact behavior pending Q-006b).

### Edge Cases

- **No `.copier-answers.yml`**: refused immediately (no brownfield path here).
- **Already at the target version**: bailiff reports "already at target, nothing to
  do"; exit 0.
- **`vcs_ref` points to a version OLDER than current**: refused (downgrade is not
  supported; user must downgrade manually via copier CLI).
- **A layer's template source is unreachable**: fail loudly before beginning
  any layer's upgrade (pre-flight check all sources before any `run_update` call).
- **Migration command fails**: copier propagates the failure; bailiff surfaces it
  with the layer name, from/to version, and the migration stage (before/after).
- **`run_update` with `pretend=True`**: dry-run upgrade to preview changes without
  writing. Bailiff must surface what would change (relies on copier's pretend mode).
- **Single layer via the multi-layer path**: N=1 must work through the same
  code path (spec 010 uniform-loop invariant extended to update).
- **`skip_tasks=True` option**: allow the user to suppress `_tasks` during upgrade
  (copier supports this). Migrations follow the same flag (open question — they are
  separate from `_tasks`; verify copier's `skip_tasks` does NOT suppress migrations).

## Requirements

### Functional Requirements

- **FR-001**: bailiff MUST provide an `update` verb in `scripts/bailiff.py` that drives
  `run_update` per layer in dependency order (spec 003's DAG, re-solved at target
  versions).
- **FR-002**: bailiff MUST announce the from→to version for each layer before any
  `run_update` call.
- **FR-003**: bailiff MUST re-solve the ordering DAG against the target template
  versions (re-read edges at the target ref) before running any layer, so a
  dependency added in a newer template version is visible (Q-006b determines exact
  behaviour for net-new deps absent from the project).
- **FR-004**: bailiff MUST trust-gate upgrade identically to init: a template with
  `_migrations` or `_tasks` from an untrusted source MUST raise `UntrustedSourceError`
  (exit 3) before calling `run_update`.
- **FR-005**: bailiff MUST enforce the new `_migrations` format: if static discovery
  detects the deprecated `before`/`after` dict form, refuse with a clear error
  (exit 1) naming the template and the deprecated format. This is a discovery-time
  check, not a runtime one.
- **FR-006**: Migrate version-crossing check: bailiff MUST only accept a `_migrations`
  entry where the version condition is `target >= entry_version > from_version`
  (matches copier's own filter; the check is copier's, bailiff's discovery only
  validates the format).
- **FR-007**: bailiff MUST surface merge conflicts: if `run_update` leaves conflict
  markers (or `.rej` files), bailiff MUST report the affected paths and exit 4.
- **FR-008**: bailiff MUST support `--vcs-ref` to target a specific version rather
  than the latest tag.
- **FR-009**: bailiff MUST add `run_update` glue to `runner.py` (`update` and
  `update_many` functions, analogous to `init`/`init_many`), reusing the existing
  trust/reproducibility pre-checks.
- **FR-010**: N=1 single-layer upgrade MUST work through the same code path as
  multi-layer (spec 010 uniform-loop invariant).
- **FR-011**: A dry-run upgrade (`--pretend`) MUST run `run_update(pretend=True)`
  per layer, writing nothing, and report what would change.
- **FR-012**: bailiff MUST refuse to downgrade (target version < current `_commit`
  version); exit 1 with a clear message.

### Key Entities

- **Upgrade announcement**: the per-layer `from_version → to_version` line bailiff
  emits before any `run_update` call.
- **run_update wrapper** (`runner.py`): `update(dest, *, vcs_ref, answers_file,
  today, pretend)` → single-layer analogue of `init`; `update_many(dest, *,
  vcs_ref_map, today, pretend)` → multi-layer analogue of `init_many`.
- **Re-solved DAG**: the dependency graph rebuilt at the target template versions
  (distinct from the reproduce-time recomputed DAG which uses pinned commits).
- **Migration**: a `_migrations` list entry in `copier.yml` (new format); runs
  only on `run_update`; trust-gated; version-crossing filtered by copier.
- **Conflict**: one or more files with inline markers (or `.rej` files) left by
  copier's 3-way merge; bailiff reports them; user resolves.

## Success Criteria

- **SC-001**: Single-layer upgrade applies template changes, updates `_commit` in
  the answers file, and exits 0 on a clean merge.
- **SC-002**: Version-crossing migration fires at the correct version boundary and
  not at others; deprecated format is refused at discovery.
- **SC-003**: Multi-layer upgrade applies layers in dependency order (re-solved at
  target versions); each answers file updated; announcements correct.
- **SC-004**: Merge conflict exits 4 and names the conflicted path(s).
- **SC-005**: Untrusted-source upgrade (migrations or tasks) exits 3 without calling
  `run_update`.
- **SC-006**: N=1 through the multi-layer path behaves identically to the
  single-layer loop (no regression).
- **SC-007**: `--pretend` runs without writing, reports what would change.

## Out of Scope

- **Brownfield adoption** (no `.copier-answers.yml` — deferred spec).
- **Downgrade** (user does this manually via copier CLI).
- **Global per-template defaults** (spec 004) — upgrade threads answers from the
  committed file; user may supply overrides via the run-spec.
- **Secrets injection** (spec 005) — update accepts the same `data=` dict; secrets
  can be re-injected per-invocation, but the secrets plumbing spec is 005.
- **Agentic module** (spec 007) — upgrade drives any template; its content is 007.
- **Release/fan-out** (spec 008).

## Open Questions

- **Q-006a — Conflict UX**: when `run_update` leaves conflict markers in files,
  bailiff needs to report them. **How should this be detected?** copier does not
  return a structured conflict report from `run_update` — it writes inline markers
  and returns the `Worker` object. Detection options: (i) grep the destination tree
  for `<<<<<<< HEAD` markers post-update; (ii) use `conflict='rej'` and look for
  `.rej` files; (iii) check copier's `Worker.result` attribute if it surfaces
  conflicts (needs verification). **What exit code?** Proposed exit 4 (distinct from
  other errors). **Severity**: medium — can implement a post-update marker scan
  as a first pass, but the UX may need iteration.

- **Q-006b — DAG re-resolution for new deps**: when the target template version
  adds a new `depends_on` edge naming a template NOT in the current project, what
  should bailiff do? Options: (i) **warn and continue**: upgrade the layers that exist,
  warn about the new dep so the user can add it separately; (ii) **refuse**: exit
  with a clear error naming the new dep — the user must add the new layer first;
  (iii) **auto-add**: initiate an `init` for the new layer before upgrading (adds
  scope, may have further cascading deps). Lean: **refuse with a clear remediation
  message** (consistent with spec 003's dangling-edge policy: refuse, name it). But
  this is a genuine UX decision — resolving it changes the test cases for US3/US5.
  Resolve at planning.

- **Q-006c — `skip_tasks` and migrations**: copier's `run_update` accepts
  `skip_tasks=True`, which suppresses `_tasks` during update. Does it also suppress
  migrations? This needs source verification (the `migration_tasks` call in copier's
  update path vs the `_tasks` path). If they are separate, bailiff should expose them
  as separate flags. If `skip_tasks` suppresses both, one flag suffices. **Verify
  against copier 9.16 source before implementing.**

- **Q-006d — `vcs_ref` for multi-layer upgrade**: when upgrading N layers and the
  user passes `--vcs-ref v1.2.0`, does that ref apply to ALL layers, or to a
  specific one? For homogeneous template families with synchronized version tags
  this is fine; for heterogeneous selections it may be wrong. Initial stance:
  `--vcs-ref` applies to all layers (user's explicit intent); a per-layer ref map
  (`--ref layer=version`) is a future extension. The run-spec can carry per-layer
  refs (FR-008). Resolve at planning.

- **Q-006e — `conflict` parameter surface**: `run_update` accepts `conflict=
  'inline'` (default) or `'rej'`. Should bailiff expose this as a flag? Initial
  stance: expose it so power users can choose `.rej` files over inline markers.
  Low-stakes decision; resolve at planning.

## Governing Constitution & ADRs

- **Constitution III** (faithful, agent-free reproduce — upgrade is the ONLY
  departure from pinned state; it MUST be explicit and announced).
- **Constitution VI** (template-author contract: new `_migrations` format enforced
  at discovery; deprecated form refused).
- **ADR-0001** (`run_update` is the third public copier operation; copier owns the
  3-way merge; migrations are update-only + trust-gated).
- **ADR-0004** (canonical non-interactive `run_update` call: `data=answers,
  defaults=True, quiet=True, settings=…`).
- **Constraints**: C-06 (migrations new format), C-07 (hardening per-step), C-11
  (glue only for what copier cannot do cross-template — DAG re-solution is the gap).
- **Spec 003** (ordering reused — this spec's direct dependency).
- **Spec 010** (delivery contract: `scripts/bailiff.py update` verb; N=1 uniform loop).
