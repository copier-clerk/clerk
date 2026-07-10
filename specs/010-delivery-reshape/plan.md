# Implementation Plan: clerk delivery reshape — skill-bundled copier wrapper

**Branch**: `010-delivery-reshape` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/010-delivery-reshape/spec.md`

## Summary

Reshape clerk's delivery so it is a **pure copier wrapper bundled in a portable
skill**, with **zero clerk-specific artifact committed into a generated project**.
This is re-packaging, not a rewrite: the discover/trust/validation logic and its
tests from 001 survive; what changes is *how the deterministic layer is packaged
and invoked*.

Concretely, for the single-template scope of 010 (multi-template orchestration is
003):

- The deterministic coordination ships as **one bundled script**, `scripts/clerk.py`,
  run `./scripts/clerk.py …` or `uv run scripts/clerk.py …` — **not** a
  `[project.scripts] clerk` console entry, **not** a PyPI package.
- `scripts/clerk.py` is scoped to **what copier cannot do itself**: static
  `discover` and `trust` management. For single-template `init` / reproduce /
  `--pretend` check — things copier already does in one command — the SKILL
  instructs the agent (or a human, or CI) to invoke **copier directly**. There is
  nothing to orchestrate for one template, so `clerk.py` does not wrap those.
- The two clerk-specific safety gates that 001's `runner.init` bundled move to
  where the constitution already places them: the **reproducibility refusal**
  (no answers-file `.jinja` → refuse) is a **discovery** responsibility
  (Constitution VI: "discovery MUST detect its absence statically and refuse"),
  surfaced by `discover` and enforced by the SKILL; the **trust surface**
  (action-taking source → name the prefix, obtain consent) is a **trust**
  responsibility (`clerk.py trust`), with copier itself the authoritative gate at
  render time.
- `init` no longer writes a `justfile` (or any clerk file) into the project. The
  committed `.copier-answers.yml` is the entire reproduce state.
- Reproduce is the pure copier-alone guarantee: `copier recopy --vcs-ref=:current:
  --defaults --overwrite`, documented in the SKILL and runnable with **no clerk and
  no just installed** (US1 / SC-001).

Technical approach, verified against copier 9.16.0 (unchanged from 001 — see
`specs/001-clerk-vertical-slice/research.md`; this spec re-verifies nothing about
copier, only re-packages clerk):

- **init (single template)** = `copier copy --data-file <run-spec.yml>
  --vcs-ref <ref> --defaults --overwrite --trust <src> <dst>` — invoked directly
  per the SKILL; copier authoritatively trust-gates and validates.
- **reproduce** = `copier recopy --vcs-ref=:current: --defaults --overwrite` in the
  project dir — direct copier, zero clerk/just dependency.
- **check** = `copier copy --pretend …` — copier's own dry run; direct.
- **discover** = `scripts/clerk.py discover <src> [--ref REF]` — the static
  `copier.yml`/file-tree/tag parse from 001 (questions, secret flags, `when:false`
  edges, `_jinja_extensions`, `reproducible`, PEP 440 `versions`). No Jinja env,
  no template code → safe on untrusted sources.
- **trust** = `scripts/clerk.py trust add <prefix>|--from-source <src>` /
  `trust list` — the only writer of copier's `settings.yml` `trust:`, on explicit
  consent; `--from-source` computes the suggested owner-path prefix (001's
  `_suggest_prefix`).

## Technical Context

**Language/Version**: Python 3.11+ for the one bundled script; shell for the
documented direct-copier invocations. (`pyproject.toml` already targets 3.11+.)

**Primary Dependencies**: `copier>=9.16,<10` (the engine, pinned), `packaging`
(PEP 440 tag filtering), `pyyaml` (static `copier.yml` read + run-spec parse) —
all already declared. No new dependency. `uv` runs the script with the project's
locked deps; `./scripts/clerk.py` works when those deps are importable. `git` and
`copier` are host tools for the direct-invocation path.

**Storage**: Files only. Inputs = the copier answers/`--data-file` run-spec the
skill authors (documented plain YAML — Constitution VIII). Outputs = the generated
project tree + copier's `.copier-answers.yml` (the *entire* reproduce state; no
clerk file). Trust lives in copier's `settings.yml`
(`~/.config/copier/settings.yml` or `COPIER_SETTINGS_PATH`).

**Testing**: `pytest`, hermetic/offline via local `git` template fixtures; one
marked network smoke test against `copier-clerk/clerk-template-example`. The loop
tests are **adapted, not weakened** (FR-007): assertions that previously invoked
`clerk init`/`clerk reproduce` now invoke `scripts/clerk.py` for discover/trust and
**copier directly** for init/reproduce/check, asserting the same outcomes
(byte-identical reproduce, refusals, exit codes). `mypy --strict` + `ruff` apply to
the bundled script and any retained library module.

**Target Platform**: Developer workstations + CI (macOS/Linux).

**Project Type**: A skill + bundled script + copier templates. NOT a published
application: no `[project.scripts] clerk`, no `uvx clerk`/PyPI target.

**Performance Goals**: None; correctness + determinism only.

**Constraints**: Hermetic/offline tests except one marked smoke test; faithful
byte-identical reproduce with **copier alone** (no clerk, no just); no clerk file
committed into a generated project; deterministic phase never prompts and never
writes trust; no deprecated copier surface (static parse suffices, no adapter);
glue justified only by a copier gap (Constitution I / C-11).

**Scale/Scope**: Single template, single render — the same loop 001 proved, now
re-packaged. Multi-template orchestration + runtime-recompute ordering are 003
(this spec fixes only the reproduce-time recompute *contract* they must satisfy,
FR-004/FR-005). Deliverables: `scripts/clerk.py`, a rewritten `skills/clerk/SKILL.md`,
an updated commands contract, an updated `try-clerk.sh`, `pyproject.toml` edits,
and the adapted test suite.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution **v2.1.0** (Principles I–VIII; III/I reconciled to
runtime-recompute in the same PR that reshaped this spec). Initial gate: **PASS**.

| Principle | Gate | How this plan satisfies it |
|---|---|---|
| I — Skills + templates + minimal glue | PASS | Deliverable is `SKILL.md` + one bundled `scripts/clerk.py` (discover/trust only). Removes `[project.scripts] clerk`; single-template copier ops are direct, not wrapped. Strictly *reduces* glue. |
| II — Two-phase; skill conducts, helpers execute | PASS | Skill authors the run-spec; the deterministic phase is `scripts/clerk.py` + direct copier calls, runnable/testable with no LLM. Agent never in reproduce. |
| III — Faithful, agent-free reproduce | PASS | Reproduce = `copier recopy --vcs-ref=:current:` run directly (no clerk, no just); bare recopy never used; multi-template order recomputed (003), never frozen. Determinism test asserts byte-identity. |
| IV — Prefer CLI + static config; adapter only if used | PASS | `discover` is a static parse; init/reproduce/check are copier's own CLI; no Jinja env, no `Template`/`Worker` → **no adapter, no drift test**. copier pinned `<10`. |
| V — Determinism via pinning; trust by source | PASS | `today` injected via `--data`; trust in `settings.yml` (expanded-https), written only by `clerk.py trust` on consent; direct copier authoritatively refuses untrusted sources; CI fails loudly. |
| VI — Template-author contract at discovery | PASS | Reproducibility refusal (answers-file `.jinja`) is enforced *at discovery* (its constitutional home) + SKILL stop-on-`reproducible:false`; version resolvability likewise. |
| VII — Hardening per-step (scaled) | PASS | DoD = byte-identical copier-only reproduce test + error surfacing (copier's own messages/exit codes on the direct path; `clerk.py` surfaces `DiscoveryError`/`UntrustedSourceError`) + adapted loop/unit tests. No adapter → no drift test. |
| VIII — Documented, dry-run-validated handoff | PASS | Handoff stays a documented plain-YAML run-spec; validation is copier's `--pretend`. No pydantic/JSON-Schema. |

**Complexity deviations**: none. This plan *removes* surface (the `clerk` console
entry, the justfile writer, the init/reproduce/check CLI verbs) rather than adding
any. See Complexity Tracking for the one retained-code judgment call.

Post-design re-check (after Phase 1): **PASS** — no new dependency, no deprecated
surface; the seam is copier's own answers/settings shapes plus the 001 discovery
result, now surfaced by a single bundled script.

## Project Structure

### Documentation (this feature)

```text
specs/010-delivery-reshape/
├── spec.md              # The reshaped spec (merged; revised to the single-script shape)
├── plan.md              # This file
├── contracts/
│   └── invocation.md    # Phase 1 — the bundled-script verbs + the documented direct-copier commands
│                        #   (supersedes 001/contracts/commands.md for the reshaped surface)
└── tasks.md             # Phase 2 (/speckit.tasks)
```

Phase-0 research is intentionally **not** re-generated: every copier fact this
spec relies on (recopy `:current:` semantics, `--pretend`, trust in `settings.yml`,
static-parse safety, PEP 440 tag filtering) was verified in
`specs/001-clerk-vertical-slice/research.md` and is unchanged. A data-model doc is
unnecessary — the data at the seam is the same run-spec / discovery-result / trust
entry / recorded answers documented in 001's contracts.

### Source Code (repository root)

```text
scripts/
├── clerk.py             # NEW: the single bundled orchestration script (shebang + `uv run`-able).
│                        #   Verbs: `discover`, `trust add|list` (copier-can't work only).
│                        #   Reuses src/clerk/{discovery,trust}.py logic. NO init/reproduce/check verbs.
└── try-clerk.sh         # UPDATED: inspectable walkthrough using scripts/clerk.py + direct copier
                         #   (drop the justfile step and the installed-clerk framing).

skills/clerk/
└── SKILL.md             # REWRITTEN: phase-1 procedure invoking `./scripts/clerk.py discover|trust`
                         #   and DIRECT copier for init/reproduce/check; documents the copier-only
                         #   reproduce fallback; removes all `clerk`-console / `just reproduce` refs.

src/clerk/               # Retained library logic (imported by scripts/clerk.py; see Complexity Tracking):
├── discovery.py         #   KEEP — static discovery incl. `reproducible` (VI gate lives here).
├── trust.py             #   KEEP — settings.yml trust read/write + prefix suggestion.
├── errors.py            #   KEEP — DiscoveryError / UntrustedSourceError / NotReproducibleError etc.
├── runner.py            #   KEEP as orchestrator substrate for 003 (copier-driving + error
│                        #   translation), unit-tested; NOT invoked on the single-template path.
│                        #   (Judgment call — see Complexity Tracking; YAGNI-strict alt = defer to 003.)
└── cli.py               #   REDUCED — drop the justfile writer (_REPRODUCE_JUST/_write_reproduce_recipe)
                         #   and the init/reproduce console wiring; discover/trust logic moves behind
                         #   scripts/clerk.py. (cli.py may be deleted outright if scripts/clerk.py
                         #   fully subsumes it — a task decides.)

pyproject.toml           # EDIT: remove [project.scripts] clerk (FR-001/US4/SC-003). Keep the package
                         #   buildable for tests importing src/clerk, or convert to a src-on-path dev
                         #   layout — a task decides the lightest shape that keeps mypy/tests green.

tests/
├── loop/                # ADAPTED (not weakened): invoke scripts/clerk.py for discover/trust and
│   │                    #   copier DIRECTLY for init/reproduce/check; same assertions.
│   ├── test_init.py                  # init via direct `copier copy`; asserts recorded answers, NO justfile written
│   ├── test_reproduce.py             # reproduce via direct `copier recopy :current:`; byte-identical; NO clerk/just needed
│   ├── test_check.py                 # `copier copy --pretend` writes nothing; surfaces invalid answers
│   ├── test_trust_refusal.py         # action-taking untrusted source refused by copier; consent via clerk.py trust → success
│   ├── test_answersfile_refusal.py   # discover reports reproducible:false; SKILL/gate refuses (VI)
│   ├── test_discover_static_safe.py  # discover executes no template code, needs no trust
│   ├── test_secret_edge_exclusion.py # secret + when:false NOT persisted (unchanged behavior)
│   └── test_smoke_remote.py          # marked network smoke vs clerk-template-example, via the new invocation
├── unit/                # KEEP — discovery parsing + runner substrate + trust/prefix suggestion
└── test_smoke.py        # ADAPTED — package/script imports; drop the `clerk.cli:main` console assumption
```

**Structure Decision**: The primary deliverables are `skills/clerk/SKILL.md` and
the single bundled `scripts/clerk.py`. `src/clerk/{discovery,trust,errors}.py` are
retained as the library the script imports; `runner.py` is retained as the
copier-driving substrate 003's orchestrator will build on (flagged below). No new
module, no adapter, no package publication. The generated project contains only
copier-native files.

## Open decision for review (flagged, not silently resolved)

**Q — `runner.py` disposition.** With single-template init/reproduce/check moving
to direct copier, `runner.init`/`reproduce`/`check` are not invoked on 010's path.
Two options:

- **(a) Keep as orchestrator substrate (RECOMMENDED).** Retain `runner.py`'s
  copier-driving + error-translation + the reproducibility/trust pre-checks as
  importable library code, exercised by unit tests, wired into the multi-template
  orchestrator at 003 (which *must* drive copier programmatically for N ordered
  runs). Rationale: it is verified working code with a concrete near-term consumer;
  deleting and rebuilding it at 003 is pure waste. The single-template *path* still
  uses direct copier, honoring the "clerk doesn't deal with that" steer.
- **(b) YAGNI-strict: remove now, rebuild at 003.** Delete `runner.py` and its
  init/reproduce tests; 003 reintroduces a programmatic driver with evidence
  (Constitution C-11 / roadmap Q4). Rationale: no speculative retained code;
  smallest possible 010 surface.

**Recommendation: (a).** It best satisfies FR-007 ("logic and tests survive nearly
intact"), avoids re-deriving verified behavior, and keeps the single-template path
direct-copier as the user asked. Tasks below assume (a); switching to (b) deletes
the "keep runner" tasks and moves the pre-check relocation entirely into discover
+ SKILL.

## Complexity Tracking

No constitutional violations. This plan reduces surface versus the merged 001 code
(removes: the `clerk` console script, the generated justfile + its writer, the
init/reproduce/check CLI verbs). The single retained-code judgment call
(`runner.py` as 003 substrate) is documented above with its YAGNI-strict
alternative, per C-11's "no speculative code" discipline — retained because it is
existing verified code with a concrete next consumer, not new speculative glue.
