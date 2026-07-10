---
description: "Task list for clerk skill packaging — installable via APM marketplaces (Claude + Codex) (spec 008)"
---

# Tasks: clerk skill packaging — installable via APM marketplaces (Claude + Codex)

**Input**: Design documents from `specs/008-packaging/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[contracts/packaging.md](./contracts/packaging.md),
[constitution](../../.specify/memory/constitution.md) v2.1.0

**Tests**: INCLUDED. Constitution VII: the preflight logic, vendored-drift check,
and pack/validate gate are part of this spec's definition-of-done.

**Organization**: grouped by user story (US1–US4 from spec.md).

## Design decisions this task list assumes (resolved; flagged for review)

- Distribution uses APM's own tooling (`apm pack`/`publish`/`marketplace`) — verified
  against the live CLI. Both Claude + Codex outputs are native (`apm pack --marketplace=claude,codex`).
- clerk's core is **vendored** (`src/clerk/*` copied into the package skill dir via
  `just vendor`, drift-checked) — NO PyPI `clerk` (spec 010). Q-008a = vendored
  modules, not single-file amalgamation.
- Third-party deps are **checked, not auto-installed** (environment-aware
  suggestion; no package manager assumed) — user direction.
- v1 = marketplace artifacts (`apm pack`); registry `apm publish` deferred until the
  `registries` feature is stable (Q-008b). Manifests committed + stable-URL-served (Q-008c).
- Fan-out / cocogitto / catalog.json / GitHub App / module scaffolder = DEFERRED (FR-008).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no incomplete-task dependency)
- Exact file paths included

---

## Phase 1: Preflight core + doctor (US4 — the portability guarantee)

**Purpose**: make the bundled script survive on a machine without its deps.

- [ ] T001 [US4] Create `src/clerk/_preflight.py` (stdlib only, NO third-party import — it runs before deps are guaranteed): a `REQUIRED_DEPS` constant (the single source of truth: copier/pyyaml/packaging/tomli-w with version notes), `missing_deps()` (importlib.util.find_spec per dep), `detect_manager()` (first on PATH of uv/pipx/pip/pip3/brew via shutil.which, documented order), `install_suggestion(missing)` (build the manager-appropriate command; generic `pip install` + uv/pipx pointer if none detected).
- [ ] T002 [US4] Wire the preflight into `scripts/clerk.py`: run it before argparse dispatch; if deps missing, print the suggestion to stderr and exit non-zero (documented code) — never a raw ImportError. Add a `doctor` verb that runs the same check and reports readiness (exit 0 ready / non-zero with suggestion). Ensure the module-resolution shim still works both from-repo (src/clerk) and installed (vendored beside the script).
- [ ] T003 [US4] Add the PEP 723 header to `scripts/clerk.py` (`# /// script` … dependencies=[…]) listing exactly `_preflight.REQUIRED_DEPS` — derive/generate so the header and the checked list share one source of truth (a test asserts they match).
- [ ] T004 [P] [US4] `tests/unit/test_preflight.py` (NEW, stdlib/hermetic): all deps present → missing_deps() empty; monkeypatch a missing dep → named in the suggestion; monkeypatch PATH so only uv / only pipx / only pip / only brew / none is present → correct suggestion each; partial-missing → only missing reported; PEP 723 header list == REQUIRED_DEPS.

**Checkpoint**: `clerk doctor` works; a missing dep yields a clean suggestion, not a traceback; header and preflight agree.

---

## Phase 2: APM package layout + marketplace block (US1/US2)

- [ ] T005 [US1] Add the `marketplace:` block to `apm.yml` via `apm marketplace init --name clerk --owner copier-clerk`, then edit per the VERIFIED schema in contracts/packaging.md: `marketplace.outputs.{claude,codex}` (nested map — claude on by default, ENABLE codex), `build.tagPattern`, and a `packages:` entry for clerk with `source: ./packages/clerk` (local), `version`, and **`category: Productivity`** (HARD requirement — `apm pack` errors if codex is enabled and any package lacks `category`). Ensure top-level `license:` is set (else SBOM NOASSERTION). Outputs write to the profile defaults `.claude-plugin/marketplace.json` + `.agents/plugins/marketplace.json` — commit both.
- [ ] T006 [US1] Create `packages/clerk/.claude-plugin/plugin.json` (match the secrets-scan reference: name/version/description/author/license/`skills: "./.apm/skills"`) and `packages/clerk/apm.yml` (package metadata: name/version/description/`type: hybrid`/`target: all`/`includes: auto`/`license`).
- [ ] T007 [US1] `just vendor` recipe: copy `src/clerk/*.py` (incl. `_preflight.py`) into `packages/clerk/.apm/skills/clerk/scripts/clerk/`, and place `scripts/clerk.py` + the source `SKILL.md` at `packages/clerk/.apm/skills/clerk/`. `just check-vendor`: regenerate to a temp path and diff vs the committed vendored copy; exit non-zero on drift. Commit the generated tree (check-vendor guards it) OR generate-at-pack (ensure `just pack` runs `vendor` first) — document which.
- [ ] T008 [P] [US2] Confirm `apm pack --marketplace=claude,codex --dry-run` reports BOTH a Claude (`.claude-plugin/marketplace.json`) and a Codex (`.agents/plugins/marketplace.json`) artifact; `apm marketplace validate` passes on each. (Verified in the spike; re-confirm against the real package layout.)

**Checkpoint**: `apm.yml` has a valid `outputs.{claude,codex}` block with the clerk package's `category` set; `apm pack --marketplace=claude,codex --dry-run` succeeds; vendored layout builds + drift-checks.

---

## Phase 3: Build/release recipes + CI gate (US3)

- [ ] T009 [US3] `justfile`: `just pack` (`apm pack --marketplace=claude,codex`), `just release` (`just vendor` → `just check-vendor` → `apm pack --marketplace=claude,codex --check-versions --check-clean` → document the `apm publish` step as deferred/optional pending the registries feature). Recipes are the documented, gated release path.
- [ ] T010 [P] [US3] `.github/workflows/pack.yml` (NEW, minimal — NOT the fan-out pipeline): on PR, run `just check-vendor` + `apm pack --marketplace=claude,codex --dry-run` + `apm marketplace validate`. A build gate only.
- [ ] T011 [P] [US3] `tests/loop/test_packaging.py` (NEW): assert `apm.yml` parses and has a marketplace block with claude+codex outputs; `apm pack --marketplace=claude,codex --dry-run` exits 0 (guard/skip if `apm` unavailable in the test env); vendored-drift check passes; `clerk doctor` subprocess exit codes. Mark apm-CLI-dependent parts so they skip cleanly where apm isn't installed.

**Checkpoint**: `just release` is a documented gated sequence; CI validates pack + vendor on PR.

---

## Phase 4: Portable SKILL + docs (US1)

- [ ] T012 [US1] Extend `skills/clerk/SKILL.md`: portable Prerequisites — document the dep preflight / `clerk doctor` / install-suggestion flow (uv/pipx/pip/brew); confirm the frontmatter description auto-triggers by semantics (not repo path) so it works installed into any project; note nothing assumes clerk's own repo. Keep the two-phase boundary intact.
- [ ] T013 [P] [US1] Extend `README.md`: `## Install` section — add the clerk marketplace (claude + codex), install the clerk package, run `clerk doctor`. Note no PyPI package; deps are checked with an install suggestion.

**Checkpoint**: the SKILL is repo-path-independent and documents the install/preflight flow; README has install instructions.

---

## Phase 5: Gate + closeout

- [ ] T014 Full gate on the branch: `uv run ruff check src/ tests/ scripts/ && uv run ruff format --check src/ tests/ scripts/ && uv run mypy && uv run pytest -q`. Confirm existing 001/010/002 tests still pass (the preflight addition + shim change must not regress single/multi init/reproduce or catalog). `apm pack --marketplace=claude,codex --dry-run` + `apm marketplace validate` green.
- [ ] T015 Update `.specify/memory/roadmap.md`: split the 008 entry — mark the **packaging** half `implemented` (skill installable via claude+codex marketplaces; vendored core; dep preflight; gated apm pack/publish path); record the **fan-out / authoring-lifecycle** half as a distinct deferred entry (008b or folded into 009's prerequisites) with its ADR-0006 scope intact. Confirm 009's dependency notes still read correctly.
- [ ] T016 Open the PR (title = user-facing changelog entry, no spec IDs; `## Spec Context` body per the hook); push via `dgit push`. Do NOT merge without the user's go-ahead.

---

## Dependencies & parallelism

- **Phase 1 (T001–T004)** is the core; T002 depends on T001; T003/T004 follow.
- **Phase 2 (T005–T008)** depends on Phase 1 (the vendored core includes
  `_preflight.py`; the package bundles the preflight-bearing script). T005/T006 can
  parallelize; T007 needs them; T008 needs T005+T007.
- **Phase 3 (T009–T011)** depends on Phase 2 (recipes/CI/tests exercise the block +
  vendoring).
- **Phase 4 (T012–T013)** is docs — parallel to Phase 3 once the surface is stable.
- **Phase 5 (T014–T016)** is closeout.

## Definition of done (maps to spec Success Criteria)

- SC-001 — clerk installs into a fresh Claude project + `clerk.py --help` runs there
  (T005–T007 layout; smoke in T011/manual).
- SC-002 — `apm pack --marketplace=claude,codex` yields both, validating (T005/T008/T011).
- SC-003 — missing dep → environment-aware suggestion + clean exit; `doctor` same
  (T001–T004).
- SC-004 — gated release sequence catches version/tree drift (T009/T010).
- SC-005 — no PyPI `clerk`; no assumed manager; vendored core drift-checked
  (T007/T014).
- SC-006 — no fan-out/authoring CI added; deferred cleanly (T015).
