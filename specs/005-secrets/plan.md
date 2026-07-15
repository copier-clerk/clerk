# Implementation Plan: bailiff secrets policy — no scaffold-time secrets; agent never handles credentials

**Branch**: `005-secrets` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-secrets/spec.md`

## Summary

005 is a **policy + guardrail**, not a secrets subsystem. The decision: bailiff-authored
templates avoid `secret: true` questions entirely (scaffolding needs no scaffold-time
credential); secrets live in generated-project runtime config or ambient-env tasks;
the phase-1 agent NEVER collects a credential. This eliminates the LLM-leak risk by
construction and keeps bailiff platform-agnostic (no store integration). Implementation
is therefore small: a lint/test enforcing the policy on bailiff-authored templates, a
SKILL guardrail for third-party secret questions, and log/dry-run leak assertions —
all building on the existing `discovery.secret_questions` + non-persistence test.

Resolved planning decisions (flagged in spec Open Questions):
- **Lint home (Q-005a)** = a **small standalone test now** over in-repo bailiff-authored
  templates (`examples/`), folded into the full authoring-lint when 008b/009 lands.
- **Third-party non-interactive behavior (Q-005b)** = **fail loud** naming the
  question (decision 4b / FR-003c) — bailiff does NOT let copier render its placeholder
  default. bailiff stays non-prompting per Constitution V (never prompts in CI, fails
  loud); a real secret must be supplied out-of-band interactively.

## Technical Context

**Language/Version**: Python 3.11+ (the lint/tests reuse `discovery`). No runtime code
change to the render path.

**Primary Dependencies**: none new. Reuses `discovery.discover().secret_questions`.

**Storage**: none. No secret ever touches bailiff state; the policy keeps the answer
layer credential-free.

**Testing**: `pytest`, hermetic. A policy test over in-repo bailiff-authored templates
(fail if any declares a secret question); extend the SKILL/discovery guardrail
coverage for the third-party case; keep + extend `test_secret_edge_exclusion.py` with
log/`--pretend`-leak assertions. `mypy`/`ruff` as usual.

**Target Platform**: dev + CI. No store, no OS-specific anything (the whole point).

**Project Type**: policy + a small mechanical guard on the existing discover→run path
(no new module, no engine) + template-content guidance.

**Constraints**: no secret question in bailiff templates; agent never collects a
credential (Constitution II); never argv, never logs, never `--pretend` output; no
store dependency (platform-agnostic — FR-006); no injection engine (C-11 — FR-007);
non-interactive reproduce never prompts (Constitution V).

**Scale/Scope**: a lint/test + SKILL guardrail wording + an `.env.example` template
pattern + leak-assertion tests. NO engine, NO resolver chain, NO adapters.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution **v2.1.0**. Initial gate: **PASS**.

| Principle | Gate | How this plan satisfies it |
|---|---|---|
| I — Skills + templates + minimal glue | PASS | Adds a lint/test + SKILL wording + template `.env.example` + a small mechanical guard (secret-key rejection + error redaction + list-form parse + one error type) on the existing discover→run path — no new module, no store engine. Strictly *less* than the roadmap's store-inject model; the guard is the minimum that makes the security invariant real (C-11). |
| II — Two-phase; agent judges, helpers execute | PASS | The core decision: the agent NEVER handles a credential. Any value reaching copier does so via the deterministic `run_copy(data=…)` path / copier's masked prompt — never the LLM. |
| III — Faithful, agent-free reproduce | PASS (unaffected) | No secret questions in bailiff templates → nothing to re-supply at reproduce. Third-party case uses copier's default (non-prompting). |
| IV — Prefer CLI + static config | PASS | Policy enforced by static `discovery.secret_questions` read; no new surface. |
| V — Determinism; trust by source | PASS | Non-interactive reproduce never prompts; fails loud / uses default. Secrets never persisted (kept test). |
| VI — Template-author contract | PASS | Adds a contract rule: bailiff-authored templates MUST NOT declare secret questions (enforced by the lint/test), and convey secret *needs* via `.env.example`. |
| VII — Hardening per-step | PASS | DoD = policy lint/test + third-party guardrail coverage + non-persistence + log/dry-run leak assertions. |
| VIII — Documented handoff | PASS (n/a) | No handoff-format change; the run-spec simply never carries a secret. |

**Complexity deviations**: none. This *removes* the roadmap's store-injection engine
in favor of a policy — the maximally C-11 outcome (no code for a need scaffolding
doesn't have). Escalation is documented + evidence-gated, not built.

Post-design re-check (after Phase 1): **PASS** — the seam is the existing discovery
+ non-persistence guarantees plus documentation; nothing new to reproduce or trust.

## Project Structure

### Documentation (this feature)

```text
specs/005-secrets/
├── spec.md              # The secrets policy spec
├── plan.md              # This file
├── contracts/
│   └── secrets.md       # Phase 1 — the policy, the third-party guardrail, the .env.example pattern, leak rules
└── tasks.md             # Phase 2 (/speckit.tasks)
```

Phase-0 research is captured inline (copier 9.16.0 secret behavior verified from
source in the spec: secret requires a default, masked, not persisted, `make_secret`
deprecated). No research.md needed.

### Source Code (repository root)

```text
src/bailiff/discovery.py   # EXTEND (FR-003b): populate secret_questions from BOTH per-question
                         #   `secret: true` AND the top-level `_secret_questions: [keys]` list form.
src/bailiff/errors.py      # EXTEND: add SecretInAnswersError(BailiffError) — carries the KEY, never the value.
src/bailiff/runner.py      # EXTEND (FR-003a/003c/004): init + init_many reject a run-spec supplying a
                         #   discovery-flagged secret key (SecretInAnswersError, both paths); fail loud on
                         #   a required secret with no value in non-interactive mode; REDACT secret values
                         #   before wrapping/surfacing copier errors (currently forwards {exc} verbatim).
skills/bailiff/SKILL.md    # EXTEND: a "secrets" note — for ANY secret question discovery surfaces
                         #   (third-party templates), the agent MUST NOT collect the value or put it
                         #   in the run-spec; explain out-of-band supply (copier's masked prompt at
                         #   the deterministic step / env). Never argv, never logs. Note bailiff rejects
                         #   a secret key in the run-spec mechanically regardless (FR-003a).

examples/bailiff-template-example/   # (optional) demonstrate the runtime-secret pattern:
                         #   a .env.example.jinja + README guidance so the GENERATED project owns its
                         #   secrets at runtime — showing "secrets go here, not in copier answers".

tests/
├── loop/
│   └── test_secret_edge_exclusion.py   # KEEP + EXTEND: still assert non-persistence; ADD assertions
│                                       #   that a secret value does not appear in stdout/stderr or in
│                                       #   `--pretend`/--check output.
└── unit/  or  loop/
    └── test_secrets_policy.py          # NEW: (a) POLICY — a bailiff-authored template fixture declaring a
                                        #   `secret: true` question fails the policy check (reusing
                                        #   discovery.secret_questions); a clean one passes. (b) GUARDRAIL —
                                        #   discovery surfaces a third-party secret question as secret_questions,
                                        #   and the documented SKILL path treats it as "do not collect".

# NOTE: NO secret-store engine, no resolver chain, no injection subsystem, no leak-scan.
# The additions are small guards on the EXISTING discover→run path (a rejection check + a
# redaction + a list-form parse + one error type). If 008b/009's authoring lint lands, fold
# the policy check into it (Q-005a).
```

**Structure Decision**: No new *module* and no subsystem — the mechanical enforcement
is a handful of guard lines on the existing `discovery`/`runner` path plus one error
type (`SecretInAnswersError`), not an engine. 005 = a policy test, a SKILL guardrail
paragraph, the runner/discovery guards (FR-003a/b/c, FR-004), an optional
`.env.example` pattern, and leak-assertion extensions to the existing secret test.
The boundary is enforced in code, not left to SKILL prose (the review's core finding).

## Dependency on 003

Minimal, but real: the third-party guardrail (FR-003/FR-004) must hold on BOTH the
single-template path and 003's `init_many` multi-layer path — a secret question in
any layer must be caught the same way and never threaded through the agent. So 005's
guardrail wording + tests should land after 003 merges, to cover the multi-layer
surface. (The policy lint on bailiff-authored templates is independent of 003.)

## Complexity Tracking

No constitutional violations; this plan *removes* scope (no store engine) versus the
roadmap. The two flagged decisions (lint home, third-party non-interactive behavior)
are resolved above with defaults + rationale; both are small and reversible. If a
concrete future template proves a scaffold-time secret is genuinely unavoidable, a
fuller agent-hands-off + store-agnostic mechanism is specced then, with evidence
(FR-007) — not now.
