# Specification Quality Checklist: clerk Single-Module Vertical Slice

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-09
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- The spec is deliberately written at the WHAT/WHY altitude: it names copier only
  as "the engine" in the Assumptions/Key Entities framing (a dependency fact), and
  keeps all API/mechanism detail (run_copy/run_recopy/VcsRef.CURRENT, pydantic,
  the adapter module, settings.yml) out of the requirements — those belong in the
  plan. Reviewers coming from the grilling session should map: FR-015/017 ↔ faithful
  reproduce (Principle III), FR-025/026 ↔ deprecated-surface adapter (Principle IV),
  FR-006/FR-004 ↔ machine-checkable seam contracts (Principle VIII), FR-019..023 ↔
  trust/consent (Principle V), FR-016 ↔ answers-file contract (Principle VI).
- Deferrals to roadmap specs 002–006/008 are recorded in Assumptions and Edge Cases
  so scope stays bounded to a single template / single source / single render.
- Items marked incomplete require spec updates before `/speckit.clarify` or
  `/speckit.plan`. All items pass on first iteration.

## Adversarial review (applied 2026-07-09)

Two independent read-only reviewers (an adversarial challenger + a cross-artifact
consistency analysis) stress-tested this spec against the constitution, roadmap, and
ADRs; both verdicts were "sound enough to plan after fixing specific items." Load-
bearing findings were re-verified against copier 9.16.0 source before applying. Fixes
folded into the spec:

- **SC-002 unfalsifiable (Critical)** → SC-002/FR-018 now require byte-identity over an
  enumerated path set with an empty exclusion allowlist; the example action makes no
  commit (verified: bare `git init` is byte-identical across runs; a commit embeds a
  timestamp).
- **Discovery code-execution hole (High)** → new FR-004a: inspection is static-only,
  reports raw un-rendered defaults, never builds the engine env or loads extensions,
  never requires trust. (Verified: `Template.questions_data` is a safe YAML parse, but
  building the jinja env imports template-declared extensions = untrusted code exec,
  and is NOT trust-gated.)
- **message_after_copy not on public return (High)** → FR-014 now requires capture
  inside the FR-025 containment point (the fetched template is cleaned up post-run;
  verified the clone is deleted on return).
- **Doc contradictions (High)** → FR-027 broadened to fix all three wrong claims
  (README bare-recopy; README "without trust / action in clerk"; pyproject "never runs
  actions").
- **Check-mode/trust precedence (High)** → FR-008 spells out that trust is checked
  before answers; untrusted-source is a valid check result and takes precedence.
- **Constitution VI(b) gap (Medium)** → FR-016a adds a cheap version-resolvability
  refusal; broader one-repo=one-template enforcement explicitly deferred to spec 002.
- **Mutable-tag caveat (Medium)** → FR-017a documents the limitation + optional
  immutable-revision record.
- **CI trust provisioning (Medium)** → FR-023a. **trust idempotence (Medium)** → FR-023b.
- **Cloneable src identity (Medium)** → FR-012a.
- **Traceability gaps (Medium)** → FR-007/FR-014/FR-013 now have SC-010/SC-011/SC-012;
  FR-013 gets a dedicated secret+edge fixture (H4).
- **Canonical URL form (Low)** → FR-022 now mandates fully-expanded URLs for fetch and
  trust storage.
- Edge cases added: reproduce-onto-existing-tree; discovery-of-untrusted-source.

Deferred deliberately (not blocking): standardizing "the deterministic tool" vs "the
system" across phase-boundary FRs (cosmetic); reconciling the constitution's
"pre-expansion URL" wording with the ADR's canonical-form directive (a plan-time note,
spec is unambiguous via FR-022).

## YAGNI re-scope to lean model (applied 2026-07-09, constitution v2.0.0)

A project-level pushback ("does this justify a Python tool, or a skill + thin glue?")
reframed clerk from a published tool into **a skill + copier templates + minimal
deterministic glue**. Verified via the copier CLI that init/reproduce/trust are each a
single command, so the wrapper's value is only cross-template coordination (roadmap
003+), not slice 1. Spec edits:

- FR-004/FR-006/SC-008: dropped the pydantic seam + committed JSON-Schema + drift gate;
  the handoff is a documented plain-YAML answers doc validated by copier's own
  `--pretend` dry run (Constitution VIII).
- FR-025/SC-009: dropped the standing deprecated-surface adapter + contract test;
  discovery is a static `copier.yml`/file-tree parse (no Jinja env, no Template/Worker),
  so there is nothing to contain this slice. Adapter is conditional on a future need
  (Constitution IV, roadmap Q3).
- FR-010: error surfacing no longer mandates a typed clerk-error hierarchy; a helper MAY
  type them, a bare recipe MAY surface copier's own message + exit code — must be legible.
- FR-014: message_after_copy is surfaced (copier already prints it), not structured-
  captured via the deprecated surface.
- Overview / Key Entities / FR-024: reframed to skill + template + glue; no uvx/PyPI
  application; copier driven primarily via its CLI.

The reproduce, trust, answers-file-contract, determinism, and template-author
requirements are unchanged — those are the substance the lean model still delivers.
plan.md was rewritten to the lean structure (no package/pydantic/adapter). This spec
supersedes the v1 tool-centric framing; constitution + roadmap bumped to v2.0.0.
