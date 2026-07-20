# Implementation Plan: Whole-plan tool-preflight gate (spec 016)

**Branch**: `016-tool-preflight-gate` · **Spec**: `spec.md` (this dir) ·
**Depends on**: the spec-014/015 engine on `main` (discovery parse surface,
`init_many` pre-render check band, `_canonical_dest`, agent seam).

## Summary

Add `_bailiff_requires` to the module manifest and a whole-plan engine gate that checks
every declared tool with `shutil.which()` BEFORE the first `run_copy`, alongside the
existing trust / reproducibility / secret / `_external_data` / collision checks. A missing
tool fails the whole init before any file is written, naming every missing
`(tool, module)` in one error. The per-module `_task` `command -v` guards stay as the
backstop (they also cover reproduce/update and third-party modules).

## Technical Context

copier renders the full template, then runs `_tasks` — so a `_task` tool-check fires after
files are written (partial tree; in `init_many`, base already committed). The gate moves
the check into bailiff's pre-render band, where trust/collision already run before any
write. Discovery already parses top-level manifest keys (`_post_tasks`, `_external_data`,
`_agent_tasks`); `_bailiff_requires` is one more. C-11 engine change; no constitution
amendment.

## Key design decisions

### D1 — `when` is a truthy answer-key check, not an expression

FR-001's `{tool, when}` gates a tool on a single answer key being truthy (covers
`install_hooks`, `aws_validate`). It deliberately does NOT evaluate expressions like
`python_pkg_manager == 'uv'`:

- A module with value-conditional tools (python: `uv` xor `pdm`) either declares the
  UNION it might need, or omits the value-conditional tool from `_bailiff_requires` and
  relies on the `_task` backstop for it.
- Rationale: parsing/evaluating answer expressions in the engine reintroduces the fragile
  shell-introspection the spec rejects. A bare truthy key is enough for the real
  fail-fast cases and stays trivially deterministic.

### D2 — The gate checks the DECLARED tool only (FR-005)

Modules that provision tools via `mise` declare `mise`; the gate checks `mise` presence,
never the mise-provisioned tool. This matches the existing `command -v mise → mise install`
chain — `mise` is the single real prerequisite; the rest is mise's job.

### D2a — Declare a tool only when its absence is FATAL

A module declares `_bailiff_requires` for a tool only if the module cannot proceed without
it (base: `git`/`gh`/`gitnr`/`mise` fail with exit 1). A tool whose in-`_task` guard is
**non-fatal by design** — `bailiff-mod-github-repo`/`gitlab-repo` skip repo creation and
exit 0 with a manual hint when `gh`/`glab` is absent — declares NOTHING, because a gate
entry would hard-fail a run the module is built to complete gracefully. The gate enforces
hard prerequisites; it does not override a module's intentional graceful-degrade path.

### D3 — `when` answers come from the same per-layer answer dict the render uses

For `init_many`, each layer's `when` is evaluated against that layer's answers (+ `today`),
the same dict passed to `run_copy`. For single `init`, `spec.answers`. Absent answer key →
falsy → tool not required (safe default: only gate when the answer explicitly opts in).

### D4 — One aggregated error, before any write (FR-004)

The gate collects ALL misses across the whole plan, then raises one `BailiffError` listing
`tool — needed by <module>` per line, with the module's install hint when present. It runs
after the other pre-render guards so an untrusted/uncloneable source fails first (the gate
needs discovery, which those guards already performed).

## Project Structure

```
specs/016-tool-preflight-gate/
  spec.md          # done
  plan.md          # this file
  tasks.md         # next

# Engine (C-11):
src/bailiff/discovery.py   # parse + validate _bailiff_requires → Discovery.requires
src/bailiff/runner.py      # _check_required_tools gate in init + init_many pre-render band
src/bailiff/errors.py      # (reuse BailiffError; no new type needed)

# Module declarations (every task-bearing first-party module):
templates/bailiff-mod-{base,python,apm,agentic,cdk,cocogitto,github-repo,gitlab-repo,
  go,moon,package-add,rust,terraform,ts,lefthook,precommit,cloudformation}/copier.yml

# Validation + docs:
scripts/check_modules.py                       # validate _bailiff_requires shape + coverage
specs/011-.../contracts/_cross-cutting.md       # document the field + backstop pairing
skills/bailiff/SKILL.md                         # authoring note
```

## Cross-cutting design (Phase 1 detail)

- **Discovery shape.** `Discovery.requires: list[dict[str, str]]` — normalize both forms to
  `{"tool": <name>, "when": <key-or-empty>}`. Empty `when` = unconditional. Validation:
  each entry is a str or a `{tool, when?}` map; unknown keys / non-str tool → DiscoveryError
  naming module + entry.
- **Gate signature.** `_check_required_tools(plan_or_spec, answers_by_layer) -> None`; uses
  `shutil.which`. Pure, deterministic, no subprocess beyond `which` (stdlib). No secret
  ever passes through (tool names + answer keys only).
- **Install hint.** Optional: reuse the URL already in each module's `_task` guard? No —
  that lives in shell. Keep the gate message tool+module only; the `_task` backstop still
  prints the URL if the user proceeds past a manual override. [Open for plan review: a
  small `hint` field on the `{tool, when}` map — DEFERRED unless the bare message reads
  poorly.]

## Coverage rule (SC-004)

`check_modules` asserts: for every module whose `_tasks`/`_post_tasks` invoke a binary
NOT provisioned via the `mise install` chain, that binary appears in `_bailiff_requires`.
Mechanically this is hard to prove by shell parsing, so the check is lighter: validate the
FIELD SHAPE, and maintain a documented expectation (the test suite's stack tests exercise
the gate for the real modules). [Open for tasks: exact check_modules assertion strength.]

## Build / test / release sequencing

1. Discovery parse + validation + unit tests (fail-first).
2. Engine gate in init/init_many + `--check`; loop tests (missing tool → fail before write;
   multi-miss aggregation; `when` opt-in/out; reproduce unaffected).
3. Declare `_bailiff_requires` across all task-bearing modules.
4. `check_modules` field validation; `_cross-cutting.md` + SKILL.md docs.
5. Full non-network suite; PR; merge; fan-out + PyPI bump.

## Complexity Tracking

- The gate is a small addition to an existing, well-populated pre-render band — low risk.
- The one judgment call is `when` scope (D1): truthy-key only, not expressions. Documented;
  the `_task` backstop covers what the gate deliberately doesn't.

## Open questions for tasks.md

- `check_modules` coverage-check strength (shape-only vs. attempt binary/declare parity).
- Whether to add an optional `hint` field to the requires entry (D-cross-cutting) or keep
  the gate message minimal and lean on the `_task` guard's URL.
