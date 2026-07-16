# Feature Specification: Module batch 2 — dev-environment, release, dependency-hygiene, monorepo, docs, GitLab-parity, and API modules (spec 012)

**Feature Branch**: `012-module-batch-2`

**Created**: 2026-07-14

**Status**: Draft — authored from the ratified 2026-07-14 decision session (same session that
produced spec 011 and spec 013's charter). Extends the 011 module family; does not reopen 011's
decisions, with exactly two sanctioned 011-artifact amendments carved out of that clause:
the FR-009 base dependabot removal and the FR-010a CI moon branch.

**Input**: The ratified maintainer decisions of 2026-07-14 covering the next module batch (eight
new modules), the `bailiff-mod-base` dependabot amendment, and the monolith-vs-split governing
rule, vendored in-tree as `specs/012-module-batch-2/decisions-ledger.md` (same pattern as 011's
`decisions-ledger.md`). These decisions are FIXED inputs; where this spec is silent, the vendored
decision ledger governs; where the ledger is silent, the item is out of scope.

---

## Overview

Spec 011 delivered the de-opinionated core family: a thin base, the language overlays, the
agentic rollup, two CI hosts, three IaC modules, and the quality/tooling belt. Spec 012 is the
**next module batch**: eight new `bailiff-mod-*` templates that fill the remaining gaps a real
project hits immediately after the 011 core — a reproducible dev container, editor defaults,
release automation, dependency-update automation, a monorepo task runner, a docs site, GitLab
repo-creation parity, and an API-first skeleton — plus **two amendments to existing 011
modules**: `bailiff-mod-base` (dependabot.yml moves out of base into the new dep-updates module,
and this MUST land before base's v1.0.0 publish — FR-009) and the CI modules
(`bailiff-mod-ci-github`/`bailiff-mod-ci-gitlab` gain a `monorepo_tool=moon` affected-detection
branch — FR-010a).

Everything in 012 is **still template content, not tool code** — C-11 / Constitution I holds
unchanged for this spec (spec 013, the engine spec, is where C-11 is relaxed; 012 does not
depend on spec 013 in any way — the two specs are fully decoupled).

This spec also **states the ratified monolith-vs-split rule as a governing principle** (FR-001)
so future module proposals are decided by rule, not per-module debate.

This spec covers **authoring/revision only**. Publishing mirrors + releases remains a
maintainer-confirmed batch via the 008b pipeline, never unattended (011 FR-023 applies).

---

## Governing principle — monolith vs split (ratified)

A family of alternatives becomes **ONE module with a choice axis** when the family is
**isomorphic**: same question shape AND same output contract, with only the rendered syntax
differing (e.g. hook managers, dependency-update tools). A family becomes **SEPARATE sibling
modules** when the renders are disjoint or the paradigms differ (CI hosts, IaC paradigms,
monorepo tools, docs engines, repo hosts, release tools). **Meta-modules are REJECTED**
(versioning + fan-out problems; mutual exclusivity is a *sibling constraint* enforced at
selection time, not containment inside a wrapper module).

Applied to this batch: `bailiff-mod-dep-updates` is one module with a `dep_update_tool` axis
(each branch renders a single managed file — isomorphic); cocogitto/release-please,
moon/turbo/nx, and mkdocs/vitepress are per-tool sibling splits (disjoint renders — the
maintainer explicitly ratified the monorepo split: "they are too distinct").

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Get a reproducible containerized dev environment (Priority: P1)

A developer selects `bailiff-mod-devcontainer` and gets a `devcontainer.json` whose toolchain
derives from the same frozen `mise_tools` union that pins the project's local toolchain — the
container and the host install the identical tool set via the mise devcontainer feature.

**Why this priority**: Environment reproducibility is bailiff's headline value extended to the
container boundary; deriving the container from `mise_tools` means zero drift between "works
on my machine" and "works in the container", with no new questions to answer.

**Independent Test**: Init `[base, python, devcontainer]` with `mise_tools={python: "3.13"}`
frozen → `.devcontainer/devcontainer.json` references the mise feature and the frozen tool
set; the file re-renders config-consistently on reproduce.

**Acceptance Scenarios**:

1. **Given** a selection whose frozen `mise_tools` is `{python: "3.13", node: "22"}`, **When**
   init, **Then** `devcontainer.json` (managed) derives its toolchain from that union via the
   mise devcontainer feature — no tool is listed that is absent from `mise_tools`, none missing.
2. **Given** a populated committed tree, **When** reproduce, **Then** the file comes back
   config-consistent with no task executed and no toolchain/network required.

### User Story 2 — Adopt commit-driven release discipline (Priority: P1)

A developer selects `bailiff-mod-cocogitto` and gets a conventional-commit + `cog`-driven release
setup — the same discipline bailiff itself dogfoods (`cog.toml`, changelog separator, version
bumping) — without bailiff performing any release or tag at scaffold time.

**Why this priority**: Release automation is the highest-leverage post-scaffold gap, and
cocogitto-first is dogfooding: bailiff's own monorepo runs on cog, so the module's correctness is
continuously validated by bailiff's own pipeline. release-please follows as a later sibling.

**Independent Test**: Init `[base, cocogitto]` → a managed `cog.toml` sized to the project
(single-package or monorepo shape) plus a conventional-commit hook block contributed to the
frozen `hook_blocks` union; no tag, no release, no network action occurs.

**Acceptance Scenarios**:

1. **Given** `bailiff-mod-cocogitto` selected, **When** init, **Then** `cog.toml` is rendered
   (managed) and `cog` is contributed as a token to the frozen `mise_tools` union — the module
   does NOT write `.mise.toml` itself.
2. **Given** `hook_manager=pre-commit` frozen, **When** init, **Then** cocogitto's
   commit-message-lint block appears in `hook_blocks` and is written by `bailiff-mod-precommit`
   (the single writer), never by this module.
3. **Given** init completes, **When** inspecting the tree and remote, **Then** no tag,
   changelog entry, or release has been created — release actions are the project's to run.

### User Story 3 — Automated dependency hygiene, with a clean base (Priority: P1)

A developer selects `bailiff-mod-dep-updates`, chooses `dep_update_tool` (renovate or
dependabot — defaulting to the tool native to the project's repo host: dependabot when
GitHub-hosted, renovate when GitLab-hosted), and gets the matching single managed config
file. `bailiff-mod-base` no longer ships `dependabot.yml` — dependency-update policy is owned
by exactly one module, chosen deliberately, and base ships one clean v1.0.0.

**Why this priority**: The base amendment is a **publish blocker**: it MUST land before the
011 Phase 7 publish batch so base's v1.0.0 is released without a file another module owns.
The module itself closes the last piece of always-wanted automation.

**Independent Test**: Init `bailiff-mod-base` alone → NO `dependabot.yml` anywhere (even with
`github_host=true`); init `[base, dep-updates]` with `github_host=true` and `dep_update_tool`
left at its default → `.github/dependabot.yml` (managed) and no renovate file; with
`github_host=false` and the default → `renovate.json` and no dependabot file; explicit
overrides render the chosen branch.

**Acceptance Scenarios**:

1. **Given** amended `bailiff-mod-base` with `github_host=true`, **When** init, **Then** the
   minimal `.github/` (issue/PR templates, CODEOWNERS) is rendered WITHOUT `dependabot.yml`.
2. **Given** a GitHub-hosted project (`github_host=true`) with `dep_update_tool` unset,
   **When** init, **Then** the default resolves to `dependabot` and exactly
   `.github/dependabot.yml` is rendered with one update entry per active ecosystem, and no
   renovate config exists.
3. **Given** a GitLab-hosted project (`github_host=false`) with `dep_update_tool` unset,
   **When** init, **Then** the default resolves to `renovate` and exactly one managed config
   file (`renovate.json`) is rendered, sized to the frozen language facts (ecosystems
   matching the selected package managers).
4. **Given** `dep_update_tool=dependabot` explicitly chosen with `github_host=false`, **When**
   init, **Then** the module still renders `.github/dependabot.yml` but emits a rendered
   warning comment in the file and a README note that dependabot only runs on GitHub-hosted
   repos.
5. **Given** the amended base, **When** the 011 Phase 7 publish batch is prepared, **Then**
   the dependabot removal is already merged — base v1.0.0 never ships `dependabot.yml`.

### User Story 4 — Monorepo task orchestration (Priority: P2)

A developer running a monorepo selects `bailiff-mod-moon` and gets a moon workspace
configuration wired to the project's package layout, closing the dangling `monorepo_tool`
answer the CI modules already read (`monorepo-affected` sizing).

**Why this priority**: The 011 CI modules read `monorepo_tool` but nothing yet supplies a real
tool — moon is the first sibling (turbo/nx later, ratified as separate modules). P2 because it
only applies to monorepo-layout projects.

**Independent Test**: Init `[base(layout=monorepo), moon]` → managed `.moon/workspace.yml`
(plus moon's toolchain config) present; `monorepo_tool=moon` is a coherent frozen answer the
CI module can consume for `monorepo-affected`.

**Acceptance Scenarios**:

1. **Given** a monorepo-layout selection including `bailiff-mod-moon`, **When** init, **Then**
   moon's workspace config is rendered (managed) matching base's package-dirs layout, and
   `moon` is contributed to the frozen `mise_tools` union.
2. **Given** `bailiff-mod-ci-github` with `ci_model=monorepo-affected` and `monorepo_tool=moon`
   frozen, **When** init, **Then** the CI workflow's affected-detection uses moon's invocation
   (not a hardcoded turborepo assumption) — delivered by the FR-010a CI-module amendment.
3. **Given** moon selected on a single-package layout, **When** init, **Then** the module
   [NEEDS CLARIFICATION: warn-and-render vs refuse — see FR-010] behaves per the
   ratified answer, never silently rendering a broken workspace file.

### User Story 5 — Documentation site (Priority: P2)

A developer selects `bailiff-mod-mkdocs` and gets an mkdocs-material docs site scaffolded over
base's `docs/` tree — managed `mkdocs.yml`, seed-once starter pages — with vitepress as a
ratified later sibling (per-engine split, not an axis).

**Why this priority**: Docs-site generation is common but not universal; it builds on base's
`docs/` output and is independent of the P1 stories.

**Independent Test**: Init `[base, mkdocs]` → `mkdocs.yml` (managed) referencing base's
`docs/` dir; `docs/index.md` seeded once; `mkdocs-material` pinned via the `mise_tools` /
Python tooling contribution; a subsequent re-run preserves edited pages.

**Acceptance Scenarios**:

1. **Given** `bailiff-mod-mkdocs` selected, **When** init, **Then** `mkdocs.yml` is a managed
   render wired to `docs/`, and starter pages are seed-once (`_skip_if_exists`).
2. **Given** a project whose `docs/index.md` was edited, **When** re-run/reproduce over the
   populated tree, **Then** the edit is preserved and `mkdocs.yml` re-renders config-consistently.
3. **Given** any init, **When** tasks run, **Then** no `mkdocs build`/site deploy occurs — no
   network or publish action at scaffold time.

### User Story 6 — GitLab repo-creation parity (Priority: P2)

A developer on GitLab selects `bailiff-mod-gitlab-repo` and gets the exact
`bailiff-mod-github-repo` semantics ported to `glab`: a trust-gated repo-creation task where
requesting **public visibility without explicit consent is a hard abort** (exit 1), and a
missing `glab` binary is non-fatal (warn-and-continue).

**Why this priority**: Completes host parity begun by `bailiff-mod-ci-gitlab`; the consent gate
is a safety property, so the port must be semantics-faithful, not just command-swapped.

**Independent Test**: Init with `bailiff-mod-gitlab-repo`, visibility public, consent not given
→ init aborts (exit 1) before repo creation; with `glab` absent → init completes with a
warning; with private visibility and `glab` present (stubbed in tests) → creation task runs
trust-gated with the token from ambient env.

**Acceptance Scenarios**:

1. **Given** public visibility requested WITHOUT the explicit consent answer, **When** the
   task runs, **Then** it exits 1 before any `glab repo create` — identical to github-repo.
2. **Given** `glab` missing from PATH, **When** init, **Then** the task warns and exits 0
   (non-fatal), and the rest of the init completes.
3. **Given** any configuration, **When** inspecting `copier.yml`, **Then** no `secret:`
   question exists; the token is read from the ambient environment inside the task.

### User Story 7 — API-first project skeleton (Priority: P3)

A developer building an API selects `bailiff-mod-api` and gets a seed-once OpenAPI skeleton plus
a managed spectral lint config, with spectral wired into the project's hook manager via the
frozen `hook_blocks` union.

**Why this priority**: Valuable but the most specialized of the batch; depends on nothing new.

**Independent Test**: Init `[base, api]` → seed-once `openapi.yaml` skeleton + managed
spectral config (`.spectral.yaml`); the spectral hook block appears in `hook_blocks` and is
written into the hook file by `bailiff-mod-precommit`.

**Acceptance Scenarios**:

1. **Given** `bailiff-mod-api` selected, **When** init, **Then** the OpenAPI skeleton is written
   seed-once and the spectral config is a managed render.
2. **Given** the project edits `openapi.yaml`, **When** re-run/reproduce, **Then** the edited
   spec is preserved (`_skip_if_exists`) and the spectral config re-renders config-consistently.
3. **Given** `hook_manager=none` frozen, **When** init, **Then** the module still renders its
   files and its `hook_blocks` contribution is inert (no hook file written by anyone).

### User Story 8 — Every 012 module is fan-out-ready (Priority: P1)

Each new module passes `just check-modules` (answers-file `.jinja`, README, CHANGELOG with the
`- - -` separator, three-way registration parity) and ships hermetic init + reproduce loop
tests with native/network tasks stubbed, so the 008b pipeline can fan it out.

**Why this priority**: Without this gate nothing in the batch can be released.

**Independent Test**: Run `just check-modules` over the finished `templates/` → `ok`; run each
module's `tests/loop/` tests → green; secrets-policy lint → green.

**Acceptance Scenarios**:

1. **Given** all eight authored modules + the amended base, **When** `just check-modules`,
   **Then** it reports `ok` (registration parity across `templates/`, `cog.toml`,
   `catalog-sources.toml`).
2. **Given** each module, **When** its loop tests run, **Then** init + reproduce pass with
   tasks stubbed offline, managed renders config-asserted, seed-once files
   `_skip_if_exists`-asserted, and no `secret:` question exists.

### User Story 9 — Consistent editor whitespace defaults (Priority: P2)

A developer selects `bailiff-mod-editorconfig` and gets an `.editorconfig` whose language
sections are sized from the project's frozen language facts — indent style per the chosen
linter's convention, max line length from the frozen linter settings — with a universal
defaults section always present.

**Why this priority**: A small quality-of-life micro-module; valuable but independent of the
P1 stories and deliberately NOT part of base (keeps base thin, ratified).

**Independent Test**: Init `[base, editorconfig]` alone → `.editorconfig` (managed) renders
the universal defaults section; with language facts frozen (e.g. `ts_linter=biome`), the
matching language section uses the linter's indent convention and derives `max_line_length`
from `ruff_line_length` where applicable; the file re-renders config-consistently on reproduce.

**Acceptance Scenarios**:

1. **Given** `bailiff-mod-editorconfig` with `ts_linter=biome` frozen as a language fact, **When**
   init, **Then** `.editorconfig` (managed) uses the indent style matching the chosen linter's
   convention; **When** no language facts are frozen, **Then** a sane universal default section
   is still rendered.
2. **Given** Python language facts frozen with a `ruff_line_length` value, **When** init,
   **Then** the Python section's `max_line_length` matches it — line width is derived from the
   linter setting; indentation comes from the linter's convention, never from line width.
3. **Given** a populated committed tree, **When** reproduce, **Then** `.editorconfig` comes
   back config-consistent with no task executed and no toolchain/network required.

### Edge Cases

- **devcontainer with empty `mise_tools`**: the module renders a minimal valid
  `devcontainer.json` (base image + mise feature with nothing to install), never an invalid
  file — a valid no-op layer, consistent with the family's empty-set convention.
- **editorconfig with no language modules selected**: universal defaults only
  (charset/newline/trailing-whitespace); no language-specific sections invented.
- **dep-updates axis flip on an existing project**: renders are disjoint files; the old
  tool's file is not deleted by bailiff (module writes only its own branch's file) — switching
  tools on a live project is a manual cleanup, documented in the module README.
- **dependabot chosen on a non-GitHub host**: `dep_update_tool=dependabot` with
  `github_host=false` still renders `.github/dependabot.yml`, but with a rendered warning
  comment and a README note that dependabot only runs on GitHub — warn-and-render, never a
  refusal. Renovate is the host-neutral branch.
- **cocogitto in a repo with non-conventional history**: `cog.toml` rendering is unaffected;
  bailiff never runs `cog bump`/`cog changelog` at scaffold time, so bad history cannot fail an
  init.
- **gitlab-repo AND github-repo both selected**: both are pure side-effect tasks; nothing
  structurally prevents dual selection today; each task independently honors its own
  consent gate.
- **Reproduce over a committed tree for every module**: all preflights and any native/network
  task are init-only-guarded (011 FR-012a); reproduce needs no toolchain or network.
- **api module in a project with no hook manager**: spectral hook block is contributed but
  inert (`hook_manager=none`), matching the §4 threading contract.

## Requirements *(mandatory)*

### Functional Requirements — governance & cross-cutting

- **FR-001** *(monolith-vs-split rule)*: Module-family shape MUST follow the ratified rule: ONE
  module with a choice axis when the family is isomorphic (same question shape + same output
  contract, only rendered syntax differs); SEPARATE sibling modules when renders are disjoint
  or paradigms differ. Meta-modules are rejected; exclusivity between siblings is a selection
  constraint, not containment. Every module in this spec is shaped by this rule, and future
  module proposals MUST cite it.
- **FR-002** *(011 house patterns inherited)*: Every 012 module MUST satisfy the 011
  cross-cutting contract unchanged: lifecycle classification of every output (managed /
  seed-once / task-output — 011 FR-008); trust-gated `_tasks` with preflight first and
  init-only guards (011 FR-009/FR-012a); no `secret:` questions (011 FR-005); frozen-union
  single-writer discipline for `gitignore_stack`, `mise_tools`, `hook_manager`+`hook_blocks`,
  `quality_languages` — 012 modules contribute tokens to these unions and MUST NOT add a second
  writer (011 critique M1); agent-frozen `--data` facts for anything read across layers (011
  FR-010); consistent snake_case `<tool>_<decision>` axis keys threaded via
  `default: "{{ <key> }}"` (011 FR-002).
- **FR-003** *(no new glue)*: No new `src/bailiff/` code or `scripts/bailiff.py` verb is introduced
  (Constitution I / C-11 — C-11 still holds for 012; the engine relaxation is spec 013's
  scope). All 012 behavior is copier questions, rendered files, `when:`/`when:false` edges, and
  trust-gated tasks.
- **FR-004** *(new axis registration)*: The one new cross-cutting axis introduced here —
  `dep_update_tool` `[renovate, dependabot]` — MUST be added to the 011 data-model axis table
  with its exact key/choices/default. Its default is NOT a static literal: it **follows the
  repo host** — `dependabot` when the project is GitHub-hosted (`github_host=true` / GitHub
  facts), `renovate` when GitLab-hosted — expressed as a computed/threaded default
  (`default: "{{ ... }}"` per the 011 FR-002 threading pattern), explicitly overridable.

### Functional Requirements — dev environment modules

- **FR-005** *(bailiff-mod-devcontainer)*: A NEW `bailiff-mod-devcontainer` module MUST render
  `.devcontainer/devcontainer.json` as a **pure managed render** (zero `_tasks`) whose
  toolchain derives from the frozen `mise_tools` union via the mise devcontainer feature — the
  container installs exactly the pinned tool set the host uses. It MUST render a minimal valid
  file when `mise_tools` is empty. It contributes no unions beyond consuming `mise_tools`;
  it does NOT write `.mise.toml` (base is the single writer). Edge: `run_after:
  [bailiff-mod-base]`. [NEEDS CLARIFICATION: base container image choice — fixed sane default vs
  a `devcontainer_image` question; not ratified.]
- **FR-006** *(bailiff-mod-editorconfig)*: A NEW `bailiff-mod-editorconfig` **micro-module** MUST
  render `.editorconfig` as a managed render — deliberately NOT part of base (keeps base thin,
  ratified). Its language sections are sized from the frozen language facts: indent style and
  size per the chosen linter's convention (e.g. the selected `ts_linter`'s convention for
  TS/JS, the Python linter's convention for Python — indentation NEVER derived from line
  width); `max_line_length` derived from the frozen linter line-length setting (e.g.
  `ruff_line_length` for Python). A universal defaults section is always present. No questions
  of its own beyond what it inherits from frozen facts. The phase-1 agent MUST additionally
  freeze via `--data` the facts editorconfig reads: `ts_linter`, the Python indent convention
  / linter identity, and `ruff_line_length` (see Assumptions). Edge: `run_after:
  [bailiff-mod-base]`.

### Functional Requirements — release automation

- **FR-007** *(bailiff-mod-cocogitto)*: A NEW `bailiff-mod-cocogitto` module MUST render a managed
  `cog.toml` sized to the project shape (single vs monorepo layout), contribute `cog` to the
  frozen `mise_tools` union and a commit-message-lint block to the frozen `hook_blocks` union
  (written by `bailiff-mod-precommit` only). It MUST NOT run `cog bump`, create tags, write
  changelog entries, or perform any release/network action at scaffold time. Cocogitto is
  FIRST (dogfooded — bailiff itself runs on cog); **release-please is a later sibling module**
  (per-tool split under FR-001 — disjoint renders), NOT an axis of this module and NOT built
  in 012. [NEEDS CLARIFICATION: whether the module also seeds a `cog`-driven release CI job
  or leaves CI wiring entirely to the CI modules — not ratified; leaving CI untouched is the
  conservative default.]

### Functional Requirements — dependency hygiene

- **FR-008** *(bailiff-mod-dep-updates)*: A NEW `bailiff-mod-dep-updates` module MUST expose the
  axis `dep_update_tool` `[renovate, dependabot]` (one module — the family is isomorphic: each
  branch renders a single managed config file answering the same question), defaulting per
  FR-004 to the repo host's native tool (dependabot on GitHub, renovate on GitLab). The
  renovate branch renders `renovate.json`; the dependabot branch renders
  `.github/dependabot.yml`; both are **managed** renders sized from the frozen language facts
  (one ecosystem entry per active package manager). Exactly one branch's file is written per
  init; the module never deletes the other tool's file. When `dep_update_tool=dependabot` is
  chosen with `github_host=false`, the module MUST still render the file but MUST emit a
  rendered warning comment in it and a README note that dependabot only runs on GitHub-hosted
  repos (warn-and-render; renovate is the host-neutral branch). Edge: `run_after:
  [bailiff-mod-base]`.
- **FR-009** *(base amendment — dependabot moves out)*: The `github_host` minimal `.github/`
  render MUST NOT include `dependabot.yml` (issue/PR templates and CODEOWNERS remain).
  Ownership moves to `bailiff-mod-dep-updates`. The concrete artifacts to amend are:
  (a) `specs/011-deopinionated-module-family/contracts/bailiff-mod-base.md` — strike
  `dependabot` from the `github_host` question row and from the minimal-`.github/` output
  list; (b) `specs/011-deopinionated-module-family/tasks.md` T004 — strike dependabot from
  the `github_host` render requirement. Both amendments MUST land BEFORE base v1.0.0 ships
  (the 011 build is in flight); if T004 has already been implemented when this lands, patch
  the built `templates/bailiff-mod-base/` template on the 011 branch as well. Base is **born
  clean** — this is NOT a post-hoc 012 patch to a shipped base. This is a **sanctioned
  011-artifact amendment**, explicitly carved out of this spec's "does not reopen 011's
  decisions" clause. **Sequencing (publish blocker)**: this change MUST land before the 011
  Phase 7 publish batch so `bailiff-mod-base` ships one clean v1.0.0 that never contained a
  file another module owns. Version/migration posture: the change rides base's
  already-planned v1.0.0 clean break (011 FR-012) — no separate major bump, no
  `copier update` path, no `_migrations`; base's loop tests (T004) are written/amended to
  assert the file's ABSENCE.

### Functional Requirements — monorepo & docs

- **FR-010** *(bailiff-mod-moon)*: A NEW `bailiff-mod-moon` module MUST render moon's workspace
  configuration (managed) wired to base's monorepo package layout and contribute `moon` to the
  frozen `mise_tools` union. Monorepo tools are **per-tool sibling splits** (ratified: "they
  are too distinct"); turbo and nx are later siblings, NOT axes here. This module closes the
  dangling `monorepo_tool` answer the CI modules already read: a selection including moon
  freezes `monorepo_tool=moon`, and `ci_model=monorepo-affected` sizes its affected-detection
  from it (the CI-side render is FR-010a's scope). Edges: `run_after: [bailiff-mod-base]`;
  consumed by CI via frozen `--data`, not run-order. [NEEDS CLARIFICATION: behavior when
  selected on a single-package layout — warn-and-render vs preflight refusal; not ratified.]
- **FR-010a** *(CI amendment — moon affected-detection branch)*: `bailiff-mod-ci-github` and
  `bailiff-mod-ci-gitlab` MUST each be amended to accept `monorepo_tool=moon` and render a
  moon-specific affected-detection invocation in the `monorepo-affected` model (not a
  hardcoded turborepo assumption), with loop-test coverage for the moon branch in both
  modules. The 011 CI contract
  (`specs/011-deopinionated-module-family/contracts/ci-github-gitlab.md`) MUST be amended to
  add `moon` to `monorepo_tool`'s value list; the plan phase reconciles this spec's
  moon/turbo/nx sibling framing with the contract's existing `turborepo/nx/pnpm-workspace`
  mention. Like FR-009, this is a **sanctioned 011-artifact amendment** carved out of the
  "does not reopen 011's decisions" clause. Version posture: a pre-v1 contract edit if the
  CI modules are unpublished when it lands; otherwise a minor bump of each CI module (new
  accepted value, no breaking change).
- **FR-011** *(bailiff-mod-mkdocs)*: A NEW `bailiff-mod-mkdocs` module MUST scaffold an
  mkdocs-material docs site over base's `docs/` tree: managed `mkdocs.yml`, seed-once starter
  pages (`_skip_if_exists`), tooling pinned via its `mise_tools` contribution (or the Python
  tooling contract where mkdocs is installed as a Python tool —
  [NEEDS CLARIFICATION: pin mkdocs-material via mise vs via the project's Python dev
  dependencies when bailiff-mod-python is co-selected; not ratified]). Docs engines are
  per-engine sibling splits; vitepress is a later sibling, NOT an axis. No build/deploy action
  at scaffold time. Edge: `run_after: [bailiff-mod-base]`.

### Functional Requirements — host parity & API

- **FR-012** *(bailiff-mod-gitlab-repo)*: A NEW `bailiff-mod-gitlab-repo` module MUST port
  `bailiff-mod-github-repo`'s semantics to `glab` exactly: output NONE (pure side-effect); a
  trust-gated `glab repo create` task; **public visibility without explicit consent = hard
  abort (exit 1) before creation**; `glab` missing or creation failure = non-fatal exit 0
  (warn-and-continue); token from the ambient environment (no `secret:` question);
  `reconcile=false`; init-only-guarded. Loop tests MUST cover the consent-abort, the
  tool-missing warn path, and the stubbed creation path — the same test shape as github-repo.
- **FR-013** *(bailiff-mod-api)*: A NEW `bailiff-mod-api` module MUST scaffold an API-first
  skeleton: a **seed-once** OpenAPI document (project-owned after init) plus a **managed**
  spectral configuration, and contribute a spectral lint block to the frozen `hook_blocks`
  union (written by `bailiff-mod-precommit` only; inert when `hook_manager=none`). `spectral` is
  contributed to `mise_tools`. No codegen, no server scaffold — the language modules own
  runtime code. [NEEDS CLARIFICATION: OpenAPI document path/name (`openapi.yaml` at root vs
  under an `api/` dir) and OpenAPI version default (3.1 assumed); not ratified.]

### Functional Requirements — naming, contract, testing, release

- **FR-014** *(justfile name stands)*: `bailiff-mod-justfile` KEEPS its name (maintainer rejected
  a preemptive rename to `bailiff-mod-runner`); a rename is reconsidered only if/when make/task
  ship as a monolith with a runner axis under FR-001. No action in 012 beyond recording this.
- **FR-015** *(contract lint + tests)*: Every 012 module MUST pass `scripts/check_modules.py`
  (`just check-modules`): answers-file `template/{{ _copier_conf.answers_file }}.jinja`,
  README, CHANGELOG containing the `- - -` separator, three-way registration parity
  (`templates/` == `cog.toml [monorepo.packages]` == `catalog-sources.toml`), published-label
  immutability. Every module MUST additionally declare `_subdirectory: template` in its
  `copier.yml` (an authoring requirement — `check-modules` does not verify it). Every module
  MUST ship hermetic init + reproduce loop tests under `tests/loop/` with native/network
  tasks stubbed to offline marker writes (`_copy_module_with_stub_tasks`), config-asserting
  managed renders, presence/structure-asserting task-output, `_skip_if_exists`-asserting
  seed-once. The spec-005 secrets-policy lint MUST stay green.
- **FR-017** *(release batch)*: Publishing the 012 mirrors + releases via the 008b pipeline is
  a maintainer-confirmed batch (mirrors pre-created per the runbook); nothing is fanned out or
  released unattended (011 FR-023 / SC-009 semantics apply unchanged).

### Out-of-module meta-items (flagged, NOT built as modules here)

- **MI-1** *(carried from 011 — version auto-updater)*: unchanged; still its own future spec.
  012 adds more pinned surfaces (mise tokens for cog/moon/spectral, devcontainer feature
  refs), increasing its value but not its scope here.
- **MI-3** *(later siblings)*: `bailiff-mod-release-please`, `bailiff-mod-turbo`, `bailiff-mod-nx`,
  `bailiff-mod-vitepress` are ratified as future sibling modules — named here so the split shape
  is on record, NOT built in 012.

### Key Entities

- **bailiff-mod-\* template**: one module — copier template under `templates/bailiff-mod-<name>/`,
  fanned out by 008b (unchanged from 011).
- **Isomorphic family**: a set of tool alternatives with the same question shape and output
  contract — rendered as ONE module with a choice axis (FR-001); `dep_update_tool` is 012's
  instance.
- **Sibling family**: tool alternatives with disjoint renders/paradigms — separate modules
  whose mutual exclusivity is a selection-time constraint, not containment (moon/turbo/nx,
  mkdocs/vitepress, cocogitto/release-please, github-repo/gitlab-repo).
- **Frozen union contribution**: a token a 012 module adds to an existing agent-frozen union
  (`mise_tools`, `hook_blocks`, `gitignore_stack`) — consumed by the union's single writer,
  never written directly.
- **Base amendment**: the FR-009 removal of `dependabot.yml` from `bailiff-mod-base`, riding the
  v1.0.0 clean break.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A project generated with `[base, python, devcontainer]` has a devcontainer
  whose installed toolchain is exactly the frozen `mise_tools` set (no drift between host
  pins and container); a project generated with `[base, editorconfig]` alone has an
  `.editorconfig` whose sections follow the frozen linter conventions (indent from the
  linter's convention, `max_line_length` from the frozen line-length setting); both files
  reproduce config-consistently.
- **SC-002**: `bailiff-mod-base` v1.0.0 as published contains no `dependabot.yml` under any
  answer combination; `bailiff-mod-dep-updates` renders exactly one dependency-update config per
  init, matching the chosen `dep_update_tool` — whose default follows the repo host
  (dependabot when GitHub-hosted, renovate when GitLab-hosted) — and covering every active
  ecosystem.
- **SC-003**: `bailiff-mod-cocogitto` initializes with zero release side effects (no tag, no
  changelog write, no network call), and its `cog.toml` is config-consistent on reproduce.
- **SC-004**: With `monorepo_tool=moon` frozen, `ci_model=monorepo-affected` renders a CI
  workflow whose affected-detection invokes moon (FR-010 supplier + FR-010a CI-module
  amendment) — the dangling `monorepo_tool` read is closed by a real supplier.
- **SC-005**: `bailiff-mod-gitlab-repo` behaves identically to `bailiff-mod-github-repo` on the
  three safety paths (public-without-consent → exit 1; tool missing → warn + exit 0; private +
  tool present → trust-gated creation), verified by loop tests with the task stubbed.
- **SC-006**: `bailiff-mod-mkdocs` and `bailiff-mod-api` preserve project-edited seed-once files
  (`docs/index.md`, the OpenAPI document) across re-runs while their managed configs re-render
  config-consistently.
- **SC-007**: All eight modules + amended base pass `just check-modules` and their loop tests;
  the secrets-policy lint stays green; reproduce over a committed tree requires no toolchain
  or network for any 012 module.
- **SC-008**: No irreversible public action (mirror creation, release) occurs without explicit
  maintainer confirmation.

## Assumptions

- The ratified 2026-07-14 maintainer decisions listed in this spec's Input are the fixed,
  authoritative record for this batch; where this spec is silent, that record governs; where
  it is silent, the item is out of scope for 012.
- A `decisions-ledger.md` MUST be vendored into `specs/012-module-batch-2/` (the 011
  precedent) as the in-tree copy of that ratified record; vendoring it is a **pre-plan task**
  — the plan phase does not start until the ledger file exists at that path.
- Spec 011's cross-cutting contract (`specs/011-deopinionated-module-family/contracts/_cross-cutting.md`)
  — choice-axis keys, frozen-union single-writer pattern, mise/native-command patterns,
  init-only guards, lint/test shape — is consumed unchanged; 012 adds tokens and one axis, no
  new patterns.
- Constitution v2.3.0 (incl. the ADR-0007 process-deterministic task-output amendment) governs
  unchanged; nothing in 012 touches the constitution. C-11 holds for 012; its relaxation is
  spec 013's scope and 013 owns the roadmap.md + Constitution I amendments.
- Spec 013 is a SEPARATE spec published separately (maintainer decision); 012 and 013 are
  fully DECOUPLED — no 012 module (including moon and mkdocs) depends on 013 for authoring
  or shipping.
- The 008b authoring/fan-out pipeline (`just new-module`, `check_modules.py`, `cog.toml`,
  `catalog-sources.toml`) is the sanctioned way to create, lint, and release every 012 module.
- The 011 Phase 7 publish batch has NOT yet occurred; the FR-009 base amendment can still land
  ahead of it. If publish timing changes, FR-009's sequencing is a hard blocker to re-plan
  around, not to waive.
- The mise devcontainer feature exists and can consume the same tool/version pins as
  `.mise.toml`; the plan phase verifies the exact feature reference and pin syntax.
- Frozen language facts injected by the phase-1 agent (011 FR-010) cover most 012 sizing
  needs, but editorconfig DOES introduce new agent-tier fact reads the phase-1 agent must
  additionally freeze via `--data`: `ts_linter`, the Python indent convention / linter
  identity, and `ruff_line_length` (FR-006). Beyond those, 012 only adds consumers of
  existing fact kinds (plus the `monorepo_tool` value moon now supplies).
