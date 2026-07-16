<!--
SYNC IMPACT REPORT (latest amendment)
==================
Version change: 2.3.0 → 3.0.0 (Version: 3.0.0)
Bump rationale: MAJOR — Principle I is REDEFINED (the same class as v1.0.0 → 2.0.0).
The "no published package / no console entry / no uvx tool" prohibition is lifted:
bailiff IS the tool (published on PyPI, invoked `uvx bailiff`), and bailiff-mod-* are
the modules. Spec 013 is the governed engine exception; the C-11 "glue only for
capabilities copier lacks" rule is scoped to module-authoring specs in the roadmap.
  - I.   "bailiff Is Skills + Templates + Minimal Glue" — title UNCHANGED; the glue
         enumeration now names the packaged CLI (`[project.scripts] bailiff`,
         `src/bailiff/cli.py`) as the third form of glue. The bundled script
         `scripts/bailiff.py` is REMOVED: the PyPI CLI is the sole invocation path
         (contributors use `uv run bailiff` via the editable install).
  - VIII. Unlock clause triggered (recorded in ADR-0008, not a text change): the
         packaged CLI, the collision check, and the capability-tag warning are
         genuine non-agent consumers of the handoff; capability fields in catalog
         artifacts and `catalog list --json` are sanctioned.
Reconciled in the same change (per governance: amend the principle with the change
that relies on it):
  - docs/decisions/0008-pypi-packaging-repositioning.md — NEW ADR recording the
    repositioning, the distribution name (bailiff, live on PyPI), the FR-019 unlock
    scope, the warn-not-block capability design, and the group-infection escape valve.
  - .specify/memory/roadmap.md — C-11 scoped to module-authoring specs; spec 013
    noted as the governed engine exception; C-01 reconciled to the packaged CLI.
Retroactive honor: spec 011's FR-011 gate ("no new src/bailiff code" for 011's scope)
remains textually intact and honored for its own scope; 013 is not retroactively
applied to 011's deliverables.
Unchanged in substance: II, III, IV, V, VI, VII.

PRIOR SYNC IMPACT REPORT (2.2.0 → 2.3.0)
==================
Version change: 2.2.0 → 2.3.0
Bump rationale: MINOR — materially expanded guidance on Principle III's existing
process-deterministic carve-out, to sanction spec 011's native-command scaffolding.
  - III. Task-output is clarified to include native-tool-generated manifests
         (uv/bun/cargo/go/cdk init) under a pinned mise toolchain — process-
         deterministic, version-pinned, NOT config-consistent — the same category as the
         existing LICENSE/gitnr/apm-lock outputs. The config-consistent guarantee is
         scoped to MANAGED renders (config bailiff owns). Faithful + agent-free intent
         UNCHANGED; only the task-output boundary is spelled out.
Reconciled in the same change (per governance: amend the principle with the change
that relies on it):
  - docs/decisions/0007-native-command-scaffolding.md — NEW ADR recording the decision,
    the per-file managed/seed-once/task-output boundary, and the tradeoff.
  - specs/011-deopinionated-module-family/{spec,plan}.md — FR-019 gate (no 011 module
    releases until this amendment + ADR-0007 land).
  - specs/007-agentic-module/spec.md — amended in the same 011 work (apm folds into
    bailiff-mod-agentic; apm FRs migrate).
Unchanged in substance: I, II, IV, V, VI, VII, VIII.
Prior roadmap-only bump 2.1.0 → 2.2.0 (2026-07-14, spec 009 de-opinionation Q8/Q9) was
recorded in the roadmap; the constitution text was untouched then and is now at 2.3.0.

PRIOR SYNC IMPACT REPORT (2.0.0 → 2.1.0)
==================
Version change: 2.0.0 → 2.1.0
Bump rationale: MINOR — reconciles the constitution to the already-ratified
runtime-recompute reproduce model (roadmap v2.1.0) and the spec-010 delivery shape,
in the change that relies on them (governance: amend the principle in the same PR).
  - III. Multi-template reproduce order: "frozen at generation into a per-project
         reproduce recipe" → "recomputed at reproduce time from committed answers +
         pinned fetches with a stable tie-break; NO committed recipe." Faithful,
         agent-free reproduce (the principle's intent) is unchanged; only the
         ordering MECHANISM is corrected. Rationale rewritten to match.
  - I.   Glue enumeration: drop "per-project reproduce recipes"; state the glue is
         one bundled script `scripts/bailiff.py` (./scripts/bailiff.py / uv run), and
         that there is NO `[project.scripts] bailiff` console entry (was implicit in
         "no uvx bailiff"; now explicit for spec 010).
Reconciled in the same change:
  - docs/decisions/0001-copier-as-engine.md — reproduce no longer cites a generated
    `just reproduce`; names `copier recopy` directly / `scripts/bailiff.py`.
  - specs/010-delivery-reshape/spec.md — single bundled script shape; Q-010b resolved.
  - .specify/memory/roadmap.md — spec-003 Outcome, C-01/C-03, Vision de-frozen.
Unchanged in substance: II, IV, V, VI, VII, VIII.

PRIOR SYNC IMPACT REPORT (v1.0.0 → 2.0.0)
==================
Version change: 1.0.0 → 2.0.0
Bump rationale: MAJOR — the project's nature was redefined after a YAGNI review.
bailiff is NOT a published Python tool; it is a skills bundle + a copier template
family + a little deterministic glue. This redefines Principle I, replaces the
Principle VIII pydantic-seam mandate, and softens Principles II and IV (the
deprecated-surface adapter becomes conditional, not a standing requirement).

Modified principles:
  - I.   "Conductor, Not a Scaffolder" → "bailiff Is Skills + Templates + Minimal Glue"
         (redefined: no published package / no uvx bailiff premise)
  - II.  "Two-Phase Boundary, CLI Seam" → "Two-Phase Boundary; the Skill Conducts,
         Deterministic Helpers Execute" (seam is skill↔helper/CLI-of-copier, not a
         packaged pydantic API)
  - IV.  "Drive copier's Stable API Only; Isolate Deprecated Surface" → "Prefer
         copier's CLI + Static Config; Contain Any Deprecated Surface IF Used"
         (adapter is conditional on actually touching Template/Worker)
  - VII. Scope reworded to helpers + templates + generated reproduce recipes
  - VIII."Machine-Checkable Seam Contracts" (pydantic models + committed JSON
         Schema drift test) → "Documented, Dry-Run-Validated Handoff" (no pydantic
         mandate; validation is copier's own dry run)
Unchanged in substance: III (faithful agent-free reproduce), V (determinism +
trust), VI (template-author contract).
Removed sections: none (VIII repurposed, not deleted).

Templates requiring updates:
  ✅ .specify/memory/constitution.md (this file)
  ✅ .specify/memory/roadmap.md — revised in the same change (lean model)
  ✅ specs/001-bailiff-vertical-slice/{spec,plan}.md — rewritten to lean shape
  ⚠  .specify/templates/plan-template.md — Constitution Check reads this file
     dynamically; no edit needed
  ✅ README.md / pyproject.toml — reproduce + trust + "never runs tasks" claims
     corrected under spec 001 (FR-027); the uvx/PyPI framing is dropped

Follow-up TODOs: none deferred.
-->

# bailiff Constitution

bailiff is an agentic conductor for [copier](https://copier.readthedocs.io). copier
is the deterministic render + reproduce engine; bailiff decides *what* to render,
authors the *inputs*, and — where copier alone cannot coordinate — computes the
small deterministic facts (ordering, dependency edges, defaults) needed to drive
it. bailiff is delivered as **an agent skill + a family of copier templates + a
small published CLI** (`bailiff` on PyPI) that carries the deterministic glue.
Every principle
below is source-verified against copier 9.16.0 and derives from the architecture
decisions in `docs/decisions/`, which are binding.

## Core Principles

### I. bailiff Is Skills + Templates + Minimal Glue

bailiff is, in order of weight: (1) **an agent skill** — the `SKILL.md` procedure
that conducts the non-deterministic work; (2) **a family of copier templates**
(`bailiff-mod-*`) — the actual reusable product; and (3) **minimal deterministic
glue** — small helpers for the few things copier and an agent cannot do directly
(dependency-edge parsing, topological ordering — recomputed at reproduce time,
not frozen into the project — writing/reading defaults, dry-run validation,
catalog listing, and init-time collision/capability checks). This glue is
delivered as a **published CLI**: the `bailiff` distribution on PyPI with a
`[project.scripts] bailiff` console entry (`src/bailiff/cli.py`), invoked
`uvx bailiff` by users and `uv run bailiff` by repo contributors via the editable
install. **bailiff is the tool; bailiff-mod-\* are the modules.** The previously
bundled `scripts/bailiff.py` is REMOVED — the PyPI CLI is the sole invocation
path. Publishing does not license growth: the CLI stays in the glue bucket, and
glue MUST NOT grow into a re-implementation of what copier already provides. New
glue is justified only by a capability copier lacks (chiefly cross-template
coordination); when in doubt, prefer a copier invocation, a template feature, or
a documented agent step over new code.

Rationale: an audit of the full roadmap found that copier already owns the whole
single-template lifecycle; bailiff's durable value is the conducting skill, the
templates, and a thin sliver of coordination logic — not a wrapper around copier's
CLI. Packaging that sliver as an installable command (ADR-0008, spec 013) changes
its delivery, not its scope: `uvx bailiff` removes the copy-a-script friction while
Principle I's growth constraint keeps the glue minimal. Spec 011's FR-011 gate
("no new `src/bailiff/` code" within 011's scope) remains honored for its scope;
spec 013 is the governed engine exception, not a retroactive change to 011.

### II. Two-Phase Boundary; the Skill Conducts, Deterministic Helpers Execute (NON-NEGOTIABLE)

Work is split into a non-deterministic phase and a deterministic phase. The
**skill (phase 1)** does only judgment work: inspect a template, present its
questions, collect answer values, and explain/obtain consent for trust. It then
produces a **frozen set of inputs** (a documented plain-text handoff — e.g. a
copier `--data-file` / answers document plus the source, ref, and trust decision).
The **deterministic phase 2** — a copier invocation, optionally wrapped by a small
helper — validates and executes with ZERO agent/LLM involvement. Everything
mechanical MUST be runnable and testable without an LLM (shell and/or small Python
helpers, exercised by hermetic tests). The agent is NEVER in the reproduce path.

Rationale: confining the LLM to genuine judgment keeps the mechanical surface
deterministic and testable, whether that surface is a shell recipe or a helper
function.

### III. Reproduce Is Faithful and Agent-Free (NON-NEGOTIABLE)

Reproduce MUST replay the committed answers at the recorded revision:
`copier recopy --vcs-ref=:current: --defaults --overwrite` (equivalently
`run_recopy(vcs_ref=VcsRef.CURRENT, defaults=True, overwrite=True)`). Bare
`recopy` (no `vcs_ref`) silently resolves the LATEST tag and UPGRADES; it MUST
NEVER be used. Moving to a newer template version is a DISTINCT, explicit
operation (`copier update`). For a multi-template project, reproduce order is
**recomputed at reproduce time** from the committed `.copier-answers*.yml` files —
each template fetched at its recorded `_commit`, its `when:false` edges read, and
the whole topo-sorted with a stable, documented tie-break — NOT frozen into a
committed per-project recipe. Because the pins are identical, the recomputed edges
and order are identical, so reproduce is deterministic and needs no agent; and
because it derives solely from committed copier state, it depends on no
bailiff-authored file a user might forget to commit. `_tasks` run at both init and
reproduce; migrations are update-only. Reproduce is process-deterministic (same
pinned inputs → same commands), not necessarily config-consistent in the world,
because tasks may touch external state. **Task-output includes native-tool-generated
files** — a manifest produced by a tool's own init command (`uv init`, `bun init`,
`cargo new`, `go mod init`, `cdk init`) under a pinned toolchain (`mise .mise.toml`)
is task-output in exactly the sense LICENSE (`gh api`), `.gitignore` (`gitnr`), and
`apm.lock.yaml` (`apm install`) already are: process-deterministic and version-pinned,
NOT asserted config-consistent, and reproduced by re-running the guarded task, not by a
config/drift test. The config-consistent guarantee holds for **managed** renders (config
bailiff owns and the tool does not generate); the per-file boundary is drawn in
[[0007-native-command-scaffolding]].

Rationale: faithful reproduce is bailiff's headline guarantee and the reason the
pinning discipline exists; recomputing the order from committed answers + pinned
fetches keeps reproduce deterministic and agent-free while committing NO
bailiff-specific artifact into the project — the earlier "freeze a recipe into the
project" mechanism is superseded because a committed recipe is one more file that
can drift from, or be omitted alongside, the answers files that are the true state.

### IV. Prefer copier's CLI + Static Config; Contain Any Deprecated Surface IF Used

The deterministic phase MUST prefer copier's supported public surface: the
`copier` CLI (`copy` / `recopy` / `update` with `--data` / `--data-file` /
`--vcs-ref` / `--defaults` / `--overwrite` / `--trust`) or the public functions
`run_copy` / `run_recopy` / `run_update` plus `copier.errors`, `Settings`,
`Phase`, `VcsRef`. Template inspection MUST prefer **static parsing of `copier.yml`
and the cloned file tree** (which executes no template code and is safe on
untrusted sources) over programmatic introspection. IF, and only if, a helper
genuinely needs copier's deprecated/internal surface (`Template` / `Worker`), that
use MUST be confined to a single containment point guarded by a drift test — but
this adapter is not a standing requirement; a slice that reads `copier.yml`
statically needs none. copier is pinned `copier>=9.16,<10`.

Rationale: the cheapest correct discovery is a YAML read; the deprecated Template
object is only worth its containment cost when static parsing genuinely cannot do
the job (e.g. resolving `!include`/inheritance for arbitrary third-party
templates), which is a later concern, not a day-one mandate.

### V. Determinism Discipline via Pinning; Trust by Source

Because `_tasks` run at reproduce, config-consistency holds only as far as inputs are
pinned: template `#ref`, the copier version, `apm.lock`, and tool versions.
FORBIDDEN in bailiff-authored templates: `jinja2_time` (`{% now %}`) and the random
filters. The current date MUST be injected as an answer (e.g. `--data today=…`)
and referenced as `{{ today }}`, so it freezes into the answers file. Trust MUST
be configured via copier `settings.yml` `trust:` (a prefix matching the raw
pre-expansion URL — so bailiff MUST use fully-expanded `https://` URLs for both
fetch and trust storage), NEVER blanket `unsafe=True`. The deterministic phase
MUST NEVER write trust: it surfaces copier's trust refusal (or bailiff's own
`UntrustedSource`), and trust is recorded only by an explicit consent action.
Unattended reproduce/CI never prompts and MUST fail loudly if trust is absent.

Rationale: reproduce determinism is only as strong as its least-pinned input;
trust grants code execution, so consent stays with a human and out of the
non-interactive path.

### VI. Template-Author Contract (Enforced at Discovery)

Every bailiff-consumable template MUST: (a) ship a
`{{ _copier_conf.answers_file }}.jinja` file — VERIFIED: without it copier writes
NO `.copier-answers.yml` and the project is unreproducible; discovery MUST detect
its absence (statically) and refuse; (b) be one git repo = one template with clean
PEP 440 tags (`vX.Y.Z`) — copier silently discards non-PEP-440 tags; (c) declare
dependency edges as `when: false` hidden answers (`depends_on` / `run_after` /
`run_before`), statically read from `copier.yml`; (d) use copier's NEW
`_migrations` format (the `before`/`after` dict form is deprecated). Published
version labels are treated as immutable.

**Secrets (spec 005):** bailiff-authored templates (`bailiff-mod-*`, examples) MUST
NOT declare `secret: true` questions. Scaffolding generates files and structure —
credentials are virtually never needed. Secrets belong in the **generated
project's runtime config** (a template-authored `.env.example` + docs) or are
read from the **ambient environment** by tasks (e.g. `GH_TOKEN`, like the
existing LICENSE task). A `_task` that needs a token reads it from the env —
never a copier answer, never persisted, never agent-visible (Constitution II).
Enforcement: a contract lint (`tests/loop/test_secrets_policy.py`) reusing
`discovery.secret_questions` fails any in-repo bailiff template that declares a
secret question.

Rationale: these are copier's real, verified constraints; enforcing (a) and
version-resolvability at discovery turns silent unreproducibility into a loud,
early failure. The secrets rule eliminates the credential-in-answers risk by
construction rather than mitigating it — the maximally simple outcome (C-11).

### VII. Hardening Is a Per-Step Mandate

Hardening is NOT a trailing phase. EVERY spec MUST land, as part of its own
definition-of-done and scaled to what it actually ships: (a) its determinism
checks (e.g. a reproduce config/drift assertion where a render is involved); (b) its
error surfacing — copier raises both `copier.errors.*` AND a bare
`builtins.ValueError` for the missing-required-question case, and both MUST be
surfaced clearly (a helper that wraps copier translates them; a bare shell recipe
surfaces copier's own message and exit code); (c) tests for any glue it adds
(helpers unit-tested; templates exercised by an init+reproduce integration test;
a drift test only if a deprecated-surface adapter exists). No spec is complete with
its own hardening deferred.

Rationale: deferred hardening becomes never-done hardening; folding it into each
spec's DoD keeps the guarantees continuously true, without mandating ceremony a
given slice doesn't need.

### VIII. Documented, Dry-Run-Validated Handoff

The phase-1 → phase-2 handoff (the frozen inputs the skill produces) MUST be a
**documented, plain-text format** the skill can author and a human can read
(copier's own answers/`--data-file` shape wherever possible, extended only as
coordination requires). Validation MUST reuse copier's own capabilities — chiefly a
**dry run** (`--pretend`) and copier's answer validation — rather than a bespoke
re-implementation. Heavier machinery (typed models, generated JSON Schemas,
schema-drift tests) is NOT required and MUST NOT be introduced until a genuine
non-agent program consumes the handoff; until then the documented format plus a
dry run is the contract. `SKILL.md` documents the format.

Rationale: the handoff's only consumer today is the agent (which reads plain
text natively) and copier (which validates natively); a pydantic/JSON-Schema layer
would stabilize a contract for consumers that do not yet exist — the YAGNI the
project's own review flagged.

## Additional Constraints (copier facts, verified against 9.16.0)

- **Answer precedence** (verified): `--data` / `data=` (highest) > answers-file
  last execution > `user_defaults=` > `settings.yml` `defaults:` > template
  `copier.yml` default.
- **Three operations, three version behaviors:** `copy` (init) → latest tag or
  explicit ref; `recopy --vcs-ref=:current:` (faithful reproduce); `update`
  (upgrade) → from recorded revision to latest.
- **`--data` answers ARE persisted** to `.copier-answers.yml` even when never
  interactively asked — but only if the answers-file template exists (VI).
  `when: false` hidden answers are NOT persisted; read them from `copier.yml`.
- **Discovery via static parse is safe**; building copier's Jinja environment
  imports template-declared extensions (code execution) and is NOT trust-gated —
  so discovery MUST NOT build the environment or render template strings.
- **Catalog holds SOURCES, not pinned refs.** The reproduce pin lives in the
  generated project's answers file. `_src_path` MUST be the split (per-template)
  repo, never the authoring monorepo.
- **`_tasks`/migrations/`_jinja_extensions` are trust-gated.** A trusted source is
  the sanctioned enabler; `unsafe=True` is reserved for the narrow
  `_external_data`-outside-destination case only.

## Development Workflow & Quality Gates

- Work is spec-driven via SpecKit. This constitution and the ADRs gate every spec;
  each plan's `Constitution Check` MUST confirm compliance with Principles I–VIII
  or justify a deviation against the "skills + templates + minimal glue" ethos.
- The roadmap decomposes delivery into dependency-ordered specs; the first is a
  tight single-template slice. Coordination code (ordering/DAG, catalog parsing)
  appears only when a spec genuinely needs it, with evidence, not speculatively.
- Every change runs the project's checks before merge: template/loop integration
  tests, and — for any Python glue — `pytest`, `mypy`, and lint. Tests are
  hermetic and offline except clearly-marked live smoke checks.
- Dependencies (if any Python glue needs them) are added via the package-manager
  CLI (`uv add`), not manifest edits; glue stays dependency-light by default.

## Governance

This constitution supersedes ad-hoc practice. The ADRs in `docs/decisions/` are
the architectural source of truth and are binding; where an ADR predates this
v2.0.0 reframing (e.g. references to a `uvx`-runnable tool, a pydantic seam, or a
mandatory adapter), THIS constitution governs, and the ADR MUST be reconciled in
the same change that relies on it. Amending a principle REQUIRES updating the
governing ADR. All specs and PRs MUST verify compliance with Principles I–VIII;
complexity beyond them MUST be justified in writing against the "skills + templates
+ minimal glue" ethos, or be rejected.

Versioning: MAJOR for backward-incompatible principle removals or redefinitions,
MINOR for a new principle or materially expanded guidance, PATCH for
clarifications.

**Version**: 3.0.0 | **Ratified**: 2026-07-09 | **Last Amended**: 2026-07-15
