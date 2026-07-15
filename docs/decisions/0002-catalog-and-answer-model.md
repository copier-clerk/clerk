# 0002 — user-owned catalog; copier answers carry the state

- Status: accepted
- Date: 2026-07-09

## Context

Bailiff must let users point the agent at *their own* templates, not depend on a
first-party hub. Separately, we needed to decide where the per-module answer
state and agentic metadata live.

## Decision — catalog

- The catalog is **user-owned configuration**, not baked into bailiff's repo. It
  lists **sources**, not templates.
- **One catalog entry = one git repo (`gituser/gitrepo`), NOT a subpath.** This
  is forced by copier's `1 template = 1 git repository` rule. VERIFIED: copier's
  version resolver (`get_latest_tag`, `_vcs.py`) lists tags via `git ls-remote`
  and **silently discards any tag that is not PEP 440-parseable**. There is NO
  tag prefix/glob/pattern filter anywhere in copier. So a monorepo with
  per-component prefixed tags (`lang-python-v1.2.0`) is unusable — copier finds
  zero valid versions. Each template must be its own repo with clean `v1.2.0`
  tags. (Authoring still happens in one monorepo; a CI step fans out per-template
  repos — see [[0006-release-and-split-model]].)
- **Catalog holds SOURCES, not pinned refs.** Do NOT store a `#ref` per entry as
  a mandatory pin — that duplicates copier's per-project pin and defeats the
  `update` flow. The reproduce pin lives in the generated project's answers file
  (`_commit`); bailiff honors it via `vcs_ref=VcsRef.CURRENT` (see
  [[0001-copier-as-engine]]). An explicit `vcs_ref` is an **optional** per-source
  override for teams standardizing a version — not the model.
- Locator form: `gituser/gitrepo` (+ optional `@ref` override). No subpath
  segment (each template is a repo root).
- **A repo using a templated `_subdirectory` for variant selection is still ONE
  catalog entry** — the variant is a *question answer*, not a separate template.
  (`_subdirectory` is template-internal; bailiff only reads it during discovery to
  locate the template files.)
- **Freshness is manual**: an explicit `just catalog` / CLI invocation refreshes;
  CI is just one caller of the same entrypoint, never a dependency.
- **Merge / id collisions: full-id always** (`catalog/template`). No
  unnamespaced first-wins convenience lookup. Support one OR more catalog
  pointers (URLs); bailiff ships an **optional, swappable** reference catalog and
  works against any user-supplied sources with zero reference templates.
- **Non-goal: no git submodules.** Templates are fetched by ref (copier's
  `git clone --mirror`), never nested as submodules in bailiff or in the catalog.

## Decision — answer model (supersedes the sidecar idea)

- **copier's committed answers file is the source of truth**, and its
  answer-source precedence ladder enforces the two-phase split for free:
  `CLI/API args > ask user > answer from last execution > copier.yml defaults`.
  - Init: the agent injects computed answers at priority 1 (`--data` /
    `run_copy(data=...)`); copier does not re-prompt them.
  - Reproduce: copier replays "answer from last execution" (priority 3) from the
    committed answers file — **agent not involved**.
- **Per-question metadata is native copier** (`type`, `choices`, `when`,
  `validator`, `help`) and carries "what is valid" and "how to fill this". A
  dedicated `bailiff.yml` sidecar for that content is therefore **not needed** and
  is rejected (see [[0003-selector-template-and-runtime-injection]] for how the
  catalog and agent guidance are supplied at runtime instead).

## Consequences

- Decentralization is native: copier's answers file records `_src_path` +
  `_commit`, so an answers file points at *its own* template at its own pin —
  users bring their own templates and never depend on bailiff's repo at reproduce
  time.
- **`_src_path` must be the SPLIT (per-template) repo URL, never the authoring
  monorepo** (verified gotcha). Because the split rewrites commit SHAs, a project
  generated from a split repo must always be reproduced/updated from that same
  split repo — mixing the monorepo and split repo makes `update` follow the wrong
  tags. bailiff always sources from split repos.
- Agent-authored answers are replayed with `recopy` + `vcs_ref=VcsRef.CURRENT`
  (faithful reproduce), not `update` (smart 3-way merge, reserved for intentional
  upgrades) — copier forbids hand-editing the answers file and `update`'s diff
  assumes prompt-captured answers.
- No `catalog.yml` artifact: source repos are persisted as answers in the
  repos-collector template (see
  [[0003-selector-template-and-runtime-injection]]); the available-template
  catalog is discovered by bailiff at runtime and injected via `--data`.

## Related

- [[0001-copier-as-engine]], [[0003-selector-template-and-runtime-injection]],
  [[0006-release-and-split-model]].
