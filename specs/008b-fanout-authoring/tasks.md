---
description: "Task list for clerk template fan-out + authoring lifecycle CI (spec 008b)"
---

# Tasks: clerk template fan-out + authoring lifecycle (spec 008b)

**Input**: Design documents from `specs/008b-fanout-authoring/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[contracts/fanout.md](./contracts/fanout.md),
[constitution](../../.specify/memory/constitution.md) v2.1.0

---

> ### ✅ VERIFIED END TO END (2026-07-13) — live canary passed
>
> All phases (T001–T016) are complete and the fan-out pipeline is proven live.
> On 2026-07-13 a real release published **`clerk-mod-base`, `clerk-mod-python`,
> and `clerk-mod-apm` at v0.1.0**: monorepo tags pushed, split-repo mirrors fanned
> out, GitHub Releases created, and `catalog.json` served via raw git at
> `https://raw.githubusercontent.com/copier-clerk/clerk/main/catalog.json` (all
> three modules). `discovery.discover()` on each fanned-out mirror returns
> `reproducible=True` at a PEP 440 tag — the consumer contract holds.
>
> The one-time maintainer setup is done (App `clerk-fanout` installed with
> Contents:write, org secrets set, monorepo public, workflow armed). NOTE: adding
> a NEW module requires pre-creating its `copier-clerk/clerk-mod-<name>` mirror once
> (`gh repo create`) — an App token cannot create org repos; see
> [`docs/runbooks/fanout-release.md`](../../docs/runbooks/fanout-release.md).
>
> Fixes applied during bring-up: org-level App token permission; cog 7.x installed
> directly (the pinned-6.4.0 action failed the monorepo bump); the `- - -` changelog
> separator (now gated by `check-modules`); REST-based mirror handling; explicit tag
> push; and the catalog commit-guard (`git add` + staged-diff).

---

**Tests**: INCLUDED for scripted parts (T003 check_modules tests, T007 catalog
generator tests, T010 scaffolder round-trip test). CI/integration tests (T014)
require a real module (blocked on 009).

**Organization**: grouped by dependency phase (unblocked first, then blocked).

## Format: `[ID] [P?] Description`

- **[P]**: parallelizable with other tasks at the same phase
- Exact file paths included

---

## Phase 1: cocogitto config (unblocked)

- [x] T001 Configure `cog.toml` at monorepo root with mandatory keys:
  `[monorepo] generate_mono_repository_global_tag = false` and `tag_prefix = "v"`;
  add an empty `[monorepo.packages]` section with a comment that `just new-module`
  populates it. Add a placeholder `[pre_bump_hooks]` entry that calls
  `just check-modules` (disabled until T009 lands). Verify `cog` parses the config
  without error (`cog --version` + `cog check` on any existing commit).

- [x] T002 [P] Wire `cocogitto-verify` pre-commit hook (already in project) to also
  run `just check-modules` before commit. Update `.pre-commit-config.yaml` with a
  local hook entry calling `scripts/check_modules.py` (or `just check-modules`).
  The hook must exit 0 if `templates/` is empty (no modules yet — 009 blocked).

---

## Phase 2: module contract linter (unblocked)

- [x] T003 Create `scripts/check_modules.py` — iterates `templates/*/`; for each:
  - Calls `discovery.discover(str(module_path))` with a local path (no network;
    discovery already handles local git repos).
  - Asserts `discovery.reproducible == True` (answers-file `.jinja` present); fails
    with a message naming the module if False.
  - Asserts `README.md` and `CHANGELOG.md` exist under the module root.
  - Reads `cog.toml [monorepo.packages]` keys; reads `catalog-sources.toml` (or
    `catalog.json` sources list if that file exists); asserts three-way parity:
    `set(templates/*/) == set(cog.toml packages) == set(catalog sources)`.
  - Checks published-label immutability: if any `git tag -l '<name>-v*'` exists in
    the monorepo, calls `discovery.discover(module_path, ref=<latest tag>)`, compares
    `choices` fields against the working-tree discover; fails if any label changed.
  - Exits 0 if `templates/` is empty (graceful no-op; 009 blocked).
  - Exits 1 with a named violation message on any failure.

- [x] T004 [P] `tests/unit/test_check_modules.py` (NEW): fixture temp dirs
  simulating: (a) a valid module (reproducible, README, CHANGELOG) → exit 0;
  (b) missing answers-file `.jinja` → exit 1, names the module; (c) missing README
  → exit 1; (d) module in `templates/` but absent from cog.toml → exit 1 (parity);
  (e) module in cog.toml but not in `templates/` → exit 1 (ghost). All offline
  (no git clone; use local temp dirs that look like cloned repos for discover()).

- [x] T005 [P] Add `check-modules` justfile target: `@uv run scripts/check_modules.py`.

---

## Phase 3: meta-template scaffolder (unblocked)

- [x] T006 Create `_meta/module-template/` — a copier meta-template rendered by
  `just new-module`. It MUST produce under `templates/{{ module_name }}/`:
  - `copier.yml` skeleton with `_answers_file: "{{ _copier_conf.answers_file }}.jinja"`
    and a minimal placeholder question.
  - `{{ _copier_conf.answers_file }}.jinja` (the answers-file template; content
    from spec 002's `contracts/answers-doc.md` shape).
  - `README.md` (title = `{{ module_name }}`; one-line placeholder description).
  - `CHANGELOG.md` (empty initial file; cog populates on first bump).
  AND writes two registration entries:
  - `cog.toml`: inserts `[monorepo.packages.{{ module_name }}]` with
    `path = "templates/{{ module_name }}"` (append to existing `[monorepo.packages]`).
  - `catalog-sources.toml` (or equivalent catalog source file): appends the module's
    split-repo URL `https://github.com/copier-clerk/{{ module_name }}.git`.

- [x] T007 Add `new-module` justfile target: `@copier copy _meta/module-template/ .
  -d module_name={{ name }}` (or equivalent copier invocation rendering into the
  monorepo root; adjust path if `_meta` layout needs `--overwrite`).

- [x] T008 [P] Round-trip test (`tests/unit/test_scaffolder.py` or shell test):
  render `_meta/module-template/` with `module_name=clerk-mod-test-fixture` into a
  temp directory; run `scripts/check_modules.py` against it; assert exit 0. Assert
  `cog.toml` and catalog source list contain the new entry. Tears down the temp dir.
  This is the scaffolder's definition of "contract-complete out of the box".

---

## Phase 4: catalog generator (unblocked for unit; blocked for end-to-end)

- [x] T009 Create `scripts/generate_catalog.py` — enumerates `templates/*/`:
  - Reads each module's `copier.yml` for `description` (and `name` if present,
    else uses the directory name).
  - Calls `discovery.list_versions(split_repo_url)` to get PEP 440 tags published
    to `copier-clerk/clerk-mod-<name>` (same filter as the consumer plane — C-11).
  - Omits modules with no published tags from output (Q-008b-a resolution).
  - Emits `catalog.json` (shape from `contracts/fanout.md`) to monorepo root.
  - Accepts `--dry-run` to print JSON without writing.

- [x] T010 [P] `tests/unit/test_generate_catalog.py` (NEW): mock `git ls-remote`
  responses (monkeypatch `discovery.list_versions`); assert JSON shape matches the
  contract; assert modules with no tags are omitted; assert `generated_at` is
  present; assert `source` URLs are fully-expanded `https://`.

---

## Phase 5: CI release workflow (BLOCKED ON 009 for integration test)

- [x] T011 Create `.github/workflows/release.yml` implementing the 6-step job from
  `contracts/fanout.md`:
  - Step 1: `cocogitto/cocogitto-action` to run `cog bump --auto`.
  - Step 2: `git push --follow-tags`.
  - Step 3: detect changed modules via `git tag --points-at HEAD | grep -E '^.+-v[0-9]'`.
  - Step 4: matrix or sequential loop — for each changed module, run the fan-out
    bash (see T012). Implement the `git ls-remote` idempotency check before tagging.
  - Step 5: `uv run scripts/generate_catalog.py`; `git add catalog.json`; `git commit`
    (skip if no diff); `git push`.
  - Step 6: `gh release create` per changed module using cog changelog body.
  Trigger: push to `main` only.
  AUTHORED: `.github/workflows/release.yml`; YAML valid; consistent with `pack.yml`
  conventions. Verified `cocogitto-action@v4` bumps/tags locally only (no push) and
  `create-github-app-token@v3` input names against upstream docs. UNPROVEN live —
  requires the T013 org secrets before the job can run.

- [x] T012 [P] Implement the fan-out bash block (inline in workflow or
  `scripts/fanout_module.sh`):
  - Inputs: `NAME`, `VERSION`, `APP_TOKEN`.
  - `gh repo create copier-clerk/clerk-mod-${NAME} || true` (idempotent).
  - Clone, replace contents, skip-commit-if-no-diff, annotated tag, push.
  - `git ls-remote --tags` pre-check for tag existence (idempotent re-run safety).
  - Commit message references `${GITHUB_SHA::8}`.
  DONE: `scripts/fanout_module.sh`; shellcheck-clean; `bash -n` OK. All four bullets
  implemented (auto-create, replace-contents, skip-if-no-diff, ls-remote pre-check,
  short-SHA commit message). Not executed against a live remote (no org token).

- [~] T013 [P] GitHub App token wiring: add `actions/create-github-app-token` step
  to the workflow (before step 4); document the required org-level secrets
  (`CLERK_FANOUT_APP_ID`, `CLERK_FANOUT_PRIVATE_KEY`) in the workflow file comments
  and in a runbook note. The App must be installed on the `copier-clerk` org with
  `contents:write` + `administration:write`; note this is a one-time manual setup
  for maintainers.
  AUTHORING DONE: `create-github-app-token@v3` step added before fan-out, scoped to
  the org with `permission-contents: write` + `permission-administration: write`;
  secrets documented in the workflow header comment and in
  `docs/runbooks/fanout-release.md`.
  MAINTAINER MANUAL SETUP REQUIRED: a `copier-clerk` org-admin must create + install
  the `clerk-fanout` App and add the two org secrets. Not doable by a code agent.

---

## Phase 6: Catalog hosting (raw git — GitHub Pages dropped 2026-07-13)

- [x] T014 Host `catalog.json` at a stable URL for spec-002 consumers.
  RESOLVED via raw git, NOT GitHub Pages: the monorepo `copier-clerk/clerk` was
  made **public**, and the `catalog.json` committed by the release job's Step 5 is
  served directly at
  `https://raw.githubusercontent.com/copier-clerk/clerk/main/catalog.json`.
  The Pages deploy step, `pages:write`/`id-token:write` permissions, and the
  `github-pages` environment were REMOVED from `release.yml`. Rationale: GitHub
  Pages on a private repo needs a paid plan; serving the already-committed file via
  raw git is simpler and plan-independent. URL documented in `README.md`, the
  runbook, `contracts/fanout.md` (Step 6), and ADR-0006. No maintainer Pages setup
  is required anymore.

---

## Phase 7: end-to-end smoke ✅ DONE — live canary passed 2026-07-13

- [x] T015 **Integration smoke test** — PASSED live on 2026-07-13. With the real
  modules present in `templates/`:
  - `just check-modules` → exit 0 ("ok — 3 module(s) checked").
  - `scripts/generate_catalog.py` → valid JSON; live catalog now lists all three
    modules (`clerk-mod-base`, `clerk-mod-python`, `clerk-mod-apm` @ v0.1.0).
  - Canary release ran the FULL job (bump → push tags → detect → fan-out → catalog)
    and published all three modules: monorepo tags, split-repo mirrors, GitHub
    Releases.
  - `discovery.discover(<split-repo-url>)` on each fanned-out mirror →
    `reproducible=True` with a PEP 440 tag present. Consumer contract verified.
  Offline parts remain in `tests/loop/test_release_smoke.py`; the live-only
  assertions (canary + `discovery.discover`) are now confirmed by the real run.

- [x] T016 Callout updated (above) to the ✅ VERIFIED state; roadmap 008b status
  flipped to `verified`. The block is fully lifted — the pipeline is proven live.

---

## Dependency summary

| Task(s) | Status |
|---|---|
| T001–T010 | ✅ Done (Phases 1–4) |
| T011, T012 | ✅ Done — proven live (release workflow + fan-out ran end to end) |
| T013 | ✅ Done — App `clerk-fanout` installed (Contents:write); org secrets set. NOTE: App tokens cannot create org repos, so mirrors are pre-created by a maintainer (runbook) |
| T014 | ✅ Done — catalog served via raw git off the public monorepo (GitHub Pages dropped — needs a paid plan for private repos) |
| T015 | ✅ Done — live canary passed 2026-07-13; `discovery.discover()` → `reproducible=True` on each mirror |
| T016 | ✅ Done — callout set to VERIFIED; roadmap 008b → `verified` |
