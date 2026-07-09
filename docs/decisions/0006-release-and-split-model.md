# 0006 — central authoring monorepo, fan-out to per-template repos

- Status: accepted (release tool: OPEN — see Decision)
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
2. **release-please manifest mode** tags each component in the monorepo as
   `<name>-v<X.Y.Z>` (KEEP the prefix here — it is release-please's discriminator
   between components).
3. **Fan-out CI** (after release-please tags): for each released component, strip
   the prefix → `vX.Y.Z`, push `templates/<name>/` to its own read-only repo
   `clerk-mod-<name>`, and create the clean `vX.Y.Z` tag there. Tool:
   `symplify/monorepo-split-github-action` (actively maintained 2026-05; creates
   the target tag verbatim), SHA-pinned. (`splitsh-lite` only if real per-commit
   history in split repos is needed — it carries no tags, so you own the tag push.)
4. **Catalog** is published from the monorepo (a JSON index of `clerk-mod-*`
   repos + latest `v*`). clerk reads it (one or more catalog pointers).
5. **Consumers/clerk always source from the split repos** (`gh:org/clerk-mod-X`),
   never the monorepo — see the `_src_path` gotcha in [[0002-catalog-and-answer-model]].

## OPEN — per-repo release tool choice

Both options need the SAME separate split step; the choice is only the tagging
mechanism in each split repo (or the monorepo pre-split):

- **release-please per repo** — proven (already used in this repo's roadmap
  extension), Google-maintained (v17.10.2, 2026-06), review-gated via a Release
  PR, `include-component-in-tag: false` → `v1.2.0`. Cost: config+workflow per
  repo (template these files so they are generated, not hand-written).
- **cocogitto per repo** — already in clerk's pre-commit stack; `cog bump --auto`
  computes version, updates CHANGELOG, and tags on merge (no Release PR),
  `tag_prefix = "v"` → `v1.2.0`. Lighter ceremony; loses the changelog-review gate.

Lean: cocogitto for lower solo-maintainer ceremony (tag-on-merge, one fewer tool),
unless the changelog-review gate is wanted → release-please. To be decided before
implementing the release pipeline.

## Risks

- `symplify/monorepo-split-github-action` is a solo-maintainer PHP-in-Docker
  action (~119 stars) — SHA-pin it; the split logic is ~150 lines that could be
  vendored if it goes stale.
- copier's PEP 440 hard requirement is load-bearing and has no relaxation knob;
  re-verify `get_latest_tag` on major copier upgrades in case a tag-filter is ever
  added (that alone could retire the split).
- Split repos must retain full history for tagged commits so `copier update` can
  diff old vs new tags (snapshot-style splits give one commit per release — fine,
  but no pre-first-release history).

## Related

- [[0001-copier-as-engine]], [[0002-catalog-and-answer-model]].
