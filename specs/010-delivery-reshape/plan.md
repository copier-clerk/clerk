# Implementation Plan: bailiff delivery reshape — skill-bundled copier wrapper

**Branch**: `010-delivery-reshape` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/010-delivery-reshape/spec.md`

## Summary

Reshape bailiff's delivery so it is a **pure copier wrapper bundled in a portable
skill**, with **zero bailiff-specific artifact committed into a generated project**.
This is re-packaging, not a rewrite: the discover/trust/validation logic and its
tests from 001 survive; what changes is *how the deterministic layer is packaged
and invoked*.

Concretely:

- The deterministic coordination ships as **one bundled script**, `scripts/bailiff.py`,
  run `./scripts/bailiff.py …` or `uv run scripts/bailiff.py …` — **not** a
  `[project.scripts] bailiff` console entry, **not** a PyPI package.
- `scripts/bailiff.py` drives the **full lifecycle** — `discover`, `trust`, `init`,
  `reproduce` — through **one uniform path for 1..N templates**. A single-template
  project is simply the **N=1** case: `reproduce` enumerates the committed
  `.copier-answers*.yml` file(s) and drives `copier recopy --vcs-ref=:current:` per
  layer (one file → one recopy at N=1); `init` drives `copier copy` per layer.
  **No separate single-template code path, and no verb that is meaningful only for
  multiple templates.** The N>1 dependency topo-sort is spec 003, which plugs into
  this loop rather than adding a second path.
- The bailiff-specific safety gates keep their constitutional homes: the
  **reproducibility refusal** (no answers-file `.jinja` → refuse) is enforced at
  **discovery** (Constitution VI) and re-checked before `init` writes; the **trust
  surface** (action-taking source → name the prefix, obtain consent) is
  `bailiff.py trust`, with copier itself the authoritative gate at render time.
- `init` no longer writes a `justfile` (or any bailiff file) into the project. The
  committed `.copier-answers.yml` is the entire reproduce state.
- The copier-only guarantee is preserved **for free**: because `bailiff.py reproduce`
  only issues plain `copier recopy` commands, a human with copier but no bailiff (and
  no `just`) runs the same commands by hand and gets a byte-identical result (US1 /
  SC-001). That direct-copier invocation is the documented **fallback**, not a
  competing primary path.

Technical approach, verified against copier 9.16.0 (unchanged from 001 — see
`specs/001-bailiff-vertical-slice/research.md`; this spec re-verifies nothing about
copier, only re-packages bailiff). Every verb is `scripts/bailiff.py <verb>`:

- **discover** `<src> [--ref REF]` — the static `copier.yml`/file-tree/tag parse
  from 001 (questions, secret flags, `when:false` edges, `_jinja_extensions`,
  `reproducible`, PEP 440 `versions`). No Jinja env, no template code → safe on
  untrusted sources.
- **trust** `add <prefix>|--from-source <src>` / `list` — the only writer of
  copier's `settings.yml` `trust:`, on explicit consent; `--from-source` computes
  the suggested owner-path prefix (001's `_suggest_prefix`).
- **init** `--run-spec <file> [--check]` — drives `run_copy(data=…, defaults=True,
  overwrite=True[, pretend=check])` per template layer (via `runner.py`); injects
  the frozen `today`; refuses an unreproducible template and an untrusted
  action-taking source before writing (the 001 pre-checks, retained). `--check`
  is copier's own `--pretend` dry run. Writes NO bailiff artifact.
- **reproduce** `[DEST]` — enumerates the committed answers file(s) and drives
  `run_recopy(vcs_ref=VcsRef.CURRENT, defaults=True, overwrite=True)` per layer
  (via `runner.py`). At N=1, one file → one recopy. Never bare recopy. Ordering of
  N>1 layers is 003's topo-sort slotting into this same loop.
- **copier-only fallback** (documented in SKILL, not a bailiff verb): `copier recopy
  --vcs-ref=:current: --defaults --overwrite` per answers file, run by hand with no
  bailiff/just — the exact commands `bailiff.py reproduce` issues.

## Technical Context

**Language/Version**: Python 3.11+ for the one bundled script; shell for the
documented direct-copier invocations. (`pyproject.toml` already targets 3.11+.)

**Primary Dependencies**: `copier>=9.16,<10` (the engine, pinned), `packaging`
(PEP 440 tag filtering), `pyyaml` (static `copier.yml` read + run-spec parse) —
all already declared. No new dependency. `uv` runs the script with the project's
locked deps; `./scripts/bailiff.py` works when those deps are importable. `git` and
`copier` are host tools for the direct-invocation path.

**Storage**: Files only. Inputs = the copier answers/`--data-file` run-spec the
skill authors (documented plain YAML — Constitution VIII). Outputs = the generated
project tree + copier's `.copier-answers.yml` (the *entire* reproduce state; no
bailiff file). Trust lives in copier's `settings.yml`
(`~/.config/copier/settings.yml` or `COPIER_SETTINGS_PATH`).

**Testing**: `pytest`, hermetic/offline via local `git` template fixtures; one
marked network smoke test against `bailiff-io/bailiff-template-example`. The loop
tests are **adapted, not weakened** (FR-007): assertions that previously invoked the
`bailiff` console script now invoke `scripts/bailiff.py <verb>` across the full loop
(discover/trust/init/reproduce), asserting the same outcomes (byte-identical
reproduce, refusals, exit codes). One reproduce test additionally runs the
**copier-only-by-hand** fallback (plain `copier recopy` with no bailiff/just) and
asserts it matches `bailiff.py reproduce` byte-for-byte (US1). `mypy --strict` +
`ruff` apply to the bundled script and the retained library modules.

**Target Platform**: Developer workstations + CI (macOS/Linux).

**Project Type**: A skill + bundled script + copier templates. NOT a published
application: no `[project.scripts] bailiff`, no `uvx bailiff`/PyPI target.

**Performance Goals**: None; correctness + determinism only.

**Constraints**: Hermetic/offline tests except one marked smoke test; faithful
byte-identical reproduce with **copier alone** (no bailiff, no just); no bailiff file
committed into a generated project; deterministic phase never prompts and never
writes trust; no deprecated copier surface (static parse suffices, no adapter);
glue justified only by a copier gap (Constitution I / C-11).

**Scale/Scope**: Single template, single render — the same loop 001 proved, now
re-packaged. Multi-template orchestration + runtime-recompute ordering are 003
(this spec fixes only the reproduce-time recompute *contract* they must satisfy,
FR-004/FR-005). Deliverables: `scripts/bailiff.py`, a rewritten `skills/bailiff/SKILL.md`,
an updated commands contract, an updated `try-bailiff.sh`, `pyproject.toml` edits,
and the adapted test suite.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution **v2.1.0** (Principles I–VIII; III/I reconciled to
runtime-recompute in the same PR that reshaped this spec). Initial gate: **PASS**.

| Principle | Gate | How this plan satisfies it |
|---|---|---|
| I — Skills + templates + minimal glue | PASS | Deliverable is `SKILL.md` + one bundled `scripts/bailiff.py` driving copier's public API once per template layer (never re-implementing it). Removes `[project.scripts] bailiff`. Uniform 1..N path — no speculative single-template branch. Strictly *reduces* glue vs 001. |
| II — Two-phase; skill conducts, helpers execute | PASS | Skill authors the run-spec; the deterministic phase is `scripts/bailiff.py` (init/reproduce/discover/trust), runnable/testable with no LLM. Agent never in reproduce. |
| III — Faithful, agent-free reproduce | PASS | `bailiff.py reproduce` drives `run_recopy(vcs_ref=CURRENT, …)` per answers file; bare recopy never used; multi-template order recomputed (003), never frozen. The exact commands run by hand without bailiff reproduce identically. Determinism test asserts byte-identity. |
| IV — Prefer CLI + static config; adapter only if used | PASS | `discover` is a static parse; init/reproduce drive copier's **public** `run_copy`/`run_recopy`; `--check` is copier's `--pretend`; no Jinja env, no `Template`/`Worker` → **no adapter, no drift test**. copier pinned `<10`. |
| V — Determinism via pinning; trust by source | PASS | `today` injected via `data=`; trust in `settings.yml` (expanded-https), written only by `bailiff.py trust` on consent; copier authoritatively refuses untrusted sources (bailiff pre-checks to name the prefix); CI fails loudly. |
| VI — Template-author contract at discovery | PASS | Reproducibility refusal (answers-file `.jinja`) is enforced *at discovery* (its constitutional home), re-checked before `init` writes, + SKILL stop-on-`reproducible:false`; version resolvability likewise. |
| VII — Hardening per-step (scaled) | PASS | DoD = byte-identical reproduce test (both via `bailiff.py reproduce` and the by-hand copier-only fallback) + error surfacing (`bailiff.py` translates copier errors + surfaces `DiscoveryError`/`UntrustedSourceError`) + adapted loop/unit tests. No adapter → no drift test. |
| VIII — Documented, dry-run-validated handoff | PASS | Handoff stays a documented plain-YAML run-spec; validation is copier's `--pretend`. No pydantic/JSON-Schema. |

**Complexity deviations**: none. This plan *removes* surface (the `bailiff` console
entry, the justfile writer) and *relocates* the init/reproduce/discover/trust logic
from an installed console script into one bundled script driven through a single
uniform 1..N path — rather than adding any. No speculative code: the uniform loop is
the minimum that serves both N=1 today and N>1 at 003.

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
`specs/001-bailiff-vertical-slice/research.md` and is unchanged. A data-model doc is
unnecessary — the data at the seam is the same run-spec / discovery-result / trust
entry / recorded answers documented in 001's contracts.

### Source Code (repository root)

```text
scripts/
├── bailiff.py             # NEW: the single bundled orchestration script (shebang + `uv run`-able).
│                        #   Verbs: `discover`, `trust add|list`, `init [--check]`, `reproduce` —
│                        #   ONE uniform 1..N path (N=1 = single template). Reuses src/bailiff/*.
└── try-bailiff.sh         # UPDATED: inspectable walkthrough using scripts/bailiff.py end-to-end +
                         #   a copier-only-by-hand reproduce finale (drop the justfile step and
                         #   the installed-bailiff framing).

skills/bailiff/
└── SKILL.md             # REWRITTEN: phase-1 procedure invoking `./scripts/bailiff.py
                         #   discover|trust|init|reproduce`; documents the copier-only reproduce
                         #   fallback; removes all `bailiff`-console / `just reproduce` refs.

src/bailiff/               # Retained library logic (imported by scripts/bailiff.py):
├── discovery.py         #   KEEP — static discovery incl. `reproducible` (VI gate lives here).
├── trust.py             #   KEEP — settings.yml trust read/write + prefix suggestion (_suggest_prefix
│                        #   lifted here so init + trust --from-source share it).
├── errors.py            #   KEEP — DiscoveryError / UntrustedSourceError / NotReproducibleError etc.
├── runner.py            #   KEEP + ACTIVE — the per-layer copier driver (run_copy/run_recopy + error
│                        #   translation + reproducibility/trust pre-checks). Used by bailiff.py init &
│                        #   reproduce today (N=1) and by 003's ordering for N>1. Add a small
│                        #   answers-file enumeration helper (reproduce loops over the file(s)).
└── cli.py               #   REMOVED — its verbs move into scripts/bailiff.py (which imports the same
                         #   discovery/trust/runner libs). Delete once scripts/bailiff.py subsumes it;
                         #   drop the justfile writer (_REPRODUCE_JUST/_write_reproduce_recipe) entirely.

pyproject.toml           # EDIT: remove [project.scripts] bailiff (FR-001/US4/SC-003). Keep the package
                         #   buildable for tests importing src/bailiff, or convert to a src-on-path dev
                         #   layout — a task decides the lightest shape that keeps mypy/tests green.

tests/
├── loop/                # ADAPTED (not weakened): invoke scripts/bailiff.py for the whole loop; same
│   │                    #   assertions. Reproduce also verified by hand with copier-only (US1).
│   ├── test_init.py                  # `bailiff.py init` (N=1); asserts recorded answers, NO justfile/bailiff file written
│   ├── test_reproduce.py             # `bailiff.py reproduce` byte-identical + the by-hand `copier recopy :current:` fallback (no bailiff/just)
│   ├── test_check.py                 # `bailiff.py init --check` (copier --pretend) writes nothing; surfaces invalid answers
│   ├── test_trust_refusal.py         # action-taking untrusted source refused; consent via bailiff.py trust → success
│   ├── test_answersfile_refusal.py   # discover reports reproducible:false; init refuses before writing (VI)
│   ├── test_discover_static_safe.py  # discover executes no template code, needs no trust
│   ├── test_secret_edge_exclusion.py # secret + when:false NOT persisted (unchanged behavior)
│   └── test_smoke_remote.py          # marked network smoke vs bailiff-template-example, via the new invocation
├── unit/                # KEEP — discovery parsing + runner (per-layer driver) + trust/prefix suggestion
└── test_smoke.py        # ADAPTED — package/script imports; drop the `bailiff.cli:main` console assumption
```

**Structure Decision**: The primary deliverables are `skills/bailiff/SKILL.md` and
the single bundled `scripts/bailiff.py`, which drives the full lifecycle through one
uniform 1..N path. `src/bailiff/{discovery,trust,errors,runner}.py` are retained as
the library the script imports — `runner.py` is the **active** per-layer copier
driver for both N=1 (this spec) and N>1 (003's ordering slots into it). `cli.py`
is removed (its verbs move into `scripts/bailiff.py`). No new module, no adapter, no
package publication. The generated project contains only copier-native files.

## Design note — uniform 1..N path (per user direction)

Single-template work uses the **same code path** as multi-template, with N=1. There
is deliberately **no single-template-only branch** and **no verb that is meaningless
at N=1**. `bailiff.py reproduce` enumerates the committed answers file(s) and drives
`copier recopy --vcs-ref=:current:` per layer; at N=1 that is one file → one recopy.
This resolves the earlier "what does `bailiff.py` expose" question: it exposes the
full lifecycle (`discover`/`trust`/`init`/`reproduce`), uniformly. `runner.py` is
therefore active on the primary path now (not merely 003 substrate), which also
settles its retention with no judgment call outstanding. The copier-only-by-hand
reproduce (US1) remains the guarantee/fallback because `bailiff.py` only ever issues
plain copier commands.

## Complexity Tracking

No constitutional violations. This plan reduces surface versus the merged 001 code
(removes: the `bailiff` console script, the generated justfile + its writer, `cli.py`)
and relocates the lifecycle logic into one bundled script on a single uniform path.
No speculative code: the uniform loop is the minimum serving N=1 now and N>1 at 003,
and `runner.py` is retained because it is the active per-layer driver, not
speculative future glue.
