---
description: "Task list for bailiff skill packaging — installable via APM marketplaces (Claude + Codex) (spec 008)"
---

# Tasks: bailiff skill packaging — installable via APM marketplaces (Claude + Codex)

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
- bailiff's core is **vendored** (`src/bailiff/*` copied into the package skill dir via
  `just vendor`, drift-checked) — NO PyPI `bailiff` (spec 010). Q-008a = vendored
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

- [X] T001 [US4] Create `src/bailiff/_preflight.py` (stdlib only, NO third-party import — it runs before deps are guaranteed): a `REQUIRED_DEPS` constant (copier `>=9.16,<10`/pyyaml/packaging/tomli-w with version specifiers), `missing_or_incompatible()` (per dep: `importlib.util.find_spec` for presence THEN `importlib.metadata.version` vs the pin — copier's pin esp. matters; carefully, since `packaging` is itself a checked dep, so version-compare copier with a stdlib fallback if packaging is absent), `detect_manager()` (first on PATH of uv/pipx/pip/pip3 via shutil.which; NO brew for pyyaml/packaging/tomli-w — brew only offered for copier), `install_suggestion(missing)` (manager-appropriate command; generic `pip install` + uv/pipx pointer if none). Scope: macOS/Linux + WSL (no native-Windows PATH/py-launcher handling).
- [X] T002 [US4] Wire the preflight into `scripts/bailiff.py` **after argparse** (so `--help`/`doctor` work with deps missing — move the top-level `yaml`/`bailiff` imports into verb handlers or lazy-import them). Missing/incompatible dep → print suggestion to stderr, exit non-zero (documented) — never a raw ImportError. Add a `doctor` verb (readiness incl. version mismatch). **Fix the module-resolution shim to DUAL-MODE (BLOCKER-1):** if a vendored `bailiff/` package dir sits beside the script, keep the script's own dir on `sys.path` (so `import bailiff` resolves to the vendored package); only insert `../src` when running from bailiff's own repo (no sibling `bailiff/`). The current shim unconditionally removes its own dir + adds `../src` → ModuleNotFoundError as-installed.
- [X] T003 [US4] Add the PEP 723 header to `scripts/bailiff.py` (`# /// script` … dependencies=[…]) listing the same deps as `_preflight.REQUIRED_DEPS`. Since the header is a static comment parsed pre-exec (can't be computed at runtime), keep them aligned with an **equality test** (T004) — not a claimed single runtime source.
- [X] T004 [P] [US4] `tests/unit/test_preflight.py` (NEW, stdlib/hermetic): all deps present+compatible → empty; monkeypatch a missing dep → named; monkeypatch an INCOMPATIBLE copier version → reported as mismatch (not "ready"); monkeypatch PATH so only uv / only pipx / only pip / none → correct suggestion each (brew only appears for copier); partial → only offending reported; `--help` and `doctor` exit 0 with deps monkeypatched absent (preflight-after-argparse); PEP 723 header list == REQUIRED_DEPS.

**Checkpoint**: `bailiff doctor` works; a missing dep yields a clean suggestion, not a traceback; header and preflight agree.

---

## Phase 2: APM package layout + marketplace block (US1/US2)

- [X] T005 [US1] Add the `marketplace:` block to `apm.yml` via `apm marketplace init --name bailiff --owner bailiff-io`, then edit per the VERIFIED schema in contracts/packaging.md: `marketplace.outputs.{claude,codex}` (nested map — claude on by default, ENABLE codex), `build.tagPattern`, and a `packages:` entry for bailiff with `source: ./packages/bailiff` (local), `version`, and **`category: Productivity`** (HARD requirement — `apm pack` errors if codex is enabled and any package lacks `category`). Ensure top-level `license:` is set (else SBOM NOASSERTION). Outputs write to the profile defaults `.claude-plugin/marketplace.json` + `.agents/plugins/marketplace.json` — commit both.
- [X] T006 [US1] Create `packages/bailiff/.claude-plugin/plugin.json` (match the secrets-scan reference: name/version/description/author/license/`skills: "./.apm/skills"`) and `packages/bailiff/apm.yml` (package metadata: name/version/description/`type: hybrid`/`target: all`/`includes: auto`/`license`).
- [X] T007 [US1] `just vendor` recipe: copy `src/bailiff/*.py` by **GLOB** (incl. `_preflight.py`, and 003's `ordering.py` once merged — do NOT enumerate a fixed list) into `packages/bailiff/.apm/skills/bailiff/scripts/bailiff/`, and place `scripts/bailiff.py` + the source `SKILL.md` at `packages/bailiff/.apm/skills/bailiff/`. `just check-vendor`: regenerate to a temp path + diff, exit non-zero on drift. **Decision: generate-at-pack** — `just pack`/`just release` run `vendor` → `check-vendor` UNCONDITIONALLY before `apm pack` (BLOCKER-2: `apm pack --check-clean` diffs only manifests, NOT the vendored copy, so the release gate alone can ship stale code). Prefer NOT committing the generated tree so it can never lead source; if committed, `check-vendor` in CI is mandatory.
- [X] T008 [P] [US2] Confirm `apm pack --marketplace=claude,codex --dry-run` reports BOTH a Claude (`.claude-plugin/marketplace.json`) and a Codex (`.agents/plugins/marketplace.json`) artifact; `apm marketplace validate` passes on each. Also confirm what Codex `policy.authentication: ON_INSTALL` requires of a credential-free skill (likely nothing — one-line check).

**Checkpoint**: `apm.yml` has a valid `outputs.{claude,codex}` block with the bailiff package's `category` set; `apm pack --marketplace=claude,codex --dry-run` succeeds; vendored layout builds + drift-checks.

---

## Phase 3: Build/release recipes + CI gate (US3)

- [X] T009 [US3] `justfile`: `just pack` (`apm pack --marketplace=claude,codex`), `just release` (`just vendor` → `just check-vendor` → `apm pack --marketplace=claude,codex --check-versions --check-clean` → document the `apm publish` step as deferred/optional pending the registries feature). Recipes are the documented, gated release path.
- [X] T010 [P] [US3] `.github/workflows/pack.yml` (NEW, minimal — NOT the fan-out pipeline): on PR, run `just check-vendor` + `apm pack --marketplace=claude,codex --dry-run` + `apm marketplace validate`. A build gate only.
- [X] T011 [P] [US3] `tests/loop/test_packaging.py` (NEW): assert `apm.yml` parses and has a marketplace block with claude+codex outputs + the bailiff package's `category` set; `apm pack --marketplace=claude,codex --dry-run` exits 0 (guard/skip if `apm` unavailable); vendored-drift check passes; `bailiff doctor` subprocess exit codes. Mark apm-CLI-dependent parts so they skip cleanly where apm isn't installed.
- [X] T011a [US1] **Required install smoke** `tests/loop/test_install_smoke.py` (NEW, marked `network`, per FR-008a): add the marketplace via the **git-repo form** (`apm marketplace add bailiff-io/bailiff`), install the bailiff package into a scratch project dir, and assert (a) the payload lands with the vendored `bailiff/` beside `scripts/bailiff.py`, and (b) the installed `scripts/bailiff.py --help` runs from the CONSUMER project root (CWD = project root, not the skill dir) — the only end-to-end proof of SC-001/BLOCKER-1. Deselected by default; a required gate in CI where network+apm are available.

**Checkpoint**: `just release` is a documented gated sequence; CI validates pack + vendor + the install smoke on PR.

---

## Phase 4: Portable SKILL + docs (US1)

- [X] T012 [US1] Extend `skills/bailiff/SKILL.md`: portable Prerequisites — document the dep preflight / `bailiff doctor` / install-suggestion flow (uv/pipx/pip; brew only for copier); scope note macOS/Linux + WSL. **Invoke the script by a path anchored to the skill's install location, NOT `./scripts/bailiff.py`** (Finding 4: the agent's CWD is the consumer project root, not the skill dir — a bare `./scripts/...` won't resolve). Confirm the frontmatter auto-triggers by semantics; nothing assumes bailiff's own repo. Keep the two-phase boundary intact.
- [X] T013 [P] [US1] Extend `README.md`: `## Install` section — add the bailiff marketplace (claude + codex), install the bailiff package, run `bailiff doctor`. Note no PyPI package; deps are checked with an install suggestion.

**Checkpoint**: the SKILL is repo-path-independent and documents the install/preflight flow; README has install instructions.

---

## Phase 5: Gate + closeout

- [X] T014 Full gate on the branch: `uv run ruff check src/ tests/ scripts/ && uv run ruff format --check src/ tests/ scripts/ && uv run mypy && uv run pytest -q`. Confirm existing 001/010/002 tests still pass (the preflight addition + shim change must not regress single/multi init/reproduce or catalog). `apm pack --marketplace=claude,codex --dry-run` + `apm marketplace validate` green.
- [X] T015 Update `.specify/memory/roadmap.md`: split the 008 entry — mark the **packaging** half `implemented` (skill installable via claude+codex marketplaces; vendored core; dep preflight; gated apm pack/publish path); record the **fan-out / authoring-lifecycle** half as a distinct deferred entry (008b or folded into 009's prerequisites) with its ADR-0006 scope intact. Confirm 009's dependency notes still read correctly.
- [X] T016 Open the PR (title = user-facing changelog entry, no spec IDs; `## Spec Context` body per the hook); push via `dgit push`. Do NOT merge without the user's go-ahead.

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

- SC-001 — bailiff installs into a fresh Claude project + `bailiff.py --help` runs there
  (T005–T007 layout; smoke in T011/manual).
- SC-002 — `apm pack --marketplace=claude,codex` yields both, validating (T005/T008/T011).
- SC-003 — missing dep → environment-aware suggestion + clean exit; `doctor` same
  (T001–T004).
- SC-004 — gated release sequence catches version/tree drift (T009/T010).
- SC-005 — no PyPI `bailiff`; no assumed manager; vendored core drift-checked
  (T007/T014).
- SC-006 — no fan-out/authoring CI added; deferred cleanly (T015).
