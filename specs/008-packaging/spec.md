# Feature Specification: clerk skill packaging — installable via APM marketplaces (Claude + Codex)

**Feature Branch**: `008-packaging`

**Created**: 2026-07-10

**Status**: Draft

**Input**: Roadmap spec 008 (Release + fan-out + authoring lifecycle) — **scoped
down** to the skill-packaging half. Governed by the constitution (I, II) and
ADR-0006. The template authoring monorepo / fan-out / catalog-generation CI is
**carved out** to a later spec (008b/009-adjacent) because there are no shippable
`clerk-mod-*` templates to fan out until spec 009 — building that machinery now
would be the speculative CI the constitution's C-11/YAGNI discipline rejects.

## Overview

clerk is a skill + a bundled deterministic script (`scripts/clerk.py` + `src/clerk/`)
+ a family of copier templates (spec 010). Today it can only be run from *this*
repo. Spec 008 makes the **clerk skill installable into any macOS/Linux (or WSL) project** — Claude Code,
Codex, or an APM-managed repo — so a user can `apm install` clerk and drive copier
from their own project, exactly as spec 010 intended ("distribute the skill via APM
marketplace; there is no `clerk` package to publish to PyPI").

APM already provides the whole publishing mechanism — this spec **uses** it, it does
not invent one:
- **`apm pack`** builds distributable artifacts from a `marketplace:` block in
  `apm.yml`, emitting **both** a Claude Code marketplace and a **Codex** marketplace
  natively (`marketplace.outputs.claude` → `.claude-plugin/marketplace.json` /
  `marketplace.outputs.codex` → `.agents/plugins/marketplace.json`), with release
  gates (`--check-versions`, `--check-clean`).
- **`apm publish`** uploads the package to a registry; **`apm marketplace`** manages
  the authoring config and consumer discovery.

The core engineering problem this spec solves is **portability**: when the skill is
installed into an arbitrary project, its bundled `scripts/clerk.py` must find (a) its
own `src/clerk/*` modules and (b) its third-party runtime deps (`copier`, `pyyaml`,
`packaging`, `tomli-w`) — with **no PyPI `clerk` package** (forbidden by spec 010)
and **no assumption of a specific package manager** (users differ: uv, pip, pipx,
brew, mise).

## Motivating decisions

1. **Distribute the skill via APM, using APM's own tooling.** Add a `marketplace:`
   block to `apm.yml`; build with `apm pack`; publish with `apm publish`. No
   hand-rolled manifest, no bespoke publish script. (ADR-0006: "distribute the SKILL
   via APM marketplace"; spec 010: "no PyPI `clerk` package.")
2. **Ship BOTH a Claude and a Codex marketplace.** `apm pack --marketplace=claude,codex`
   emits both from one config (`marketplace.outputs.{claude,codex}`). Codex is a
   first-class native target — not a separate hand-built manifest. (Codex requires
   each package to declare `category:`.)
3. **clerk's own code is VENDORED into the package** (self-contained). The package
   bundles `src/clerk/*.py` alongside `scripts/clerk.py` under the skill dir, so
   `import clerk.*` resolves from the installed skill with no PyPI dependency. A
   documented build/sync step copies `src/clerk/*.py` (a **glob**, not an enumerated
   list — so it tracks new modules like 003's `ordering.py` automatically) into the
   package layout at pack time (the shipped tree is derived from `src/`, kept in
   sync, not hand-maintained). **The `scripts/clerk.py` module-resolution shim MUST
   be dual-mode**: when a vendored `clerk/` package sits beside the script (installed
   case), keep the script's own dir on `sys.path` so `import clerk` resolves to that
   package; only fall back to `../src` when running from clerk's own repo. (The
   current shim removes its own dir and adds `../src` unconditionally — verified to
   `ModuleNotFoundError` in an installed tree; this is BLOCKER-1, fixed here.)
4. **Third-party deps are CHECKED, not auto-installed** (per user direction: no
   package manager is assumed). `scripts/clerk.py` runs a light **preflight**: if
   `copier`/`pyyaml`/`packaging`/`tomli-w` is missing **or an installed version
   violates the pin** (esp. `copier>=9.16,<10` — `find_spec` alone would pass an
   incompatible copier and then crash deep in a verb), it prints an
   **environment-aware install suggestion** — detecting `uv`/`pipx`/`pip` on PATH
   (and `brew` **only for `copier`**, since `pyyaml`/`packaging`/`tomli-w` are not
   brew formulae) — then exits cleanly, never a raw `ImportError`/traceback. The
   preflight MUST run **after argparse** so `--help` and `doctor` work even with deps
   missing (move the `yaml`/`clerk` imports out of module top / lazy-import them).
   `clerk doctor` reports absence AND version mismatch. **Platform scope: macOS/Linux
   + WSL on Windows** (no native-Windows PATH/py-launcher handling).
5. **PEP 723 inline metadata stays as opt-in ergonomics.** `scripts/clerk.py` keeps
   a PEP 723 `# /// script` dependency header so users who *do* have `uv` get
   frictionless `uv run scripts/clerk.py` ephemeral provisioning for free — but the
   preflight-and-suggest path (decision 4) is what keeps every other user unbroken.
   No single manager is required.
6. **The SKILL is portable and self-describing.** Its frontmatter auto-triggers on
   semantics (spec 010); its Prerequisites document the dep check + install
   suggestion. It MUST invoke the script by a path **anchored to the skill's own
   install location** (e.g. resolved relative to the skill dir), NOT a bare
   `./scripts/clerk.py` — the agent's CWD is normally the consumer project root, not
   the skill dir, so `./scripts/...` would not resolve (review Finding 4). Portability
   claim is scoped to **macOS/Linux + WSL** (not unqualified "any project").
7. **Carve out the template fan-out / authoring lifecycle.** cocogitto monorepo tags,
   the snapshot-mirror fan-out to `clerk-mod-*` repos, `catalog.json` generation, the
   GitHub App identity, and the `just new-module` / `check-modules` authoring tooling
   are **out of scope** here — they have no real templates to operate on until spec
   009. They land in a dedicated later spec (see "Deferred").

## Adversarial review — findings folded in (2026-07-10)

A pre-implementation adversarial review (verified against the live `apm` 0.24.0 CLI
+ the committed code) returned CHALLENGED. Dispositions:

- **BLOCKER 1 — inverted `sys.path` shim** → decision 3 (dual-mode shim; verified the
  vendored layout is viable *only* with the script's own dir kept on path).
- **BLOCKER 2 — `apm pack` ships stale vendored code** (`--check-clean` diffs only
  manifests, not the vendored copy): `just pack`/`just release` and the CI gate MUST
  run `vendor` → `check-vendor` **before** `apm pack`; prefer **generate-at-pack** so
  a committed vendored tree can never lead source (resolves T007's open choice).
- **Finding 3 — local-path source vs hosting (RESOLVED, user)**: consumers add the
  marketplace as a **git repo** — `apm marketplace add copier-clerk/clerk` (Claude)
  / the Codex equivalent — NOT a bare raw `marketplace.json` URL. The local
  `source: ./packages/clerk` resolves against the fetched repo tree (verified). The
  install-into-scratch-project smoke is **promoted from manual to a required
  network-marked gate** (it is the only proof of SC-001).
- **Finding 4 — CWD-relative invocation** → decision 6 (skill-location-anchored path;
  a task verifies invocation from the consumer project root).
- **Finding 5 — preflight checks presence not version** → decision 4 (version-pin
  check, esp. copier `>=9.16,<10`).
- **Finding 6 — preflight gates `--help`; brew dead-ends** → decision 4 (run
  preflight after argparse; brew suggested only for `copier`).
- **Finding 7 — vendored list hardcodes `ordering.py`** → decision 3 (`just vendor`
  globs `src/clerk/*.py`; the contract stops naming 003's not-yet-merged module).
- **Finding 8 (minor) — "single source of truth" for deps is really two-lists+test**
  → reworded FR-005 to "kept in sync by an equality test," not a false guarantee.
- **Platform scope (RESOLVED, user)**: macOS/Linux + **WSL** on Windows; no native
  Windows. SKILL/README say so; drop the unqualified "any project."
- **Sound as-is**: Claude+Codex dual build, the `category:` gate, and the release
  gates (`--check-versions` exit 3 / `--check-clean` exit 4) all verified. One
  residual to confirm in impl: what Codex `policy.authentication: ON_INSTALL` demands
  of a credential-free skill (likely nothing; a one-line check).

## User Scenarios & Testing

### US1 — Install clerk into a Claude Code project and drive copier (Priority: P1)

A developer adds the clerk marketplace, installs the clerk skill into their own
(non-clerk) Claude Code project, and uses it to scaffold + reproduce a project.

**Why this priority**: this is the feature — clerk usable outside its own repo.

**Independent Test**: from a scratch project, register the built marketplace and
install the clerk package; assert `scripts/clerk.py --help` runs from the installed
location (its `src/clerk` modules resolve), and the SKILL is discoverable/triggerable
in that project.

**Acceptance Scenarios**:
1. **Given** the built Claude marketplace, **When** a user installs the clerk
   package into a fresh project, **Then** the skill + bundled script + vendored
   `src/clerk` land in the install location and `clerk.py` runs.
2. **Given** the installed skill, **When** the required third-party deps are absent,
   **Then** `clerk.py` prints an environment-aware install suggestion and exits
   cleanly (no traceback), rather than crashing on import.

### US2 — Install clerk into a Codex project (Priority: P1)

The same, for Codex — a Codex marketplace is built and installable.

**Independent Test**: `apm pack --marketplace=codex` produces a valid Codex
marketplace manifest at `.agents/plugins/marketplace.json`; `apm marketplace
validate` passes; installing from it lands the clerk skill in a Codex project.

**Acceptance Scenarios**:
1. **Given** the `marketplace:` block with `outputs.codex` enabled and the package's
   `category:` set, **When** `apm pack --marketplace=claude,codex`, **Then** both a
   Claude (`.claude-plugin/marketplace.json`) and a Codex
   (`.agents/plugins/marketplace.json`) artifact are produced and validate.
2. **Given** `outputs.codex` enabled but a package missing `category:`, **When**
   `apm pack`, **Then** it hard-errors ("packages must define 'category'") — the
   clerk package MUST set `category:` to satisfy the Codex target.

### US3 — Build + publish is a documented, gated command (Priority: P2)

A maintainer builds and publishes a new clerk version with release gates catching
version/working-tree drift.

**Independent Test**: `apm pack --check-versions --check-clean --dry-run` exits 0 on
an aligned, clean tree and non-zero (exit 3/4) on version misalignment / stale
marketplace output; the documented release steps (`apm pack` → `apm publish`) are
captured and runnable.

### US4 — Dependency preflight / `clerk doctor` (Priority: P1)

A user runs a preflight that reports exactly which deps are missing and how to
install them for their environment.

**Independent Test**: with all deps present + version-compatible, `clerk doctor`
reports ready (exit 0); with one removed OR an incompatible `copier`, it names the
dep and suggests the install command for the detected manager (uv/pipx/pip; brew only
for copier), exit non-zero — deterministic, no LLM. `clerk doctor`/`--help` work even
with deps missing (preflight runs after argparse).

### Edge Cases

- **No package manager detected**: the suggestion falls back to a generic
  `pip install <deps>` line plus a pointer to install one of uv/pipx, never a crash.
- **Partial deps** (some present, some missing): report only the missing ones.
- **Installed into a project that already has copier** (common): preflight passes
  IFF the version satisfies the pin; an incompatible `copier` (e.g. `>=10`) is
  reported as a mismatch, not silently accepted.
- **Vendored `src/clerk` drift**: `just pack`/`just release` + CI MUST run `vendor` →
  `check-vendor` before `apm pack`; prefer generate-at-pack so a committed vendored
  tree can never lead source. `--check-clean` covers only manifests, NOT the vendored
  copy (verified) — so the vendor step is the guard, not the release gate.
- **PEP 723 header vs preflight list**: two representations (a static header comment
  parsed by uv pre-exec, and the runtime preflight list) kept aligned by an equality
  test — not a single runtime source.
- **Codex vs Claude layout differences**: whatever APM's `pack` emits per target is
  authoritative; clerk does not hand-tune per-target files.
- **Consumer adds a bare raw `marketplace.json` URL** (instead of the git repo): the
  local `./packages/clerk` payload has no repo root to resolve against — documented
  as unsupported; the git-repo add form is the supported path (FR-008a).

## Requirements

### Functional Requirements

- **FR-001**: `apm.yml` MUST gain a `marketplace:` block (via `apm marketplace init`)
  declaring the clerk skill package with **both** `marketplace.outputs.claude` and
  `marketplace.outputs.codex` enabled (verified schema: a nested `outputs:` map, NOT
  `marketplace.claude/codex`). Enabling `codex` REQUIRES every package to declare
  `category:` (`apm pack` hard-errors otherwise) — the clerk package MUST set one
  (e.g. `category: Productivity`). `license:` MUST be present (else SBOM
  NOASSERTION). The clerk package uses a local-path `source: ./packages/clerk` (it
  ships itself, not a remote tag).
- **FR-002**: `apm pack --marketplace=claude,codex` MUST build both marketplace
  artifacts (`.claude-plugin/marketplace.json` + `.agents/plugins/marketplace.json`);
  the outputs MUST pass `apm marketplace validate`. The build MUST be reproducible
  from the committed `apm.yml` + lockfile.
- **FR-003**: The clerk package MUST bundle the SKILL, `scripts/clerk.py`, and a
  **vendored copy of `src/clerk/*.py`** (copied by a **glob**, not an enumerated list)
  so that `import clerk.*` resolves from the installed skill location with **no PyPI
  `clerk` dependency**. `scripts/clerk.py`'s module-resolution shim MUST be
  **dual-mode**: keep the script's own dir on `sys.path` when a vendored `clerk/`
  package sits beside it (installed), fall back to `../src` only from-repo. A
  documented build/sync step MUST produce the vendored layout from `src/clerk/`.
- **FR-004**: `scripts/clerk.py` MUST run a **preflight** (also via `clerk doctor`)
  that checks its third-party deps are present **and version-compatible** (esp.
  `copier>=9.16,<10` — presence alone is insufficient). A missing/incompatible dep
  MUST produce a clear **environment-aware install suggestion** (detect `uv`/`pipx`/
  `pip`; suggest `brew` **only for `copier`**) and a clean non-zero exit — never a
  bare `ImportError`/traceback, never auto-install. The preflight MUST run **after
  argparse** so `--help`/`doctor` succeed even with deps missing. Scope: macOS/Linux
  + WSL.
- **FR-005**: `scripts/clerk.py` MUST carry a PEP 723 inline-dependency header
  listing the same deps, so `uv run scripts/clerk.py` works with zero setup for uv
  users. The header (a static comment) and the preflight's list MUST be **kept in
  sync by an equality test** (not a single runtime source — the header is parsed
  before execution).
- **FR-006**: The SKILL MUST be portable: frontmatter auto-triggers by semantics
  (not repo path); it MUST invoke the script by a path **anchored to the skill's
  install location**, not `./scripts/clerk.py` (the agent's CWD is the consumer
  project root, not the skill dir). It MUST NOT assume it runs from clerk's own repo.
- **FR-008a**: The documented consumer install path MUST be the **git-repo
  marketplace form** (`apm marketplace add copier-clerk/clerk` for Claude / the Codex
  equivalent), NOT a bare raw `marketplace.json` URL — the local `source:
  ./packages/clerk` resolves against the fetched repo tree. An **install-into-a-
  scratch-project smoke MUST be a required (network-marked) gate**, since it is the
  only end-to-end proof of SC-001.
- **FR-007**: The release path MUST be a documented, **gated** command sequence:
  `apm pack --check-versions --check-clean` (release gates) → `apm publish`. The gate
  behavior (exit 3 version misalignment, exit 4 working-tree drift) MUST be captured.
- **FR-008**: This spec MUST NOT build the template fan-out, cocogitto monorepo
  release, `catalog.json` generation, GitHub App identity, or the `new-module` /
  `check-modules` authoring tooling — those are deferred (no `clerk-mod-*` templates
  exist to fan out until spec 009).

### Key Entities

- **clerk package**: the APM package — `apm.yml` (name/version/description/tags/
  `target: all`/`includes: auto`/`type: hybrid`) + `.apm/skills/clerk/SKILL.md` +
  bundled `scripts/clerk.py` + vendored `src/clerk/` + `.claude-plugin/plugin.json`.
- **marketplace block**: the `apm.yml` `marketplace:` config with `claude` + `codex`
  outputs and a versioning strategy.
- **preflight / doctor**: the deterministic dep-check + environment-aware
  install-suggestion surface.
- **vendored core**: the shipped copy of `src/clerk/*.py`, generated from source at
  pack time, drift-checked.

## Success Criteria

- **SC-001**: The clerk skill installs into a fresh Claude Code project from the
  built marketplace, and `scripts/clerk.py --help` runs there (its modules resolve).
- **SC-002**: `apm pack --marketplace=claude,codex` produces a Claude AND a Codex marketplace,
  both passing `apm marketplace validate`.
- **SC-003**: With a required dep missing, invocation prints an environment-aware
  install suggestion and exits cleanly (no traceback); `clerk doctor` reports the
  same, deterministically.
- **SC-004**: The release sequence is documented and gated — `apm pack
  --check-versions --check-clean` catches version/working-tree drift (exit 3/4).
- **SC-005**: No PyPI `clerk` package is introduced, and no package manager is
  assumed; the vendored core keeps clerk self-contained with a drift check.
- **SC-006**: No fan-out / authoring-lifecycle CI is added (deferred cleanly).

## Deferred (carved out of the roadmap's original 008)

To a dedicated later spec (paired with / after spec 009, when real `clerk-mod-*`
templates exist):
- cocogitto monorepo release (`<name>-vX.Y.Z` tags, `generate_mono_repository_global_tag=false`).
- snapshot-mirror fan-out to `copier-clerk/clerk-mod-*` read-only repos + prefix-strip tagging.
- `catalog.json` generation + GitHub Pages hosting (the catalog *producer*; spec 002
  built the *consumer*).
- the org-owned "clerk-fanout" GitHub App identity (`contents:write` +
  `administration:write`, auto-create missing repos).
- `just new-module` meta-template scaffolder + `just check-modules` contract lint.

All of this is fully specified in ADR-0006 *Authoring lifecycle* and remains binding
for that later spec; it is only sequenced after the modules it operates on exist.

## Open Questions

- **Q-008a — Vendoring mechanism**: copy `src/clerk/*.py` into the package skill dir
  at pack time via (a) a small `just`/script sync step run before `apm pack`, vs (b)
  a single-file amalgamation of `src/clerk` + `clerk.py`. Lean: **(a) vendored
  modules** (keeps the readable multi-module layout; drift-checked) over a generated
  single file. Resolve at planning; either keeps zero PyPI dep.
- **Q-008b — Registry vs marketplace-only for v1**: publish to an APM registry
  (`apm publish`, experimental `registries` feature) now, or ship marketplace
  artifacts only (`apm pack`) and defer registry upload? Lean: **marketplace
  artifacts first** (self-hostable, no experimental flag), registry when the
  `registries` feature is stable. Resolve at planning.
- **Q-008c — Where the built marketplace manifests live**: committed in-repo (served
  via a stable raw URL / GitHub Pages) vs a release asset. Lean: committed +
  stable-URL (mirrors ADR-0006's catalog-hosting choice). Resolve at planning.

## Governing constitution & ADRs

- Constitution I (skills + templates + minimal glue — the durable artifact is the
  skill, distributed, not a published app), II (the preflight/doctor is deterministic
  and LLM-free).
- ADR-0006 (distribution = skill via APM marketplace; templates via their own repos;
  the fan-out/authoring lifecycle it details is deferred here, not discarded),
  ADR-0002 (catalog = consumer of sources; the *producer* catalog.json is deferred),
  spec 010 (no PyPI `clerk`; bundled `scripts/clerk.py` is the surface).
- Constraints: C-01 (no published application — a distributed skill is not that),
  C-09 (release/fan-out — partially deferred), C-11 (no speculative machinery — the
  reason the fan-out is carved out).
