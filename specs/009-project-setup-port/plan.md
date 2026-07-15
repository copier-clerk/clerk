# Implementation Plan: project-setup module port → bailiff-mod-* (spec 009) — **Phase 0**

**Branch**: `009-project-setup-port` (planned on worktree branch `009-clarify`) |
**Date**: 2026-07-13 | **Spec**: [spec.md](./spec.md)

**Input**: The CLARIFIED spec 009 (7 questions resolved 2026-07-13). Governed by the
constitution v2.1.0 (Principles I–VIII) and ADR-0002/0003/0006.

---

> ### SCOPE: PHASE 0 ONLY
>
> This plan and its `tasks.md` cover **Phase 0 = v1** only: the collapsed
> **`bailiff-mod-base`** (6 base modules) + one language overlay **`bailiff-mod-python`**.
> Phases 1–3 (remaining languages, quality/tooling, agent-steered/integration) are
> **deferred** — see the *Forward note* at the end. Do NOT decompose later phases here.
>
> Phase 0 is the minimal real module slice that **unblocks spec 008b** (its
> fan-out/release/e2e phases are hard-blocked until ≥1 real `bailiff-mod-*` module lands
> under `templates/`).

---

## Summary

Port the two Phase-0 modules from the `project-setup` skill
(`~/.claude/skills/project-setup/`) into copier templates authored in this monorepo
under `templates/bailiff-mod-base/` and `templates/bailiff-mod-python/`. The port is a
**mechanical translation, not a rewrite** (D-009-2): project-setup `[[inputs]]` →
copier questions; `[order]` → `when:false` edges; deterministic `python` steps →
rendered template files; code-executing / network steps → trust-gated copier `_tasks`;
one `agent`-tier decision (`agents-md` resolve-arch) → phase-1 judgment frozen as
structured-fact `--data` answers.

**No new tool code** (Constitution I / C-11): everything is copier template content
authored via the 008b authoring plane (`just new-module`, `scripts/check_modules.py`,
`cog.toml`, `catalog-sources.toml`). The existing spec-003 `init_many`/`reproduce_many`
engine and the single source-trust gate drive these two templates exactly as any other
layer. This plan verified the port surfaces **no** copier gap (Constitution I / C-11):
questions, rendered files, conditional `when:`, `when:false` edges, and trust-gated
`_tasks` are all native copier features.

## Technical Context

**Language/Version**: No application code. Deliverables are copier YAML + Jinja
templates + shell `_tasks`. `check_modules.py` (existing, Python 3.11+) is the lint;
no new `src/bailiff/` module, no new `scripts/bailiff.py` verb.

**Primary Dependencies**: copier `>=9.16,<10` (the render/reproduce engine, pinned).
Generated-project tooling invoked by tasks: `git`, `gh` (LICENSE fetch, as
`bailiff-template-example` today), `gitnr` (pinned, `.gitignore` generation — Q7), and for
`bailiff-mod-python` the `uv` toolchain surfaced by preflight.

**Storage**: N/A — files rendered into the generated project tree; state carried in each
layer's `.copier-answers.yml` (`_src_path` = split repo, `_commit` = pin — ADR-0002).

**Testing**: `pytest` init+reproduce integration tests under `tests/loop/` reusing the
existing `build_template_repo` / `multi_template_set` fixtures (cf. 007). Tasks stubbed
to deterministic offline no-ops so the suite is hermetic (Constitution VII / dev
workflow). `just check-modules` is the contract gate (SC-006).

**Target Platform**: developer/CI shells (macOS/Linux); copier CLI + trust via
`settings.yml`.

**Project Type**: copier template family authored in a monorepo, fanned out per-repo by
008b (ADR-0006). Consumed as multi-template layers (ADR-0003).

**Constraints**: reproduce is faithful + agent-free (Constitution III); byte-identical
for **managed** renders only; **seed-once** files (`AGENTS.md`, `pyproject.toml`) via
`_skip_if_exists`; **task outputs** (`.gitignore` via gitnr, `LICENSE` via gh) are
process-deterministic, outside the byte-identical set. NO `jinja2_time`; `today` injected
as an answer (Constitution V). NO `secret:` questions (Constitution VI).

**Scale/Scope**: 2 modules. `bailiff-mod-base` collapses 6 project-setup base modules into
one template (Q1/FR-013); `bailiff-mod-python` is one language overlay `run_after` base.

## Constitution Check

*GATE: passed before design; re-checked against the clarified decisions below.*

| Principle | Verdict | How Phase 0 satisfies it |
|---|---|---|
| **I — Skills + Templates + Minimal Glue (C-11)** | PASS | Pure template content under `templates/bailiff-mod-{base,python}/`. NO new `src/bailiff/` module, NO new `scripts/bailiff.py` verb. Q5 (gates→copier booleans + source trust), Q6 (preflight `_task`), Q7 (gitnr `_task`) each avoid new glue — verified no copier gap. Authored via existing `just new-module`; linted by existing `check_modules.py`. |
| **II — Two-Phase; skill conducts, helpers execute** | PASS | The one `agent`-tier decision (`agents-md` resolve-arch) is phase-1 judgment: the skill freezes `architecture_md` + `agent_editable_globs` as `--data` answers (structured facts, Q3). Reproduce replays them; no agent in the reproduce path. |
| **III — Reproduce is faithful + agent-free** | PASS (with lifecycle split) | **Managed** files (dir scaffold `.gitkeep`s, AGENTS.md skeleton render) re-render byte-identically from committed answers. **Seed-once** files (`AGENTS.md`, `pyproject.toml`) use `_skip_if_exists` — on a *fresh-checkout* reproduce they render normally (III holds); the skip only protects an already-populated re-run/`update` tree (SC-003a). **Task outputs** (`.gitignore`/gitnr, `LICENSE`/gh) are process-deterministic (III explicitly allows task side-effects). Order recomputed from committed answers + pinned edges (base internal; python `run_after` base). |
| **IV — copier CLI + static config** | PASS | Edges are `when:false` hidden answers statically read from `copier.yml`; no deprecated Template/Worker surface introduced. |
| **V — Determinism via pinning; trust by source** | PASS | `gitnr` and `gh` LICENSE and `git init/commit` are trust-gated `_tasks`; `gitnr` **version-pinned** in the task command (Q7); `today` injected as an answer, never `jinja2_time`. Trust is source-level; the deterministic phase never writes trust. |
| **VI — Template-author contract** | PASS | Both modules ship `{{ _copier_conf.answers_file }}.jinja`; clean PEP 440 tags via cocogitto fan-out (ADR-0006); `when:false` edges; new `_migrations` format only if any declared (none in Phase 0); **NO `secret:` questions** — LICENSE/`gh` reads token from ambient env (like `bailiff-template-example`). |
| **VII — Hardening is per-step** | PASS | Each module lands an init+reproduce integration test; managed-render byte/drift assertion; error surfacing via the existing `_translate`; `check_modules.py` gate. No deprecated-surface adapter → no drift test needed. |
| **VIII — Documented, dry-run-validated handoff** | PASS | Frozen inputs are copier answers (`--data`/answers-file) documented in `SKILL.md`; the agent-frozen `architecture_md` is **structured facts rendered deterministically**, not a bespoke schema. Validation reuses copier's own dry run + answer validation. |

No violations → **Complexity Tracking is empty** (see end).

## Project Structure

### Documentation (this feature)

```text
specs/009-project-setup-port/
├── spec.md              # CLARIFIED spec (source of truth)
├── plan.md              # This file (Phase 0)
└── tasks.md             # Phase-0 dependency-ordered tasks
```

No separate `contracts/` doc: the per-module question / file-lifecycle / edge / task
contract lives inline in this plan (the *Module → file → lifecycle mapping* and
*Ordering-edge design* sections). A standalone contracts file would duplicate it — the
economy call; add one only if a later phase needs a shared cross-module contract.

### Authored template content (repository root)

```text
templates/
├── bailiff-mod-base/                         # Q1: 6 base modules collapsed into ONE template
│   ├── copier.yml                          # questions, when:false edges, _tasks (preflight→gitnr→license→git)
│   ├── {{ _copier_conf.answers_file }}.jinja
│   ├── README.md                           # documents git/gh/gitnr prerequisites (FR-007b)
│   ├── CHANGELOG.md                        # cog-managed
│   └── template/                           # _subdirectory: rendered subtree
│       ├── {{ _copier_conf.answers_file }}.jinja
│       ├── AGENTS.md.jinja                 # SEED-ONCE (single/monorepo body + arch splice)
│       └── <dir scaffold>/.gitkeep         # MANAGED — the 20 base dirs (+15 monorepo targets)
└── bailiff-mod-python/                       # language overlay, run_after bailiff-mod-base
    ├── copier.yml                          # threaded project_name, python_version, framework, run_after edge, uv preflight
    ├── {{ _copier_conf.answers_file }}.jinja
    ├── README.md                           # documents uv prerequisite (FR-007b)
    ├── CHANGELOG.md
    └── template/
        ├── {{ _copier_conf.answers_file }}.jinja
        └── pyproject.toml.jinja            # SEED-ONCE (language manifest)

# Registration (edited by `just new-module`, verified by check_modules.py three-way parity):
cog.toml                 # [monorepo.packages.bailiff-mod-base] + [.bailiff-mod-python]
catalog-sources.toml     # [[sources]] url for each (created on first new-module run)
skills/bailiff/SKILL.md    # FR-012: documents the ported family + base-selection step
```

**Structure Decision**: mirror `examples/bailiff-template-example/` (a `_subdirectory:
template` subtree so `copier.yml` never lands in the generated project) and the
`_meta/module-template/` scaffolder output. Both modules are authored in-monorepo; 008b
fans each out to `bailiff-io/bailiff-mod-<name>` (consumers source the split repo, never
the monorepo — ADR-0002 `_src_path` gotcha).

---

## Phase-0 module → file → lifecycle mapping

Each output is classified **managed** (re-rendered byte-identically, Constitution III),
**seed-once/living** (`_skip_if_exists`; scaffolded at init, then project-owned —
D-009-7 / FR-005a), or **task-output** (process-deterministic, outside the
byte-identical set — like `bailiff-template-example`'s LICENSE).

### `bailiff-mod-base` (collapses core-identity, dirs-scaffold, gitignore-generate, license-write, agents-md, git-init)

| Output | Source module | Lifecycle | Notes |
|---|---|---|---|
| Directory scaffold `<dir>/.gitkeep` (20 base dirs; +15 monorepo targets when `layout=monorepo`) | dirs-scaffold | **managed** | Verbatim dir list from `dirs-scaffold/module.py` `_BASE_DIRS`/`_MONOREPO_TARGETS`. (module.py docstring says "21" but the local list is **20** entries — verify exact list at port; FR-011 forbids adding/removing.) Rendered as empty `.gitkeep` files. |
| `AGENTS.md` | agents-md | **seed-once** (`_skip_if_exists`) | Rendered from `template/AGENTS.md.jinja` = the `single.md`/`monorepo.md` body (chosen by `layout`) with `PROJECT_NAME`/`ORG`/description substituted, plus the `## Architecture` sentinel span rendered from frozen `architecture_md` **iff `write_architecture=true`** (Q3+Q5). Seed-once because the project evolves it during development (D-009-7). Fresh-checkout reproduce still renders it (III holds). |
| `.gitignore` | gitignore-generate | **task-output** (gitnr, pinned) | Q7: NOT a choice list and NOT a byte-rendered file. Generated by a version-pinned `gitnr` trust-gated `_task` from a threaded `gitignore_stack` answer (see *Ordering* below). Process-deterministic; regenerates the whole file (idempotent on reproduce). |
| `LICENSE` | license-write | **task-output** (gh api) | Ported exactly like `bailiff-template-example`: `test -f LICENSE || gh api /licenses/<key>` with `[year]`/`[fullname]` filled from frozen `today`/`org`. Network-sourced → outside the byte-identical set; guard makes reproduce idempotent. `license` is a fixed 13-SPDX `choices:` question (FR-003 / Q7). |
| `.git/` + optional initial commit | git-init | **task-output** (git) | `git init --quiet` (idempotent), then — iff `initial_commit=true` — `git add -A && git commit`. Ordered **last** among base `_tasks` (Q1/FR-013 template-internal). See the git-commit-scope caveat under *Residual ambiguities*. |
| `.copier-answers.yml` | (copier) | **managed** | copier writes it from the answers-file `.jinja`; records `_src_path` + `_commit` for faithful reproduce. |

**core-identity** contributes **no file** — faithful to project-setup (its `record` step
is a no-op that only provides the upstream answers `project_name`/`org`/`description`/
`layout`/`license`). In the collapsed template these become plain `copier.yml` questions.

### `bailiff-mod-python` (ports lang-python — reconciled against `lang-python-v1.3.0`)

| Output | Lifecycle | Notes |
|---|---|---|
| `pyproject.toml` | **seed-once** (`_skip_if_exists`) | Language manifest (FR-005a explicit): uv/ruff/pytest config + `requires-python` pinned from `python_version`; threaded `{{ project_name }}` in `[project].name`. Project bumps deps after init → never re-rendered. |
| Python `.gitignore` entries | **task-output** (via base gitnr) | lang-python's "appends Python .gitignore entries" is realized by threading `python` into the base `gitignore_stack` answer that base's gitnr task consumes — one `.gitignore` generation point, no double-append (see *Ordering*). |
| ruff pre-commit hook fragment | **DEFERRED / flagged** | lang-python-v1.3.0 appends its ruff hook block (`astral-sh/ruff-pre-commit` `rev: v0.6.9`, `ruff --fix` + `ruff-format`) to a `.pre-commit-config.yaml` **owned by `precommit-setup`** (a Phase-1 module). With no precommit-setup in Phase 0 there is no file to append to — do not invent a standalone precommit file in Phase 0. Moves in (rev pinned from `ruff_version`) when `bailiff-mod-precommit` lands. |

**Managed vs seed-once summary**: MANAGED = base dir scaffold + copier-answers files;
SEED-ONCE = `AGENTS.md`, `pyproject.toml`; TASK-OUTPUT = `.gitignore` (gitnr), `LICENSE`
(gh), `.git/` + commit.

---

## Ordering-edge design

**`bailiff-mod-base` — no cross-module edges** (it is the upstream root). Its
`depends_on`/`run_after`/`run_before` `when:false` answers default `[]`. The internal
6-module ordering (identity → dirs/gitignore → license → agents-md → git-commit-last) is
**template-internal** (Q1/FR-013), expressed two ways inside the one template:

1. **Render order** is irrelevant for independent files (copier renders the whole
   subtree); the identity answers are just `copier.yml` questions available to every
   Jinja file.
2. **`_tasks` order** (copier runs tasks post-render, in listed order) encodes the
   consequential sequence:
   1. **preflight** (Q6) — `git`/`gh`/`gitnr` presence check, fails with install
      guidance. Ordered **FIRST** so no consequential task runs against a missing tool.
   2. **gitnr** → `.gitignore`.
   3. **gh** → `LICENSE`.
   4. **git init**.
   5. **git commit** (last, `when: initial_commit`).

**`bailiff-mod-python` — one edge**: `run_after: [bailiff-mod-base]` as a `when:false`
hidden answer (ADR-0003). The spec-003 engine sequences base fully before python. NO
hardcoding of "base supplied `project_name`" — python declares
`default: "{{ project_name }}"` and bailiff threads it via `data=` (FR-010); the overlay
also renders standalone with defaults (US2 #2 / SC-006-style self-containment).

**gitnr stack threading (the one multi-layer subtlety)**: base owns the single
`.gitignore` gitnr task, keyed off a `gitignore_stack` list answer (default `[]`,
base/global editors + OS). Because the phase-1 skill knows the WHOLE selection up front
(base + python), bailiff injects the selected language(s) into `gitignore_stack` via
`--data` at init; the answer is frozen, so reproduce replays gitnr identically. The
python overlay does **not** write `.gitignore` (avoids two writers / non-idempotent
appends). Flagged as a design decision — see *Residual ambiguities*.

---

## How each clarified decision is realized in copier terms

- **Q1 — collapsed base (FR-013)**: ONE `templates/bailiff-mod-base/` template, one
  answers file, one `cog.toml`/`catalog-sources.toml`/fan-out entry. The 6 modules'
  inter-base `[order]` edges (`dirs after core-identity`, `gitignore after dirs`,
  `license requires core-identity`, `agents-md after dirs requires core-identity`,
  `git-init after *`) collapse to template-internal `_tasks` ordering + shared questions
  — **no cross-module `when:false` edges among the 6**.
- **Q3 — file lifecycle + agent-tier facts**: per-file classification above
  (`_skip_if_exists: [AGENTS.md, pyproject.toml]`). The `agents-md` architecture decision
  freezes **structured facts** — `architecture_md` (the section body) + `agent_editable_globs`
  — as `--data` answers (from `steering/resolve-arch.md`'s emitted `answers_to_persist`),
  rendered deterministically into the sentinel span. NOT a whole prose blob; the skeleton
  is a fixed template.
- **Q5 — gates → safe-default booleans + source trust**: `agents-md`'s `allow-arch-write`
  hard gate becomes `write_architecture: bool = false` (a copier question whose persisted
  answer gates the arch splice render). git-init's commit becomes `initial_commit: bool =
  false`. Code **execution** (gitnr/gh/git tasks) stays behind the single source-trust
  gate. NO per-action consent layer / `allow_flag` mechanism (C-11).
- **Q6 — tool preflight**: each module ships a preflight `_task` ordered FIRST that
  checks its required tools and fails with explicit install guidance
  (`bailiff-mod-base`: git/gh/gitnr; `bailiff-mod-python`: uv). Plus a README prerequisite
  note. copier runs all tasks post-render, so this is task-ordered-first, not literally
  pre-render (FR-007b).
- **Q7 — option lists / gitignore**: `license` = fixed 13-SPDX `choices:` (FR-003);
  `python_version` = fixed `choices:`. `.gitignore` is the exception — generated by a
  **version-pinned** `gitnr` trust-gated `_task` from the `gitignore_stack` answer, its
  output task-generated (process-deterministic). No runtime `--data` catalog injection
  needed in Phase 0.

---

## Forward note — Phases 1–3 (DEFERRED, not planned here)

Per the spec's phasing (Q2/OQ-009-b), later slices are fast-follow, NOT v1, and are
**not** decomposed in this plan:

- **Phase 1** — remaining pure-`python`-tier overlays + quality/tooling: `lang-ts`,
  `lang-go`, `lang-rust`, `precommit-setup`, `quality-hooks`, `justfile-write`,
  `ci-github-actions`, `worktreeinclude-write`. (When `precommit-setup` lands, resolve
  bailiff-mod-python's deferred ruff-hook contribution.)
- **Phase 2** — agent-steered + integration (harder translations): `env-example`,
  `readme-draft`, `stack-adr`, `github-repo`, `org-policy`, `package-add`.
- **Phase 3** — REMOVED (Q4/OQ-009-d): 009 ports NO `agentic` modules; 007's family owns
  that space.

Each later phase gets its own plan+tasks when scheduled.

## Complexity Tracking

No Constitution violations → no entries.
