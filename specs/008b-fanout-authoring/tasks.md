---
description: "Task list for clerk template fan-out + authoring lifecycle CI (spec 008b)"
---

# Tasks: clerk template fan-out + authoring lifecycle (spec 008b)

**Input**: Design documents from `specs/008b-fanout-authoring/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[contracts/fanout.md](./contracts/fanout.md),
[constitution](../../.specify/memory/constitution.md) v2.1.0

---

> ### SPEC 009 DELIVERED — CODE AUTHORED; GATE IS MAINTAINER ORG SETUP + LIVE CANARY
>
> Spec 009 landed real modules (`templates/clerk-mod-base/` + `clerk-mod-python/`),
> so the 009 block is lifted. Phases 1–4 (T001–T010) are done; Phases 5–7 code is
> now authored: `release.yml` (T011), `scripts/fanout_module.sh` (T012), the App
> token step + runbook (T013), the Pages deploy step + docs (T014), and the offline
> smoke test (T015 offline parts).
>
> The remaining gate is **one-time maintainer setup on the `copier-clerk` org** that
> a code agent cannot perform, plus a live canary that depends on it:
> - create + install the `clerk-fanout` GitHub App (contents:write + administration:write);
> - store org secrets `CLERK_FANOUT_APP_ID` + `CLERK_FANOUT_PRIVATE_KEY`;
> - enable GitHub Pages (Source: GitHub Actions);
> - then run a live canary release (bump → push → fan-out → catalog → Pages) and
>   assert `discovery.discover()` on a fanned-out `clerk-mod-*` repo.
>
> See [`docs/runbooks/fanout-release.md`](../../docs/runbooks/fanout-release.md).
> The pipeline is correct-by-construction but UNPROVEN end-to-end until that setup
> exists. Do NOT flip the roadmap entry to `verified` until the live canary passes.

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

## Phase 6: GitHub Pages (BLOCKED ON 009 end-to-end)

- [~] T014 Configure GitHub Pages for `copier-clerk/clerk-templates`: source =
  repository root (or a `docs/` folder if `catalog.json` must be nested); path
  delivers `catalog.json` at the stable URL. Add a Pages deployment workflow step
  (or use the built-in Pages deploy action) triggered by changes to `catalog.json`
  on main (path filter: `catalog.json`). Document the stable URL in `README.md`
  and in the spec 002 catalog consumer instructions.
  AUTHORING DONE: `release.yml` assembles `_site/catalog.json` and deploys via
  `upload-pages-artifact@v3` + `deploy-pages@v4` (`pages:write` + `id-token:write`
  permissions, `github-pages` environment). Stable URL
  `https://copier-clerk.github.io/clerk-templates/catalog.json` documented in
  `README.md` + the runbook. NOTE: deploy runs as part of the release job (not a
  separate path-filtered workflow) so the freshly-regenerated catalog publishes in
  the same run; a dedicated path-filtered trigger was not added (YAGNI — no second
  consumer of the deploy).
  MAINTAINER MANUAL SETUP REQUIRED: enable Pages (Settings → Pages → Source: GitHub
  Actions) on the org repo. Not doable by a code agent.

---

## Phase 7: end-to-end smoke (BLOCKED ON 009)

- [~] T015 **Integration smoke test** (marked `@pytest.mark.network` or a separate
  CI job): with at least one real `clerk-mod-*` module from spec 009 present in
  `templates/`:
  - Run `just check-modules` → exit 0.
  - Dry-run `scripts/generate_catalog.py --dry-run` → valid JSON with at least one
    module entry.
  - Run a canary release (on a staging branch or staging org) to verify the full
    job: bump → push → detect → fan-out → catalog → Pages.
  - Call `discovery.discover(<split-repo-url>)` against the fanned-out repo;
    assert `reproducible=True` and a PEP 440 tag is present.
  This task CANNOT be marked done until spec 009 delivers a real module.
  OFFLINE PARTS DONE: `tests/loop/test_release_smoke.py` — `check-modules` → exit 0
  against the real templates (verified: "ok — 2 module(s) checked"), and the
  generator emits valid JSON containing both real modules once split tags exist
  (mocked). Both pass. VERIFIED + DOCUMENTED the catalog-empty-until-fanout rule: a
  live `--dry-run` today returns `"modules": []` because the split repos have no
  published tags yet (Q-008b-a).
  NOT RUN (skip-marked `network`, cannot be faked): the dry-run `modules == []`
  live assertion, the canary release, and `discovery.discover()` on a fanned-out
  repo — all require the T013/T014 org setup + a real fan-out.

- [~] T016 Update `specs/008b-fanout-authoring/spec.md` to remove the
  "IMPLEMENTATION BLOCKED ON SPEC 009" callout once the smoke test (T015) passes
  and the spec 009 dependency is confirmed satisfied. Update roadmap status to
  `verified`.
  PARTIAL: the callout in `spec.md` (and this tasks.md) is UPDATED to reflect the
  new reality (009 delivered; code authored; remaining gate = maintainer org setup +
  live canary) rather than removed — T015's live canary has NOT passed, so the block
  is not fully lifted. Roadmap status intentionally NOT flipped to `verified`.

---

## Dependency summary

| Task(s) | Status |
|---|---|
| T001–T010 | Done (Phases 1–4) |
| T011, T012 | Done — authored + statically verified; unproven live (no org token) |
| T013 | Authoring done; MAINTAINER manual org setup remains (App + org secrets) |
| T014 | Authoring done; MAINTAINER manual Pages enablement remains |
| T015 | Offline parts done; live canary remains (needs T013/T014 org setup) |
| T016 | Partial — callout updated (not removed); roadmap NOT set `verified` |
