# Feature Specification: project-setup module port → clerk-mod-* templates (spec 009)

**Feature Branch**: `009-project-setup-port`

**Created**: 2026-07-13

**Status**: Draft (first-draft framing — see Open Questions; scope is deliberately
framed for review, not committed)

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
replays the frozen answer. This is the single largest translation risk in the port
(these modules were designed around a runner callback the agent responds to at runtime),
and it is flagged as OQ-009-c.

### D-009-4 — Code-executing / network steps become trust-gated `_tasks`

Modules that run code on the target project (`apm-install` runs `apm install`;
`github-repo` calls `gh repo create`; `git-init` runs `git init`; `speckit-bridge`
installs speckit; `license-write` may fetch from the GitHub Licenses API) map to copier
`_tasks`, gated by clerk's trust mechanism exactly as `clerk-template-example`'s
`git init` + `gh api` LICENSE task is today. The user consents at trust-record time;
reproduce replays the task under the same gate (`_tasks` run at both init and reproduce
— Constitution III). Network-touching tasks are process-deterministic, not
byte-identical (Constitution III) — pin versions in the task command where possible.

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
re-implement 007's `clerk-mod-apm`. The boundary — whether 009 ports the project-setup
agentic modules at all, defers them to 007, or ports only the non-overlapping ones
(`codex-config`) — is an explicit open question (OQ-009-d). Lean: 009 excludes the
agentic category from its port (007 owns that space); 009 ports base + languages +
quality + tooling + docs + integration + monorepo.

---

## What is NOT in scope

- **New capabilities not present in project-setup** (roadmap Scope-out, explicit). The
  port is a translation; no module gains a feature its project-setup ancestor lacks.
- **The fan-out / release pipeline** (spec 008b) — 009 authors module *content* into
  `templates/clerk-mod-*/`; 008b's CI fans them out. 009 unblocks 008b by existing; it
  does not build the pipeline.
- **The catalog subsystem, ordering engine, upgrade/migrations engine, delivery shape**
  (specs 002/003/006/010) — consumed, not rebuilt.
- **spec 007's `clerk-mod-apm`** — independent; 009 does not port the overlapping
  agentic modules if OQ-009-d resolves that way.
- **Porting project-setup's runner, SDK, or manifest format** — those are the mechanisms
  clerk replaces with copier + the spec-003 DAG. The runner does not ship; only the
  modules' behaviour is re-expressed as templates.
- **project-setup's home-config catalog / `sources.toml` / `answers.toml` machinery** —
  clerk's spec-002 catalog + copier answers files supersede these.
- **Brownfield adoption** (the deferred spec).

---

## User Scenarios & Testing

### US1 — Scaffold a project from the base module(s) (Priority: P1)

A developer selects the clerk base (`clerk-mod-base`, or the base set if split) with a
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
a `--data` answer at init; reproduce replays the frozen answer and re-renders the same
file with no agent involvement.

**Acceptance Scenarios**:
1. **Given** an agent-drafted README frozen as an answer, **When** `reproduce`, **Then**
   the README re-renders from the frozen answer, byte-identically, with no agent call.

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
- **`[tools]` requirement with no copier equivalent**: copier has no `[tools]` block;
  a module that required `uv`/`gh`/`go` must surface the prerequisite via the task's own
  failure (copier surfaces the exit code) or a documented preflight (OQ-009-f).
- **A `multichoice` whose options are large/dynamic** (e.g. gitignore templates, MCP
  servers): copier `multiselect` with fixed `choices:` versus runtime `--data`
  injection (ADR-0003) — the same tradeoff 007's OQ-007-a raises.
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
- **FR-005**: Each module's deterministic (`python`-tier) outputs MUST be produced by
  rendered template files, byte-identical across reproduce runs (Constitution III /
  VII a).
- **FR-006**: Each module's agent-steered (`agent`-tier) decisions MUST be produced in
  phase 1 and frozen as `--data` answers persisted to the answers file, so reproduce
  replays them with no agent (Constitution II).
- **FR-007**: Each code-executing or network-touching action MUST be a trust-gated
  `_task`, not a render-time side effect (Constitution V); version pins in the task
  command where determinism allows.
- **FR-008**: Each module MUST be testable in isolation (with stub threaded answers) and
  as a layer in a multi-template project (init + reproduce integration test —
  Constitution VII c).
- **FR-009**: Every shipped module MUST pass `scripts/check_modules.py`
  (`just check-modules`) and be registered for 008b fan-out (directory ==
  `cog.toml [monorepo.packages]` == `catalog-sources.toml` parity).
- **FR-010**: Modules threading answers from an upstream layer MUST use copier's
  `default: "{{ upstream_answer }}"` mechanism (threaded via `data=`, ADR-0003) and MUST
  NOT hardcode which upstream layer supplied it (cf. 007 FR-006).
- **FR-011**: The port MUST NOT add any capability absent from the module's project-setup
  ancestor (roadmap Scope-out).
- **FR-012**: The SKILL.md procedure MUST document the ported family: which modules exist,
  the base-selection step, per-module trust consent for tasks, and the multi-layer handoff
  shape.
- **FR-013** *(base split — pending OQ-009-a)*: The 6 base modules MUST ship EITHER as one
  collapsed `clerk-mod-base` template OR as separate `clerk-mod-*` repos; the plan MUST
  record which, with the edge-identity and reproduce consequences.

### Key Entities

- **`clerk-mod-*` template**: one ported module — a copier template in the monorepo under
  `templates/clerk-mod-<name>/`, fanned out to `copier-clerk/clerk-mod-<name>` by 008b.
- **`clerk-mod-base`** *(or the base set)*: the collapsed base scaffold (core identity +
  dirs + gitignore + license + AGENTS.md + git-init), OR the 6 separate base modules —
  OQ-009-a.
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
| **base** (always-on) | core-identity, dirs-scaffold, gitignore-generate, license-write, agents-md, git-init | Collapse into `clerk-mod-base` OR keep separate — OQ-009-a. `agents-md` has an `agent` step + a hard gate; `git-init`/`license-write` are tasks. |
| **language** | lang-python, lang-ts, lang-go, lang-rust | Overlays; `run_after` base; thread `project_name`. Straight `python`-tier renders. |
| **quality** | precommit-setup, quality-hooks | `run_after` base + language; renders `.pre-commit-config.yaml`, hook files. |
| **tooling** | justfile-write, ci-github-actions, env-example, worktreeinclude-write | `ci-github-actions` sizes YAML to the active stack (reads sibling answers); `env-example` is `agent`-tier (stack→env-keys). |
| **docs** | stack-adr, readme-draft | Both `agent`-tier (frozen prose/pins) — the reproduce-determinism risk (OQ-009-c). |
| **agentic** | apm-install, mcp-config, speckit-bridge, codex-config | Overlaps spec 007 — likely EXCLUDED from 009 (OQ-009-d); `codex-config` is the only clearly non-overlapping one. Installs are trust-gated tasks. |
| **integration** | github-repo, org-policy | `github-repo` = `gh repo create` task + public-repo hard gate; `org-policy` reads a pinned org source. |
| **monorepo** | package-add | Adds a package dir to a monorepo layout (`layout=monorepo` from base). |

---

## Success Criteria

Provisional — subject to Open Questions.

- **SC-001**: A generated base project contains the correct scaffold (dirs, `.gitignore`,
  `LICENSE`, `AGENTS.md`) and a `.copier-answers.yml`, and reproduces byte-identically
  with copier alone.
- **SC-002**: A `[base, lang-python]` project applies base first (spec-003 ordering),
  threads `project_name`, and produces the same observable output project-setup's
  `lang-python` produced.
- **SC-003**: Reproduce of any ported project re-renders all files byte-identically and
  re-runs trust-gated tasks; the order is recomputed from committed answers + pinned
  fetches (no frozen recipe).
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

- New capabilities beyond project-setup (roadmap Scope-out).
- The 008b fan-out/release pipeline (built by 008b; 009 supplies content).
- Catalog / ordering / upgrade / delivery machinery (specs 002/003/006/010 — consumed).
- spec 007's `clerk-mod-apm` (independent) and, per OQ-009-d's lean, the overlapping
  agentic modules.
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

**009 ↔ 007 (independent; possible apm overlap):** 007 ships `clerk-mod-apm`
independently (007's clarify). 009 does NOT depend on 007 and MUST NOT duplicate it. The
overlap is in project-setup's `agentic` category (`apm-install`, `mcp-config`,
`speckit-bridge`, `codex-config`), which covers similar ground to 007's module. 007's own
OQ-007-g already flags this boundary from the other side. 009 resolves it in OQ-009-d;
the lean is that 007 owns the agentic space and 009 excludes that category (porting at
most the non-overlapping `codex-config`).

---

## Proposed phasing (this is a large port — deliver in slices)

~25 modules with several agent-steered and task-bearing members is too large for one
slice, and the primary near-term value is **unblocking 008b**. Proposed phases (a lean,
not a commitment — OQ-009-b):

- **Phase 0 — Contract slice (unblocks 008b):** port `clerk-mod-base` (or its first base
  member) + one language overlay (`clerk-mod-python`). This is the minimal real module set
  that lets 008b run fan-out/release/e2e end to end. Exercises base identity, `run_after`
  edges, answer threading, a trust-gated task, and the contract lint. **Highest priority.**
- **Phase 1 — Remaining languages + quality/tooling (pure `python`-tier):** `lang-ts`,
  `lang-go`, `lang-rust`, `precommit-setup`, `quality-hooks`, `justfile-write`,
  `ci-github-actions`, `worktreeinclude-write`. Mostly deterministic renders; lowest
  translation risk after Phase 0.
- **Phase 2 — Agent-steered + integration (the hard translations):** `env-example`,
  `readme-draft`, `stack-adr` (frozen-answer determinism — OQ-009-c), `github-repo`,
  `org-policy`, `package-add`.
- **Phase 3 (conditional on OQ-009-d) — agentic residue:** only the project-setup agentic
  modules that 007 does NOT cover (at most `codex-config`).

Each phase is independently valuable and independently testable; Phase 0 alone delivers
the 008b-unblocking outcome the roadmap prioritises.

---

## Open Questions

**This section is the substantive product of this first-draft framing spec. The
orchestrator and user MUST resolve these before implementation is scoped.** Leans are
flagged for review, not decided.

### OQ-009-a — Base split: one `clerk-mod-base` vs several separate repos (HIGH PRIORITY)

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

### OQ-009-b — Phasing / scope of v1 (which modules ship first, how many at once)

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

### OQ-009-c — Reproduce determinism for `agent`-tier modules (HIGH PRIORITY)

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

### OQ-009-d — Which project-setup `agentic` modules (if any) does 009 port? (boundary with 007)

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

### OQ-009-e — How do project-setup gates map onto clerk?

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

### OQ-009-f — `[tools]` prerequisites with no copier equivalent

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

### OQ-009-g — Multichoice options: fixed `choices:` vs runtime `--data` injection

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
- 007 is independent; 009 neither depends on nor blocks 007, and defers the agentic
  overlap to 007 (OQ-009-d lean).
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
