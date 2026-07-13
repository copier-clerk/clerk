# Runbook — clerk-templates release + fan-out

How the `copier-clerk/clerk-templates` monorepo releases modules, and the
one-time maintainer setup the automated pipeline depends on.

Implements spec 008b (ADR-0006). The pipeline is
[`.github/workflows/release.yml`](../../.github/workflows/release.yml); the
fan-out step is [`scripts/fanout_module.sh`](../../scripts/fanout_module.sh).

---

## TL;DR — what runs automatically vs. what a maintainer must do once

**Automatic, on every push to `main`** (once setup is done):
`cog bump --auto` → push tags → detect changed modules → mirror each to
`copier-clerk/clerk-mod-<name>` with a clean `vX.Y.Z` tag → regenerate + publish
`catalog.json` via GitHub Pages → one GitHub Release per changed module.

**Manual, one-time, requires `copier-clerk` org-admin** (the pipeline fails
until all three are done):

1. Create + install the `clerk-fanout` GitHub App.
2. Store its App ID + private key as org-level Actions secrets.
3. Enable GitHub Pages on `copier-clerk/clerk-templates` (Source: GitHub Actions).

Until then `release.yml` fails at the "Mint clerk-fanout App token" step, and no
`clerk-mod-*` split repo or catalog entry exists.

---

## One-time maintainer setup

### 1. Create the `clerk-fanout` GitHub App

The fan-out and catalog steps write repos *other than* the workflow's own repo,
so the default Actions `GITHUB_TOKEN` (scoped to `clerk-templates` only) is
insufficient. An org-owned App issues short-lived per-run tokens with a
cross-repo grant and is not tied to any individual maintainer (ADR-0006 "CI
identity").

Org Settings → Developer settings → GitHub Apps → **New GitHub App**:

- **Name**: `clerk-fanout`
- **Homepage URL**: the repo URL (any valid URL).
- **Webhook**: disable (uncheck Active).
- **Repository permissions**:
  - **Contents: Read and write** — push commits + tags to `clerk-mod-*` mirrors.
  - **Administration: Read and write** — auto-create a missing `clerk-mod-<name>`
    mirror on first release of a new module.
- **Where can this App be installed?**: Only on this account (`copier-clerk`).

Create it, then **Install** it on the `copier-clerk` org and grant **All
repositories** (new `clerk-mod-*` repos are created on demand, so scoping to a
fixed list would break auto-create).

> If you drop auto-create and instead `gh repo create` each new module by hand,
> the App no longer needs **Administration: write** — Contents: write alone
> suffices (ADR-0006).

### 2. Store the App credentials as org secrets

From the App's settings page, note the **App ID** and generate a **private key**
(downloads a `.pem`).

Org Settings → Secrets and variables → Actions → **New organization secret**:

- `CLERK_FANOUT_APP_ID` = the numeric App ID.
- `CLERK_FANOUT_PRIVATE_KEY` = the full contents of the downloaded `.pem`
  (including the `-----BEGIN/END PRIVATE KEY-----` lines).

Scope both to the `clerk-templates` repo (or all repos). The workflow reads them
via `actions/create-github-app-token@v3`.

### 3. Enable GitHub Pages

`copier-clerk/clerk-templates` → Settings → Pages → **Source: GitHub Actions**.

This lets the workflow's `deploy-pages` step publish `catalog.json` at the stable
consumer URL:

```
https://copier-clerk.github.io/clerk-templates/catalog.json
```

That URL is what clerk consumers add as a catalog source. It is empty
(`{"version":1,"modules":[]}`) until the first module is fanned out (see below).

---

## Authoring + releasing a module

1. **Scaffold**: `just new-module name=clerk-mod-<name>` renders the meta-template
   into `templates/<name>/` and registers it in `cog.toml [monorepo.packages]` +
   `catalog-sources.toml`.
2. **Author** the module's `copier.yml` + `template/` tree. `just check-modules`
   must stay green (it also runs in pre-commit and as a cog `pre_bump_hooks`
   preflight — a contract violation aborts the bump before any tag is created).
3. **Merge to `main`** with a conventional commit (`feat(<name>): …`).
   `release.yml` then bumps, tags `<name>-vX.Y.Z`, fans out, and publishes.

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
   prefix and mirrors `templates/<name>/.` to `copier-clerk/<name>` as a clean
   `vX.Y.Z` snapshot (auto-creating the repo if missing). See invariants below.
5. **Regenerate `catalog.json`** — enumerate `templates/*/`, read each split
   repo's published PEP 440 tags, emit JSON; commit + push if changed.
6. **GitHub Pages deploy** — publish `catalog.json` at the stable URL.
7. **`gh release create`** — one Release per changed module, notes from
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

`generate_catalog.py` reads published tags from `copier-clerk/clerk-mod-<name>`
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
secrets + Pages above and has **not** been run yet.
