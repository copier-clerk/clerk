# Phase 0 Research — spec 014

Research-first spec: the primary-source verification and the ratified decisions already live in
[decisions-ledger.md](./decisions-ledger.md). This file consolidates them into the
Decision / Rationale / Alternatives shape the plan workflow expects, and adds the cross-module
fact audit (2026-07-16) that fixed the exact first-party fact set. All NEEDS CLARIFICATION from
the spec are resolved (ledger §RATIFIED R1–R10 + FR-006 inversion; the dependency model was
redesigned by the 2026-07-16 grill + engineering critique — see R0.8).

## R0.1 — copier isolates templates by default; `_external_data` is the sanctioned cross-read

- **Decision**: Read cross-module facts through copier `_external_data` aliases; drop bailiff's
  blanket answer-bleed entirely.
- **Rationale**: copier docs "Applying multiple templates" — one answers file per template, no
  shared answer namespace; the blanket bleed is a bailiff invention, not a copier requirement.
  copier docs "Template Composition with External Data" — `_external_data` gives namespaced,
  opt-in reads (`_external_data.<alias>.<key>`) that do NOT pollute the consumer's answers file.
- **Alternatives rejected**: (a) the `<vendor>__<name>` double-underscore prefix scheme + a
  `check_modules.py` shared-key lint — REJECTED (R5/FR-007): alias namespacing already isolates
  structurally, works cross-vendor (each producer's answers file is a distinct alias), needs no
  convention to lint. (b) A central first-party `SHARED_KEYS` allowlist — REJECTED: cannot know a
  third-party vendor's shared keys; does not scale to an open ecosystem.

## R0.2 — private-by-default threading kills the poisoning class

- **Decision**: `init_many` stops accreting non-`_` answers across layers; a module's questions are
  layer-local. Reproduce applies the same isolation.
- **Rationale**: the `framework` collision (python `{none,fastapi,django,flask}` vs ts
  `{plain,nuxt,vite,sst}`) shipped and broke every Python+TS stack; `test_runner` (ts vs rust) is a
  latent second instance. Isolation makes the whole CLASS impossible by construction — the 013
  philosophy "enforce structure, don't trust author discipline." Grounded: `runner.py:457`
  `data = {**accumulated, **layer_answers}`; `accumulated` grows via `_merge_layer_answers`
  (runner.py:532, called line 484).
- **Alternatives rejected**: per-key renames only (the merged `framework` point-fix) — treats
  instances, not the class; the next colliding key re-introduces the bug.

## R0.3 — mise `.mise/conf.d/` dissolves the `mise_tools` union

- **Decision**: per-module `.mise/conf.d/<vendor>-<module>.toml` drop-ins; no module writes
  `.mise.toml`; devcontainer runs bare `mise install`.
- **Rationale**: verified against mise source `config_root.rs` — `.mise/conf.d` is a config root;
  mise merges all drop-in files at runtime. The `mise_tools` union (the largest, 10 contributors)
  existed only because `.mise.toml` was assumed single-writer — exactly a 013 file-collision.
  Native merge eliminates the constraint; the 013 collision check passes (distinct paths).
- **Alternatives rejected**: keep a single-writer `.mise.toml` fed by a frozen `mise_tools` answer
  (011's M1 resolution) — that IS the anti-pattern 014 removes.

## R0.4 — pre-commit has no native drop-in → owner-side vendored bundler

- **Decision**: each hook module writes `.pre-commit.d/<vendor>-<module>.yaml`;
  `bailiff-mod-precommit` vendors ONE Python bundler (`scripts/_merge_precommit.py`), run as a
  **`_post_task`** (R11 — NOT inline, since precommit is ordered first as a `hook_manager` producer),
  that folds all fragments into `.pre-commit-config.yaml` deterministically after the render loop;
  on a rev-pin conflict it picks the **highest rev and warns** (R2 revised — never aborts).
- **Rationale**: pre-commit config model — a single `.pre-commit-config.yaml`, no include/drop-in;
  the combine is irreducible. Owner-side single reader is the only place that (a) orders
  deterministically, (b) dedups repos, (c) can SEE all fragments to resolve a rev-pin conflict.
  Vendored (not a `bailiff merge` CLI) so a generated project never depends on the bailiff CLI at
  render/reproduce time (no module task does today) and third-party modules can ship their own.
- **Alternatives rejected**: (a) `bailiff merge` in-binary CLI — REJECTED (R1): couples generated
  projects to the bailiff CLI, not third-party-extensible. (b) per-contributor append scripts —
  REJECTED: N writers on one file (multi-writer collision returns) and none can see all fragments to
  resolve the rev-pin rule. (c) hard-error on rev-pin — REJECTED (R2 revised): a lagging third-party
  module could veto a valid stack, colliding with the open-ecosystem premise; highest-wins+warn is safe.

## R0.5 — gitignore has no committed-file merge → owner-side idempotent concat

- **Decision**: per-module `.gitignore.d/<vendor>-<module>` fragments (gitnr-produced OR literal
  static lines); the gitignore owner runs ONE idempotent ordered-concat as a **`_post_task`** (R11,
  delimited blocks). No `gitignore_stack` fact.
- **Rationale**: git composes ignores by precedence (root, per-dir, info/exclude, global), NOT by
  merging multiple committed root files — so no native drop-in. Concat is trivial (delimited blocks
  → idempotent, no duplicate on reproduce), so it needs no vendored script — but it runs as a
  post-task (after the render loop) so it sees every contributor's fragment regardless of layer order.
  Supports non-gitnr/static-list packages.
- **Alternatives rejected**: keep `gitignore_stack` as a frozen shared fact + single gitnr call —
  workable but keeps a cross-layer fact where a fragment/concat is simpler and vendor-open.

## R0.6 — config-consistency supersedes byte-identity for merged artifacts

- **Decision**: reproduce guarantee is CONFIG-CONSISTENT (same tools/hooks/ignore rules), not
  byte-identical, for merged artifacts; single-module MANAGED renders stay deterministic /
  byte-identical.
- **Rationale**: a YAML re-emit (pre-commit) or an append (gitignore) cannot be byte-identical; the
  contract-level guarantee across the system is config-equivalence. Already ratified + prose-swept
  on main (`498315f`); the reproduce byte-assertions on merged files dropped surgically (byte-drop
  branch, merged to main).
- **Alternatives rejected**: force byte-identity on merges — impossible without freezing a single
  writer, i.e. re-introducing the union.

## R0.7 — Cross-module fact audit (2026-07-16) → the exact first-party fact set

Full ripgrep audit of all 26 non-base `templates/bailiff-mod-*/` for reads of keys the module does
not itself originate. Findings (file:line evidence in the audit; summarized here):

- **`project_name`** — 18 modules redeclare `default: "{{ project_name }}"` (agentic, api, apm, cdk,
  ci-gitlab, cocogitto, devcontainer, github-repo, gitlab-repo, go, mkdocs, moon, python, readme,
  rust, stack-adr, ts, terraform). Canonical base fact.
- **`layout`** — base + moon, cocogitto, package-add (structural branching). Base fact.
- **`github_host`** — base + dep-updates (also derives `dep_update_tool` default from it). Base fact.
- **`description`** — base + apm, api, mkdocs, python, readme. DIVERGENT today: 4 of 5 default to
  `""` so users retype it. Audited as a genuine fact (renders into base AGENTS.md, readme
  README.md, api openapi.yaml, apm apm.yml, mkdocs site_description+index). KEEP + make a base fact
  so consumers inherit with a local fallback.
- **`default_branch`** — LATENT BUG: no module defines it, yet ci-github (`copier.yml:80-82`) and
  ci-gitlab (`:91-93`) thread `default: "{{ default_branch }}"` from a non-existent producer;
  ci-github even guards against the literal un-rendered string leaking into its workflow. FIX: add
  `default_branch` to base as a fact.
- **`monorepo_tool` / `monorepo_packages`** — produced by moon (`copier.yml:42`/`:34`; moon "is the
  supplier … freezes monorepo_tool=moon for CI consumption"); read by ci-github (`monorepo_tool`),
  ci-gitlab (both), cocogitto (`monorepo_packages`). NON-base producer facts (alias `moon`) — proves
  `_external_data` is not base-specific.
- **`hook_manager`** (ADDED after a second exhaustive audit; the first pass MISSED it by only grepping
  base/moon reads) — produced by precommit; read by python, ts, api, go, rust, terraform, justfile.
  Precommit co-occurs with language overlays in the same stack, so this is a genuine non-exclusive
  cross-layer read; private-by-default without an alias would render it EMPTY (silent lint/hook break).
- **`js_pkg_manager`** (ADDED) — produced by ts; read by justfile, package-add.
- **`ts_linter`** (ADDED) — produced by ts; read by editorconfig.
- **Bare-private (NOT facts)**: `org`, `copyright_name`, `branch_strategy` (base-only, no
  cross-reader); the exclusive-sibling keys `visibility`/`remote_protocol`/`push_after_create`/`team`
  (github-repo vs gitlab-repo), the `ci_*` keys (ci-github vs ci-gitlab), and `placement_dir`
  (terraform/cdk/cloudformation) — mutually exclusive at runtime, cannot collide, need no alias.
- **Collision-class (stay private)**: `test_runner` — go `{go-test,gotestsum}` vs rust
  `{cargo-test,nextest}` vs ts `{none,vitest-*,bun-test,playwright-only}`, disjoint domains. Reading it
  cross-layer IS the poisoning bug; private-by-default fixes it wholesale.

- **Decision**: producers = **base** {`project_name`, `layout`, `github_host`, `description`,
  `default_branch`} + **precommit** {`hook_manager`} + **ts** {`js_pkg_manager`, `ts_linter`} +
  **moon** {`monorepo_tool`, `monorepo_packages`}; everything else bare-private or collision-class.
- **Rationale**: the minimal closure of keys ACTUALLY read across layers, per an EXHAUSTIVE audit
  (copier.yml `default:` lines AND template/ bodies — the first audit's `copier.yml`-only method missed
  the precommit/ts choice-axis reads), plus the one latent-bug fix (`default_branch`). No speculative facts.
- **Alternatives rejected**: promoting `org`/`copyright_name`/`branch_strategy` — no cross-layer reader.

## R0.8 — dependency model: single `depends_on` edge + stratified DAG + fact-read-as-hard-dep (2026-07-16 grill)

- **Decision**: (a) reading a fact via `_external_data` is a HARD data-dependency — bailiff statically
  parses the alias and requires the producer present + ordered-before; absent → loud error (FR-006
  INVERTED — no graceful fallback). (b) Collapse the edge vocabulary to a SINGLE `depends_on`;
  drop `run_after` + `run_before`. (c) pre/normal/post stratified DAG with edge-legality validation.
- **Rationale**: copier's `_external_data` on a missing file returns `{}` (`_user_data.py:597-603`,
  `warn_on_missing=True`), so an unguarded read renders EMPTY STRING — the exact silent mis-render
  SC-006 forbids; bailiff must produce the error copier won't. Empirically, `depends_on`/`run_after`
  are byte-identical in code (`ordering.py:90`) and only `run_after: base` is used (0 uses of
  `depends_on`/`run_before`); a single edge minimizes DAG cycle surface (one arrow direction). The
  strata give structural "run first/run last" without a last-mover enumerating N edges.
- **Alternatives rejected**: (a) graceful fallback (original FR-006) — silent mis-render. (b) soft
  `run_after` (order-if-present) — no such case exists; reintroduces tolerate-absence. (c) auto-INJECT
  a hidden edge from `_external_data` — rejected for VALIDATE-visible-declaration (013 ethos: structure
  in the file, not synthesized by a memorized rule). (d) `run_before` kept — 0 uses, doubles cycle surface.
- **Migration gate (R10)**: copier silently ignores unknown recorded keys, so a `_bailiff_schema: 014`
  marker + refuse-on-mismatch in `reproduce_many` is REQUIRED to make the documented break loud (SC-006).

## R0.9 — post-tasks + marker write-path (2026-07-16 re-critique of the redesigned model)

The re-critique verified the redesign and found ONE load-bearing NEW hole + corrected the marker mechanism:
- **CONFIRMED sound**: `_external_data` is statically parseable (copier reads it as a plain top-level
  `_`-key, `_template.py:340` — same `yaml.safe_load` discovery already does), so FR-006 enforcement is
  implementable; and the real fact graph (base→all; precommit→languages; ts→justfile/package-add/
  editorconfig; moon→ci) is ACYCLIC (precommit reads nothing ts produces). base is fact-free as a consumer.
- **NEW hole → R11 (post-tasks)**: FR-006 orders precommit FIRST (languages read `hook_manager`), but the
  pre-commit merge must run LAST (needs language fragments). copier runs `_tasks` INLINE per layer
  (`runner.py:461`, no global post-pass), so an inline merge in precommit sees no fragments → empty
  `.pre-commit-config.yaml` (fails US4). FIX: `_post_tasks` — bailiff (driving copier as a library) runs
  collected post-tasks after the render loop, on init AND reproduce. NO `_pre_tasks` ("run first" = be
  the first module + a normal `_task`). Rejected: building the `post` MODULE-phase finalizer now
  (heavier); the sub-render "phase = separate copier render" model (3× answers files, phase-leaking alias
  paths, 3-pass engine, for a merge that's a script either way).
- **Marker write-path (R10 refined)**: the marker CANNOT be a copier answer — a `when:false` hidden
  question is OMITTED from the answers file (`_main.py:613-616` `answers.hide()` → "Omit its answer from
  the answers file"; the very mechanism `depends_on` edges use to stay out), an askable question drops the
  leading `_` + pollutes the namespace + is user-overridable, and `--data _key` is stripped by the
  `not k.startswith("_")` filter (`_main.py:374`). So bailiff APPENDS `_bailiff_schema: 014` post-render
  (one engine site), mirroring copier's own special-cased `_commit`/`_src_path` writes (`_main.py:367-369`).
  POSITIVE allowlist chosen over negative dissolved-key detection (generalizes to 015+; pre-014 can't fake it).
