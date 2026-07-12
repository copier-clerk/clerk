# Feature Specification: clerk agentic-ecosystem module (spec 007)

**Feature Branch**: `007-agentic-module`

**Created**: 2026-07-10

**Status**: Draft (open-ended — see Open Questions; shape is deliberately framed for
review, not committed)

**Input**: Roadmap spec 007 (Agentic-ecosystem module — template content), governed
by the constitution v2.1.0 (Principles I and VI in particular) and ADR-0003. Depends
on spec 003 (multi-template ordering) and the retained ADR-0003 runtime-injection
fact; spec 002 catalog is the upstream context. Spec 010 delivery contract applies:
this module ships as template + task content, driven by the existing engine.

---

## Overview

Spec 007 is clerk's **distinctive value**, as stated in the Vision: the
agentic-ecosystem wiring (APM / MCP / SpecKit / ADR scaffolding) that turns a
generated project into a ready-to-use agentic toolchain. Crucially, the roadmap
frames this as **template content, not tool code**: the wiring is delivered inside a
copier template (`clerk-mod-apm`) whose questions, `_tasks`, and rendered files do the
work — driven by the existing discover/init/reproduce/ordering machinery specs
001/002/003/010 already built.

This spec is intentionally product-shaped and open-ended. The intent of this
document is to **frame the decisions clearly** and flag the significant open questions
for the orchestrator + user to resolve before implementation is scoped. Do not
read the "scope" sections as final commitments — they are a first-draft framing of
a plausible v1.

The module's job, at the highest level:

1. Ask the user which agentic components they want (APM package/version, which MCP
   servers, SpecKit bridge on/off, steering/ADR scaffolding on/off — details TBD by
   open questions).
2. Render the corresponding config files, scaffold files, and hook stubs into the
   generated project.
3. Where installation must run code (APM install), surface that as a trust-gated
   `_task` so the user consents and the action is reproducible.
4. Be faithfully reproducible: the rendered files + task side-effects replay
   identically at reproduce (subject to the same trust-gated-task semantics
   Constitution III defines).

---

## Motivating decisions

### D-007-1 — Template content, not tool code (Constitution I, C-11)

The agentic wiring is delivered entirely inside a `clerk-mod-apm` copier template.
No new `src/clerk/` module, no new `scripts/clerk.py` verb. The existing
`init_many` / `reproduce_many` engine drives it identically to any other template
layer. This is the Principle I mandate: clerk's value is in the templates, not in
growing the glue.

Deviation from this principle must be justified against C-11: new deterministic code
only for a capability copier lacks. APM questions, rendered config files, and
trust-gated tasks are all expressible as copier features — no gap.

### D-007-2 — Internal multiselect via copier's own mechanism (ADR-0003)

ADR-0003's retained fact: a `choices: "{{ catalog }}"` multiselect with runtime
injection via `--data` works from question 1. For 007's internal selections (which
APM packages, which MCP servers, which SpecKit extension set) the same mechanism
applies INTERNALLY INSIDE the template — not at the meta-template layer (ADR-0003
superseded that). `clerk-mod-apm` itself uses copier's `multiselect` type to let
the user select components; the catalog-like list is either baked into the template's
`copier.yml` (for a fixed, well-known set) or injected at runtime via `--data` (for
an extensible set). The choice between these is open question OQ-007-a.

### D-007-3 — APM install as a trust-gated `_task`

Installing APM packages runs code on the target project (writes files, possibly
runs install commands). This maps naturally to copier's `_tasks`: a shell command
gated by copier's trust mechanism (the source must be trusted, via `settings.yml`,
before `_tasks` run). The user consents at trust-record time (step 3 of the skill
procedure); reproduce replays the task under the same trust gate. This aligns with
how `clerk-template-example` handles its `gh api` LICENSE task today.

Consequence: a project that includes the APM module MUST have the source trusted;
clerk refuses at init if trust is absent (exit 3). This is already the behaviour
for any template with tasks (see `runner._require_trust_if_action_taking`).

### D-007-4 — SpecKit bridge and steering/ADR as rendered content

SpecKit integration and steering/ADR scaffolding are rendered static files (config,
`.specify/` directory skeleton, ADR template stubs) — not code that runs at
reproduce. They are template content: rendered at init, committed to the project,
and replayed byte-identically at reproduce. No new trust requirement beyond the
general APM `_task` above.

### D-007-5 — This module is ONE layer in a multi-template project

`clerk-mod-apm` declares its `depends_on` edges (at minimum: it must follow any base
language layer, so it can reference answers from earlier layers). The spec 003
ordering engine picks these up automatically. The agent presents it as one entry in
the catalog selection; ordering is computed by the engine, not by this spec.

---

## What is NOT in scope

- Base / language templates (spec 009) — those are the layers this module typically
  follows.
- Delivery mechanics (spec 010) — already implemented; this module honours the
  invocation contract.
- Catalog and ordering machinery (specs 002/003) — reused, not rebuilt.
- The APM marketplace / SpecKit extension catalog itself — those are upstream
  external projects. This module only generates the configuration wiring to consume
  them.
- Making the module work with APM versions or package sets not known at template
  time — that is an extensibility concern, not v1 scope (unless OQ-007-a resolves
  toward runtime injection).

---

## User Scenarios & Testing

### US1 — Generate a project with APM wiring (Priority: P1)

A developer selects `clerk-mod-apm` (alongside a base template); clerk applies the
layers in order; the generated project contains a complete `apm.yml`, dependency
entries, and MCP config skeleton. An APM install task runs (trust-gated), writing
the resolved `apm.lock.yaml`.

**Acceptance Scenarios**:
1. **Given** a selection of [base, apm] with `project_name=myapp`, APM packages
   selected, **When** `init`, **Then** the generated project contains an `apm.yml`
   with the correct package entries and the `apm.lock.yaml` is written by the task.
2. **Given** the same selection with the source UNTRUSTED, **When** `init`, **Then**
   clerk refuses at exit 3, naming the `trust add` command, before writing anything.

### US2 — Reproduce a project with APM wiring (Priority: P1)

A developer reproduces the project on a fresh machine; the `apm.yml` is re-rendered
byte-identically and the task re-runs (trust-gated).

**Acceptance Scenarios**:
1. **Given** a generated APM-wired project, **When** `reproduce`, **Then** `apm.yml`
   and all scaffolded files are re-rendered byte-identically (same recorded answers
   + pinned commit).
2. **Given** the task side-effects (APM install): **When** `reproduce`, **Then** the
   task re-runs under trust (reproduce is NOT agent-free for task side-effects, per
   Constitution III — `_tasks` run at both init and reproduce).

### US3 — Select a subset of agentic components (Priority: P1)

A developer opts in to APM + SpecKit but out of MCP servers; the generated project
contains APM config and SpecKit scaffold but no MCP stubs.

**Acceptance Scenarios**:
1. **Given** APM + SpecKit selected, MCP deselected, **When** `init`, **Then** MCP
   config files are absent; APM + SpecKit files are present.
2. **Given** a different developer selects APM only, **When** `init`, **Then**
   SpecKit scaffold is absent.

### US4 — Steering / ADR scaffolding on opt-in (Priority: P2)

A developer opts in to steering + ADR scaffolding; the generated project contains
`.claude/` or equivalent steering stubs and an `docs/decisions/` ADR template.

### Edge Cases

- **No components selected**: if every component is deselected, `clerk-mod-apm`
  renders nothing meaningful — consider whether to refuse or produce an empty-safe
  output. (OQ-007-d)
- **APM task fails**: copier surfaces the task failure; clerk translates via
  `_translate`. The generated files are already written; the task failure is
  distinct from a render failure.
- **Source pinning at reproduce**: the APM `_task` install command MAY fetch
  packages from the network at reproduce time. Pin versions in the task command to
  make reproduce deterministic (or accept network variance — OQ-007-e).
- **SpecKit extensions catalog**: at template render time, the SpecKit catalog URL
  may be baked in or configurable. Future catalog version changes could make
  reproduce diverge — pin or document.

---

## Requirements

### Functional Requirements

These are a first draft — subject to revision once open questions are resolved.

- **FR-001**: `clerk-mod-apm` MUST be a valid copier template: ships the
  `{{ _copier_conf.answers_file }}.jinja` file (Constitution VI); has clean PEP 440
  tags; declares `when:false` dependency edges.
- **FR-002**: The template MUST expose questions for each agentic component category
  in scope (APM packages, MCP server set, SpecKit on/off, steering/ADR on/off). The
  exact question shape depends on OQ-007-a (fixed choices vs runtime injection).
- **FR-003**: Selecting APM packages MUST render a valid `apm.yml` in the generated
  project; selecting MCP servers MUST render the appropriate MCP config skeleton;
  selecting SpecKit MUST render the `.specify/` skeleton; selecting steering/ADR MUST
  render steering stubs and the ADR directory.
- **FR-004**: APM install (and any other code-executing action) MUST be a `_task`,
  not a render-time side effect, so it is trust-gated and runs at both init and
  reproduce (Constitution III / V).
- **FR-005**: The template MUST declare `depends_on` edges for any base layer it
  must follow (so the spec 003 ordering engine sequences it correctly).
- **FR-006**: Questions that reference earlier layers' answers (e.g. `project_name`
  from a base layer) MUST use copier's `default: "{{ project_name }}"` mechanism
  (threaded via `data=`, ADR-0003). The template MUST NOT hardcode assumptions about
  which base layer was applied.
- **FR-007**: The template MUST be testable in isolation (with a minimal stub base
  layer providing the expected threaded answers) and as a layer in a multi-template
  project.
- **FR-008**: APM package version pins MUST be committed to the answers file (via
  copier's answer persistence) so reproduce uses the same versions.
- **FR-009**: The `_task` commands MUST NOT use ambient PATH commands that are not
  explicitly declared; they MUST reference versioned, pinned tools (e.g. `uv run
  apm==<version>` not bare `apm`). (OQ-007-e is the reproduce-determinism angle.)
- **FR-010**: The SKILL.md procedure MUST document the apm module step: when to
  include it, what the multiselect presents, trust consent for the task, and the
  handoff shape.

### Key Entities

- **`clerk-mod-apm`**: the copier template. Lives in the `clerk` monorepo under its
  own directory; fans out to a read-only `copier-clerk/clerk-mod-apm` repo at release
  (spec 008).
- **`apm.yml`**: the rendered APM configuration file — the primary rendered output.
- **`apm.lock.yaml`**: written by the APM install `_task`, NOT by the render. Cannot
  be byte-identical at reproduce if APM resolution changes between runs — this is a
  known tension with Constitution III's "process-deterministic" reproduce model.
- **APM packages / MCP servers / SpecKit / steering-ADR**: the selectable component
  categories (details in OQ-007-a, OQ-007-b, OQ-007-c).

---

## Success Criteria

These are provisional — subject to scope resolution in Open Questions.

- **SC-001**: A generated project with APM wiring contains a correct `apm.yml` and
  the task has produced `apm.lock.yaml` on a trusted source.
- **SC-002**: Reproduce re-renders `apm.yml` byte-identically from committed answers
  and re-runs the task on a trusted source.
- **SC-003**: Component deselection leaves the corresponding files absent from the
  generated project.
- **SC-004**: An untrusted source is refused at init (exit 3) before any write.
- **SC-005**: A multi-template project with [base, apm] applies base first (via
  spec 003 ordering) and threads `project_name` + other base answers into the APM
  layer.
- **SC-006**: The template is self-contained: it can be applied in isolation (no
  base layer), producing a standalone APM config with defaults for all threaded
  questions.

---

## Out of scope

- Base / language templates (spec 009).
- Delivery mechanics (spec 010 — already done).
- Catalog and ordering machinery (specs 002 / 003 — consumed, not built).
- APM marketplace, SpecKit extension catalog, MCP server registry — upstream external
  projects; this module only generates config wiring.
- Brownfield adoption (the deferred spec).

---

## Open Questions

**This section is the substantive product of this first-draft spec. The orchestrator
and user MUST resolve these before implementation is scoped.**

---

### OQ-007-a — Fixed choices vs runtime-injected multiselect (HIGH PRIORITY)

**The question**: For the internal APM packages / MCP servers selection, should
`clerk-mod-apm` use:

- **(A) Fixed `choices:` in `copier.yml`** — the template bakes in a curated list of
  well-known APM packages and MCP servers. Simple; no injection machinery. Drawback:
  the list is frozen at template version time; adding a package requires a template
  release. Users with custom/private packages need a template fork or can only use
  `answers` to override.

- **(B) Runtime-injected multiselect via `--data`** — ADR-0003's retained mechanism:
  the agent (or a catalog step) injects `--data apm_packages=[…]` and the template
  uses `choices: "{{ apm_packages }}"`. More flexible; the agent can present a
  dynamic/up-to-date list. Drawback: requires the agent to produce the inject list;
  more moving parts; the skill becomes non-trivial (it must build the list from some
  source).

- **(C) Hybrid** — a baked-in curated set as the default choices, with a free-text
  "additional packages" question for unlisted ones.

**Tradeoffs**:
- (A) is the simplest template. It aligns with C-11 (no new tool code). The list
  ages out-of-date but is correctable by a minor template bump.
- (B) reuses ADR-0003's verified mechanism. But it pushes more work onto the agent
  (phase 1) and requires the skill to know where to source the catalog. It also
  means the template cannot be used standalone without the injected data.
- (C) is pragmatic for v1: bake in the clerk-native packages (speckit, dep-audit,
  secrets-scan, etc.) and let the user add custom ones via a string question.

**Lean (flagged for review)**: (C) or (A) for v1 — simpler template, skill stays
thin. (B) is a later extensibility concern. Resolve before planning.

---

### OQ-007-b — Component scope: what is in v1?

**The question**: Which of these component categories are in scope for the first
shipped version?

| Category | What it generates | Complexity | In v1? |
|---|---|---|---|
| APM `apm.yml` + install task | `apm.yml`, task to install | Medium | TBD |
| MCP servers config | `.mcp.json` or equivalent | Low–Medium | TBD |
| SpecKit bridge | `.specify/` skeleton, `speckit-gate` config | Medium | TBD |
| Steering/ADR scaffolding | steering stubs, `docs/decisions/` | Low | TBD |
| `apm.lock.yaml` generation | Task-driven; network call | Medium | TBD (reproduce tension) |

**Tradeoffs**:
- A monolithic "all in one template" is simpler to ship but harder to maintain and
  test in isolation; each category is also independently valuable.
- Splitting into `clerk-mod-apm`, `clerk-mod-mcp`, `clerk-mod-speckit`,
  `clerk-mod-steering` lets users mix-and-match and makes each template focused and
  testable. But it multiplies templates and increases the 003-ordering complexity (more
  `depends_on` edges to declare and test).
- A phased approach: start with APM only, add others as separate templates later.

**Key question for the user**: Is there value in shipping MCP/SpecKit/steering in
the same release, or does APM alone (the baseline that makes clerk's own toolchain
self-describing) justify a v1? The spec-010 invocation contract and spec-003 ordering
would be exercised even by APM alone.

**Flag**: The roadmap entry says "an `apm` copier template" (singular) with all four
in scope. This spec flags the split-vs-monolithic decision as unresolved. Resolve
before planning.

---

### OQ-007-c — SpecKit bridge depth

**The question**: "SpecKit bridge" could mean:

- **(A) Config scaffolding only**: render `.specify/constitution.md` stub,
  `apm.yml` entries for speckit packages, `integration.json`. No SpecKit-specific
  skill step. Simple.
- **(B) Full SpecKit setup**: run `speckit-setup` as a `_task` (or instruct the
  user to run it post-init). More useful but `speckit-setup` is a skill, not a
  shell command — it cannot be a copier `_task` directly.
- **(C) Hybrid**: render the config files (constitution stub, extensions, etc.) as
  template content so SpecKit is usable out-of-the-box without running a separate
  setup; add a `_task` only if a shell-executable install step is identified.

**Lean**: (A) or (C) — template content wins over a skill-invocation task. If
SpecKit setup is a YAML-file concern (which it largely is: the `.specify/` directory
structure), then rendering it as template content is correct. Resolve at planning.

---

### OQ-007-d — Empty selection behaviour

**The question**: If a user selects no APM packages, no MCP servers, SpecKit=off,
steering=off — should `clerk-mod-apm` render nothing? refuse? produce a minimal
scaffold?

Options:
- Render an empty but valid `apm.yml` skeleton (the safest; project can be
  augmented later).
- Refuse with a clear message: "no agentic components selected; skip this template".
- Let the template render silently empty (rely on the user knowing what they did).

**Lean**: produce a minimal valid skeleton (an `apm.yml` with no dependencies is
still a valid starting point). Resolve at planning.

---

### OQ-007-e — Reproduce determinism for network-calling `_tasks`

**The question**: The APM install `_task` calls the network (fetches packages).
Constitution III says reproduce is "process-deterministic (same pinned inputs →
same commands), not necessarily byte-identical in the world, because tasks may touch
external state." So `apm.lock.yaml` may differ between runs if the upstream APM
resolution changes.

Options:
- **Accept non-byte-identical lock**: document this explicitly; the reproduce
  contract holds for rendered files, not lock files. Simplest.
- **Commit the lock file**: if `apm.lock.yaml` is committed to the project,
  reproduce re-renders it from the answers (but the task would overwrite it). This
  is a product decision about whether the lock is generated content or committed
  state.
- **Pin the APM version strictly in the task command**: `uv run apm==X.Y.Z install`
  so the resolution is as deterministic as possible. Still network-dependent.

**This is also a question about the role of `apm.lock.yaml`**: is it a generated
artifact (should be committed and can be reproduced) or an external state file (like
a Poetry `.lock` that the user pins separately)?

**Flag for the user**: this is a product decision about the reproduce contract for
task side-effects. Resolve before planning.

---

### OQ-007-f — One monolithic template vs several focused ones

Restates OQ-007-b from the template-architecture angle.

If all four categories (APM/MCP/SpecKit/steering-ADR) ship as ONE `clerk-mod-apm`
template:

- Pro: one `depends_on` edge to declare; simpler catalog entry.
- Con: one big `copier.yml` with many conditional sections; harder to test each
  category independently; a user who only wants MCP gets APM questions too.

If each ships as a separate `clerk-mod-*` template:

- Pro: each is focused and independently selectable; existing spec 003 machinery
  handles ordering naturally.
- Con: more templates to maintain; more fan-out repos (spec 008); more `depends_on`
  edges to get right.

**Lean**: split is architecturally cleaner and fits the `clerk-mod-*` family model
better. The monolith is an expedient shortcut. But the roadmap entry says "an `apm`
copier template" (singular). Flag for the user.

---

### OQ-007-g — Relationship to spec 009 (project-setup port)

**The question**: Spec 009 ports the project-setup module set as `clerk-mod-*`
templates. Some of those (e.g. `clerk-mod-precommit`, `clerk-mod-ci`) may naturally
`depends_on` or `run_before` `clerk-mod-apm`. Is 007 a prerequisite for 009, or can
they be developed independently?

Also: should `clerk-mod-apm`'s APM packages question include entries for the
clerk-native packages already in clerk's own `apm.yml` (speckit, dep-audit,
secrets-scan)? That list is in-repo and known; baking it in is the simplest v1.

**Flag**: ordering dependency between 007 and 009. Resolve before planning.

---

## Governing constitution & ADRs

- Constitution I (template content, not tool code — C-11: new code only for copier
  gap; there is no copier gap here), II (two-phase; the APM install task is the
  deterministic phase-2 side-effect, not agent-run), III (reproduce: rendered files
  are byte-identical; task side-effects are process-deterministic — see OQ-007-e),
  V (trust-gated tasks; reproducibility via pinned task commands), VI
  (template-author contract: answers-file `.jinja`, PEP 440 tags, `when:false`
  edges).
- ADR-0003 (retained fact: `--data` runtime injection in scope from question 1 —
  relevant for OQ-007-a option B; internal multiselect is inside the template, not
  the meta layer).
- ADR-0001 (copier as engine; trust mechanism).
- Constraints: C-01 (no new tool, template content), C-05 (trust by source,
  determinism via pinning), C-06 (template-author contract), C-11 (glue only for
  copier gap — no gap here; all content is template content).
- Depends on: spec 002 (catalog — module is a catalog entry), spec 003
  (multi-template ordering — module declares edges, engine sequences it), spec 010
  (delivery contract — module is invoked via the existing bundled script surface).
- Informs: spec 008 (fan-out — module gets a `clerk-mod-apm` read-only repo),
  spec 009 (project-setup — likely `run_before` or `depends_on` adjacency).
