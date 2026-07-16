# Contract — the universal fragment/merge model (spec 014)

Replaces 011 cross-cutting §2 (`mise_tools`), §4 (`hook_manager`/`hook_blocks`), §5
(`quality_languages`), and the §6 "accreting unions are agent-frozen → single writer" rule. A
cross-module union is an anti-pattern; every one is replaced by the same shape.

## The universal shape

> Each module renders ONLY its own fragment into its OWN path inside a `.d/` directory. The combined
> artifact is produced by a merge — the tool's NATIVE drop-in where one exists, else a single
> **merged-file-owner** merge (never per-contributor). The bailiff ENGINE does ZERO merging.

N-writers-of-one-file (a 013 collision) becomes N-writers-of-N-files (no collision) + one merge.

## Surface 1 — mise (native drop-in), FR-008/009/010

- Each tool-contributing module renders `.mise/conf.d/<vendor>-<module>.toml` with ONLY its own
  `[tools]`. Example: `bailiff-mod-python` → `.mise/conf.d/bailiff-mod-python.toml`.
- NO module writes `.mise.toml`. NO `mise_tools` union answer. mise merges all `.mise/conf.d/*.toml`
  at runtime (verified: `config_root.rs`), so `mise install` installs the union.
- `bailiff-mod-devcontainer`'s `postCreateCommand` runs bare `mise install` (no explicit tool list;
  it reads the merged conf.d) — FR-009.
- The 013 collision check passes (distinct paths). Reproduce: each drop-in is a normal single-module
  MANAGED render → byte-identical per file (no cross-layer dependency).
- Modules affected: base (was the `.mise.toml` writer — now contributes its own conf.d + drops
  `.mise.toml`) plus every tool contributor (~python, ts, go, rust, cocogitto, moon, api, cdk,
  terraform, …). `mise_tools` removed from base `copier.yml`.

## Surface 2 — pre-commit (no native drop-in → owner-side vendored bundler), FR-011/012

- Each hook-contributing module renders `.pre-commit.d/<vendor>-<module>.yaml` — its hook block
  only, MAY be conditional on the module's own answers.
- `bailiff-mod-precommit` ships ONE vendored bundler `scripts/_merge_precommit.py` (template
  content) run as a **`_post_task`** (FR-021, R11) — NOT an inline `_task`. This is load-bearing:
  precommit is ordered FIRST (languages read `hook_manager` from it via `_external_data`), so an
  inline task at precommit's layer would see NO language fragments. As a post-task, bailiff runs it
  AFTER the whole render loop, when every fragment exists. It:
  - reads ALL `.pre-commit.d/*.yaml`;
  - emits `.pre-commit-config.yaml` deterministically, order-independent (same fragment set →
    equivalent config regardless of layer order);
  - deduplicates repos;
  - on a rev-pin conflict (two fragments pin the SAME hook repo at DIFFERENT revs) picks the
    **HIGHEST rev and WARNS** — never aborts (R2 revised: a hard error would let a lagging third-party
    module veto a valid stack, colliding with the open-ecosystem premise).
- EXACTLY ONE merger (precommit). When precommit is absent or `hook_manager=none`, no merge runs and
  no `.pre-commit-config.yaml` is produced (fragments are inert) — FR-012.
- Per-contributor merging is FORBIDDEN: N writers on one output re-creates the multi-writer collision
  014 removes, and no contributor can see all fragments to resolve the rev-pin rule.
- Dependencies: Python + PyYAML only (never the bailiff CLI). Runs on init AND reproduce (post-tasks,
  like copier `_tasks`, run on both). Reproduce: config-consistent (same hooks), NOT byte-identical.
  `check_modules.py` MAY lint the single-merger invariant.

## Surface 3 — gitignore (no committed-file merge → owner-side idempotent concat), FR-013

- Each contributing module renders `.gitignore.d/<vendor>-<module>` — gitnr-produced OR literal
  static lines (supports non-gitnr / static-list packages).
- The gitignore owner (base) runs ONE idempotent ordered-concat as a **`_post_task`** (FR-021,
  delimited blocks, e.g. `# >>> <module> >>> … # <<< <module> <<<`) folding fragments into
  `.gitignore` after the render loop. A post-task (not inline) so it sees every contributor's fragment
  regardless of layer order. NO vendored script (concat is trivial); NO `gitignore_stack` fact.
- Idempotent: reproduce MUST NOT duplicate entries (delimited blocks are replaced, not appended).
  Guarantee is config-consistency (same ignore rules), not byte-identity.

## Consequence (spec-level)

There are ZERO cross-module answer unions after 014. What remains: per-module fragments, native/task
merges, and namespaced facts via `_external_data` ([`_facts.md`](./_facts.md)). `quality_languages`
(011 §5) is NOT shared — it is declared AND consumed by `bailiff-mod-quality` alone, so it stays a
local question, no change.

## FR-018 rewrite target

This contract file, together with `_threading.md` and `_facts.md`, is the content that replaces 011
cross-cutting §2/§4/§5/§6. The 011 file MUST be rewritten (not just cross-referenced) so a module
author reads ONE current contract, per FR-018.
