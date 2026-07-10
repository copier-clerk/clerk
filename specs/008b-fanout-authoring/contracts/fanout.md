# Contract — clerk template fan-out + authoring lifecycle (spec 008b)

This contract documents the observable interfaces, data shapes, CLI steps, and
config keys that the implementation must satisfy. It is the primary reference for
reviewers and for future specs that consume the catalog.

---

## cocogitto monorepo release config

Mandatory settings (any deviation would either create umbrella PEP 440 tags the
fan-out cannot filter, or wrong tag shapes copier cannot parse):

```toml
# cog.toml — monorepo root

[monorepo]
generate_mono_repository_global_tag = false   # MANDATORY: no umbrella vX.Y.Z in the monorepo
tag_prefix = "v"                              # MANDATORY: yields <name>-vX.Y.Z

[monorepo.packages.clerk-mod-base]
path = "templates/clerk-mod-base"
# ... one entry per module; added by `just new-module`

[monorepo.packages.clerk-mod-python]
path = "templates/clerk-mod-python"
```

**Source-verified behaviour (cog v7)**:

- A commit touching only `templates/A/**` bumps and tags ONLY package A.
  Packages B, C get no tag, no version commit, no changelog change
  (path-based detection in `filters.rs`; unchanged packages skipped in `monorepo.rs`).
- Per-package versions are independent: A can be `v2.3.0` while B is `v1.0.5`.
- `[monorepo.packages.<name>]` is the v7 key; older docs showing `[packages.<name>]`
  are stale — do not use.
- `public_api = false` may be used to exclude an experimental module from
  influencing any global version while still tagging it independently.
- `pre_bump_hooks` rolls back (stash-and-exit) → safe for preflight checks.
  `post_bump_hooks` has **no rollback** → fan-out MUST NOT run there.

---

## CI release job — step contract

The entire release is one GitHub Actions job (not a separate job per module;
fan-out failure happens after the monorepo release is safely done, enabling
idempotent re-run of fan-out steps only):

```
Step 1  cog bump --auto
          Commits version file(s) + CHANGELOG.md per changed module.
          Creates per-module tags <name>-vX.Y.Z locally.
          cog never pushes.

Step 2  git push --follow-tags
          Monorepo release is finalized BEFORE any fan-out.
          Re-run safety: if step 3+ fails, re-run from step 3 only
          (steps 1-2 are idempotent against existing tags).

Step 3  git tag --points-at HEAD | grep -E '^.+-v[0-9]'
          Derive the changed module set from the bump commit.
          Output: one <name>-vX.Y.Z tag per changed module.
          No hook, no cog dry-run parsing needed.

Step 4  for each <name>-vX.Y.Z in changed set:
          strip prefix  →  VERSION=vX.Y.Z
          NAME=<name>   (everything before the last -v[0-9])
          run fan-out (see Fan-out mechanics below)

Step 5  regenerate catalog.json
          Script reads templates/*/, each copier.yml description + name,
          and the latest v* tag from each split repo.
          Commits catalog.json to monorepo root; pushes.

Step 6  GitHub Pages deployment
          Triggered by catalog.json change on main.
          Stable URL (e.g. https://copier-clerk.github.io/clerk-templates/catalog.json)
          is the URL spec 002 catalog consumers configure.

Step 7  gh release create <name>-vX.Y.Z \
          --title "<name> vX.Y.Z" \
          --notes "$(cog changelog <name> --at <name>-vX.Y.Z)"
          One GitHub Release per changed module.
```

---

## Fan-out mechanics (one module)

Input: `NAME` (e.g. `clerk-mod-base`), `VERSION` (e.g. `v1.2.0`), monorepo
checked out at the release commit, App token available.

```bash
# 1. Clone or init the split repo
TARGET="copier-clerk/clerk-mod-${NAME}"
gh repo create "${TARGET}" --private=false 2>/dev/null || true   # auto-create; idempotent
git clone "https://x-access-token:${APP_TOKEN}@github.com/${TARGET}.git" /tmp/split

# 2. Replace contents
rm -rf /tmp/split/*
cp -r "templates/${NAME}/." /tmp/split/

# 3. Skip-if-no-diff
cd /tmp/split
git add -A
git diff --cached --quiet && echo "no diff, skipping" && exit 0

# 4. Commit + tag + push
git commit -m "release: ${VERSION} (mirrored from copier-clerk/clerk-templates@${GITHUB_SHA::8})"
git tag -a "${VERSION}" -m "${NAME} ${VERSION}"
git push origin HEAD --follow-tags
```

**Invariants**:
- Contents of the split repo = exactly `templates/<name>/` at the release commit.
  Nothing else: no monorepo `cog.toml`, no CI files, no other module directories.
- Tag `vX.Y.Z` in the split repo is PEP 440 and copier-consumable directly.
- Commit message references the monorepo SHA so the audit trail is navigable.
- The split repo has one commit per released version (snapshot history); copier
  only needs tree-at-tag and never walks intermediate commits.
- Re-run against an already-pushed tag: `git push --follow-tags` will fail
  on the already-existing remote tag. Idempotency requires a `git tag` existence
  check before tagging, and a `git push --force-with-lease` or push skip if the
  tag already exists remotely. *(Implement with a `git ls-remote --tags` pre-check.)*

---

## GitHub App token contract (`clerk-fanout`)

| Permission | Scope | Reason |
|---|---|---|
| `contents:write` | `copier-clerk/clerk-mod-*` repos | push commits + tags |
| `administration:write` | org `copier-clerk` | auto-create missing repos |

Token is minted per-run via `actions/create-github-app-token` (or equivalent).
The App is org-owned (`copier-clerk`), auditable, and issues short-lived tokens —
not tied to any individual maintainer.

**Fallback (documented, not chosen)**: a fine-grained PAT with the same two grants
stored as a repo secret. Acceptable for bootstrapping or a single maintainer.
The App is justified specifically by auto-creation; if auto-create is ever replaced
by manual `gh repo create` per new module, drop `administration:write`.

---

## `catalog.json` shape

Generated (not hand-maintained). The catalog subsystem in spec 002 consumes this.

```json
{
  "version": 1,
  "generated_at": "2026-07-10T14:30:00Z",
  "modules": [
    {
      "name": "clerk-mod-base",
      "description": "Base project scaffold — git, license, README, .gitignore",
      "source": "https://github.com/copier-clerk/clerk-mod-base.git",
      "latest_version": "v1.2.0",
      "tags": ["v1.0.0", "v1.1.0", "v1.2.0"]
    }
  ]
}
```

**Field semantics**:
- `source`: fully-expanded `https://` URL (ADR-0002 trust contract; no SSH, no
  shorthand). This is the value a user adds to their `clerk catalog add` command.
- `latest_version`: informational display only; the real reproduce pin lives in
  each project's committed `.copier-answers.yml` (ADR-0002). May be absent or
  `null` if a module has been scaffolded but not yet released.
- `tags`: all PEP 440 tags published to the split repo, sorted oldest → newest.
  Filtered to PEP 440 (same filter as `discovery.list_versions`).
- Modules with no published tag MAY be omitted (Q-008b-a; resolve at planning).

**Generation script** (`scripts/generate_catalog.py` or equivalent):
- Enumerate `templates/*/`; read `copier.yml` for `name` / `description`.
- For each module, `git ls-remote --tags <split-repo-url>` to get published tags.
- Filter tags to PEP 440; sort; emit `latest_version` + `tags`.
- Write `catalog.json` to monorepo root; the release CI job commits it.

**Hosting**: committed to `copier-clerk/clerk-templates` root; served via GitHub
Pages at a stable URL. No separate catalog repo. clerk consumers configure this URL
as a catalog source in `~/.config/clerk/catalog.toml`.

---

## Module contract (enforced by `check-modules`)

Each `templates/<name>/` MUST satisfy all of:

| Check | Tool | Detail |
|---|---|---|
| Valid `copier.yml` | `discovery.discover()` | Parseable YAML; not empty |
| Answers-file `.jinja` present | `discovery.discover()` | `_ships_answers_file()` → `reproducible=True`; absence = refuse (FR-016) |
| `README.md` present | file-tree glob | May be minimal; must exist |
| `CHANGELOG.md` present | file-tree glob | cog manages it; must exist after first bump |
| Three-way registration parity | script | `templates/*/` == `cog.toml [monorepo.packages]` keys == catalog source entries |
| Published-label immutability | `discovery` + git tag | If any `<name>-v*` tag exists: `copier.yml` choices at HEAD MUST match choices at the latest tag (C-06); mutation = refuse |

**Where it runs**:
- `pre-commit` hook (fast; catches violations before commit).
- `cog.toml` `pre_bump_hooks` (pre_bump rolls back cleanly → fail before any tag).
- Manually: `just check-modules`.

---

## `just new-module` scaffolder contract

`just new-module <name>` renders `_meta/module-template/` with copier (dogfood),
producing:

```
templates/<name>/
  copier.yml            # skeleton with _answers_file .jinja key
  {{_copier_conf.answers_file}}.jinja   # the answers-file template
  README.md
  CHANGELOG.md          # empty; cog bump populates it on first release
```

AND writes registration entries:
- `cog.toml`: adds `[monorepo.packages.<name>]` with `path = "templates/<name>"`.
- Catalog source list in the monorepo (the file `check-modules` reads for
  three-way parity; exact filename resolved at planning — e.g. `catalog-sources.toml`).

After scaffold, `just check-modules` MUST pass immediately (the scaffold produces a
contract-complete module stub, even if its `copier.yml` has no real questions yet).

---

## Exit codes (authoring surface)

| Code | Meaning |
|---|---|
| 0 | check-modules clean / scaffold succeeded |
| 1 | contract violation (check-modules); named in stderr |
| 2 | scaffolder error (bad module name, already exists, copier render failure) |
