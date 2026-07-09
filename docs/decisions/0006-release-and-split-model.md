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
   `copier-clerk/clerk-mod-<name>`, and create the clean annotated `vX.Y.Z` tag
   there.
   **Mechanism = snapshot mirror, NOT history-preserving split.** VERIFIED: copier
   only needs the correct tree at each tag + a PEP440 tag — it diffs tree-at-old
   vs tree-at-new on update and never walks intermediate history. So the fan-out
   is just `cp subdir → commit → tag → push`; history-preserving tooling
   (splitsh-lite, `git subtree split`, `git-filter-repo`, copybara) solves a
   problem clerk does not have and is rejected as over-engineering.
   - **DECIDED: hand-rolled ~25-line GitHub Actions workflow** (matrix over
     `templates/<name>`): checkout monorepo at the release tag → clone target
     `copier-clerk/clerk-mod-<name>` (PAT auth) → replace contents with
     `templates/<name>/.` → commit (skip if no diff) → `git tag -a vX.Y.Z` → push
     HEAD + tags. Zero external deps, no history-rewrite edge cases, fits clerk's
     "own the thin layer" ethos. NOT adopting a third-party split action.
   - (For reference only, not adopted: `danharrin/monorepo-split-github-action`
     is the maintained symplify continuation doing the identical snapshot-mirror
     logic — the hand-roll is a ~25-line de-obfuscation of it, so we own it
     rather than pin an external action.)
   - Two edge cases: skip-commit-when-no-diff, and PAT scoping (token that can
     push to the `copier-clerk/clerk-mod-*` repos).
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
4. **Catalog** is published from the monorepo (a JSON index of `clerk-mod-*`
   repos + latest `v*`). clerk reads it (one or more catalog pointers).
5. **Consumers/clerk always source from the split repos**
   (`https://github.com/copier-clerk/clerk-mod-<name>.git` — expanded https form,
   per the trust contract in [[0001-copier-as-engine]]), never the monorepo — see
   the `_src_path` gotcha in [[0002-catalog-and-answer-model]].

## DECIDED — release tooling

There are two release contexts; the decision is deliberately uniform on
**cocogitto** to keep one tool across the whole family.

- **Authoring monorepo (`copier-clerk/clerk-templates`)** — cocogitto in monorepo
  mode tags each package as `<name>-vX.Y.Z` (the prefix disambiguates components
  and is exactly what the fan-out step strips). This replaces the earlier
  release-please assumption. `cog` generates each package's CHANGELOG.
- **Split repos (`copier-clerk/clerk-mod-*`) and the clerk tool repo
  (`copier-clerk/clerk`)** — cocogitto single-package: `cog bump --auto` computes
  the version, updates `CHANGELOG.md`, and tags `vX.Y.Z` (`tag_prefix = "v"`,
  clean PEP440 for copier) on merge, via `cocogitto/cocogitto-action`.

**Rationale:** cocogitto is already in clerk's pre-commit stack (`cocogitto-verify`),
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

## Risks

- The fan-out is hand-rolled (no external split action to track). Its risk is the
  ~25 lines of workflow bash we own + PAT scoping — legible and low.
- copier's PEP 440 hard requirement is load-bearing and has no relaxation knob;
  re-verify `get_latest_tag` on major copier upgrades in case a tag-filter is ever
  added (that alone could retire the split).
- Split repos must retain full history for tagged commits so `copier update` can
  diff old vs new tags (snapshot-style splits give one commit per release — fine,
  but no pre-first-release history).

## Related

- [[0001-copier-as-engine]], [[0002-catalog-and-answer-model]].
