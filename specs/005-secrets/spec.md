# Feature Specification: clerk secrets policy — no scaffold-time secrets; agent never handles credentials

**Feature Branch**: `005-secrets`

**Created**: 2026-07-10

**Status**: Draft

**Input**: Roadmap spec 005 (Secrets injection) — **reframed**. The roadmap's
"inject secret answers from an external store (`op read …` → `--data secret=…`)"
model is superseded: it assumes a specific store (not platform-agnostic) and, worse,
routes the credential through the **phase-1 agent** (an LLM context leak). Grounded in
verified copier 9.16.0 behavior + the constitution (II two-phase, V trust/secrets).

## Overview

A `secret: true` copier question is a credential asked at generation time. Spec 005
answers "how does clerk handle secrets" with a deliberate, evidence-driven **policy
rather than a store-integration engine**:

> **clerk-authored templates MUST NOT use `secret: true` questions.** Scaffolding
> generates *files and structure*, not a running service — a credential is virtually
> never needed to lay down a project. Secrets belong in the **generated project's
> runtime configuration** (a template-authored `.env.example` + docs, or the secret
> manager the generated project itself uses), and any *task* that genuinely needs a
> token reads it from the **ambient environment** (exactly as slice-001's
> LICENSE-via-`gh` task already reads `gh`'s auth), never as a copier answer.

Because there is then **no secret question**, the phase-1 agent never has a
credential to collect, log, or leak — the risk is *eliminated by construction*, not
mitigated. This is the C-11 / YAGNI-aligned choice: do not build a secrets subsystem
for a need scaffolding does not have; introduce one later, with evidence, only if a
concrete template proves it necessary.

The spec is therefore small: a **policy** (clerk templates avoid secret questions),
a **contributor lint** (fail if a clerk-authored template declares one), and — because
a prose SKILL rule is not a security boundary — a **mechanical guardrail in the
deterministic phase**: `runner` refuses to accept a value for any question discovery
flagged secret, so a secret can never flow through even if the agent misbehaves. The
existing `secret_questions` discovery and the non-persistence test are kept as the
safety net.

An adversarial pre-implementation review (against copier 9.16.0 + the code) proved
the pure-prose policy was unenforced and missed leak channels; this spec folds in
mechanical enforcement (decision 4a), a discovery parsing fix (decision 6a), error
scrubbing (decision 5), and fail-loud-not-default (decision 4b). Scope stays a policy
+ small guards — **no secret store, no injection engine, platform-agnostic** — and a
credential pasted into a *non-secret* field is explicitly the user's responsibility
(out of scope), not something clerk scans for.

## Verified copier behavior (9.16.0, source-checked)

- A `secret: true` question **REQUIRES a default value** (`_user_data.py`
  `_check_secret_question_default_value` — raises `ValueError` otherwise). A secret
  question is never truly empty; absent input it falls back to its default.
- The interactive prompt is **masked** (rendered as a `password` field).
- A secret answer is **NOT persisted** to `.copier-answers.yml` (confirmed by our own
  `tests/loop/test_secret_edge_exclusion.py`; matches ADR-0002). So the committed
  project never contains the value — the reproduce-time re-supply problem is real,
  and the cleanest way to not have it is to not have secret questions.
- `make_secret` (auto-generate) is **deprecated** — not a mechanism to build on.

## Motivating decisions

1. **No secret questions in clerk-authored templates (the policy).** Enforced by a
   contributor lint at discovery: a clerk template whose `copier.yml` declares a
   `secret: true` question fails the check with a message pointing to the runtime-
   config pattern. (This is authoring-plane enforcement; it reuses the existing
   `secret_questions` discovery.)
2. **Secrets live in generated-project runtime, not copier answers.** Templates that
   need to convey a secret requirement ship a `.env.example` + README guidance (plain
   render content) — the *generated project* owns its secrets at run time. clerk's
   answer layer stays credential-free.
3. **Tasks read tokens from ambient env, never as answers.** A `_task` needing a
   credential (e.g. `gh`, a registry token) reads it from the environment the user
   already has (`GH_TOKEN`, etc.), exactly like the existing LICENSE task. Copier
   never sees it; it is not a question, not persisted, not agent-visible.
4. **Agent never collects a secret (the guardrail).** If clerk drives a *third-party*
   template that declares a `secret: true` question, the SKILL MUST NOT ask the user
   for the value and MUST NOT place it in the run-spec. It explains the situation and
   directs the user to supply it out-of-band — via copier's own **masked interactive
   prompt** at the deterministic step, or an environment mechanism — so the value
   never enters the LLM context or a committed file.
4a. **Mechanical enforcement (the boundary is CODE, not prose).** `runner.init` and
   `runner.init_many` MUST reject a run-spec that supplies a value for any key
   discovery flagged secret — fail loud, non-zero exit, naming the offending KEY (never
   the value) — on BOTH the single-template and multi-layer paths. This makes decision
   4 an enforced invariant, not an LLM instruction the agent could violate. (Review
   finding A5: `runner.py` currently has zero `secret` awareness.)
4b. **Fail loud, don't default, on a required secret in non-interactive mode.** For a
   third-party `secret: true` question in a non-interactive reproduce/CI run with no
   value supplied, clerk MUST fail loud (naming the question) rather than silently
   letting copier render its placeholder default into output. (Review: defaulting a
   credential silently ships a placeholder — not sane.)
5. **Never on argv; never in logs — and scrub surfaced errors.** Any value that *does*
   reach copier (third-party case) travels through the programmatic `run_copy(data=…)`
   path clerk already uses — **never** `copier --data key=SECRET` on argv (leaks into
   `ps`). Secret values MUST NOT appear in clerk logs, error messages, or `--pretend`
   output. Concretely: `runner`'s error wrapping currently forwards copier's `{exc}`
   verbatim (`runner.py:146` and the multi-layer paths), and a template `validator`
   error can carry the answer value — so for any run involving secret keys, clerk MUST
   **redact secret answer values before wrapping/surfacing** copier errors (generic
   message, never the value). (Review finding A4: clerk currently re-emits the secret.)
6. **Platform-agnostic by omission.** Because clerk integrates no store, there is
   nothing OS- or manager-specific to depend on (no `op`, no `vault`, no keychain).
   The generated project's own runtime secret handling is the template author's and
   user's choice, outside clerk.
6a. **Discovery must recognize BOTH secret forms.** copier flags secrets two ways: a
   per-question `secret: true`, AND a top-level `_secret_questions: [keys]` list.
   `discovery.py` currently parses only the per-question key, so a list-form secret is
   surfaced to the agent as an ordinary question and slips past the guardrail/lint.
   Discovery MUST parse `_secret_questions:` too, so its `secret_questions` set matches
   copier's own exclusion set. (Review finding A2 — this is what makes 4a/1 sound.)
7. **Evidence-gated escalation.** If a real, concrete template ever needs a
   scaffold-time secret that runtime-config cannot cover, a fuller mechanism
   (agent-hands-off env-var/resolver injection) is specced THEN, with that evidence —
   not preemptively (C-11 / roadmap Q1 resolves to "none for now").

## User Scenarios & Testing

### US1 — A clerk-authored template with a secret question is rejected (Priority: P1)

A contributor authoring a `clerk-mod-*` template adds a `secret: true` question; the
contract lint refuses it, pointing to the runtime-config pattern.

**Why this priority**: this is the policy — it keeps clerk's own family credential-free.

**Independent Test**: run the discovery-backed contract lint against a template
fixture that declares a `secret: true` question; assert it fails naming the question
and citing the "secrets belong in generated-project runtime, not copier answers"
guidance. A clean template (no secret questions) passes.

**Acceptance Scenarios**:
1. **Given** a clerk template with a `secret: true` question, **When** the lint runs,
   **Then** it fails naming the offending question.
2. **Given** a template conveying a secret need via `.env.example` + docs (no secret
   question), **When** the lint runs, **Then** it passes.

### US2 — The agent never collects a third-party template's secret (Priority: P1)

clerk drives a third-party template that declares a `secret: true` question; the
agent does not ask for the value and instead instructs out-of-band supply.

**Why this priority**: the LLM-leak guardrail — the reason the roadmap's store-inject
model was rejected.

**Independent Test**: with discovery reporting a `secret_questions` entry for a
source, assert the SKILL's documented procedure (a) does NOT put the secret in the
run-spec, (b) tells the user to supply it via copier's masked prompt / env, and (c)
the mechanical path never receives the value from the agent. (Verified by the SKILL
contract + a discovery test that the secret question is surfaced as "do not collect".)

### US3 — A secret value never lands in a committed file, log, or dry-run (Priority: P1)

**Independent Test**: for the third-party case where a value IS supplied at the
deterministic step, assert it is (a) absent from `.copier-answers.yml` (existing
non-persistence test), (b) absent from clerk's stdout/stderr and any error text, and
(c) absent from the `--pretend` all-gaps preflight output (which reports the *question*
as needing a secret, never a value).

### Edge Cases

- **Third-party secret question with only its (required) default**: in a
  non-interactive reproduce/CI run with no value supplied, clerk MUST **fail loud**
  naming the question (decision 4b) — NOT silently render copier's placeholder default
  into output. clerk never prompts in the non-interactive path (Constitution V), never
  hangs.
- **Agent (or a caller) supplies a secret key in the run-spec anyway**: the mechanical
  guard (4a) rejects it — fail loud naming the key (never the value), non-zero exit —
  on both single and multi-layer paths, regardless of the SKILL instruction.
- **Secret rendered into a generated file**: if a template references a secret value in
  a rendered file, copier writes it to disk — OUTSIDE clerk's answers layer and outside
  clerk's control. This is documented as inherent (it strengthens the no-scaffold-time-
  secret policy); clerk does not scan generated output.
- **Credential pasted into a NON-secret field**: persists to `.copier-answers.yml` like
  any answer — this is user responsibility, explicitly OUT of scope (no leak-scan).
- **A task needs a token but none is in the env**: the task fails with the ambient
  tool's own message (e.g. `gh` "not authenticated") — clerk surfaces it; it is not a
  clerk secret-management concern.
- **A contributor argues a secret is genuinely needed**: the lint failure names the
  escalation path (decision 7) — spec a real mechanism with evidence, don't smuggle a
  `secret:` question past the policy.

## Requirements

### Functional Requirements

- **FR-001**: clerk-authored (`clerk-mod-*` / example) templates MUST NOT declare
  `secret: true` questions. A contract lint (reusing `discovery`'s `secret_questions`)
  MUST fail an authored template that declares one, naming the question and citing the
  runtime-config pattern.
- **FR-002**: The secrets policy MUST be documented: secrets belong in the generated
  project's runtime config (`.env.example` + docs) or are read from ambient env by
  tasks — never as a copier answer. Template-author guidance MUST state this.
- **FR-003**: The SKILL MUST instruct the agent, for ANY secret question surfaced by
  discovery (third-party templates), to NEVER collect the value and NEVER put it in the
  run-spec; instead explain out-of-band supply (copier's masked prompt at the
  deterministic step, or an env mechanism). The value MUST NOT enter the agent's inputs.
- **FR-003a (mechanical enforcement)**: `runner.init` and `runner.init_many` MUST
  reject a run-spec that supplies a value for any discovery-flagged secret key — fail
  loud, non-zero exit, naming the KEY (never the value) — on BOTH the single-template
  and multi-layer paths. This is the enforced boundary behind FR-003; it MUST hold
  regardless of agent behavior (a new error type, e.g. `SecretInAnswersError`).
- **FR-003b (recognize both secret forms)**: `discovery` MUST populate its
  `secret_questions` set from BOTH per-question `secret: true` AND the top-level
  `_secret_questions: [keys]` list form, so the flag set matches copier's own exclusion
  set (else FR-003a has a blind spot).
- **FR-003c (fail loud, don't default)**: for a required secret question with no value
  supplied in a non-interactive run, clerk MUST fail loud naming the question, NOT
  silently render copier's placeholder default.
- **FR-004**: Any secret value that reaches copier MUST travel via the programmatic
  `run_copy(data=…)` path, NEVER via `copier --data key=value` on argv. Secret values
  MUST NOT appear in clerk logs, error messages, or `--pretend` preflight output —
  clerk MUST **redact secret answer values before wrapping/surfacing** copier errors
  (which can carry a value via a template `validator`); it currently forwards `{exc}`
  verbatim, which MUST be fixed.
- **FR-005**: The existing non-persistence guarantee MUST be preserved and tested — a
  secret answer is never written to `.copier-answers.yml` (keep
  `test_secret_edge_exclusion.py`).
- **FR-006**: clerk MUST NOT integrate any specific secret store or manager (no `op`,
  `vault`, keychain, etc.) — remaining platform-agnostic. Generated-project runtime
  secret handling is the template author's / user's choice, outside clerk.
- **FR-007**: This spec MUST NOT build a secret-injection engine, resolver chain, or
  store adapter, and MUST NOT scan for credentials pasted into non-secret fields (that
  is the user's responsibility — explicitly out of scope). The mechanical enforcement
  of FR-003a/003b/003c is a small refusal/redaction guard on the EXISTING
  discover→run path, NOT a subsystem. Escalation to a fuller injection mechanism is
  deferred and evidence-gated (C-11); if introduced later it MUST remain
  agent-hands-off (FR-003) and store-agnostic (FR-006).

### Key Entities

- **Secret question**: a copier `secret: true` question (requires a default, masked,
  never persisted). clerk templates avoid them; third-party ones are handled
  defensively.
- **Contract lint**: the authoring-plane check (reusing `discovery.secret_questions`)
  that fails a clerk-authored template declaring a secret question.
- **Runtime-config pattern**: `.env.example` + README guidance shipped by a template
  so the *generated project* owns its secrets at run time.
- **Out-of-band supply**: copier's masked prompt / env — the only channels a
  third-party secret value may use; never the agent, never argv, never a committed file.

## Success Criteria

- **SC-001**: A clerk-authored template declaring a `secret: true` question fails the
  contract lint, naming the question; a secret-free template passes.
- **SC-002**: The SKILL documents (and a discovery test confirms) that a surfaced
  secret question is treated as "do not collect — instruct out-of-band"; the value
  never enters the run-spec / agent context.
- **SC-003**: No secret value appears in `.copier-answers.yml`, clerk logs/errors, or
  `--pretend` output (persistence test kept; log/dry-run + error-redaction assertions
  added — a `validator`-carried secret is scrubbed, not re-emitted).
- **SC-003a (mechanical)**: a run-spec supplying a value for a discovery-flagged secret
  key is REJECTED (fail loud, non-zero, names the key not the value) on both single and
  multi-layer paths — enforced in code, verified by a test that bypasses the SKILL.
- **SC-003b**: discovery flags secrets declared BOTH per-question and via
  `_secret_questions:` list; a test with each form confirms both land in
  `secret_questions`.
- **SC-003c**: a required secret with no value in non-interactive mode fails loud
  (named), does NOT render copier's placeholder default.
- **SC-004**: clerk introduces no secret-store dependency and remains
  platform-agnostic (no `op`/`vault`/keychain code); no non-secret-field leak scan.
- **SC-005**: Secrets that generated projects need at runtime are conveyed via
  template `.env.example` + docs, not copier answers (documented; an example template
  may demonstrate the pattern).

## Out of scope

- A secret-injection engine / resolver chain / store adapters (deferred, evidence-
  gated — FR-007). The roadmap's `op read → --data secret=` model is explicitly
  superseded by this policy.
- Generated-project runtime secret management (the project's own concern; clerk only
  provides the `.env.example` + docs pattern via template content).
- Multi-template ordering (003), defaults (004), upgrade (006).

## Open Questions

- **Q-005a — Lint home**: the "no secret question" check runs at the authoring-plane
  contract lint. That lint is part of the deferred authoring-lifecycle (008b/009-era).
  Until it exists, is the policy enforced by (a) a standalone test over
  `examples/`/`templates/` now, or (b) documented-only until the lint lands? Lean:
  **(a) a small test now** over any in-repo clerk-authored templates, folded into the
  full lint later. Resolve at planning.
- **Q-005b — Third-party non-interactive: fail loud vs default (RESOLVED)**: for a
  third-party `secret: true` question with no value in a non-interactive reproduce/CI
  run, clerk **fails loud** naming the question (decision 4b / FR-003c / SC-003c) — it
  does NOT let copier render its placeholder default into output. Fail-loud is the
  Constitution V choice; silently shipping a placeholder credential is the option 4b
  rejects. A real secret is supplied out-of-band interactively (copier's masked
  prompt) or via env.

## Governing constitution & ADRs

- Constitution II (two-phase — the agent does judgment, never handles credentials),
  V (secrets/determinism; deterministic phase never prompts in CI, fails loud).
- ADR-0001 (secrets: injected per-run, never persisted — honored, and taken further:
  clerk templates avoid them entirely), ADR-0002 (secret + `when:false` not
  persisted). Constraints: C-05 (trust/secrets), C-11 (no speculative engine — the
  reason this is a policy, not a subsystem). Roadmap Q1 (which store first) resolves
  to **none** under this policy.
