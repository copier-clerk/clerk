# Runbook — bailiff release + fan-out

How the `bailiff-io/bailiff` monorepo releases modules, and the
one-time maintainer setup the automated pipeline depends on.

Implements spec 008b (ADR-0006). The pipeline is
[`.github/workflows/release.yml`](../../.github/workflows/release.yml); the
fan-out step is [`scripts/fanout_module.sh`](../../scripts/fanout_module.sh).

---

## TL;DR — what runs automatically vs. what a maintainer must do once

**Automatic, on every push to `main`** (once setup is done):
`cog bump --auto` → push tags → detect changed modules → mirror each to
`bailiff-io/bailiff-mod-<name>` with a clean `vX.Y.Z` tag → regenerate + commit
`catalog.json` (served via raw git from the public monorepo) → one GitHub Release
per changed module.

**Manual, one-time, requires `bailiff-io` org-admin** (the pipeline stays
dormant until done):

1. Create + install the `bailiff-fanout` GitHub App.
2. Store its App ID + private key as org-level Actions secrets.
3. Arm the workflow (set `BAILIFF_FANOUT_ARMED=true`).

The monorepo is **public**, so `catalog.json` is served directly via raw git — no
GitHub Pages setup is needed. Until armed, `release.yml` is skipped cleanly on
every push; no `bailiff-mod-*` split repo or catalog entry exists until the first
armed release.

---

## One-time maintainer setup

### 1. Create the `bailiff-fanout` GitHub App

The fan-out and catalog steps write repos *other than* the workflow's own repo,
so the default Actions `GITHUB_TOKEN` (scoped to `bailiff` only) is
insufficient. An org-owned App issues short-lived per-run tokens with a
cross-repo grant and is not tied to any individual maintainer (ADR-0006 "CI
identity").

Org Settings → Developer settings → GitHub Apps → **New GitHub App**:

- **Name**: `bailiff-fanout`
- **Homepage URL**: the repo URL (any valid URL).
- **Webhook**: disable (uncheck Active).
- **Repository permissions**:
  - **Contents: Read and write** — push commits + tags to `bailiff-mod-*` mirrors.
- **Where can this App be installed?**: Only on this account (`bailiff-io`).

Create it, then **Install** it on the `bailiff-io` org and grant **All
repositories** (so it can push to every current and future `bailiff-mod-*` mirror).

> **Mirror repos are pre-created by a maintainer — the App does NOT create them.**
> In practice a GitHub App installation token is refused on `POST /orgs/{org}/repos`
> ("403 Resource not accessible by integration") even with organization
> Administration granted — repository *creation* is effectively a human/PAT action.
> So the App is scoped to **Contents: write only** (no Administration permission),
> and the fan-out treats a missing mirror as a maintainer to-do, not an auto-create.
>
> **When adding a NEW module**, create its mirror once (any org admin):
> ```
> gh repo create bailiff-io/bailiff-mod-<name> --public
> ```
> The fan-out then pushes into it on every release. (The existing
> `bailiff-mod-base` and `bailiff-mod-python` mirrors are already created.)

### 2. Store the App credentials as org secrets

From the App's settings page, note the **App ID** and generate a **private key**
(downloads a `.pem`).

Org Settings → Secrets and variables → Actions → **New organization secret**:

- `BAILIFF_FANOUT_APP_ID` = the numeric App ID.
- `BAILIFF_FANOUT_PRIVATE_KEY` = the full contents of the downloaded `.pem`
  (including the `-----BEGIN/END PRIVATE KEY-----` lines).

Scope both to the `bailiff` repo (or all repos). The workflow reads them
via `actions/create-github-app-token@v3`.

### 3. Catalog hosting — nothing to set up (raw git)

The monorepo `bailiff-io/bailiff` is **public**, and the release workflow commits
`catalog.json` to it (pipeline step 5). Consumers fetch it directly via raw git at
the stable URL:

```
https://raw.githubusercontent.com/bailiff-io/bailiff/main/catalog.json
```

That URL is what bailiff consumers add as a catalog source. It is empty
(`{"version":1,"modules":[]}`) until the first module is fanned out (see below).
No GitHub Pages configuration is required — this replaces the earlier Pages-based
hosting (dropped because Pages on a private repo needs a paid plan; serving the
already-committed file via raw git is simpler and plan-independent).

### 4. Arm the workflow

`release.yml` is guarded by `if: vars.BAILIFF_FANOUT_ARMED == 'true'` so it stays
**dormant** (no failed runs) on every push to `main` until steps 1–2 are done.
Once they are, arm it:

```
gh variable set BAILIFF_FANOUT_ARMED --org bailiff-io --body true
```

(or repo/org Settings → Secrets and variables → Actions → **Variables** →
`BAILIFF_FANOUT_ARMED = true`). Until this variable is `true`, the release job is
skipped cleanly rather than failing at the token step. To pause releases later,
set it back to `false` or delete the variable.

---

## Authoring + releasing a module

1. **Scaffold**: `just new-module name=bailiff-mod-<name>` renders the meta-template
   into `templates/<name>/` and registers it in `cog.toml [monorepo.packages]` +
   `catalog-sources.toml`.
2. **Author** the module's `copier.yml` + `template/` tree. `just check-modules`
   must stay green (it also runs in pre-commit and as a cog `pre_bump_hooks`
   preflight — a contract violation aborts the bump before any tag is created).
3. **Create the split-repo mirror — MANUAL, ONCE PER NEW MODULE (agent process).**
   The release App CANNOT create it (an App installation token is refused on
   `POST /orgs/{org}/repos` with `403 Resource not accessible by integration`, even
   with org Administration granted — repo creation is not available to App tokens).
   Create it with the `gh` CLI (a user/PAT token, which DOES have this ability):

   ```
   gh repo create bailiff-io/bailiff-mod-<name> --public \
     --description "Mirror of bailiff-io/bailiff:templates/bailiff-mod-<name> (generated; do not edit)"
   ```

   > **For an agent doing a release:** this is a required prerequisite step, not an
   > optional one. If `templates/bailiff-mod-<name>/` is new (no `bailiff-io/bailiff-mod-<name>`
   > repo yet), run the `gh repo create` above BEFORE merging to `main`. The fan-out
   > pushes into an existing mirror with the App's `contents:write`; it will fail
   > loudly (`a maintainer must pre-create it`) if the mirror is absent. Idempotent —
   > safe to re-run; a "name already exists" is fine. Existing mirrors:
   > `bailiff-mod-base`, `bailiff-mod-python`.
4. **Merge to `main`** with a conventional commit (`feat(<name>): …`).
   `release.yml` then bumps, tags `<name>-vX.Y.Z`, fans out (pushing into the
   pre-created mirror), and publishes.

## The release pipeline, step by step

Contract: [`specs/008b-fanout-authoring/contracts/fanout.md`](../../specs/008b-fanout-authoring/contracts/fanout.md).

1. **`cog bump --auto`** — path-based detection bumps only changed modules,
   creating `<name>-vX.Y.Z` tags + per-module `CHANGELOG.md` commits locally.
   `cog` never pushes. `generate_mono_repository_global_tag = false` suppresses an
   umbrella tag; `tag_prefix = "v"` yields the `<name>-vX.Y.Z` shape.
2. **`git push --follow-tags`** — the monorepo release is finalized *before* any
   fan-out, so a later fan-out failure never leaves a half-published release.
3. **Detect changed modules** — `git tag --points-at HEAD | grep -E '^.+-v[0-9]'`.
4. **Fan-out** — for each `<name>-vX.Y.Z`, `scripts/fanout_module.sh` strips the
   prefix and mirrors `templates/<name>/.` to `bailiff-io/<name>` as a clean
   `vX.Y.Z` snapshot (auto-creating the repo if missing). See invariants below.
5. **Regenerate `catalog.json`** — enumerate `templates/*/`, read each split
   repo's published PEP 440 tags, emit JSON; commit + push if changed. Because the
   monorepo is public, this committed file IS the published catalog — consumers
   fetch it via `raw.githubusercontent.com/bailiff-io/bailiff/main/catalog.json`.
   No separate publish step.
6. **`gh release create`** — one Release per changed module, notes from
   `cog changelog <name> --at <name>-vX.Y.Z`.

### Fan-out invariants (`scripts/fanout_module.sh`)

- The split repo contains **exactly** `templates/<name>/` at the release commit —
  no `cog.toml`, no CI, no sibling modules.
- The `vX.Y.Z` tag is clean PEP 440, directly copier-consumable.
- The commit message references the monorepo short SHA for an audit trail.
- **Idempotent / re-run-safe**: auto-create is `|| true`; a `git ls-remote --tags`
  pre-check skips a version already present remotely; the commit is skipped when
  the content is unchanged. So re-running steps 3–7 after a mid-fan-out failure is
  safe.

---

## Catalog is empty until the first fan-out

`generate_catalog.py` reads published tags from `bailiff-io/bailiff-mod-<name>`
and **omits any module with no published tags** (Q-008b-a). Before the first
successful fan-out, those split repos do not exist, so:

```
$ uv run scripts/generate_catalog.py --dry-run
{ "version": 1, "generated_at": "...", "modules": [] }
```

is expected and correct. The catalog fills in only after the release pipeline
mirrors + tags each module. This is verified offline in
`tests/loop/test_release_smoke.py`.

---

## Recovering a failed release

- **Fail before step 2 (bump/push)**: no tags pushed; fix and re-merge.
- **Fail during fan-out / catalog / release (steps 3–7)**: the monorepo release is
  already final. Re-run the workflow (or re-run steps 3–7 manually with the same
  App token) — every downstream step is idempotent against existing tags.

## Local canary (before the org setup exists)

Offline, no org access needed:

```sh
just check-modules                        # contract lint -> exit 0
uv run scripts/generate_catalog.py --dry-run   # valid JSON (empty until fan-out)
shellcheck scripts/fanout_module.sh       # fan-out script is clean
```

A live end-to-end canary (actually mirroring to a staging org and asserting
`discovery.discover()` reproducibility at a PEP 440 tag) requires the App + org
secrets + arming above and has **not** been run yet.
