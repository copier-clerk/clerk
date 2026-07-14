# Feature Specification: project-setup module port → clerk-mod-* templates (spec 009)

**Feature Branch**: `009-project-setup-port`

**Created**: 2026-07-13

**Status**: Clarified (2026-07-13 session — 7 questions resolved OQ-009-a…g; v1 scope =
collapsed `clerk-mod-base` + `clerk-mod-python`, agentic category excluded). **Amended
2026-07-14** (Session 2026-07-14, Q8–Q9): the port is re-scoped from a *faithful
translation* to a *de-opinionated generalization* — every module offers sane, finite
tooling/config choices instead of baking one opinion, and `clerk-mod-ci` gains multiple
agent-selectable CI models. This deliberately relaxes FR-011 (see the amended FR-011 +
new FR-014/FR-015). Ready for `/speckit.plan` (Phases 1–3 + built-module revision).

**Input**: Roadmap spec 009 (project-setup module port → templates), governed by the
constitution v2.1.0 (Principles I, III, V, VI in particular) and ADR-0002/0003/0006.
Depends on specs 002 (catalog), 003 (multi-template ordering), 006 (upgrade/migrations),
008 (packaging). Delivers the first real `clerk-mod-*` modules, which **unblocks** the
already-specced 008b fan-out/authoring pipeline (008b Phases 5–7 are hard-blocked until
009 lands ≥1 module).

---

## Overview

Spec 009 re-homes the mature, battle-tested **project-setup** capability
(`~/.claude/skills/project-setup/`, ~25 modules) as a family of **copier templates**
(`clerk-mod-*`) driven by clerk's existing discover/init/reproduce/ordering machinery
(specs 001/002/003/006/010). project-setup today is a bespoke Python **runner** with its
own manifest format (`module.toml`), its own DAG/ordering engine, its own two-phase
model, its own gate/consent system, and its own catalog. clerk already owns
faithful equivalents of every one of those mechanisms (copier + the spec-003 DAG + the
trust gate + the spec-002 catalog). **The port is therefore a translation, not a
rewrite**: each project-setup module becomes a copier template whose `copier.yml`
questions replace `[[inputs]]`, whose `when:false` edges replace `[order]`, whose
rendered files replace `python` steps, and whose trust-gated `_tasks` replace
code-executing steps — with NO new clerk tool code (Constitution I / C-11).

This spec is intentionally product-shaped and open-ended, modelled on spec 007. Its
job is to **frame the decisions clearly** and flag the significant open questions for
the orchestrator + user to resolve before a plan is scoped. This is a **large** port
(~25 modules, several with agent-steered decisions and consent gates that do not map
1:1 onto copier), so the sections below are a first-draft framing of a plausible
phased delivery, not final commitments. The Open Questions section is the substantive
product of this draft.

---

## Clarifications

### Session 2026-07-14 (amendment — de-opinionation + multi-model CI)

- Q8: Faithful translation vs de-opinionated generalization? → A: **De-opinionate.**
  The maintainer directs that ported modules be **generic and offer the user sane,
  finite choices** rather than bake in a single opinion — e.g. a JS package-manager
  choice (`bun`/`pnpm`/`yarn`), a Python package-manager choice (`uv`/`poetry`/`pdm`),
  linter/formatter/test-runner/hook-manager choices, etc. Genuinely dead or legacy
  options MAY be dropped rather than offered (dropping bare `pip` as a Python PM is
  explicitly acceptable — "generic up to a point"). This **relaxes FR-011**: adding a
  finite choice dimension a module's project-setup ancestor lacked is now sanctioned
  (see amended FR-011 + new FR-014). Choices MUST stay static/finite (Q7), keep a sane
  modern default, and honour every other clerk constraint (no `secret:` questions;
  language manifests seed-once; code-executing steps trust-gated; deterministic
  renders). Applies to the **already-built** modules too (`clerk-mod-base`,
  `clerk-mod-python`, `clerk-mod-apm` are revised, not left as-is).
- Q9: CI module scope — one sized workflow vs multiple optimization models? → A:
  **Multiple agent-selectable CI models.** `clerk-mod-ci` MUST offer a finite,
  named set of CI **models/topologies** (e.g. serial single-job; parallel jobs +
  fan-in gate; version/OS matrix; change-based filtering + caching + concurrency;
  monorepo-affected; merge-queue) plus standard presets. The **phase-1 agent selects
  the model** from project complexity/needs (single vs monorepo, language count, PR
  volume, deploy target) and freezes it as a `--data` answer; the template renders
  the chosen model deterministically (agent never in the reproduce path). See new
  FR-015. The proposed CI-models design is itself grilled before authoring.
- Process note (both Q8 & Q9): **every module is adversarially grilled individually
  before authoring** (built modules included) to strip unwanted opinionation; the CI
  model design is grilled as its own artifact. This is a quality gate, not a spec
  requirement, but is recorded here as the sanctioned working method for this amendment.

### Session 2026-07-13

- Q: Base split — one `clerk-mod-base` vs several separate repos (OQ-009-a) → A:
  **One collapsed `clerk-mod-base`.** The 6 base modules (core-identity,
  dirs-scaffold, gitignore-generate, license-write, agents-md, git-init) ship as ONE
  copier template. Inter-base ordering becomes template-internal (identity → files →
  license → agents-md → git commit last); one repo / tag line / catalog entry /
  answers file. Faithful to project-setup's always-on, non-deselectable base; drops
  5 fan-out targets for zero lost capability. Resolves roadmap Q2.
- Q: Phasing / scope of v1 (OQ-009-b) → A: **Phase 0 = `clerk-mod-base` +
  `clerk-mod-python`** is v1 (the first merged slice) — the minimal real module set
  that unblocks 008b's fan-out/release/e2e, and de-risks the translation by proving
  the full loop (base identity, `run_after` edges, answer threading, a trust-gated
  task, contract lint) on the smallest surface. Phases 1–3 follow as fast-follow
  slices, NOT part of v1.
- Q: Reproduce determinism for `agent`-tier modules + file lifecycle (OQ-009-c) → A:
  Two decisions. **(1)** `agent`-tier decisions freeze **structured facts** (stack,
  env-keys, stack pins, resolved-architecture choice) as `--data` answers, and the
  template renders deterministically from them — NOT whole prose blobs (matches
  project-setup's "draft from frozen scaffold facts"; honours Constitution VIII).
  **(2) Every module classifies its outputs into two lifecycles:** **managed** files
  (clerk owns; re-rendered byte-identically at reproduce) vs **seed-once / living**
  files (scaffolded at init, then OWNED and evolved by the project — clerk must not
  clobber them). Seed-once files include **`AGENTS.md`** (updated during
  development/deployment) and **language manifests** (`pyproject.toml`, `go.mod`,
  `Cargo.toml`, `package.json` — the project adds/bumps deps). Seed-once is
  implemented with copier's native **`_skip_if_exists`** (no new tool code — C-11).
  This is compatible with Constitution III: on a fresh-checkout reproduce the file
  does not yet exist so it still renders identically; `_skip_if_exists` only protects
  an already-populated tree. The per-file behaviour under `clerk update` (never-merge
  vs copier 3-way merge) is deferred to the plan (per-module classification).
- Q: Which project-setup `agentic` modules does 009 port? (OQ-009-d, 007 boundary) →
  A: **None.** 009 excludes the entire `agentic` category (`apm-install`, `mcp-config`,
  `speckit-bridge`, `codex-config`). 007's family owns all agentic wiring: `apm-install`
  = 007's `clerk-mod-apm` (v1); `mcp-config`/`speckit-bridge` = future 007-family
  modules (per 007 Q1). `codex-config` (a Codex-only `.codex/config.toml` client
  config, the one non-overlapping module) is deferred to a future module if demand
  appears — not worth porting one orphan agentic module into 009 and muddying the
  "007 owns agentic" boundary. This tightens the spec's original lean (which was
  port-`codex-config`).
- Q: How do project-setup gates map onto clerk? (OQ-009-e) → A: **Consequential
  choices become safe-defaulting copier boolean questions** (e.g.
  `create_public_repo: false`, `write_architecture: false`) whose persisted answers
  gate the corresponding render/task; **all code execution stays behind the single
  source-trust gate**. project-setup's per-action `allow_flag`/`hardness` granularity
  is NOT re-implemented — that would be new tool code (C-11 violation). The gate
  *intent* (never do consequential things silently) is preserved; the mechanism moves
  from CLI flags to copier answers + source trust.
- Q: `[tools]` prerequisites with no copier equivalent (OQ-009-f) → A: **A preflight
  `_task`** that checks a module's required tools (`uv`/`gh`/`go`/…) and fails with
  explicit install guidance, so the user/agent is steered toward installing the tool
  rather than hitting a cryptic mid-action failure. Nuance (baked in for the plan):
  copier runs ALL `_tasks` post-render (no true pre-render hook), so the preflight is
  not literally before render — but ordered FIRST among the tasks it fails before any
  consequential action task runs. Pair with a documented README prerequisite. This
  tightens the spec's original lean (task's-own-failure-only).
- Q: Multichoice options — fixed `choices:` vs runtime injection (OQ-009-g) → A:
  **Fixed `choices:` for all finite well-known sets** (SPDX licenses, language
  versions, etc.), **EXCEPT `.gitignore`**, which is NOT a choice list at all: it is
  **generated by the `gitnr` tool from the project baseline** (the stack/language
  answers). `gitnr` is a code-executing tool → a **trust-gated `_task` with its version
  pinned** (Constitution V); the emitted `.gitignore` is task-generated output
  (process-deterministic, like the LICENSE fetch), not a byte-rendered file. No runtime
  `--data` injection is needed for 009 (the only genuinely dynamic lists were the
  agentic category, excluded by Q4).

At the highest level, 009 must:

1. **Inventory** the project-setup module set and decide, per module, how it becomes a
   copier template (rendered files, questions, edges, tasks).
2. **Decide the base split** — one collapsed `clerk-mod-base` versus several separate
   `clerk-mod-*` repos for the 6 base modules (the roadmap flags both; HIGH-priority
   open question).
3. **Re-express ordering** as `when:false` `depends_on`/`run_after`/`run_before` edges
   so the spec-003 engine sequences the layers (e.g. precommit/ci after base; git
   commit last).
4. **Honour the template-author contract** (Constitution VI) on every shipped module:
   answers-file `.jinja`, clean PEP 440 tags, `when:false` edges, new `_migrations`
   format, and — critically — **NO `secret:` questions** (Constitution VI secrets rule).
5. **Map the tier model faithfully**: project-setup `python` steps → copier render;
   `agent` steps → phase-1 judgment frozen into a `--data` answer; `gate`/consent →
   clerk's trust gate + copier `when:` conditionals; code-executing steps →
   trust-gated `_tasks`.
6. **Phase delivery** — ship the slice that unblocks 008b first (base + one language),
   not all ~25 modules at once.
7. **Test** every module with an init+reproduce integration test and pass
   `scripts/check_modules.py`.

---

## Motivating decisions

These frame a plausible v1. Read them as leaning-toward, not committed; the Open
Questions flag what is genuinely unresolved.

### D-009-1 — Template content, not tool code (Constitution I, C-11)

The entire port is delivered as copier template content authored in the clerk monorepo
under `templates/clerk-mod-*/`, scaffolded via `just new-module` and linted by
`just check-modules` (the 008b authoring tooling). NO new `src/clerk/` module and NO new
`scripts/clerk.py` verb is introduced. The existing `init_many`/`reproduce_many` engine
(spec 003) and the trust gate drive these templates identically to any other layer. Any
deviation must be justified against C-11 (new deterministic code only for a capability
copier lacks) — and this port surfaces no such gap: questions, rendered files,
conditional sections, ordering edges, and trust-gated tasks are all native copier
features.

### D-009-2 — The port is a mechanical translation of an existing manifest

project-setup already encodes, per module, exactly the metadata clerk needs. The port is
a field-by-field translation:

| project-setup `module.toml`            | clerk `copier.yml`                                          |
|----------------------------------------|-------------------------------------------------------------|
| `[[inputs]]` (string/bool/choice/multichoice) | copier questions (`type: str/bool`, `choices:`, `multiselect`) |
| `[order]` `requires`/`after`/`before`  | `when:false` `depends_on`/`run_after`/`run_before` (ADR-0003) |
| `[tools]` required                     | task preflight / documented prerequisite (copier has no `[tools]`; see OQ-009-f) |
| `python` step (deterministic write)    | rendered template file(s) under the template subtree        |
| `agent` step (+ `steering/` doc)       | phase-1 agent judgment, frozen as a `--data` answer (Constitution II) |
| `gate` (`hardness`, `allow_flag`)      | clerk trust gate + copier `when:` conditional (see OQ-009-e) |
| code-executing step (install/network)  | trust-gated copier `_task` (Constitution V)                 |
| `default_enabled = true` (base set)    | base modules — always selected (the base-split question, OQ-009-a) |

The value of the translation lens: it bounds the port (no new capability is invented;
Scope-out below forbids it) and it makes each module's target shape mechanically
derivable from its source manifest.

### D-009-3 — Agent-steered decisions become phase-1 answers, never runtime code

Several project-setup modules carry `agent` (Tier-2) steps — the agent reads a
`steering/` doc and records a decision (e.g. `agents-md` resolves architecture;
`env-example` maps a stack to env keys; `readme-draft` drafts a README; `stack-adr`
freezes stack pins). In clerk's two-phase model (Constitution II) these are **phase-1
judgment**: the skill makes the decision and freezes it as a `--data` answer that the
template renders deterministically. The agent is NEVER in the reproduce path — reproduce
replays the frozen answer. **Resolved (Q3/OQ-009-c):** what freezes is the
**structured facts** the decision produces (stack, env-keys, stack pins,
resolved-architecture choice), NOT a whole prose blob; the template renders the
document deterministically from those facts (matches how project-setup drafts "from
frozen scaffold facts" and keeps answers files sane — Constitution VIII).

### D-009-4 — Code-executing / network steps become trust-gated `_tasks`

Modules that run code on the target project (`apm-install` runs `apm install`;
`github-repo` calls `gh repo create`; `git-init` runs `git init`; `speckit-bridge`
installs speckit; `license-write` may fetch from the GitHub Licenses API) map to copier
`_tasks`, gated by clerk's trust mechanism exactly as `clerk-template-example`'s
`git init` + `gh api` LICENSE task is today. The user consents at trust-record time;
reproduce replays the task under the same gate (`_tasks` run at both init and reproduce
— Constitution III). Network-touching tasks are process-deterministic, not
byte-identical (Constitution III) — pin versions in the task command where possible.
**Consent granularity (Q5/OQ-009-e):** project-setup's per-action gates
(`allow-public-repo`, `allow-arch-write`, `allow-install`, `hardness`) do NOT become a
new per-action consent layer. Instead, a consequential *choice* becomes a
safe-defaulting copier boolean question (`create_public_repo: false`,
`write_architecture: false`, …) whose persisted answer gates the render/task, and code
*execution* stays behind the single source-trust gate. No new tool code (C-11).

### D-009-5 — This family is many layers in a multi-template project

Each ported module (or the collapsed base) declares its `depends_on` edges so the
spec-003 engine sequences the whole graph. The natural edges observed in project-setup's
`[order]`:

- base identity (`core-identity`) is the upstream root every layer references;
- language overlays (`lang-*`), `precommit-setup`, `ci-github-actions`,
  `env-example`, `readme-draft`, `stack-adr` all `run_after` base;
- `git-init`'s commit step declares soft `after` edges over **every** other module (it
  must commit last) — in clerk this is a `run_after`-all / `run_before: []`-tail edge;
- `license-write` `requires` `core-identity`.

The agent presents the family as catalog entries; ordering is computed by the engine,
not by this spec (ADR-0003).

### D-009-6 — Relationship to spec 007 (independent; possible apm overlap)

Per 007's clarify, `clerk-mod-apm` (spec 007) is shipped **independently**; it is NOT a
prerequisite of 009 and 009 MUST NOT depend on it. However, project-setup's `apm-install`,
`mcp-config`, `speckit-bridge`, and `codex-config` modules (its `agentic` category)
**overlap in intent** with 007's agentic-ecosystem module. 009 MUST NOT duplicate or
re-implement 007's `clerk-mod-apm`. **Resolved (Q4/OQ-009-d): 009 excludes the ENTIRE
`agentic` category** (`apm-install`, `mcp-config`, `speckit-bridge`, `codex-config`).
007's family owns all agentic wiring — `apm-install` is 007's `clerk-mod-apm` (v1);
`mcp-config`/`speckit-bridge` are future 007-family modules; `codex-config` (Codex-only
`.codex/config.toml`) is deferred to a future module if wanted, not ported here. 009
ports base + languages + quality + tooling + docs + integration + monorepo.

### D-009-7 — Two file lifecycles: managed (re-rendered) vs seed-once (living) (Q3/OQ-009-c)

Not every file a module writes should be owned by clerk forever. Each module MUST
classify its outputs into two lifecycles:

- **Managed** — clerk owns the file; reproduce re-renders it byte-identically from the
  committed answers (Constitution III). The default for pure scaffold/config.
- **Seed-once / living** — clerk scaffolds the file at init, then the **project owns and
  evolves it**; clerk MUST NOT clobber it on a re-run. These are files that legitimately
  drift from the template after creation:
  - **`AGENTS.md`** — seeded once, then updated during development/deployment.
  - **Language manifests** — `pyproject.toml`, `go.mod`, `Cargo.toml`, `package.json` —
    seeded with initial deps, then the project adds/bumps dependencies. Re-rendering
    would revert real work.

Seed-once is implemented with copier's native **`_skip_if_exists`** (a `copier.yml` list
of destination paths never overwritten once present) — no new clerk tool code (C-11).
This does NOT weaken Constitution III: on a true reproduce onto a fresh checkout the file
does not exist yet, so it still renders identically; `_skip_if_exists` only protects an
already-populated working tree (the re-run / `update` case). The exact per-file behaviour
under `clerk update` (never re-touch vs copier's 3-way merge) is a plan-level, per-module
classification.

---

## What is NOT in scope

- **New behavioural capabilities not present in project-setup** (roadmap Scope-out). No
  module gains a new file, side-effecting task, or integration its ancestor lacks.
  **NOT excluded (amended Q8/FR-011/FR-014):** de-opinionating a hardcoded decision into a
  finite tooling/config `choices:` question (e.g. package manager, linter, test runner),
  and `clerk-mod-ci`'s multiple agent-selectable CI models (Q9/FR-015) — these are
  sanctioned generalizations, not new capability.
- **The fan-out / release pipeline** (spec 008b) — 009 authors module *content* into
  `templates/clerk-mod-*/`; 008b's CI fans them out. 009 unblocks 008b by existing; it
  does not build the pipeline.
- **The catalog subsystem, ordering engine, upgrade/migrations engine, delivery shape**
  (specs 002/003/006/010) — consumed, not rebuilt.
- **spec 007's `clerk-mod-apm` and the whole `agentic` category** — independent; 009
  ports NONE of `apm-install`/`mcp-config`/`speckit-bridge`/`codex-config` (Q4/OQ-009-d);
  007's family owns that space.
- **Porting project-setup's runner, SDK, or manifest format** — those are the mechanisms
  clerk replaces with copier + the spec-003 DAG. The runner does not ship; only the
  modules' behaviour is re-expressed as templates.
- **project-setup's home-config catalog / `sources.toml` / `answers.toml` machinery** —
  clerk's spec-002 catalog + copier answers files supersede these.
- **Brownfield adoption** (the deferred spec).

---

## User Scenarios & Testing

### US1 — Scaffold a project from the base module(s) (Priority: P1)

A developer selects the collapsed clerk base (`clerk-mod-base`, Q1) with a
`project_name`, `org`, and `license`; clerk applies it; the generated project contains
the directory scaffold, `.gitignore`, `LICENSE`, `AGENTS.md`, and a committed
`.copier-answers.yml`. `git init` runs as a trust-gated task.

**Acceptance Scenarios**:
1. **Given** a base selection with `project_name=demo`, `org=acme`, `license=MIT`,
   **When** `init`, **Then** the generated project contains the scaffold + a
   `.copier-answers.yml` recording the source and pinned commit, and reproduces with
   copier alone (no agent, no clerk).
2. **Given** the same selection with the source UNTRUSTED, **When** `init`, **Then**
   clerk refuses at exit 3 (naming the `trust add` command) before running the
   `git init`/LICENSE tasks.

### US2 — Add a language overlay on top of base (Priority: P1)

A developer selects `[clerk-mod-base, clerk-mod-python]`; the spec-003 engine applies
base first (edge-ordered), threads `project_name` into the language layer, and the
generated project gains `pyproject.toml`, Python `.gitignore` entries, and ruff
pre-commit hooks — the exact output project-setup's `lang-python` produces.

**Acceptance Scenarios**:
1. **Given** `[base, lang-python]` with `python_version=3.13`, framework unset, **When**
   `init`, **Then** base renders first, the Python overlay renders after it, and
   `project_name` is threaded from base into the overlay (ADR-0003 `default:` +
   `data=`).
2. **Given** the language overlay alone (no base), **When** `init`, **Then** it renders
   standalone with defaults for every threaded question (self-contained — cf. 007 SC-006).

### US3 — Reproduce a ported project faithfully (Priority: P1)

A developer reproduces a base + language project on a fresh machine; every rendered file
is byte-identical (same recorded answers + pinned commit), and trust-gated tasks re-run.

**Acceptance Scenarios**:
1. **Given** a generated `[base, lang-python]` project, **When** `reproduce`, **Then**
   all rendered files are byte-identical and the reproduce order is recomputed from the
   committed answers + pinned fetches (Constitution III), not a frozen recipe.
2. **Given** the project's tasks (git init, LICENSE fetch), **When** `reproduce`,
   **Then** they re-run under trust (reproduce is not agent-free for task side-effects).

### US4 — An agent-steered decision replays deterministically (Priority: P2)

A developer scaffolds a project whose README/STACK/env are agent-drafted (the
`readme-draft`/`stack-adr`/`env-example` equivalents). The agent's decision is frozen as
**structured facts** in `--data` answers at init; reproduce replays the frozen facts and
re-renders the file deterministically with no agent involvement (Q3).

**Acceptance Scenarios**:
1. **Given** agent-resolved structured facts (stack, env-keys, pins) frozen as answers,
   **When** `reproduce`, **Then** the derived file (README/STACK/env) re-renders from
   those frozen facts byte-identically, with no agent call.
2. **Given** a project whose `AGENTS.md` and language manifest were edited after init
   (seed-once/living files), **When** `reproduce` (or a re-run), **Then** those files
   are NOT clobbered — `_skip_if_exists` preserves the project-owned edits (Q3/D-009-7).

### US5 — Every ported module passes the contract lint (Priority: P1)

Each module authored under `templates/clerk-mod-*/` passes `just check-modules`
(answers-file `.jinja`, README, CHANGELOG, registration parity, label immutability) so
008b can fan it out.

**Acceptance Scenarios**:
1. **Given** a newly ported module, **When** `just check-modules`, **Then** it reports
   `ok` (the module is contract-complete and 008b-fannable).

### Edge Cases

- **Base split changes edge identity**: if the 6 base modules collapse into one
  `clerk-mod-base`, the fine-grained `requires`/`after` edges between them disappear
  (they become one template's internal ordering). If they stay separate, all their edges
  must be re-expressed as `when:false` edges — and the spec-003 tie-break is by
  **basename** (spec 003 completion note), so base module basenames must be collision-free.
- **`agent` step with no clean phase-1 answer**: a steering doc that produces
  free-form prose (e.g. a full README body) must be freezable as a single `--data`
  answer. If a decision cannot be reduced to a plain-text answer, it violates
  Constitution VIII's documented-handoff rule — flag such modules (OQ-009-c).
- **`[tools]` requirement with no copier equivalent**: copier has no `[tools]` block. A
  module requiring `uv`/`gh`/`go` ships a **preflight `_task`** (ordered first among its
  tasks) that checks for the tool and fails with explicit install guidance before any
  consequential action task runs, plus a documented README prerequisite (Q6/OQ-009-f).
  Note: copier runs all `_tasks` post-render, so the preflight is task-ordered-first,
  not literally pre-render.
- **Multichoice / list options** (Q7/OQ-009-g): finite well-known sets (SPDX licenses,
  language versions) use fixed copier `choices:`. **`.gitignore` is the exception** — it
  is NOT a choice list; it is generated by the **`gitnr`** tool from the project baseline
  (stack/language answers) via a **version-pinned trust-gated `_task`**, and the emitted
  file is task-generated output (process-deterministic, like the LICENSE fetch), not a
  byte-rendered file. No runtime `--data` injection is needed in 009 (the dynamic lists
  were the agentic category, excluded by Q4).
- **Secret-shaped answers**: project-setup enforces a G8 secret-shape guard at its
  interview boundary. clerk's equivalent is Constitution VI (no `secret:` questions) +
  spec-005's `runner.init` secret-key rejection. Ported modules MUST declare no
  `secret:` questions; any credential is read from the ambient env by a task.
- **`license-write`'s dynamic fetch**: like `clerk-template-example`, the LICENSE is a
  task side effect outside the byte-identical reproduce set (network-sourced) — port it
  the same way (guarded, idempotent task).
- **Overwrite / drift on re-run**: project-setup hard-gates destructive overwrites;
  clerk's `reproduce` uses `--overwrite` (faithful replay) and `update` is the explicit
  merge path (spec 006). The port must not smuggle project-setup's diff/confirm loop in.
  **Seed-once / living files** (`AGENTS.md`, language manifests) are protected from the
  `--overwrite` replay via copier's `_skip_if_exists` (D-009-7 / Q3), so a re-run does
  not revert project-owned edits; on a fresh-checkout reproduce they render normally.

---

## Requirements

### Functional Requirements

First draft — subject to revision once open questions resolve.

- **FR-001**: Every shipped module MUST be a valid copier template: it ships the
  `{{ _copier_conf.answers_file }}.jinja` file (Constitution VI a), has clean PEP 440
  tags (VI b), declares `when:false` dependency edges (VI c), and uses the new
  `_migrations` format if it declares any (VI d).
- **FR-002**: No shipped module MAY declare a `secret:` question (Constitution VI
  secrets rule); credentials needed by a task MUST be read from the ambient environment
  (as `clerk-template-example`'s LICENSE task reads `gh` auth), never a copier answer.
- **FR-003**: Each module's project-setup `[[inputs]]` MUST be re-expressed as copier
  questions preserving type and choices verbatim (e.g. `license-write`'s 13 SPDX
  choices, not a shortlist — cf. project-setup RULE 5).
- **FR-004**: Each module's project-setup `[order]` edges MUST be re-expressed as
  `when:false` `depends_on`/`run_after`/`run_before` answers so the spec-003 engine
  sequences the layers; edge identity MUST be collision-free by basename (spec 003).
- **FR-005**: Each module's deterministic (`python`-tier) **managed** outputs MUST be
  produced by rendered template files, byte-identical across reproduce runs
  (Constitution III / VII a). See FR-005a for the seed-once exception.
- **FR-005a** *(file lifecycle — Q3/OQ-009-c/D-009-7)*: Each module MUST classify its
  outputs as **managed** (re-rendered) or **seed-once/living** (scaffolded at init,
  thereafter project-owned). Seed-once files — at minimum `AGENTS.md` and language
  manifests (`pyproject.toml`, `go.mod`, `Cargo.toml`, `package.json`) — MUST be listed
  in the module's copier `_skip_if_exists` so a re-run/`update` does not clobber
  project-owned edits. On a fresh-checkout reproduce they render normally (Constitution
  III holds). The plan records each module's per-file classification.
- **FR-006**: Each module's agent-steered (`agent`-tier) decisions MUST be produced in
  phase 1 and frozen as `--data` answers persisted to the answers file, so reproduce
  replays them with no agent (Constitution II). What is frozen is the **structured
  facts** the decision yields (stack, env-keys, pins, resolved-architecture choice),
  from which the template renders deterministically — NOT a whole free-form prose blob
  (Q3/OQ-009-c; Constitution VIII).
- **FR-007**: Each code-executing or network-touching action MUST be a trust-gated
  `_task`, not a render-time side effect (Constitution V); version pins in the task
  command where determinism allows.
- **FR-007a** *(gate mapping — Q5/OQ-009-e)*: A project-setup per-action consent gate
  MUST be re-expressed EITHER as a safe-defaulting copier boolean question (for a
  consequential *choice*, e.g. `create_public_repo: false`, `write_architecture: false`)
  whose persisted answer gates the render/task, OR as reliance on the single
  source-trust gate (for code *execution*). No new per-action consent layer or
  `allow_flag`-style mechanism may be introduced (C-11).
- **FR-007b** *(tool preflight — Q6/OQ-009-f)*: A module whose task requires an external
  tool (`uv`/`gh`/`go`/etc.) MUST ship a preflight `_task`, ordered FIRST among its
  tasks, that verifies the tool's presence and fails with explicit install guidance
  before any consequential action task runs; the module README MUST also document the
  prerequisite. (copier runs all tasks post-render, so this is task-ordered-first, not
  literally pre-render.) No `[tools]`-equivalent clerk glue is added (C-11).
- **FR-007c** *(option lists — Q7/OQ-009-g)*: Finite well-known option lists (SPDX
  licenses, language versions, etc.) MUST use fixed copier `choices:` (no runtime
  injection). `.gitignore` MUST NOT be a choice list: it MUST be generated by the
  version-pinned `gitnr` tool from the project baseline (stack/language answers) via a
  trust-gated `_task` (per FR-007/FR-007b), and its output is task-generated
  (process-deterministic), not a byte-rendered managed file.
- **FR-008**: Each module MUST be testable in isolation (with stub threaded answers) and
  as a layer in a multi-template project (init + reproduce integration test —
  Constitution VII c).
- **FR-009**: Every shipped module MUST pass `scripts/check_modules.py`
  (`just check-modules`) and be registered for 008b fan-out (directory ==
  `cog.toml [monorepo.packages]` == `catalog-sources.toml` parity).
- **FR-010**: Modules threading answers from an upstream layer MUST use copier's
  `default: "{{ upstream_answer }}"` mechanism (threaded via `data=`, ADR-0003) and MUST
  NOT hardcode which upstream layer supplied it (cf. 007 FR-006).
- **FR-011** *(RELAXED — Q8, 2026-07-14)*: The port MUST NOT add **behavioural
  capability** (new files, new side-effecting tasks, new integrations) absent from the
  module's project-setup ancestor. **EXCEPTION (Q8/FR-014):** adding a finite,
  static-`choices:` **tooling/config choice dimension** that generalizes a decision the
  ancestor hardcoded (e.g. package manager, linter, formatter, test runner, hook
  manager, task runner) is explicitly permitted and encouraged — this is
  de-opinionation, not new capability. Dropping a dead/legacy option (e.g. bare `pip`)
  is likewise permitted. The line: offering *which tool does the same job* is allowed;
  inventing a *new job the module never did* is not.
- **FR-012**: The SKILL.md procedure MUST document the ported family: which modules exist,
  the base-selection step, per-module trust consent for tasks, and the multi-layer handoff
  shape.
- **FR-014** *(de-opinionation — Q8, 2026-07-14)*: Each module MUST NOT force a
  consequential tooling/config opinion where competent teams reasonably differ; such a
  decision MUST be exposed as a copier question with a finite static `choices:` set and a
  sane modern default, UNLESS there is a single clear best answer (then it MAY stay
  hardcoded) or the alternatives are dead/legacy (then they are dropped, not offered).
  Cross-cutting axes (e.g. `pkg_manager`, `linter`, `formatter`, `test_runner`,
  `hook_manager`, `task_runner`) MUST be expressed consistently across modules (same
  key/choices shape) so a multi-layer selection reads coherently. The choice MUST branch
  only rendered files / task commands / edges — no new `src/clerk/` code (C-11). This
  requirement applies to the already-built `clerk-mod-base`, `clerk-mod-python`, and
  `clerk-mod-apm` (they are REVISED to satisfy it), not only to newly authored modules.
- **FR-015** *(multi-model CI — Q9, 2026-07-14)*: `clerk-mod-ci` MUST offer a finite,
  named `ci_model` choice set covering distinct CI execution topologies/optimizations
  (at minimum: a minimal serial model; a parallel-jobs-plus-fan-in-gate model; a
  version/OS matrix model; and a change-filtering/caching/concurrency-optimized model;
  monorepo-affected and merge-queue models as the stack warrants). The selected model
  MUST be a phase-1 **agent** decision frozen as a `--data` answer (per FR-006), chosen
  from project signals (single vs monorepo layout, active language count, PR volume,
  deploy target); the template renders the chosen model **deterministically** (managed
  render, action versions pinned; no agent in the reproduce path — FR-005/FR-006). CI
  MUST size itself to the active stack by reading sibling-layer answers threaded via the
  engine's accumulated `data=` (FR-010), with the zero-languages / zero-commands guards
  preserved. Orthogonal toggles (caching, concurrency-cancel, required-gate, OS matrix)
  MAY be separate boolean/choice questions with safe defaults.
- **FR-013** *(base split — RESOLVED, Q1/OQ-009-a)*: The 6 base modules MUST ship as ONE
  collapsed `clerk-mod-base` copier template. Their inter-base ordering (identity →
  dirs/gitignore → license → agents-md → git-init commits last) is expressed
  template-internally, NOT as cross-module `when:false` edges. `clerk-mod-base` is a
  single fan-out target with one answers file. Later layers (languages, quality, etc.)
  `run_after` `clerk-mod-base` as a whole.

### Key Entities

- **`clerk-mod-*` template**: one ported module — a copier template in the monorepo under
  `templates/clerk-mod-<name>/`, fanned out to `copier-clerk/clerk-mod-<name>` by 008b.
- **`clerk-mod-base`**: the single collapsed base scaffold template (core identity +
  dirs + gitignore + license + AGENTS.md + git-init in one module; Q1/OQ-009-a). One
  fan-out target, one answers file; inter-base ordering is template-internal.
- **Language overlays** (`clerk-mod-python`/`-ts`/`-go`/`-rust`): stack tooling layers
  that `run_after` base.
- **Frozen agent answer**: a phase-1 decision (README draft, stack pins, env keys)
  persisted as a `--data` answer — the reproduce state for `agent`-tier behaviour.
- **Trust-gated `_task`**: the copier task carrying a code-executing action (install,
  `gh repo create`, `git init`, license fetch).

### The module inventory to be ported

The authoritative source is `~/.claude/skills/project-setup/` (SKILL.md + the addon
`catalog.json`). ~25 modules across 8 categories:

| Category | Modules | Port note |
|---|---|---|
| **base** (always-on) | core-identity, dirs-scaffold, gitignore-generate, license-write, agents-md, git-init | Collapsed into ONE `clerk-mod-base` (Q1/OQ-009-a). `agents-md` has an `agent` step + a hard gate and its `AGENTS.md` is seed-once (`_skip_if_exists`, D-009-7); `gitignore-generate` shells out to `gitnr` (pinned trust-gated task, Q7); `git-init`/`license-write` are tasks. |
| **language** | lang-python, lang-ts, lang-go, lang-rust | Overlays; `run_after` base; thread `project_name`. Straight `python`-tier renders. |
| **quality** | precommit-setup, quality-hooks | `run_after` base + language; renders `.pre-commit-config.yaml`, hook files. |
| **tooling** | justfile-write, ci-github-actions, env-example, worktreeinclude-write | `ci-github-actions` sizes YAML to the active stack (reads sibling answers); `env-example` is `agent`-tier (stack→env-keys). |
| **docs** | stack-adr, readme-draft | Both `agent`-tier (frozen prose/pins) — the reproduce-determinism risk (OQ-009-c). |
| **agentic** | apm-install, mcp-config, speckit-bridge, codex-config | **EXCLUDED from 009 entirely** (Q4/OQ-009-d) — 007's family owns all agentic wiring. `codex-config` deferred to a future module. |
| **integration** | github-repo, org-policy | `github-repo` = `gh repo create` task + public-repo hard gate; `org-policy` reads a pinned org source. |
| **monorepo** | package-add | Adds a package dir to a monorepo layout (`layout=monorepo` from base). |

---

## Success Criteria

Provisional — subject to Open Questions.

- **SC-001**: A generated base project contains the correct scaffold (dirs, `.gitignore`,
  `LICENSE`, `AGENTS.md`) and a `.copier-answers.yml`. Its **managed** rendered files
  reproduce byte-identically with copier alone; `.gitignore` (gitnr) and `LICENSE`
  (fetch) are task-generated (process-deterministic), and `AGENTS.md` is seed-once —
  consistent with SC-003/SC-003a.
- **SC-002**: A `[base, lang-python]` project applies base first (spec-003 ordering),
  threads `project_name`, and produces the same observable output project-setup's
  `lang-python` produced.
- **SC-003**: Reproduce of any ported project onto a fresh checkout re-renders all
  **managed** files byte-identically and re-runs trust-gated tasks; the order is
  recomputed from committed answers + pinned fetches (no frozen recipe).
- **SC-003a**: On a re-run/`update` over an already-populated tree, **seed-once** files
  (`AGENTS.md`, language manifests) that the project has edited are NOT overwritten
  (`_skip_if_exists`, Q3/D-009-7).
- **SC-004**: An untrusted source is refused at init (exit 3) before any task runs.
- **SC-005**: An agent-drafted output (README/STACK/env) replays from its frozen answer at
  reproduce with no agent call.
- **SC-006**: Every shipped module passes `just check-modules` and is fan-out-registered
  (parity across `templates/`, `cog.toml`, `catalog-sources.toml`).
- **SC-007**: No shipped module declares a `secret:` question (spec-005 policy lint over
  in-repo templates stays green).
- **SC-008**: The phase-1 slice (base + one language) is sufficient for 008b to run its
  fan-out end to end against a real module (unblocking 008b Phases 5–7).

---

## Out of scope

- New **behavioural** capabilities beyond project-setup (roadmap Scope-out) — but NOT
  de-opinionation choices or the multi-model CI, which are in scope per Q8/Q9 (FR-011
  relaxed; FR-014/FR-015 added).
- The 008b fan-out/release pipeline (built by 008b; 009 supplies content).
- Catalog / ordering / upgrade / delivery machinery (specs 002/003/006/010 — consumed).
- spec 007's `clerk-mod-apm` (independent) and the entire project-setup `agentic`
  category (apm-install/mcp-config/speckit-bridge/codex-config) — excluded per
  Q4/OQ-009-d; 007's family owns agentic wiring.
- porting project-setup's runner/SDK/manifest format or its home-config catalog.
- Brownfield adoption (deferred spec).

---

## Dependency direction — 009 unblocks 008b; 009 is independent of 007

**009 → 008b (unblocks, HARD):** 008b's spec carries an explicit "IMPLEMENTATION BLOCKED
ON SPEC 009" banner: its fan-out/release/e2e phases cannot run because the only template
that exists is `examples/clerk-template-example/` (a demo, not a shippable module). 009 is
the linchpin — the moment it lands ≥1 real `clerk-mod-*` module under `templates/`, 008b
can fan out. Consequently 009's phasing (below) is explicitly ordered to deliver a minimal
real module (base + one language) as its FIRST slice, precisely to unblock 008b as early as
possible. The `cog.toml` `pre_bump_hooks = ["just check-modules || true"]` and
`check_modules.py`'s empty-`templates/` no-op already anticipate this hand-off.

**009 ↔ 007 (independent; agentic category is 007's):** 007 ships `clerk-mod-apm`
independently (007's clarify). 009 does NOT depend on 007 and MUST NOT duplicate it.
**Resolved (Q4/OQ-009-d): 009 excludes the entire project-setup `agentic` category**
(`apm-install`, `mcp-config`, `speckit-bridge`, `codex-config`) — 007's family owns that
space (`apm-install`=007 v1; MCP/SpecKit=future 007-family modules; `codex-config`
deferred to a future module). 007's own OQ-007-g flags this boundary from the other side.

---

## Proposed phasing (this is a large port — deliver in slices)

~25 modules with several agent-steered and task-bearing members is too large for one
slice, and the primary near-term value is **unblocking 008b**. Phasing (v1 = Phase 0,
RESOLVED Q2/OQ-009-b; later phases are a lean, not a commitment):

- **Phase 0 — Contract slice = v1 (unblocks 008b):** port the collapsed `clerk-mod-base`
  (Q1) + one language overlay (`clerk-mod-python`). This is the minimal real module set
  that lets 008b run fan-out/release/e2e end to end. Exercises base identity, `run_after`
  edges, answer threading, a trust-gated task, and the contract lint. **Highest priority.**
- **Phase 1 — Remaining languages + quality/tooling (pure `python`-tier):**
  `clerk-mod-ts`, `clerk-mod-go`, `clerk-mod-rust`, `clerk-mod-precommit`,
  `clerk-mod-quality`, `clerk-mod-justfile`. Mostly deterministic renders; lowest
  translation risk after Phase 0. Each de-opinionated per Q8/FR-014.
- **Phase 2 — Agent-steered + integration + monorepo + CI (the hard translations):**
  `clerk-mod-env`, `clerk-mod-readme`, `clerk-mod-stack-adr` (frozen-answer determinism
  — OQ-009-c), `clerk-mod-ci` (multi-model, Q9/FR-015), `clerk-mod-github-repo`,
  `clerk-mod-package-add` (monorepo), and last `clerk-mod-org-policy` (a no-op until an
  org-source-fetch module exists — flagged). `clerk-mod-codex` (codex-config) is ported
  as a small deterministic seed-once module (2026-07-14 decision, overriding the earlier
  Q4 defer for this one non-overlapping Codex-only file; the rest of the agentic category
  — apm/mcp/speckit — remains 007's).
- **Dropped:** `worktreeinclude-write` (`clerk-mod-worktree`) — niche, low-value, awkward
  to port onto the gitnr-generated `.gitignore`; deferred indefinitely (2026-07-14).
- **~~Phase 3 — agentic residue~~ (REMOVED, Q4/OQ-009-d):** 009 ports no
  apm/mcp/speckit modules; those remain 007's family. There is no Phase 3.

Each phase is independently valuable and independently testable; Phase 0 alone delivers
the 008b-unblocking outcome the roadmap prioritises.

---

## Open Questions

**All seven questions below were RESOLVED in the 2026-07-13 clarify session** (see the
Clarifications section for the decisions). Each question is retained with its original
tradeoffs/leans for historical context and marked `[RESOLVED — Qn]` in its heading.

### OQ-009-a — Base split: one `clerk-mod-base` vs several separate repos (HIGH PRIORITY)  [RESOLVED — Q1, 2026-07-13]

**Resolution**: (A) one collapsed `clerk-mod-base`. The 6 base modules ship as one
copier template; inter-base ordering is template-internal; one fan-out target / tag
line / answers file. Faithful to project-setup's always-on indivisible base.
Resolves roadmap Q2. Options retained below for context.

**The question**: The 6 project-setup base modules (core-identity, dirs-scaffold,
gitignore-generate, license-write, agents-md, git-init) — do they collapse into ONE
`clerk-mod-base` copier template, or ship as several separate `clerk-mod-*` repos? The
roadmap explicitly flags both ("a real clerk-mod-base could collapse 5 project-setup base
modules; 009 may instead ship them as separate clerk-mod-* repos"). This is roadmap
open-question **Q2** ("keep `clerk-mod-base` as one template or re-split?"), which the
roadmap says is "resolved when 009 is scoped" — i.e. here.

**Tradeoffs**:
- **(A) One collapsed `clerk-mod-base`**: one repo, one tag line, one catalog entry, one
  fan-out target, one answers file. The internal ordering between the 6 becomes template-
  internal (no cross-module `when:false` edges needed among them). Simplest for the
  consumer (base is one selection). Con: `license-write`'s optional-ness and the 13-license
  choice, `git-init`'s opt-in commit, and `agents-md`'s agent step all live in one bigger
  `copier.yml`; a user always gets the whole base (project-setup already treats the base
  set as always-on, so this is faithful).
- **(B) Several separate base modules**: each of the 6 is its own `clerk-mod-*` repo. Maps
  1:1 onto project-setup's structure and preserves the fine-grained `requires`/`after`
  edges as `when:false` edges (exercising the spec-003 engine harder). Con: 6 repos, 6 tag
  lines, 6 fan-out targets, 6 answers files for what project-setup treats as an
  indivisible base; more `depends_on` edges to get right; basename-collision care needed
  (spec-003 tie-break).

**Lean (flagged for review)**: **(A) one collapsed `clerk-mod-base`** — project-setup
already treats the 6 as an always-on indivisible base (`default_enabled = true`, base set
"cannot be deselected"), so collapsing is faithful and drops 5 fan-out targets + 5 answers
files for zero lost capability. The separate-repo model buys granularity project-setup
itself does not offer at the base layer. Resolve before planning.

### OQ-009-b — Phasing / scope of v1 (which modules ship first, how many at once)  [RESOLVED — Q2, 2026-07-13]

**Resolution**: v1 = Phase 0 (`clerk-mod-base` + `clerk-mod-python`). Unblocks 008b
fastest and de-risks the translation on the smallest real module set; Phases 1–3 are
fast-follow, not v1. Retained below for context.

**The question**: Is Phase 0 (base + one language) the right v1, or should v1 be larger
(e.g. all base + all four languages + precommit + ci)? How many of the ~25 modules are in
the first shipped release?

**Tradeoffs**: A minimal Phase 0 unblocks 008b fastest and de-risks the translation
(prove the loop on the smallest real module set). A larger v1 ports more value at once but
front-loads the agent-steered/task-bearing translation risk. project-setup's own value is
concentrated in base + languages + precommit + ci (the "recommended for a FastAPI service"
set in its SKILL.md).

**Lean**: Phase 0 (base + `clerk-mod-python`) as the first merged slice (unblocks 008b),
then Phase 1 as a fast follow. Resolve before planning.

### OQ-009-c — Reproduce determinism for `agent`-tier modules (HIGH PRIORITY)  [RESOLVED — Q3, 2026-07-13]

**Resolution**: Two decisions. **(1)** Freeze **structured facts** and render
deterministically (option (ii) below) — not whole prose blobs. **(2)** Beyond the
agent-tier question, every module classifies its outputs into **managed** (re-rendered
byte-identically) vs **seed-once/living** (scaffolded once, then project-owned):
`AGENTS.md` and language manifests (`pyproject.toml`/`go.mod`/`Cargo.toml`/
`package.json`) are seed-once, protected via copier's `_skip_if_exists` (no new tool
code; Constitution III still holds on fresh-checkout reproduce). See D-009-3, D-009-7,
FR-005a, FR-006. The per-file `clerk update` merge policy is a plan-level detail.
Options retained below for context.

**The question**: project-setup's `agent`-tier steps (`agents-md` resolve-arch,
`env-example`, `readme-draft`, `stack-adr`) make a runtime judgment via a `steering/` doc.
In clerk's model that judgment MUST happen in phase 1 and freeze into a `--data` answer
that renders deterministically (Constitution II/III; D-009-3). Can every such decision be
reduced to a plain-text answer that (a) the skill can author, (b) copier can render, and
(c) reproduce replays byte-identically with no agent?

- A README *draft* is a large free-form string — freezable as one multiline answer, but is
  a whole document a healthy copier answer, or should the draft be rendered from
  structured facts (project name, stack, license) the way project-setup's `readme-draft`
  actually derives it "from frozen scaffold facts"?
- `stack-adr` freezes stack *pins* — clearly structured, low risk.
- `env-example` maps a stack to an `env_keys` list — structured, low risk, but the mapping
  judgment is the agent's.

**Tradeoffs**: (i) Freeze the whole agent output as one answer (simplest; but bloats the
answers file and couples reproduce to the exact prose). (ii) Freeze the structured inputs
(stack, keys, pins) and render the document deterministically from them (cleaner reproduce;
matches how project-setup derives these "from frozen facts"; more template work). (iii)
Defer the genuinely-prose modules (`readme-draft`) to a later phase.

**Lean**: **(ii)** — freeze structured facts, render deterministically. This is what
project-setup already does ("draft from frozen scaffold facts"), keeps answers files sane,
and honours Constitution VIII (documented plain-text handoff). Resolve before planning.

### OQ-009-d — Which project-setup `agentic` modules (if any) does 009 port? (boundary with 007)  [RESOLVED — Q4, 2026-07-13]

**Resolution**: (a) — 009 ports NONE of the agentic category. 007's family owns all
agentic wiring (`apm-install`=007 v1; `mcp-config`/`speckit-bridge`=future 007-family
modules; `codex-config`=deferred to a future module). This tightens the original lean
(b), which was port-only-`codex-config`. Options retained below for context.

**The question**: project-setup's `agentic` category (`apm-install`, `mcp-config`,
`speckit-bridge`, `codex-config`) overlaps spec 007's `clerk-mod-apm`. Does 009 (a) port
none of them (007 owns the agentic space), (b) port only the non-overlapping ones
(`codex-config`), or (c) port them all as separate focused modules that coexist with
007's?

**Tradeoffs**: 007 is `planned` and explicitly independent; its OQ-007-b/f debate monolith
vs split for exactly this space. Porting the project-setup agentic modules in 009 risks
duplicating 007 and creating two `apm`-ish modules. Excluding them keeps a clean boundary
but means a 009-only consumer has no agentic wiring until 007 lands.

**Lean**: **(b)** — 009 excludes `apm-install`/`mcp-config`/`speckit-bridge` (007's
territory) and ports at most `codex-config` (no 007 equivalent). Coordinate the final call
with 007's OQ-007-g. Resolve before planning.

### OQ-009-e — How do project-setup gates map onto clerk?  [RESOLVED — Q5, 2026-07-13]

**Resolution**: (ii)+(i) — consequential *choices* become safe-defaulting copier
boolean questions (persisted answers gate the render/task); code *execution* stays
behind the single source-trust gate; no new per-action consent layer (C-11). Options
retained below for context.

**The question**: project-setup has a rich gate system (`hardness` hard/soft/informational,
per-action `allow_flag`/`skip_flag`, e.g. `allow-public-repo`, `allow-arch-write`,
`allow-install`, `allow-stack-write`). clerk has a coarser model: one trust gate (source
trusted → `_tasks` run) + copier `when:` conditionals for opt-in/opt-out. Do the
fine-grained per-action consents map onto clerk, or collapse into "the source is trusted
and the user selected the module"?

**Tradeoffs**: clerk's trust gate is all-or-nothing per source; it does not have
project-setup's per-action `--allow-public-repo`-style granularity. Options: (i) collapse
each gate into module selection + the single trust gate (a public repo is created because
the user selected `github-repo` on a trusted source); (ii) re-express a consequential
choice as a copier boolean question (`create_public_repo: false` default) so the user
opts in via an answer, not a CLI flag; (iii) accept a loss of granularity as faithful to
clerk's simpler, source-level trust model.

**Lean**: **(ii)+(i)** — consequential choices become copier boolean questions (defaulting
safe), and code execution stays behind the single source-trust gate. This is faithful to
clerk's model without inventing a per-action consent layer (which would be new tool code —
C-11 violation). Resolve before planning.

### OQ-009-f — `[tools]` prerequisites with no copier equivalent  [RESOLVED — Q6, 2026-07-13]

**Resolution**: (iii)+(ii) — a preflight `_task` (ordered first among a module's tasks)
checks the required tool and fails with explicit install guidance before consequential
tasks run, plus a documented README prerequisite. Steers the user/agent to install the
tool rather than hitting a cryptic mid-action failure. No new preflight machinery in
clerk glue (C-11). Options retained below for context.

**The question**: project-setup modules declare required `[tools]` (`uv`, `gh`, `go`,
etc.) and the runner preflights them. copier has no `[tools]` block and no preflight. How
does a ported module ensure its tools are present?

**Tradeoffs**: (i) Let the `_task` fail with copier surfacing the exit code + message
(clerk's `_translate` reports it) — simplest, but the failure is late (after render).
(ii) Document the prerequisite in the module README and rely on the task's own
error. (iii) Add a preflight `_task` that checks the tool early and fails loudly. Note
that clerk already has `clerk doctor` (spec 008) for clerk's OWN deps — not the
generated project's, so it does not cover this.

**Lean**: **(i)+(ii)** — rely on the task's own loud failure + a documented prerequisite,
consistent with how `clerk-template-example` requires `gh` (its task fails if `gh` is
absent/unauthenticated). No new preflight machinery (C-11). Resolve at planning.

### OQ-009-g — Multichoice options: fixed `choices:` vs runtime `--data` injection  [RESOLVED — Q7, 2026-07-13]

**Resolution**: Fixed `choices:` for all finite well-known sets (SPDX licenses, language
versions). **`.gitignore` is the exception** — generated by the version-pinned `gitnr`
tool from the project baseline via a trust-gated task (task output, not a choice list or
a byte-rendered file). No runtime `--data` injection in 009 (dynamic lists were the
agentic category, excluded by Q4). Original text retained below for context.

**The question**: Modules with large or extensible option lists (gitignore templates in
`gitignore-generate`; MCP servers if any agentic module is ported; APM packages) — bake
the list into `copier.yml` `choices:` or inject at runtime via `--data` (ADR-0003)? This
is the same tradeoff as 007's OQ-007-a.

**Lean**: fixed `choices:` for well-known finite sets (gitignore bases, license SPDX list,
language versions) — simplest, ages via a minor bump. Runtime injection only where a set is
genuinely dynamic (defer to 007's resolution for the agentic overlap). Resolve at planning.

---

## Assumptions

- The project-setup source at `~/.claude/skills/project-setup/` (SKILL.md + addon
  `catalog.json` + bundled `modules/`) is the authoritative behavioural spec for each
  ported module; where a module's addon source is not locally present, its `catalog.json`
  description + SKILL.md characterization defines its job for scoping (the plan will read
  each module's full manifest before porting it).
- Specs 002/003/006/008/010 are implemented and their machinery is consumed unchanged; 009
  adds no `src/clerk/` code (C-11).
- The 008b authoring tooling (`just new-module`, `scripts/check_modules.py`,
  `_meta/module-template/`, `cog.toml`) is the sanctioned way to create and lint every
  009 module; 009 modules land under `templates/clerk-mod-*/`.
- 007 is independent; 009 neither depends on nor blocks 007, and excludes the entire
  agentic category — 007's family owns it (Q4/OQ-009-d).
- The base set is faithfully always-on (project-setup treats it as non-deselectable), so
  collapsing vs splitting it (OQ-009-a) is a packaging decision, not a capability one.

---

## Governing constitution & ADRs

- **Constitution I** (template content, not tool code — C-11: no copier gap here; the
  port is questions + rendered files + edges + trust-gated tasks, all native copier).
- **Constitution II** (two-phase: `agent`-tier decisions are phase-1 judgment frozen into
  answers; renders + tasks are deterministic phase 2).
- **Constitution III** (faithful, agent-free reproduce: rendered files byte-identical;
  order recomputed from committed answers + pinned fetches, no frozen recipe; task side
  effects process-deterministic).
- **Constitution V** (determinism via pinning; trust by source: code-executing steps are
  trust-gated `_tasks`; no `jinja2_time`; `today` injected).
- **Constitution VI** (template-author contract on EVERY module: answers-file `.jinja`,
  PEP 440 tags, `when:false` edges, new `_migrations`, and the secrets rule — NO `secret:`
  questions; credentials read from ambient env by tasks).
- **Constitution VII** (per-step hardening: each module lands its init+reproduce
  integration test and passes `check_modules.py`).
- **ADR-0002** (user-owned catalog; answers carry state; `_src_path` = split repo; PEP 440
  tags; full-id collisions; no submodules).
- **ADR-0003** (`when:false` dependency edges statically read; `--data` runtime injection
  in scope from question 1; clerk threads answers between layers via `data=`).
- **ADR-0006** (authoring monorepo → fan-out; `just new-module` scaffolder; `check-modules`
  contract lint; catalog-sources parity — the plane 009's modules are authored into).
- **Constraints**: C-01 (skills + templates + minimal glue), C-06 (template-author
  contract), C-09 (authoring monorepo → fan-out), C-11 (glue only for a copier gap — none
  here), and roadmap Q2 (base re-split — resolved here as OQ-009-a).
- **Depends on**: spec 002 (catalog), 003 (ordering), 006 (upgrade), 008 (packaging),
  010 (delivery contract). **Unblocks**: spec 008b (fan-out/release/e2e). **Independent
  of**: spec 007 (agentic module — possible apm-category overlap, OQ-009-d).
