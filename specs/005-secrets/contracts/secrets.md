# Contract — clerk secrets policy + guardrail (spec 005)

clerk handles secrets by **policy, not by a store engine**: clerk-authored templates
avoid secret questions; the phase-1 agent never handles a credential; clerk depends
on no secret store. This contract states the policy, the third-party guardrail, the
runtime-secret pattern, and the leak rules.

## The policy (clerk-authored templates)

- A `clerk-mod-*` / example template's `copier.yml` **MUST NOT declare a `secret:
  true` question.** Enforced by a contract lint reusing `discovery.discover(...).
  secret_questions` — a non-empty list for a clerk-authored template is a failure,
  with a message naming the question(s) and pointing to the runtime-secret pattern.
- A template that needs to convey a secret *requirement* ships a **`.env.example`**
  (render content) + README guidance: the **generated project** owns its secrets at
  runtime. clerk's copier-answer layer stays credential-free.
- A `_task` that needs a token reads it from the **ambient environment** (e.g.
  `GH_TOKEN`, like the existing LICENSE-via-`gh` task) — never a copier answer, never
  a question, never persisted, never agent-visible.

## The guardrail (third-party templates clerk drives)

clerk cannot control third-party templates. If discovery reports a `secret_questions`
entry for a source clerk is asked to drive:

- The **SKILL MUST NOT** ask the user for the secret value and **MUST NOT** place it
  in the run-spec / `--data` it authors. (Phase-1 agent stays credential-free — the
  whole point.)
- The SKILL explains the situation and directs **out-of-band supply**:
  - copier's own **masked interactive prompt** at the deterministic step (the human
    types it into copier directly, not to the agent), OR
  - an environment mechanism the user controls.
- **Non-interactive reproduce/CI** (Constitution V): clerk never prompts and never
  hangs. For a **required** secret question with no value supplied, clerk **fails loud**
  naming the question — it does NOT silently render copier's placeholder default into
  output (a defaulted credential is not sane). A real secret must be supplied
  out-of-band interactively.

## Mechanical enforcement (the boundary is code, not this prose)

The SKILL rule above is the ergonomic path; these are the *enforced* guarantees in
`runner`/`discovery`, which hold regardless of agent behavior:

- **Reject secret keys in the run-spec.** `runner.init` / `init_many` compute
  `set(answers) & secret_questions` per layer and raise `SecretInAnswersError(keys)` —
  fail loud, non-zero exit, naming the KEY (never the value) — on BOTH single and
  multi-layer paths. A secret value cannot flow through even if the agent puts one in.
- **Recognize both secret forms.** `discovery` flags secrets from per-question
  `secret: true` AND the top-level `_secret_questions: [keys]` list, matching copier's
  own exclusion set (else the rejection above has a blind spot).
- **Redact surfaced errors.** For runs involving secret keys, clerk scrubs secret
  answer values before wrapping/surfacing copier errors (a template `validator` error
  can carry the value; `runner` currently forwards `{exc}` verbatim — must be fixed).
- **Out of scope:** a credential pasted into a *non-secret* field (persists like any
  answer) is the user's responsibility — clerk does NOT scan for it.

## Leak rules (any value that DOES reach copier)

For the third-party case where a value is supplied at the deterministic step:

- It travels via the programmatic **`run_copy(data=…)`** path clerk already uses —
  **NEVER** `copier --data key=value` on argv (leaks into `ps`/process listings).
- Secret values **MUST NOT** appear in clerk logs, error messages, or the
  `--pretend` / all-gaps-preflight output. The preflight reports the *question* as
  needing a secret, never a value.
- Secret answers are **NOT persisted** to `.copier-answers.yml` (copier's own
  behavior; guarded by `test_secret_edge_exclusion.py`). Reproduce re-obtains the
  value out-of-band, identically — it is never read back from a committed file.

## The runtime-secret pattern (what templates ship instead)

```text
{{ _copier_conf.answers_file }}.jinja   # (existing) records non-secret answers
.env.example.jinja                       # NEW pattern: documents the secrets the GENERATED
                                          #   project needs at RUNTIME (names, not values)
README.md.jinja                           # guidance: "copy .env.example → .env, fill secrets"
```

The generated project's runtime secret handling (dotenv, the project's own secret
manager, CI secrets) is the **template author's + user's** choice — outside clerk,
which is why clerk stays platform-agnostic (no `op`/`vault`/keychain code).

## What clerk does NOT build (deferred, evidence-gated)

No secret-injection engine, resolver chain, or store adapter. The roadmap's `op read
→ --data secret=` model is **superseded** by this policy. If a concrete template ever
proves a scaffold-time secret is unavoidable, a fuller mechanism is specced then — and
it MUST remain **agent-hands-off** (the value never enters the LLM context) and
**store-agnostic** (no clerk dependency on a specific manager).

## Exit codes

| Surface | Code | Meaning |
|---|---|---|
| policy lint (clerk-authored template) | 0 | no secret questions |
| | non-zero | a `secret: true` question found — named, with the runtime-pattern pointer |
| existing clerk verbs | 0/1/2/3 | unchanged (spec 010/002/003) |

(No new runtime exit codes — 005 adds a lint/policy + guardrail wording, not a new
command surface.)
