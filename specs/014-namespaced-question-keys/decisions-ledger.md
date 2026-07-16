# Decisions Ledger — spec 014 (namespaced keys, private-by-default threading, fragment/merge model)

**Source**: The 2026-07-16 design session triggered by the spec-013 integration tests finding
a real cross-module answer-poisoning bug (`framework` collision across python/ts/stack-adr),
plus copier and mise capability research verified against primary sources the same day. This
file is the in-tree authoritative record: where spec.md is silent, this ledger governs; where
this ledger is silent, the item is out of scope for 014. **Research-first spec** — plan.md and
tasks.md follow after this ledger is accepted.

## Verified research (primary sources, 2026-07-16)

| Finding | Source | Implication |
|---|---|---|
| copier isolates templates by default (one answers file per template; no shared answer namespace) | copier docs "Applying multiple templates" | bailiff's blanket cross-layer answer bleed is a bailiff invention, not a copier requirement — it can be removed. |
| copier `_external_data` provides namespaced, opt-in cross-template reads (`_external_data.<ns>.<key>`), does not pollute the consumer's answers file | copier docs "Template Composition with External Data" | This is the sanctioned mechanism for threaded facts (project_name, layout, …). |
| copier `when: false` computed values render a value without prompting; can be locked into the answers file | copier FAQ "computed value" / "lock a computed value" | A module can render an injected value deterministically for reproduce. |
| copier reserves a single leading `_` for settings/metadata; `_`-prefixed keys cannot be answerable questions | copier config model | A private question CANNOT be named `_framework`; privacy must come from threading control, not the `_` prefix. |
| mise merges all `.mise/conf.d/*.toml` drop-in files at runtime | mise source `config_root.rs` (`.mise/conf.d` is a config root); mise docs config hierarchy | `mise_tools` union dissolves: per-module drop-in files, native merge, no combine. |
| git has NO committed-file merge for `.gitignore` (composes by precedence: root, per-dir, info/exclude, global) | git ignore model | gitignore cannot use a native drop-in; needs a fact or a bailiff merge/append. |
| pre-commit has NO include/drop-in for `.pre-commit-config.yaml` (single file) | pre-commit config model | pre-commit needs a bailiff post-install MERGE task over per-module fragments. |

## The governing decision — universal fragment/merge pattern (ratified)

**A cross-module answer "union" is an anti-pattern.** It exists only because a single output
file was assumed to have a single writer. Every union is replaced by:

> Each module renders ONLY its own fragment into its own path. The combined artifact is
> produced by a merge — the tool's NATIVE drop-in merge where one exists, or a single bailiff
> post-install merge task where it does not.

**Ratified consequence: there are ZERO cross-module answer unions after 014.** No key like
`mise_tools` or `hook_blocks` is threaded across layers. What remains: per-module fragments,
native/task merges, and namespaced shared *facts* (single values) via `_external_data`.

This mechanism is the DEFAULT for anything without native drop-in support (maintainer:
"that mechanism works best for everything that does not support this natively").

## Config-consistency invariant (ratified — supersedes byte-identity)

bailiff's reproduce guarantee is **config-consistency**, not byte-identity: a reproduced or
merged file expresses the SAME configuration (same tools/hooks/ignore rules), not necessarily
the same bytes. A merge (YAML re-emit, append) cannot be byte-identical; it is config-equivalent.
Single-module managed renders remain deterministic and, in practice, byte-identical — but the
CONTRACT-level guarantee across the system is config-consistency. A repo-wide prose sweep
reframes all "byte-identical" invariant language to "config-consistent" (running on branch
`byte-to-config-sweep`; test byte-assertions are NOT auto-weakened — flagged for per-assertion
review).

## Union dispositions (ratified)

| Former union | Disposition |
|---|---|
| `mise_tools` | DELETED as a union. Per-module `.mise/conf.d/<vendor>-<module>.toml`; mise merges natively. No module writes `.mise.toml`. devcontainer runs bare `mise install` (reads merged conf.d), no frozen tool list. |
| `hook_blocks` | DELETED as an answer union. Per-module `.pre-commit.d/<vendor>-<module>.yaml` fragments; precommit runs ONE post-install merge task → `.pre-commit-config.yaml`. Config-consistent. |
| `gitignore_stack` | NOT a union (it is a token-list fact, task-output via gitnr, already config-consistent). Stays a shared fact OR becomes per-module fragment+merge — plan-phase pick. |
| `quality_languages` | NOT shared — declared and consumed by the same module (quality). No change. |

## Threading model (ratified)

- **Private by default**: `init_many`'s `_merge_layer_answers` stops merging all non-`_` keys;
  a module's questions stay in its own layer. Kills the answer-poisoning class structurally
  (the `framework` collision could not occur under isolation).
- **Shared facts are explicit + vendor-namespaced**: a key that must cross layers is named
  `<vendor>__<name>` (double underscore) and shared via `_external_data` on the consumer side;
  the producer writes it to its answers file. `bailiff__` is first-party-reserved.
- **Vendor prefix = collision boundary** (ratified over a central allowlist): a centralized
  first-party `SHARED_KEYS` list was REJECTED because it cannot know a third-party vendor's
  shared keys. Vendor-scoping (`bailiff__`, `acme__`) works across an open ecosystem.

## framework collision point-fix (separate, in flight)

The specific `framework` collision (python/ts/stack-adr) is being fixed NOW on
`fix-framework-collision` (rename to `python_framework` / `ts_framework` / `stack_framework`)
to unblock the integration suite. 014 generalizes the CLASS; it does not depend on that
point-fix and vice versa.

## NEEDS CLARIFICATION — resolve before plan phase

1. **pre-commit merge implementation** (FR-011): how the merge task folds `.pre-commit.d/*.yaml`
   — a pinned bailiff helper invoked as a task, or a small vendored merge script? Plus the
   rev-pin conflict rule (highest-wins vs explicit error).
2. **gitignore disposition** (FR-013): shared frozen fact + single gitnr call, vs per-module
   fragment + idempotent merge.
3. **Rename migration** (FR-014): documented break + re-init recommendation (justified by
   near-zero pre-014 population — greenfield, no external users, 27 mirrors freshly published
   and re-fannable), vs an alias/migration shim. Leaning: documented break.
4. **Exact first-party shared-fact set** (FR-007): ratify the final list. Candidates from the
   enumeration: `project_name`, `layout`, `github_host`, `default_branch`, `monorepo_tool`,
   `monorepo_packages`, gitnr token list. Note the exclusive-sibling keys (`visibility`,
   `remote_protocol`, `push_after_create`, `team` in github-repo/gitlab-repo; the `ci_*` keys
   in ci-github/ci-gitlab) — under private-by-default these NEVER collide at runtime (mutually
   exclusive siblings), so they can stay bare-private and need NO prefix. Confirm this reading.
5. **`__` separator sanity** (FR-004): `bailiff__name` has no leading `_`, so copier treats it
   as a normal key — confirm no bailiff/copier tooling ascribes special meaning to a `__`
   infix.

## Out of scope for 014

- New module features or new modules.
- The `framework` point-fix itself (separate branch).
- Conditional-Jinja contribution expressiveness beyond what the pre-commit fragment needs.
- Stack presets (013 FR-017, still deferred).
- Constitution amendment (none anticipated; engine changes fall under the 013 C-11 relaxation).
