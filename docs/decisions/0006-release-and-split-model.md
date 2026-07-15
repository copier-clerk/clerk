# 0006 — central authoring monorepo, fan-out to per-template repos

- Status: accepted
- Date: 2026-07-09

## Context

[[0002-catalog-and-answer-model]] establishes that each copier template must be
its own git repo with clean PEP 440 tags (`v1.2.0`), because copier's version
resolver **silently discards non-PEP-440 tags and has no prefix/pattern filter**
(verified in `_vcs.py get_latest_tag`). But authoring ~24 templates as ~24
hand-managed repos is untenable. We want central authoring with per-repo
distribution — the Symfony/Laravel model.

Key verified constraints:
- A monorepo CANNOT emit unprefixed per-component tags: release-please
  `include-component-in-tag: false` collapses every component to `v1.2.0` in one
  shared `refs/tags/` namespace → collision. Unprefixed tags are coherent only
  when the component IS the whole repo (one release config per repo).
- No release tool (release-please, cocogitto, semantic-release, release-plz) does
  multi-repo publishing. The monorepo→per-repo split is ALWAYS a separate CI
  concern from the release tool.
- Split tools carry commits/branches but NOT tags; the clean `v*` tag must be
  created in the target repo separately (a one-line prefix-strip in CI).

## Decision

1. **Source monorepo** holds all templates under `templates/<name>/`, each with
   its own `copier.yml`. All authoring + review happens here.
2. **cocogitto (monorepo mode)** tags each component in the monorepo as
   `<name>-v<X.Y.Z>` (KEEP the prefix here — it disambiguates components; the
   fan-out strips it). See the DECIDED release-tooling section below.
3. **Fan-out CI** (after the component tag lands): for each released component,
   strip the prefix → `vX.Y.Z`, push `templates/<name>/` to its own read-only repo
   `bailiff-io/bailiff-mod-<name>`, and create the clean annotated `vX.Y.Z` tag
   there.
   **Mechanism = snapshot mirror, NOT history-preserving split.** VERIFIED: copier
   only needs the correct tree at each tag + a PEP440 tag — it diffs tree-at-old
   vs tree-at-new on update and never walks intermediate history. So the fan-out
   is just `cp subdir → commit → tag → push`; history-preserving tooling
   (splitsh-lite, `git subtree split`, `git-filter-repo`, copybara) solves a
   problem bailiff does not have and is rejected as over-engineering.
   - **DECIDED: hand-rolled ~25-line GitHub Actions workflow** (matrix over
     `templates/<name>`): checkout monorepo at the release tag → clone (or
     auto-create if missing) target `bailiff-io/bailiff-mod-<name>` → replace
     contents with `templates/<name>/.` → commit (skip if no diff) → `git tag -a
     vX.Y.Z` → push HEAD + tags. Auth is an org GitHub App minting short-lived
     tokens, NOT a personal PAT — see *CI identity for cross-repo writes* below.
     Zero external deps, no history-rewrite edge cases, fits bailiff's "own the thin
     layer" ethos. NOT adopting a third-party split action.
   - (For reference only, not adopted: `danharrin/monorepo-split-github-action`
     is the maintained symplify continuation doing the identical snapshot-mirror
     logic — the hand-roll is a ~25-line de-obfuscation of it, so we own it
     rather than pin an external action.)
   - Two edge cases: skip-commit-when-no-diff, and token scoping (the GitHub App
     installation token must reach the `bailiff-io/bailiff-mod-*` repos, and hold
     **organization** `administration:write` for auto-create — creating a repo is
     an org-level action, not repo-level — see *CI identity* below).
   - **Direct push, NOT a PR into the split repos.** Considered opening a PR per
     mirror for a paper trail; rejected. The split repos are generated read-only
     mirrors (nothing to review — the content derives from an already-reviewed,
     already-released monorepo tag), so a PR is a rubber-stamp that makes the
     release two-phase and stall-prone (24 PRs to merge before anything is
     consumable) and complicates tagging (tag must land on the merged commit). A
     PR also does NOT add history — granularity comes from the split *strategy*
     (snapshot vs history-preserving), not from PR-vs-push. If per-commit history
     in mirrors is ever wanted, switch the split strategy, do not add PRs. The
     monorepo history + release changelog already provide the audit trail; the
     mirror commit message references the monorepo release.
   - Rejected/dead: `git-subsplit` (abandoned since 2018), `meta`/`git-xargs`
     (multi-repo managers, wrong shape), `git-subrepo` (vendoring, wrong
     direction), copybara (JDK/Bazel/Starlark — disproportionate for ~24 `cp`s).
4. **Catalog** is published from the monorepo (a JSON index of `bailiff-mod-*`
   repos + latest `v*`). bailiff reads it (one or more catalog pointers). It is
   GENERATED, not hand-maintained — see the *Authoring lifecycle* section for how
   it is derived, hosted (in-monorepo + GitHub Pages), and kept drift-free.
5. **Consumers/bailiff always source from the split repos**
   (`https://github.com/bailiff-io/bailiff-mod-<name>.git` — expanded https form,
   per the trust contract in [[0001-copier-as-engine]]), never the monorepo — see
   the `_src_path` gotcha in [[0002-catalog-and-answer-model]].

## DECIDED — release tooling

There are two release contexts; the decision is deliberately uniform on
**cocogitto** to keep one tool across the whole family.

- **Authoring monorepo (`bailiff-io/bailiff`)** — cocogitto in monorepo
  mode tags each package as `<name>-vX.Y.Z` (the prefix disambiguates components
  and is exactly what the fan-out step strips). This replaces the earlier
  release-please assumption. `cog` generates each package's CHANGELOG.
- **Split repos (`bailiff-io/bailiff-mod-*`) and the bailiff tool repo
  (`bailiff-io/bailiff`)** — cocogitto single-package: `cog bump --auto` computes
  the version, updates `CHANGELOG.md`, and tags `vX.Y.Z` (`tag_prefix = "v"`,
  clean PEP440 for copier) on merge, via `cocogitto/cocogitto-action`.

**Rationale:** cocogitto is already in bailiff's pre-commit stack (`cocogitto-verify`),
so it is one tool for verify + release across every repo — no second releaser to
learn or maintain. It gives native changelogs (committed `CHANGELOG.md`, and the
changelog body can be piped into `gh release create` for GitHub Release notes),
and clean `v*` tags copier consumes directly.

**Accepted trade-off:** cocogitto tags **on merge to main** (no Release-PR review
gate). For a solo maintainer optimizing low ceremony this is preferred over
release-please's merge-a-Release-PR flow; the cost is that release notes are not
reviewed in a PR before they publish. If a changelog-review gate is ever wanted,
release-please remains the drop-in alternative (it produces the same `v1.2.0`
tags via `include-component-in-tag: false`).

**Note on the fan-out interaction:** because cocogitto (like release-please) uses
prefixed tags in monorepo mode, the split step still strips `<name>-` → `vX.Y.Z`.
The split is independent of the release tool (no tool does multi-repo publishing).

### Verified cocogitto v7 behavior + REQUIRED config (source-checked)

Release isolation is correct — a commit touching only `packages/A/**` bumps and
tags ONLY package A; B/C get no tag, no version commit, no changelog change
(path-based detection in `filters.rs`; unchanged packages skipped in
`monorepo.rs`). Per-package versions are independent (each tracked by its own
`<name>-v*` tag), so A can be v2.3.0 while B is v1.0.5. But two settings are
MANDATORY, because the defaults would misbehave for us:

- **`generate_mono_repository_global_tag = false`** — by DEFAULT cog also creates
  an umbrella plain `vX.Y.Z` tag on every release. Disable it: we want pure
  isolated per-package tags and no PEP440-parseable umbrella tag in the monorepo.
- **`tag_prefix = "v"`** + default `-` separator → `<name>-vX.Y.Z` (the format the
  fan-out strips).
- Config lives under `[monorepo.packages]` (v7 breaking change; older `[packages]`
  in some docs is stale — declare each template with its `path`).
- `public_api = false` can exclude a package from influencing any global version,
  but it still gets its own tag.

### Fan-out is a later STEP in the same CI job — NOT inside a cog hook

VERIFIED (cog v7.0.0 source): per-package `post_bump_hooks` DO fire only for
bumped packages and expose `{{package}}` + `{{version}}` (use `v{{version}}` for
the clean split tag; `{{version_tag}}` is the prefixed monorepo form) — so a hook
*could* drive the fan-out. We DON'T, because **post_bump hooks have NO rollback**
(docs: "There is no rollback procedure for post-bump hook"): a failing fan-out
hook leaves the version commit + all package tags created locally, aborts the
remaining packages' hooks, and skips global post_bump. Fan-out to ~24 downstream
repos is inherently flaky (network/token/remote conflicts) and must not be able to
half-finish the release.

DECISION — one CI job, fan-out as later steps (no separate job needed):
1. `cog bump --auto` — commits + creates `<name>-vX.Y.Z` tags (cog never pushes).
2. `git push --follow-tags` — monorepo release finalized.
3. `git tag --points-at HEAD | grep -E '^.+-v'` — the changed set is exactly the
   new package tags on the bump commit (no hook, no dry-run parsing needed; the
   `cocogitto-action` exposes no "bumped packages" output, so derive it here).
4. For each: strip prefix → `cp + commit + tag vX.Y.Z + push` to
   `bailiff-io/bailiff-mod-<name>`.
A fan-out failure fails the workflow AFTER the monorepo release is safely done;
re-run steps 3-4 alone against existing tags (idempotent, testable in isolation,
the cross-repo token scoped to the fan-out steps only — see *CI identity* below).

OPTIONAL — `pre_bump_hooks` as preflight: validate mirror repos reachable + token
valid BEFORE bumping. pre_bump DOES roll back (stash-and-exit), so this is the one
place cog's "abort the bump" semantics are an asset — fail fast before any tag
exists. Not required for MVP.

Config gotchas (verified): package hooks run with CWD = `packages/<name>` (not
repo root) — use an absolute script path; put a single fan-out entry in global
`post_package_bump_hooks` if ever hook-driving (not per-package ×24); v7 config
key is `[monorepo.packages.<name>]` (older docs show stale `[packages.<name>]`).

### If cocogitto's tag-detection scripting proves fragile

release-please isolates equally well and needs NO "which bumped" scripting (its
per-component release PRs make the changed set explicit) and never forces an
umbrella tag. It remains the drop-in fallback if the `git tag --points-at HEAD`
approach becomes a maintenance burden.

## Alternatives considered — repo topology

Before committing to the monorepo→per-repo snapshot split, two other shapes were
weighed. Both are rejected; recorded so the split is not re-litigated.

### Git submodules (rejected)

The appeal: "keep everything in the main repo and run one CI pipeline." It does
not work, because it does not touch the load-bearing constraint. copier resolves
"latest version" from PEP 440 git tags **in the repo it fetched**, with no
prefix/pattern filter (`_vcs.py get_latest_tag`). A consumable template must
therefore be a repo whose `vX.Y.Z` tags mean *that template* — and git tags are
not branch- or subdirectory-scoped, so one repo yields exactly one version line
(`_subdirectory` does not rescue this; it shares the single tag namespace).
Submodules are a *source-composition* pointer to a pinned commit of another repo;
they publish nothing and create no tags, so they cannot supply the per-template
clean `v*` tag the split exists to produce.

Neither direction helps:
- **Child repos authoritative, monorepo aggregates them as submodules** —
  reintroduces the 24-repo hand-authoring this ADR rejects as untenable, and adds
  pointer-bump ceremony. The "one pipeline" claim is false: release still has to
  create a clean tag in each child (recursing into each child's CI or pushing per
  child) — that push *is* the fan-out, relocated.
- **Monorepo authoritative, mirrors are submodules used only as publish targets**
  — strictly more work than today's `cp → commit → tag → push` (adds detached-HEAD
  checkouts + pointer bumps), no upside.
- **Hazard:** copier walks the template tree to render it. A `templates/<name>`
  that is actually a submodule (a gitlink / `.git` file) is not something copier's
  renderer expects to vendor — undefined-to-awkward at best.

The single-pipeline goal is already met without submodules: decision #3 runs the
fan-out as later STEPS in the same CI job, not a separate pipeline. This also
restates the standing "no submodules" rule from [[0002-catalog-and-answer-model]].

### copier "multi-template composition" (not a rival — the reason for the split)

Two distinct copier features go by this name, and both are *consumer-side*
layering, not a release topology:
1. **Multiple answers files** — a consumer applies several INDEPENDENT templates
   to one project, each tracked by its own answers file
   (`copier copy -a .copier-answers.<layer>.yml <repo> .`), each updated
   independently (`copier update -a .copier-answers.<layer>.yml`). Each layer is
   STILL its own repo with its own `v*` tag line. This is exactly bailiff's
   `bailiff-mod-*` model (base + pre-commit + CI + …) and is the *payoff* of the
   split, not an alternative to it — it strengthens the case for many small,
   independently-tagged repos.
2. **`_external_data`** — one template reads another already-applied template's
   answers file as data (e.g. default a child's `target_version` from a parent's
   answer). Orthogonal to repo topology; it reads a file in the *generated
   project*, not another repo. This is the future cross-module answer-inheritance
   seam (roadmap 003/004 territory), not a release decision.

## Authoring lifecycle — structure, indexing, scaffolding, publishing

The release mechanics above cover *version bump → tag → fan-out*. This section
covers the rest of the module lifecycle in the authoring monorepo
(`bailiff-io/bailiff`): creating modules, keeping the family
structured, and deriving the published catalog. It is the design detail behind
roadmap **spec 008**; slice 001 implements none of it.

**Framing — an authoring plane that REUSES the consumer plane (C-11).** Slice 001
built the consumer plane (`discover / init / reproduce / trust`). The authoring
lifecycle is the same thin helpers aimed *inward* at the monorepo — the module
lint IS `discovery.discover()` run against local `templates/<name>/` instead of a
remote repo. No new engine, no second tool; this keeps the lifecycle inside
C-01/C-11 (glue only where copier cannot; prefer template content + CI bash).

1. **Creating modules — a copier meta-template (dogfood).** `just new-module
   <name>` renders `_meta/module-template/` with copier itself, laying down a
   contract-complete module: `copier.yml` skeleton with the MANDATORY answers-file
   `.jinja`, `README.md`, cog-managed `CHANGELOG.md`, a golden-render test fixture,
   and the registration edits (`cog.toml [monorepo.packages.<name>]` + a catalog
   source entry). Template content, not tool code. (Alternatives: a bash/sed
   generator — simpler but bespoke and non-dogfooding; or defer and hand-author
   first — most YAGNI-strict. Chosen: meta-template, to exercise the module
   contract on every creation.)

2. **Keeping it structured — a module contract, enforced in pre-commit AND CI.**
   One `just check-modules` loops `templates/*/` and calls `discovery.discover()`
   on each, asserting:
   - valid `copier.yml` + present answers-file `.jinja` (the reproduce invariant —
     the exact slice-001 check);
   - `README.md` + cog-managed `CHANGELOG.md` present;
   - **three-way registration parity**: directory listing == `cog.toml` packages
     == catalog source entries (no orphan module, no ghost registration);
   - **published-label immutability** (Constitution VI / C-06): a module's
     `copier.yml` choice labels, once shipped, do not silently change — diff
     against the last `<name>-v*` tag.
   This runs in the `pre_bump_hooks` preflight slot already reserved above
   (pre_bump rolls back cleanly → fail before any tag exists).

3. **Auto-derived indexes — nothing hand-edited.**
   - `cog.toml [monorepo.packages]` stays DECLARATIVE (the scaffolder writes the
     entry); the lint VERIFIES it matches the directory rather than regenerating a
     release tool's own config (auto-generating it is fragile).
   - The **catalog JSON index** (what bailiff consumers read) is GENERATED on release
     from monorepo state: enumerate `templates/*/`, read name + description from
     each `copier.yml` + latest `v*` tag, emit JSON. Per
     [[0002-catalog-and-answer-model]] it holds SOURCES, not mandatory pins — the
     latest tag is informational display only; the real reproduce pin lives in each
     project's answers file. **Hosting (updated 2026-07-13):** committed as
     `catalog.json` in the monorepo and served via **raw git off the public
     monorepo** (`raw.githubusercontent.com/bailiff-io/bailiff/main/catalog.json`) —
     one versioned source of truth, plan-independent. GitHub Pages was the original
     choice but was dropped (Pages on a private repo needs a paid plan; the monorepo
     was made public and raw git serves the already-committed file with no extra
     deploy step). (Alternatives: a dedicated `bailiff-io/catalog` repo — extra
     repo + PAT + push target; or a Release asset — no always-live URL.)

4. **Publishing — the release job, extended.** The decision-#3 job gains a catalog
   step: `cog bump --auto` → `git push --follow-tags` → `git tag --points-at HEAD`
   → per-changed-module fan-out (cp + strip-prefix tag + push) → **regenerate +
   publish `catalog.json`** → `gh release create` with the cog changelog body. The
   catalog regeneration is the one new step on the already-decided flow.

### CI identity for cross-repo writes + repo auto-creation

The fan-out and (new) repo-creation steps write repos OTHER than the workflow's
own, so the default Actions `GITHUB_TOKEN` (scoped to its own repo) is
insufficient — a cross-repo credential is required regardless of topology.

**Split repos are auto-created if missing.** The fan-out runs `gh repo create
bailiff-io/bailiff-mod-<name>` when the target does not exist (idempotent), so a
newly scaffolded module needs zero manual pre-provisioning and one code path owns
repo existence. Creating a repo in the org needs **`administration: write`** on
the org — a higher grant than the `contents: write` a push needs.

**DECIDED — an org-owned GitHub App ("bailiff-fanout"), not a personal PAT.** The
workflow mints a short-lived (~1h) installation token per run (e.g.
`actions/create-github-app-token`) with `contents: write` + `administration:
write`. Rationale: the elevated org-admin grant belongs to an auditable,
org-owned identity that survives a maintainer leaving and issues ephemeral tokens
— not a long-lived personal PAT sitting in repo secrets.
- **Fallback (documented, not chosen):** a fine-grained PAT with the same two
  grants works for low ceremony but is tied to a person and long-lived.
- **Note:** if auto-create is ever dropped for a manual `gh repo create` per new
  module, the CI credential only needs `contents: write` and the App's
  `administration: write` becomes unnecessary — the App is justified specifically
  by auto-creation.

## Risks

- The fan-out is hand-rolled (no external split action to track). Its risk is the
  ~25 lines of workflow bash we own + GitHub App token scoping — legible and low.
- copier's PEP 440 hard requirement is load-bearing and has no relaxation knob;
  re-verify `get_latest_tag` on major copier upgrades in case a tag-filter is ever
  added (that alone could retire the split).
- Split repos must retain full history for tagged commits so `copier update` can
  diff old vs new tags (snapshot-style splits give one commit per release — fine,
  but no pre-first-release history).

## Related

- [[0001-copier-as-engine]], [[0002-catalog-and-answer-model]].
