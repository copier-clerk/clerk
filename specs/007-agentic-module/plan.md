# Implementation Plan: clerk agentic-ecosystem module (spec 007)

**Branch**: `007-agentic-module` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Status**: Draft — BLOCKED ON OPEN QUESTIONS. This plan captures the known design
shape and flags the decisions that must be resolved before tasks can be generated.
See `spec.md` Open Questions (OQ-007-a through OQ-007-g) for the full list.

**Input**: Feature specification from `specs/007-agentic-module/spec.md`,
constitution v2.1.0, ADR-0001/0003.

---

## Summary

Spec 007 delivers clerk's distinctive value: the `clerk-mod-apm` copier template
that wires an agentic toolchain (APM / MCP / SpecKit / steering-ADR) into a
generated project. The implementation is **pure template + task content** — no new
`src/clerk/` module, no new `scripts/clerk.py` verb. The existing 003/010 engine
drives it identically to any other template layer.

The plan has three logical phases:

1. **Template skeleton** — scaffold `clerk-mod-apm/` as a valid copier template
   (answers-file `.jinja`, `copier.yml`, PEP 440 tags, `depends_on` edges), prove
   the spec 003 ordering engine picks it up correctly as a multi-template layer.
2. **Component content** — add the questions + rendered files for each in-scope
   component (APM, MCP, SpecKit, steering-ADR — subject to OQ-007-b/f scope decision)
   and the trust-gated `_tasks` for install steps.
3. **Hardening** — end-to-end tests, skill update, reproduce validation.

**Blocked items** (must resolve before tasks): OQ-007-a (question shape / injection
mechanism), OQ-007-b (v1 component scope), OQ-007-c (SpecKit bridge depth),
OQ-007-f (monolith vs split).

---

## Technical Context

**Language**: copier template (YAML + Jinja2). No new Python. The template lives in
the authoring monorepo; fan-out to `copier-clerk/clerk-mod-apm` is spec 008.

**Primary Dependencies**: copier ≥9.16,<10 (already in repo). The `_tasks` will
invoke the APM CLI; the pinned form is TBD pending OQ-007-e.

**Storage**: the template renders into the target project's directory. Key files
generated:
- `apm.yml` (rendered from template; committed to project)
- MCP config (e.g. `.mcp.json`) — if in scope
- `.specify/` skeleton — if SpecKit in scope
- Steering stubs (e.g. `.claude/`) and `docs/decisions/` — if in scope
- `apm.lock.yaml` — task side-effect; see OQ-007-e for reproduce implications

**Testing**: hermetic, offline. Multi-template integration tests via local git
fixtures (extend the spec 003 conftest pattern): a minimal stub base layer + the
APM layer. Assert rendered files are correct, `depends_on` edge is honoured,
reproduce is byte-identical for rendered files.

**Target Platform**: developer workstations + CI (macOS/Linux). Template tasks must
work on both.

**Project Type**: a `clerk-mod-*` copier template in the authoring monorepo.
No new Python package, no new CLI surface.

**Performance**: none special. Template render is fast; the APM install `_task`
may take seconds over the network — acceptable and documented.

**Constraints**:
- Template content only (Constitution I / C-11).
- Trust-gated `_tasks` for all code-running steps (Constitution V).
- Answers-file `.jinja` required (Constitution VI).
- PEP 440 tags; `when:false` dependency edges; reproducible rendered output.
- APM install task must be pinned for process-determinism (OQ-007-e).
- The template MUST NOT assume a specific base layer — it threads via `data=`.

---

## Constitution Check

*GATE: evaluated against constitution v2.1.0. Initial gate: **PASS** (with the
noted conditions).*

| Principle | Gate | How this plan satisfies it |
|---|---|---|
| I — Skills + templates + minimal glue | PASS | 007 is PURE TEMPLATE CONTENT. No new `src/clerk/` module, no new `scripts/clerk.py` verb, no new tool. The APM install is a `_task` inside the template — copier's own mechanism. C-11 confirmed: there is no copier gap requiring coordination glue; questions + rendered files + `_tasks` cover everything. |
| II — Two-phase boundary | PASS | Phase 1 (agent): present questions, collect answers, obtain trust consent, author run-spec. Phase 2 (deterministic): `run_copy` → copier renders files and runs `_tasks`. The agent is NEVER in the reproduce path. |
| III — Faithful, agent-free reproduce | PASS (with condition) | Rendered files reproduce byte-identically from committed answers + pinned commit. `_tasks` re-run at reproduce under trust (Constitution III explicitly states tasks run at both init and reproduce). The lock-file tension (OQ-007-e) is a documented known limitation, not a violation — Constitution III's "process-deterministic not byte-identical" carve-out covers it. |
| IV — Prefer CLI + static config | PASS | Template uses static `copier.yml` questions + Jinja rendering. No `Template`/`Worker` adapter. Discovery reads edges statically (existing `discovery.py`). |
| V — Determinism via pinning; trust by source | PASS (condition: OQ-007-e) | The source is trusted via `settings.yml` before `_tasks` run. Task commands MUST pin tool versions (OQ-007-e). `today` is threaded from earlier layers or injected by clerk. The `when:false` edges carry no secrets. |
| VI — Template-author contract | PASS | `clerk-mod-apm` ships `{{ _copier_conf.answers_file }}.jinja`, has PEP 440 tags, declares `depends_on` edges as `when:false` hidden answers, uses the new `_migrations` format. Enforced at discovery. |
| VII — Hardening per-step | PASS | DoD = render-output test (correct `apm.yml` per selection), reproduce byte-identical test for rendered files, trust-refusal test (exit 3 on untrusted source), component-deselection test (absent files), multi-template ordering test (base before apm), all-gaps preflight test. No adapter → no drift test. |
| VIII — Documented, dry-run-validated handoff | PASS | Run-spec is the standard multi-template shape (spec 003 contract). Validation reuses copier `--pretend`. The `_task` step is documented in the contract file and SKILL.md. No pydantic/JSON-Schema. |

**Complexity deviation**: none. This is the simplest possible delivery — a copier
template with no new tool code. Any deviation from "pure template content" must be
justified against C-11.

---

## Project Structure

### Documentation (this feature)

```text
specs/007-agentic-module/
├── spec.md              # The agentic module spec (this draft)
├── plan.md              # This file
├── contracts/
│   └── agentic-module.md  # Template questions shape, rendered file inventory,
│                          #   task commands, depends_on edges, exit codes
└── tasks.md             # Generated after open questions resolve (/speckit.tasks)
```

### Template (repository root)

```text
clerk-mod-apm/           # The copier template (location in monorepo TBD — see OQ-007-f)
├── copier.yml           # Questions: component selection, APM packages, MCP servers,
│                        #   project_name default (threaded), SpecKit on/off, steering on/off.
│                        #   Hidden when:false: depends_on declaration.
│                        #   _tasks: APM install command (trust-gated).
├── {{ _copier_conf.answers_file }}.jinja   # Required for reproducibility (VI).
├── apm.yml.jinja        # Rendered APM config (conditional on APM selection).
├── .mcp.json.jinja      # Rendered MCP config (conditional on MCP selection).
├── .specify/            # SpecKit scaffold (conditional on SpecKit selection).
│   ├── constitution.md.jinja
│   └── ...
├── .claude/             # Steering stubs (conditional on steering selection).
│   └── CLAUDE.md.jinja
└── docs/decisions/      # ADR template (conditional on ADR selection).
    └── 0001-example.md.jinja
```

*(Exact paths TBD; depends on OQ-007-b scope and OQ-007-f monolith-vs-split
decision. If split, each component gets its own `clerk-mod-*` template directory.)*

### Source code changes

**None** — this spec adds no `src/clerk/` code. The only changes to existing Python
are:

- `scripts/clerk.py` — NO CHANGE. The existing `init`/`reproduce` surface drives
  the new template identically to any other.
- `src/clerk/` — NO CHANGE. The ordering, discovery, catalog, runner machinery is
  reused unchanged.

### Skill + documentation changes

```text
skills/clerk/SKILL.md    # EXTEND: document the agentic-module step (when to
                         #   include clerk-mod-apm, what the multiselect presents,
                         #   trust consent for the _task, handoff shape). Reference
                         #   specs/007-agentic-module/contracts/agentic-module.md.
```

### Tests

```text
tests/
├── conftest.py          # EXTEND: add clerk-mod-apm fixture (local git, valid
│                        #   template, minimal questions, stub _task).
└── loop/
    ├── test_apm_render.py        # US1/US3 — render + component selection (correct
    │                             #   apm.yml, absent files for deselected components).
    ├── test_apm_reproduce.py     # US2 — reproduce byte-identical for rendered files.
    ├── test_apm_trust.py         # US1 SC-004 — untrusted source refuses exit 3.
    └── test_apm_ordering.py      # US1 SC-005 — [base, apm] applies base before apm
                                  #   via spec 003 depends_on edge.
```

---

## Known Blocked Decisions

The following planning decisions are deliberately deferred to open-question
resolution. Tasks CANNOT be generated until these are resolved.

| # | Question | Blocks |
|---|---|---|
| OQ-007-a | Fixed vs runtime-injected multiselect | `copier.yml` question shape for APM packages + MCP servers |
| OQ-007-b | v1 component scope (APM / MCP / SpecKit / steering-ADR) | Which `.jinja` files to author; number of `_tasks`; test scope |
| OQ-007-c | SpecKit bridge depth (config-only vs task-driven setup) | Whether SpecKit generates a `_task` or only `.jinja` files |
| OQ-007-e | Reproduce contract for `apm.lock.yaml` (commit vs document-as-variance) | `_task` pinning; whether lock file is a `.jinja` output or task side-effect |
| OQ-007-f | One monolithic template vs several focused `clerk-mod-*` templates | Directory structure; number of fan-out repos; `depends_on` edge graph |
| OQ-007-g | Dependency ordering relative to spec 009 | Whether 007 can be built independently or must wait for 009 base templates |

---

## Complexity Tracking

No constitutional violations. This plan intentionally produces **zero new Python
code** — a direct consequence of Principle I and C-11. All work is template content
(YAML + Jinja2), and the existing machinery drives it. If any planning decision
discovers a genuine copier gap requiring coordination glue, that deviation must be
justified in writing against C-11 before it is added.

Post-open-question-resolution, the plan will be updated and tasks generated via
`/speckit.tasks`.
