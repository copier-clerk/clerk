---
description: "Task list for clerk secrets policy — no scaffold-time secrets; agent never handles credentials (spec 005)"
---

# Tasks: clerk secrets policy — no scaffold-time secrets; agent never handles credentials

**Input**: Design documents from `specs/005-secrets/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[contracts/secrets.md](./contracts/secrets.md),
[constitution](../../.specify/memory/constitution.md) v2.1.0

**Tests**: INCLUDED. Constitution VII: the policy lint, the third-party guardrail, and
the leak (persistence/log/dry-run) assertions are this spec's definition-of-done.

**Organization**: grouped by user story (US1–US3 from spec.md).

## Design decisions this task list assumes (resolved; flagged for review)

- 005 is a **policy + guardrail**, NOT a secrets engine. No `src/clerk/` module added;
  `discovery.secret_questions` (slice 001) is the whole detection mechanism.
- Lint home (Q-005a) = a small standalone policy test now over in-repo clerk-authored
  templates; fold into the full authoring lint when 008b/009 lands.
- Third-party non-interactive (Q-005b) = fail loud naming the question (decision 4b /
  FR-003c); clerk never prompts (Constitution V) and does NOT render copier's
  placeholder default; document out-of-band interactive supply.
- Depends on 003 for the multi-layer guardrail surface (the policy lint itself is
  003-independent).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no incomplete-task dependency)
- Exact file paths included

---

## Phase 1: Policy lint (US1 — clerk templates stay credential-free)

- [ ] T001 [US1] `tests/loop/test_secrets_policy.py` (NEW): a policy check that runs `discovery.discover(...)` over each in-repo clerk-authored template (start with `examples/clerk-template-example/`, and any `templates/*` if present) and asserts `secret_questions == []`. Provide a fixture template that DECLARES a `secret: true` question and assert the same check fails it, naming the question. (This is the enforcement until the full authoring lint of 008b/009 exists; write it so it can be lifted into that lint later.)
- [ ] T002 [P] [US1] Document the policy in the template-author contract surface: add to the constitution's Principle VI note / a `docs/` or SKILL contributor section that clerk-authored templates MUST NOT declare `secret: true` questions and MUST convey runtime secret needs via `.env.example` + docs. (Docs only; no code.)

**Checkpoint**: a clerk-authored template with a secret question fails the policy test; clean templates pass.

---

## Phase 2: Third-party guardrail (US2 — agent never collects a credential)

- [ ] T003 [US2] Extend `skills/clerk/SKILL.md` with a **secrets** step: for ANY secret question surfaced in discovery's `secret_questions` (third-party sources), the agent MUST NOT ask the user for the value and MUST NOT put it in the run-spec; explain out-of-band supply — copier's masked prompt at the deterministic step, or an env mechanism — and note that a required secret with no value in a non-interactive run FAILS LOUD (Constitution V; NOT silently defaulted). Note that clerk mechanically rejects a secret key in the run-spec (Phase 2b) regardless. Reference specs/005-secrets/contracts/secrets.md. Must hold on BOTH single-template and 003 multi-layer (`init_many`) paths.
- [ ] T004 [P] [US2] `tests/loop/test_secrets_policy.py` (extend): with a fixture third-party template declaring a `secret: true` question, assert discovery surfaces it in `secret_questions`, and that the documented run-spec authoring path does NOT include the secret key (i.e. a secret question is never a required agent-collected answer in the inputs clerk builds). Cover the multi-layer case once 003's `init_many` is on main.

**Checkpoint**: a third-party secret question is surfaced as "do not collect"; no path threads its value through the agent inputs.

---

## Phase 2b: Mechanical enforcement (US2 — the boundary is code, not prose)

**Depends on 003** (`runner.init_many` multi-layer path). The guard must hold on both paths.

- [ ] T004a [US2] `src/clerk/discovery.py` (FR-003b): populate `secret_questions` from BOTH per-question `secret: true` AND the top-level `_secret_questions: [keys]` list form (copier honors both — verified). Add the list-form parse after the per-question loop; dedupe. So clerk's flag set matches copier's own exclusion set.
- [ ] T004b [US2] `src/clerk/errors.py`: add `SecretInAnswersError(ClerkError)` — carries the offending KEY name(s), NEVER the value; message names the key + explains secrets are supplied out-of-band, not in the run-spec.
- [ ] T004c [US2] `src/clerk/runner.py` (FR-003a): in `init` AND `init_many`, before calling copier, compute `set(answers) & secret_questions` for each layer's source (via `discovery`); if non-empty, raise `SecretInAnswersError(keys)` — fail loud, non-zero exit, on BOTH paths. This is the enforced boundary behind the SKILL rule.
- [ ] T004d [US2] `src/clerk/runner.py` (FR-004): redact secret answer values before wrapping/surfacing copier errors — the current `raise InvalidRunSpecError(f"...{exc}")` at ~line 146 (and the multi-layer error paths) can echo a `validator`-carried secret. For runs involving secret keys, use a generic message / scrub the value from `{exc}` before re-raising.
- [ ] T004e [US2] `src/clerk/runner.py` (FR-003c): for a required secret question with no value supplied in a non-interactive run, fail loud naming the question rather than proceeding on copier's placeholder default.
- [ ] T004f [P] [US2] `tests/loop/test_secrets_enforcement.py` (NEW): bypass the SKILL entirely — construct a run-spec that DOES supply a secret key's value → assert `SecretInAnswersError` (single + `init_many` multi-layer), non-zero exit, KEY named but VALUE absent from the message/output; `_secret_questions:` list-form fixture → flagged + rejected the same way; a `validator`-echoing-the-secret fixture → the surfaced error does NOT contain the value; a required secret with no value in non-interactive mode → fails loud, not defaulted.

**Checkpoint**: a secret value in a run-spec is rejected in code (both paths); list-form secrets are caught; no secret leaks through a surfaced error; required-secret-no-value fails loud.

---

## Phase 3: Leak assertions + runtime pattern (US3)

- [ ] T005 [US3] Extend `tests/loop/test_secret_edge_exclusion.py`: keep the non-persistence assertion; ADD assertions that when a secret value IS supplied at the deterministic step (programmatic `run_copy(data=…)`), the value does NOT appear in (a) `.copier-answers.yml`, (b) captured stdout/stderr, (c) `--pretend`/`--check` output. Confirm clerk never builds a `copier --data key=value` argv for a secret.
- [ ] T006 [P] [US3] (Optional, demonstrates the pattern) Add `.env.example.jinja` + README guidance to `examples/clerk-template-example/` showing the runtime-secret pattern — the generated project owns its secrets at runtime, NOT via copier answers. Keep it minimal; it doubles as living documentation for SC-005.

**Checkpoint**: no secret value leaks to a committed file, log, or dry-run; the runtime pattern is demonstrated.

---

## Phase 4: Gate + closeout

- [ ] T007 Full gate: `uv run ruff check src/ tests/ scripts/ && uv run ruff format --check src/ tests/ scripts/ && uv run mypy && uv run pytest -q`. Confirm existing 001/010/002/003 tests still pass (esp. the existing secret_edge_exclusion + multi-template).
- [ ] T008 Update `.specify/memory/roadmap.md`: mark spec 005 `planned → implemented` with a completion note (secrets handled by POLICY — clerk templates avoid secret questions; agent never collects; no store dependency; roadmap's op-read/store-inject model superseded). Confirm Q1 (which store first) is resolved to "none" under this policy.
- [ ] T009 Update `README.md` (brief) if secrets warrant a note; open the PR (title = user-facing changelog entry, no spec IDs; `## Spec Context` body per the hook); push via `dgit push`. Do NOT merge without the user's go-ahead.

---

## Dependencies & parallelism

- **Phase 1 (T001–T002)** is 003-independent — the policy lint on clerk-authored
  templates can land anytime.
- **Phase 2 (T003–T004)** depends on 003 for the multi-layer (`init_many`) surface —
  land the guardrail after 003 merges so the test covers both paths.
- **Phase 2b (T004a–T004f)** is the mechanical enforcement (code) — depends on 003's
  `init_many`; T004a (discovery) precedes T004c/T004f. This is the security-load-bearing
  phase: the SKILL rule (Phase 2) is the ergonomic path, Phase 2b is the enforced boundary.
- **Phase 3 (T005–T006)** builds on the existing secret test; T006 is optional
  template content.
- **Phase 4** is closeout.

## Definition of done (maps to spec Success Criteria)

- SC-001 — clerk-authored template with a secret question fails the policy lint
  (T001).
- SC-002 — SKILL treats a surfaced secret question as "do not collect"; value never
  enters the run-spec (T003/T004).
- SC-003 — no secret value in answers file / logs / `--pretend`; validator-carried
  secret scrubbed from surfaced errors (T004d/T005).
- SC-003a — a run-spec supplying a secret key is REJECTED in code, both paths, key
  named not value (T004c/T004f).
- SC-003b — discovery flags both `secret: true` and `_secret_questions:` list forms
  (T004a/T004f).
- SC-003c — required secret with no value in non-interactive mode fails loud, not
  defaulted (T004e/T004f).
- SC-004 — no store dependency, platform-agnostic, no non-secret-field leak scan
  (inherent; confirmed in T007).
- SC-005 — runtime-secret pattern via `.env.example` + docs (T002/T006).
