# Decisions Ledger — spec 012 (module batch 2)

**Source**: Ratified maintainer decisions from the 2026-07-14 decision session (the same
session that produced spec 011 and spec 013's charter), plus the 2026-07-15 maintainer
resolution of this spec's NEEDS CLARIFICATION items. This file is the in-tree authoritative
record per the spec's Input clause: where spec.md is silent, this ledger governs; where
this ledger is silent, the item is out of scope for 012.

## Governing rule — monolith vs split (ratified 2026-07-14)

A family of alternatives is **ONE module with a choice axis** when the family is
**isomorphic**: same question shape AND same output contract, only the rendered syntax
differs. A family is **SEPARATE sibling modules** when renders are disjoint or paradigms
differ. **Meta-modules are REJECTED** (versioning + fan-out problems); mutual exclusivity
between siblings is a selection-time constraint, not containment.

Applied to this batch:

- `bailiff-mod-dep-updates` = ONE module with the `dep_update_tool [renovate, dependabot]`
  axis (each branch renders a single managed config answering the same question —
  isomorphic).
- cocogitto/release-please, moon/turbo/nx, mkdocs/vitepress = per-tool sibling splits
  (disjoint renders; maintainer verbatim on monorepo tools: "they are too distinct").

## Module batch decisions (ratified 2026-07-14)

| Module | Decision | Rationale |
|---|---|---|
| bailiff-mod-devcontainer | Build (P1); pure managed render deriving from frozen `mise_tools` | Zero drift between host pins and container |
| bailiff-mod-editorconfig | Build (P2); micro-module, deliberately NOT part of base | Keeps base thin; sections derive from frozen linter facts |
| bailiff-mod-cocogitto | Build (P1); dogfooded (bailiff runs on cog); release-please is a later sibling | Disjoint renders = sibling split (FR-001) |
| bailiff-mod-dep-updates | Build (P1); ONE module with `dep_update_tool` axis; default follows repo host | Isomorphic family; host-native default (dependabot on GitHub, renovate otherwise) |
| bailiff-mod-moon | Build (P2); turbo/nx are later siblings | Monorepo tools "too distinct" for an axis; closes the dangling `monorepo_tool` CI read |
| bailiff-mod-mkdocs | Build (P2); vitepress is a later sibling | Per-engine split, not an axis |
| bailiff-mod-gitlab-repo | Build (P2); exact semantic port of github-repo to `glab` | Host parity; consent gate is a safety property, ported faithfully |
| bailiff-mod-api | Build (P3); seed-once OpenAPI skeleton + managed spectral config | API-first without codegen or server scaffold |

## Sanctioned 011-artifact amendments (ratified 2026-07-14)

Exactly two amendments are carved out of the "does not reopen 011's decisions" clause:

| Amendment | Rationale | Sequencing |
|---|---|---|
| FR-009: remove `dependabot.yml` from `bailiff-mod-base` | Dependency-update policy is owned by exactly one module (`bailiff-mod-dep-updates`); base ships one clean v1.0.0 | MUST land before the 011 Phase 7 publish batch — **already merged (commit a68295e)**; only spec-artifact annotations remain |
| FR-010a: CI modules accept `monorepo_tool=moon` | Moon is the first real monorepo-tool supplier; the CI modules' `monorepo-affected` model must accept it before moon exists | MUST land before `bailiff-mod-moon` is authored (plan Phase 2 before Phase 4) |

## Naming decision (ratified 2026-07-14)

FR-014: `bailiff-mod-justfile` KEEPS its name — the maintainer rejected a preemptive rename
to `bailiff-mod-runner`. Reconsidered only if/when make/task ship as a monolith with a
runner axis under FR-001.

## NEEDS CLARIFICATION resolutions (maintainer-ratified 2026-07-15)

| Item | Decision | Rationale |
|---|---|---|
| FR-005 devcontainer base image | **Fixed default: `mcr.microsoft.com/devcontainers/base:ubuntu`**; no `devcontainer_image` question | The module's value is zero-decision reproducibility derived from `mise_tools`; a question undermines that. Projects needing another image edit after scaffold. |
| FR-007 cocogitto CI job seeding | **Leave CI untouched** | CI modules are the single owners of workflow/pipeline files. A cog-driven release job is a CI-model decision (possible future `ci_model` variant), not release-tool-module scope. Preserves single-writer discipline. |
| FR-010 moon on single-package layout | **Warn-and-render** | Moon works as a single-project task runner; a refusal would second-guess a deliberate choice. Consistent with the dependabot-on-non-GitHub warn-and-render precedent. Warning text: moon is primarily a monorepo workspace tool; single-package config will be minimal. |
| FR-011 mkdocs pin strategy | **`mise_tools` contribution** (`mkdocs`, `mkdocs-material` tokens), regardless of `bailiff-mod-python` co-selection | Every non-runtime tool pins through the `mise_tools` frozen union; a Python-dev-deps special case would introduce conditional pin behavior and a second mental model. |
| FR-013 OpenAPI path/version | **Root `openapi.yaml`, OpenAPI 3.1** | Lowest-friction default (spectral/editors find it without config); the document is seed-once, so a project can move it and re-runs never clobber. 3.1 is current stable. |

## Plan amendment (maintainer-ratified 2026-07-15)

`bailiff-mod-api` (T010) has no dependency on any Slice B module — it moves into the
Slice B parallel set (Phase 4). Phase 5 (Slice C) is dissolved. The P3 priority label is
unchanged; only execution scheduling changes.

## Out of scope for 012

- `bailiff-mod-release-please`, `bailiff-mod-turbo`, `bailiff-mod-nx`, `bailiff-mod-vitepress`
  (MI-3 — ratified as future siblings, named so the split shape is on record)
- MI-1 version auto-updater (separate future spec)
- Constitution / C-11 / roadmap changes (spec 013 owns the engine relaxation; C-11 holds
  unchanged for 012)
- Capability declarations (`_bailiff_provides` / `_bailiff_exclusive`) are spec 013 engine
  scope; 012 modules MAY carry them when authored after 013 defines them (inert on
  pre-013 engines), but they are not a 012 requirement.
