# bailiff — End-State Component Inventory

Durable reference for what bailiff consists of once the whole roadmap (specs
001–009) is delivered. Companion to [`.specify/memory/roadmap.md`](../../.specify/memory/roadmap.md)
and the [constitution](../../.specify/memory/constitution.md) (v2.0.0).

bailiff is a **skill + a family of copier templates + minimal deterministic glue** —
NOT a published application. copier owns the single-template lifecycle; bailiff adds
the conducting skill, the templates, and only the sliver of coordination copier
lacks. This document maps every component to its category and the spec that
delivers it.

Legend for "kind": **skill** = markdown procedure · **template** = copier template
content · **glue** = small deterministic code/script · **CI** = pipeline bash ·
**config** = user/tool config file · **output** = artifact written into a generated
project.

---

## 1. The conducting skill (bailiff's primary deliverable)

One APM-distributed skill: `SKILL.md` plus the glue it invokes. This *is* the
agentic conductor; it does only non-deterministic phase-1 work and is never in the
reproduce path.

| Component | Kind | What it is | Spec |
|---|---|---|---|
| `SKILL.md` (conduct) | skill | Phase-1 procedure: discover → present questions → collect answer values → explain/consent to trust → author inputs doc → `--pretend` check → init → hand off | 001 (extended 002–007) |
| Selection sub-procedure | skill | Present a multi-source catalog + multiselect; read discovery output; decide which modules to enable | 002, 003 |
| Trust-consent sub-procedure | skill | Scripted explanation of the code-execution implication + the exact `trust add` step | 001 |
| Upgrade/migration sub-procedure | skill | Drive an announced `bailiff upgrade`; surface migration effects | 006 |
| Agentic-wiring guidance | skill | Reason about APM/MCP/SpecKit selections for the agentic module | 007 |

## 2. The copier template family (`bailiff-mod-*`) — the reusable product

Each is **one git repo = one template**, clean `vX.Y.Z` (PEP 440) tags, and ships
`{{ _copier_conf.answers_file }}.jinja` (required for reproducibility). Content,
not code. Every template also carries its questions, `secret:` flags, `when:false`
dependency edges (`depends_on`/`run_after`/`run_before`), and new-format
`_migrations`.

| Template | Kind | Purpose | Spec |
|---|---|---|---|
| `bailiff-template-example` | example template | Slice-001 demonstrator: identity → README/.gitignore/dirs + `git init` + LICENSE-via-`gh` tasks. Proves the loop + the template contract; disposable, NOT a shippable module | 001 (hand-published) |
| `bailiff-mod-base` | template | Repo foundation: identity → README/LICENSE/.gitignore/dirs + `git init` task. Would collapse 5 project-setup base modules | 008 (automated), 009 (maybe re-split) |
| repos-collector (meta) | template | Persists the user's source repos in its own answers file | 002 |
| selector (meta) | template | Catalog injected at runtime via `--data catalog=…`; multiselect | 002 |
| `bailiff-mod-lang-{python,ts,go,rust}` | template | Language overlays | 009 |
| `bailiff-mod-{apm,mcp,precommit,ci-github,readme,justfile,…}` | template | Remaining ported project-setup modules | 009 |
| `bailiff-mod-agentic` | template | APM/MCP/SpecKit/ADR wiring; APM install as a trust-gated `_task`; the distinctive value | 007 |

## 3. Minimal deterministic glue (the entire code surface)

Deliberately small: glue exists only for what copier's CLI and the agent cannot do
directly (Constitution I / C-11).

| Component | Kind | What it does | Spec |
|---|---|---|---|
| `bailiff-discover` helper | glue | Static parse of `copier.yml` + file-tree glob for the answers-file `.jinja` + `git ls-remote` PEP 440 tag filter → prints discovery output. **No Jinja env, no `Template`/`Worker`** | 001 |
| Catalog parse helper | glue | Read N source repos' `copier.yml` statically → catalog list | 002 |
| Ordering / DAG helper | glue | Topological order from `when:false` edges — the one genuinely algorithmic piece | 003 |
| All-gaps preflight | glue | Collate every question across enabled modules + `--pretend` dry-run → report all missing answers at once | 003 |
| Defaults helper | glue | Read `~/.config/bailiff` defaults → `user_defaults=` per module | 004 |
| Secrets fetch script | glue | e.g. `op read …` → `--data secret=…` (bash-shaped) | 005 |
| Trust read / add / list | glue | Read copier `settings.yml` `trust:`; `trust add` appends the expanded-`https://` prefix on consent; `trust list` | 001 |
| _(conditional)_ deprecated-surface adapter + drift test | glue | ONLY if third-party templates need `!include`/inheritance resolution static parsing can't do (roadmap Q3) — not guaranteed to ever exist | 002+ (if needed) |

## 4. Authoring monorepo + release/fan-out (CI, not app code)

| Component | Kind | What it is | Spec |
|---|---|---|---|
| `bailiff` monorepo | CI | All templates authored under `templates/<name>/` | 008 |
| cocogitto config | CI | Monorepo mode, `<name>-vX.Y.Z` tags, `generate_mono_repository_global_tag=false`, `tag_prefix=v` | 008 |
| Fan-out CI job | CI | `cog bump` → push → `git tag --points-at HEAD` → ~25-line snapshot-mirror (cp+commit+strip-prefix-tag+push, PAT-scoped, skip-if-no-diff) to `bailiff-mod-*` | 008 |
| Catalog index publisher | CI | JSON index of `bailiff-mod-*` repos + latest `v*` | 008 |

## 5. Config & distribution

| Component | Kind | What it is | Spec |
|---|---|---|---|
| copier `settings.yml` `trust:` | config | User's trusted-source prefixes (copier's own file; bailiff reads/writes) | 001 |
| `~/.config/bailiff/defaults.yml` | config | User's global per-module default answers | 004 |
| Catalog pointer(s) | config | One or more URLs to catalog indexes; swappable, user-owned | 002 |
| APM marketplace entry | config | How the skill is distributed (NOT PyPI / `uvx`) | 008 |

## 6. Artifacts written into the user's generated project (the output)

| Artifact | Kind | Written by | Notes |
|---|---|---|---|
| Rendered files | output | copier | README/LICENSE/src/etc. |
| `.copier-answers.yml` (per module) | output | copier | Reproduce source of truth: `_src_path` (split repo), `_commit`, answers; excludes secrets + `when:false` edges |
| Generated `just reproduce` recipe | output | bailiff at init | Ordered `copier recopy --vcs-ref=:current: --defaults --overwrite` per module — freezes DAG order so reproduce needs no agent and no live ordering code |

---

## The through-line

The only durable *code* bailiff ships is category 3 — a handful of small helpers,
most of them thin wrappers around static YAML parsing and copier CLI calls, with
the single genuinely-algorithmic piece (the DAG) in spec 003. Everything else is a
skill (markdown), templates (content), CI (bash), or config (files). There is no
published application, no pydantic layer, and no standing deprecated-surface
adapter.
