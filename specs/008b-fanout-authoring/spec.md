# Feature Specification: bailiff template fan-out + authoring lifecycle (CI)

**Feature Branch**: `008b-fanout-authoring`

**Created**: 2026-07-10

**Status**: Draft

---

> ### 009 DELIVERED — CODE AUTHORED; REMAINING GATE IS MAINTAINER ORG SETUP + LIVE CANARY
>
> The original block ("cannot be implemented until spec 009 creates the first real
> `bailiff-mod-*` modules") is **lifted**: spec 009 landed
> `templates/bailiff-mod-base/` + `templates/bailiff-mod-python/`. All of 008b is now
> authored — the cocogitto config, scaffolder, contract linter, catalog generator
> (Phases 1–4), and the release/fan-out pipeline (`.github/workflows/release.yml`,
> `scripts/fanout_module.sh`, the GitHub App token step, the Pages deploy step, and
> the offline smoke test, Phases 5–7).
>
> **The pipeline is correct-by-construction but UNPROVEN end-to-end.** It cannot run
> until a `bailiff-io` org-admin performs one-time manual setup a code agent
> cannot do: create + install the `bailiff-fanout` GitHub App, add the org secrets
> `BAILIFF_FANOUT_APP_ID` + `BAILIFF_FANOUT_PRIVATE_KEY`, and arm the workflow
> (`BAILIFF_FANOUT_ARMED=true`). A live canary release (and a `discovery.discover()`
> check against a fanned-out repo) is the final verification gate. See
> [`docs/runbooks/fanout-release.md`](../../docs/runbooks/fanout-release.md).
> Until that canary passes, do **not** mark this spec `verified`.
>
> **Catalog hosting update (2026-07-13):** GitHub Pages was DROPPED. Pages on a
> private repo requires a paid plan; instead the monorepo was made **public** and
> the already-committed `catalog.json` is served via raw git
> (`https://raw.githubusercontent.com/bailiff-io/bailiff/main/catalog.json`).
> References to "GitHub Pages" below are superseded by this raw-git hosting.

---

## Overview

Spec 008 (packaging) took the skill-distribution half of roadmap spec 008. This
spec takes the other half: the **authoring monorepo infrastructure** — cocogitto
monorepo release config, the snapshot-mirror fan-out CI job, the `bailiff-fanout`
GitHub App identity, the `just new-module` scaffolder, the `check-modules`
contract lint, and the generated `catalog.json` published via GitHub Pages.

The outcome is a `bailiff-io/bailiff` monorepo that can:

1. Accept authoring of any number of modules under `templates/<name>/`.
2. Release changed modules (`cog bump --auto`) → push → fan-out each changed
   module as a snapshot mirror to `bailiff-io/bailiff-mod-<name>` with a clean
   `vX.Y.Z` tag copier can resolve.
3. Keep the family structurally sound (contract lint in pre-commit + pre-bump).
4. Serve a generated `catalog.json` index via GitHub Pages.

This is CI bash + template content, zero new application code (Constitution I,
Principle C-11). The authoring plane reuses the consumer-plane `discovery.discover()`
aimed inward at local `templates/<name>/` — no second tool.

## Motivating decisions (all from ADR-0006; see that document for rationale)

1. **Central authoring, per-repo distribution** — copier's PEP 440 tag constraint
   requires one repo per template; hand-authoring 24 repos is untenable. Solution:
   one monorepo → per-repo snapshot mirror. History-preserving splits (splitsh-lite,
   git-filter-repo, copybara) rejected — copier only needs the correct tree at each
   tag, not intermediate commits.

2. **cocogitto monorepo mode** — one tool across the whole family (already in
   pre-commit as `cocogitto-verify`). Tags each module as `<name>-vX.Y.Z`;
   fan-out strips the prefix to emit `vX.Y.Z` in the split repo.
   Two MANDATORY settings:
   - `generate_mono_repository_global_tag = false` (suppress the umbrella `vX.Y.Z`
     tag; we want only isolated per-module tags in the monorepo).
   - `tag_prefix = "v"` (with the default `-` separator → `<name>-vX.Y.Z`).

3. **Fan-out as CI job steps, not cog hooks** — `post_bump_hooks` have no rollback;
   a failing fan-out to 24 repos would half-finish a release. The CI job orders:
   cog bump → push (monorepo release finalized) → derive changed set → fan-out.
   A fan-out failure fails AFTER the monorepo release is safe; re-run is idempotent.

4. **Snapshot mirror, hand-rolled ~25-line workflow bash** — not an external split
   action. Zero external deps; the logic is `cp subdir → commit → tag → push`.
   Direct push, not PR, into split repos (mirrors are generated read-only; PR review
   would be rubber-stamping and makes tagging two-phase).

5. **`bailiff-fanout` org GitHub App** — mints short-lived installation tokens
   (`contents:write` + `administration:write`). The elevated org-admin grant belongs
   to an auditable org-owned identity; a long-lived personal PAT is the documented
   fallback only.

6. **Auto-create missing split repos** — `gh repo create bailiff-io/bailiff-mod-<name>`
   (idempotent); one code path owns repo existence. Requires `administration:write`
   on the App token.

7. **Authoring lifecycle = consumer plane aimed inward** (C-11, C-09):
   - `just new-module <name>` renders `_meta/module-template/` with copier (dogfood).
   - `just check-modules` loops `templates/*/`, calls `discovery.discover()` on each,
     asserts the contract. Runs in pre-commit + `pre_bump_hooks`.
   - `catalog.json` GENERATED on release (not hand-maintained), committed in
     monorepo, served via GitHub Pages.

## User Scenarios & Testing

### US1 — Release a changed module, fan it out (Priority: P1)

A maintainer merges a commit touching `templates/bailiff-mod-base/`. CI runs
`cog bump --auto`, pushes, detects the new `bailiff-mod-base-vX.Y.Z` tag, mirrors
`templates/bailiff-mod-base/` to `bailiff-io/bailiff-mod-base`, creates tag `vX.Y.Z`
there, regenerates `catalog.json`, and creates a GitHub Release.

**Acceptance Scenarios**:
1. Only the changed module is fanned out (unchanged modules are skipped).
2. The split repo receives exactly the contents of `templates/bailiff-mod-base/`,
   tagged `vX.Y.Z` (PEP 440, copier-consumable).
3. If `bailiff-io/bailiff-mod-base` did not exist, it is auto-created.
4. If no diff between the current snapshot and the previous one, the commit is
   skipped (idempotent re-run).

### US2 — Scaffold a new module (Priority: P1)

A maintainer runs `just new-module bailiff-mod-python`. The scaffolder renders
`_meta/module-template/` and places a contract-complete module stub under
`templates/bailiff-mod-python/` with: `copier.yml` (answers-file `.jinja` entry),
`README.md`, `CHANGELOG.md`, and registration edits (`cog.toml` + catalog source
entry). Running `just check-modules` passes immediately after scaffold.

### US3 — Contract lint catches a violation (Priority: P1)

`just check-modules` runs in pre-commit and `pre_bump_hooks`. It must refuse (exit
non-zero) for: missing answers-file `.jinja`; missing README/CHANGELOG; directory
listing not matching `cog.toml` packages or catalog source entries; a
published-label mutation (an existing `<name>-v*` tag's `copier.yml` choices
differing from the working tree).

### US4 — Catalog is current after release (Priority: P2)

After the fan-out step, `catalog.json` is regenerated, committed to the monorepo,
and the GitHub Pages site reflects the new module versions within one pipeline run.

## Requirements

### Functional Requirements

- **FR-001**: The monorepo MUST use cocogitto in monorepo mode with
  `generate_mono_repository_global_tag = false` and `tag_prefix = "v"` so each
  module is tagged `<name>-vX.Y.Z` and no PEP 440-parseable umbrella tag is emitted.
- **FR-002**: The CI release job MUST execute these steps in order:
  1. `cog bump --auto` (commits + creates per-module tags; cog never pushes)
  2. `git push --follow-tags` (monorepo release finalized before fan-out begins)
  3. `git tag --points-at HEAD | grep -E '^.+-v[0-9]'` (derive the changed module set
     from the bump commit's tags — no hook, no dry-run parsing)
  4. For each changed module: snapshot-mirror fan-out (FR-003)
  5. Regenerate + commit `catalog.json` to monorepo; push; GitHub Pages serves it
  6. `gh release create` using cog's generated CHANGELOG body
- **FR-003**: The snapshot-mirror fan-out for one module MUST:
  - Clone (or auto-create if missing) `bailiff-io/bailiff-mod-<name>`
  - Replace the repo contents with `templates/<name>/`
  - Skip the commit if there is no diff (idempotent re-run)
  - Create an annotated tag `vX.Y.Z` (prefix stripped: `<name>-vX.Y.Z` → `vX.Y.Z`)
  - Push HEAD + tags directly (no PR)
- **FR-004**: Fan-out MUST authenticate via the `bailiff-fanout` org GitHub App
  installation token (short-lived, per-run) with `contents:write` +
  `administration:write` permissions; a fine-grained PAT with the same grants is
  the documented fallback (not chosen for production).
- **FR-005**: `just new-module <name>` MUST render the `_meta/module-template/`
  copier meta-template, producing a contract-complete module stub:
  `copier.yml` (with `_answers_file` `.jinja` key), `README.md`, `CHANGELOG.md`,
  registration entries in `cog.toml [monorepo.packages.<name>]` and the catalog
  source list.
- **FR-006**: `just check-modules` MUST loop every `templates/*/` entry and assert:
  - Valid `copier.yml` + answers-file `.jinja` present (reusing `discovery.discover()`)
  - `README.md` + `CHANGELOG.md` present
  - Three-way registration parity: directory listing == `cog.toml` packages ==
    catalog source entries (no orphan, no ghost)
  - Published-label immutability: if any `<name>-v*` tag exists, `copier.yml`
    choice labels in the working tree MUST match those at the last tag (C-06)
- **FR-007**: `check-modules` MUST run in the `pre_bump_hooks` slot (so a contract
  violation aborts the bump before any tag is created) and in a pre-commit hook.
- **FR-008**: `catalog.json` MUST be generated (not hand-maintained) by enumerating
  `templates/*/`, reading name + description from each `copier.yml` + latest `v*`
  tag from the split repo, and emitting a JSON index. It MUST be committed to the
  monorepo root and served via GitHub Pages at a stable URL bailiff consumers fetch.
- **FR-009**: The fan-out CI steps MUST be idempotent: re-running them against
  existing tags (after a prior partial failure) MUST not create duplicate tags or
  fail on already-existing repos.

### Key Entities

- **Module**: one directory `templates/<name>/` — a complete copier template with
  `copier.yml`, answers-file `.jinja`, README, CHANGELOG.
- **Split repo**: `bailiff-io/bailiff-mod-<name>` — a read-only generated mirror;
  consumers source templates from here, never from the monorepo.
- **Monorepo tag**: `<name>-vX.Y.Z` — cocogitto's per-module tag; the fan-out strips
  the prefix.
- **Split tag**: `vX.Y.Z` — the PEP 440 tag copier resolves in the split repo.
- **`catalog.json`**: the generated index of all modules + latest versions; hosted
  via GitHub Pages; consumed by bailiff's catalog subsystem (spec 002).

## Success Criteria

- **SC-001**: A commit touching only `templates/bailiff-mod-base/` results in only
  `bailiff-mod-base-vX.Y.Z` being tagged in the monorepo; only `bailiff-io/bailiff-mod-base`
  is pushed; unchanged modules are not touched.
- **SC-002**: The split repo `bailiff-io/bailiff-mod-base` contains exactly the
  contents of `templates/bailiff-mod-base/` at the release commit, tagged `vX.Y.Z`.
  `discovery.discover()` can resolve it (PEP 440 tag present).
- **SC-003**: A newly scaffolded module passes `check-modules` immediately and can
  be released in the same pipeline run.
- **SC-004**: `check-modules` in `pre_bump_hooks` aborts the bump (no tag created)
  when any module violates the contract.
- **SC-005**: `catalog.json` lists every module under `templates/*/`, reflects the
  post-release latest versions, and is served at the GitHub Pages URL within one
  pipeline run.
- **SC-006**: Re-running the fan-out steps against already-existing tags and repos
  succeeds without error (idempotent).

## Out of scope

- Skill packaging / APM distribution (spec 008 — already split out).
- Module content itself (spec 009 — 008b builds the pipeline; 009 fills it).
- History-preserving splits (rejected in ADR-0006 — copier needs only tree-at-tag).
- A standalone catalog repo (rejected — index lives in the monorepo).
- Submodules (rejected — do not satisfy copier's per-repo clean-tag rule).
- Fan-out driven by `post_bump_hooks` (rejected — no rollback; see ADR-0006).
- The `pre_bump_hooks` network preflight (optional per ADR-0006; not MVP).

## Open Questions

- **Q-008b-a — Catalog generation scope at MVP**: should `catalog.json` include
  only modules that have at least one published split-repo tag, or all declared
  modules including unreleased? ADR-0006 implies "enumerate templates/* + read
  latest v* tag" — an unreleased module would appear with no version. Recommend:
  exclude modules with no published tag; surface this in the generator script.
  *(Low risk; resolve at planning.)*
- **Q-008b-b — GitHub Pages trigger**: does the catalog page rebuild on every push
  to main (including non-release commits) or only after the release step pushes a
  fresh `catalog.json`? Recommend: trigger on `catalog.json` changes only (avoids
  spurious deploys). *(Resolve at planning.)*

## Governing constitution & ADRs

- Constitution I (this is CI bash + template content, no new application code),
  VI (published-label immutability, C-06), C-09 (authoring monorepo → fan-out),
  C-11 (authoring plane reuses consumer-plane discovery, no second tool).
- ADR-0006 (primary: fan-out mechanics, cocogitto config, GitHub App, authoring
  lifecycle, catalog hosting — fully settles this spec's design).
- ADR-0002 (catalog and answer model — `_src_path` = split repo; PEP 440 tag
  requirement; consumers source split repos).
- Constraints: C-06 (label immutability), C-09 (fan-out shape), C-11 (reuse
  discovery).
- **Depends on**: spec 001 (discovery.discover() exists), spec 002 (catalog
  consumers). **IMPLEMENTATION BLOCKED ON**: spec 009 (no real modules yet).
