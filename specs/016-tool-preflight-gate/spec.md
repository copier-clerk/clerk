# Feature Specification: Whole-plan tool-preflight gate (spec 016)

**Feature Branch**: `016-tool-preflight-gate`

**Created**: 2026-07-20

**Status**: Draft — research-first. Motivated by a cleanroom run against `bailiff 0.4.1`:
a stack selecting a module whose required binary was absent failed mid-render with
copier's raw `command not found` (exit 127), on an already-materialized tree.

**Input**: The 015 cleanroom finding (missing `lefthook`/`pre-commit`/`aws` binaries) plus
the architectural fact that copier RENDERS the whole template before it runs `_tasks` —
so a `_task` tool-check fires only after files are written. Governed by the constitution
(v3.0.0) and ADRs 0001–0008. Builds on the spec-014/015 engine.

---

## Overview

Every task-bearing `bailiff-mod-*` module already ships a `_task` preflight that fails
loud with install guidance when a required binary is absent. Two structural weaknesses
remain, both from *where* that check runs:

1. **It runs after render.** copier renders the full template, then executes `_tasks`.
   A missing-tool `_task` therefore aborts on an already-written tree (a partial project;
   in `init_many`, a half-built multi-layer stack with base already committed).
2. **It is per-layer, not whole-plan.** Each module discovers its own missing tool only
   when its render turn comes — a stack missing three tools reports them one failed
   render at a time, never upfront.

Spec 016 adds a declarative required-tools manifest field and a whole-plan engine gate
that runs BEFORE any file is written, alongside the existing pre-render checks (trust,
reproducibility, secrets, `_external_data` deps, collision scan). The `_task` guards
stay as an enforcement backstop (they also cover reproduce/update task execution).

Philosophy (Constitution I): enforce structure, don't trust discipline. A required tool
should be *declared* and *checked by the engine before writing*, not merely guarded by a
shell line the engine cannot see.

---

## User Scenarios & Testing

### US1 — Missing tool fails before any write (primary)

A user inits a stack that includes a module requiring a binary that is not on PATH. The
engine refuses BEFORE rendering any layer, naming the tool, the module that needs it, and
an install hint. No file is written; no partial tree is left.

**Acceptance**: init `[base + <module requiring absent tool>]`; exit non-zero; the dest is
empty (or absent); the error names the tool + module + install hint.

### US2 — Whole-plan report

A stack missing multiple tools reports ALL of them in one pass, not one-per-failed-render.

**Acceptance**: init a stack missing two distinct tools; the single error lists both.

### US3 — Conditionally-required tools respect their gate

A tool required only under an answer (e.g. `install_hooks=true`, `aws_validate=true`) is
checked only when that condition holds; opting out (`install_hooks=false`) needs no binary.

**Acceptance**: init the module with the opt-out answer and the tool absent → succeeds; with
the opt-in answer and the tool absent → fails at the gate.

### US4 — Reproduce/update unaffected by the init-time gate design

The gate is an init-plan concern. reproduce/update keep their own trust/task guards; the
tool gate MUST NOT make reproduce of a committed project fail differently than today.

**Acceptance**: reproduce of a project whose tools are present behaves unchanged.

### Edge cases

- A module declares a tool already provisioned via `mise` (the `command -v mise → mise
  install` chain): the gate checks `mise` presence, not the mise-provisioned tool (that
  is mise's job) — see FR-005.
- A tool name that is a shell builtin or absolute path → [NEEDS DESIGN: normalize to the
  base command; resolve in plan.md].
- No `_bailiff_requires` declared → the gate is a no-op for that module (back-compat).

---

## Requirements

### Manifest declaration

- **FR-001**: A module MAY declare `_bailiff_requires`, a list of entries; each entry is
  either a bare tool name (`"lefthook"`) or a mapping `{tool: <name>, when: <answer-key>}`
  making the requirement conditional on a truthy answer (mirrors a `_task` `when:`).
- **FR-002**: Discovery parses `_bailiff_requires` into the `Discovery` record and
  validates the shape (list of strings / `{tool, when}` maps); malformed → fail loud at
  discovery, naming the module.
- **FR-003**: `_bailiff_requires` is advisory metadata, not a question or an edge — it is
  never written to the answers file and never affects ordering.

### Engine gate

- **FR-004**: `init`/`init_many` run a tool-preflight BEFORE the first `run_copy`, after the
  existing trust/reproducibility/secret/`_external_data`/collision checks. For every
  selected module, for each `_bailiff_requires` entry whose `when` (if any) is truthy given
  that layer's answers, check `shutil.which(tool)`. Any misses → raise a single error
  listing every `(tool, module, install-hint?)`, before any write.
- **FR-005**: The gate checks the DECLARED tool only. A module that provisions tools via
  `mise` declares `mise` (not the provisioned tool); mise's own `mise install` remains the
  mechanism for the rest (unchanged).
- **FR-006**: `--check` (preflight/dry-run) runs the tool gate too, so a dry run surfaces
  missing tools without writing.

### Backstop

- **FR-007**: The per-module `_task` `command -v` guards REMAIN (they also protect the
  reproduce/update task-execution paths and third-party modules that omit
  `_bailiff_requires`). The engine gate and the `_task` guard are complementary.

### Authoring

- **FR-008**: The FR-018 authoring guide + `_cross-cutting.md` document `_bailiff_requires`
  as the canonical way to declare a module's required tools, with the `command -v` `_task`
  guard as the paired backstop. `check_modules` validates the field.

---

## Success Criteria

- **SC-001**: A stack missing a required tool fails BEFORE any file is written (US1).
- **SC-002**: A stack missing N tools names all N in one error (US2).
- **SC-003**: A conditionally-required tool is checked only when its `when` answer is truthy
  (US3).
- **SC-004**: Every first-party task-bearing module declares `_bailiff_requires` matching
  the binaries its `_tasks` actually invoke (validated by `check_modules`).
- **SC-005**: `--check` surfaces missing tools without writing (FR-006).
- **SC-006**: No regression to reproduce/update behavior (US4).

---

## Out of scope

- Parsing arbitrary shell in `_tasks` to auto-derive required tools (fragile, unsafe) —
  tools are DECLARED via `_bailiff_requires`, not inferred.
- Installing missing tools for the user (bailiff reports + hints; it never installs).
- Version pinning of tools (a tool's version is the tool's/mise's concern; the gate checks
  presence only).
- The mise-provisioned tool chain (unchanged; the gate checks `mise` presence only).

---

## Dependencies

- Spec 014/015 engine (discovery parse surface, `init_many` pre-render check band).
- Precedent: the existing pre-render guards (`_check_external_data_deps`,
  `_scan_init_collisions`) are the band this gate joins.

## Governed by

ADR-0001..0008; Constitution I (enforce structure), II (LLM-free engine), V (fail loud);
C-11 (engine exception).
