<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.0 → 2.0.0
Bump rationale: MAJOR — direction change. A YAGNI review reframed clerk from a
published Python tool into a skills bundle + copier template family + minimal
deterministic glue (constitution v2.0.0). Vision, decisions C-01/C-04/C-08, and
every spec entry are restated so coordination code appears only where copier
genuinely cannot coordinate; everything else is a copier invocation, template
content, per-project reproduce recipe, or CI bash.

Changes this revision:
  - Vision restated (skills + templates + glue; no uvx/PyPI tool)
  - C-01 clerk-nature rewritten; C-04 adapter → conditional; C-08 pydantic seam →
    documented dry-run-validated handoff; C-11 added (glue-only-when-copier-cannot)
  - Every spec 001–009 re-scoped to the lean model; deferred entry unchanged
Specs affected: 001–009 (all re-scoped), DEFERRED-rewrite (unchanged)
Open questions: Q1/Q2/Q3 retained; Q4 added (when does coordination justify a tool)
Notes: supersedes the v1.0.0 tool-centric roadmap. ADRs referencing a uvx tool /
pydantic seam are governed by constitution v2.0.0 until reconciled.
-->

# clerk — Spec Roadmap

Living, non-binding map of the specs planned for clerk. It captures the
spec-specific decisions, technology choices, outcomes, and constraints surfaced
during the constitution + grilling + YAGNI-review phases so they are not lost
before the spec that needs them is written. Specs are scoped when they are
actually started. Foundations: the project [constitution](constitution.md)
(v2.0.0) and the ADRs in [`docs/decisions/`](../../docs/decisions/).

Status legend (lifecycle): **undecided** · **needs-info** · **planned** ·
**specced** · **in-progress** · **implemented** · **verified** · **deferred** ·
**abandoned**.

---

## Vision & End States

- clerk is an **agentic conductor for copier**, delivered as **an agent skill + a
  family of copier templates (`clerk-mod-*`) + minimal deterministic glue** — NOT
  a published `uvx`/PyPI application. copier already owns the single-template
  lifecycle; clerk adds the conducting skill, the templates, and only the sliver of
  coordination copier lacks.
- A **two-phase model**: the skill authors the *inputs*; a deterministic phase (a
  copier invocation, optionally wrapped by a small helper) executes. The agent is
  confined to non-deterministic judgment; everything mechanical runs and tests
  without an LLM.
- **Faithful, agent-free reproduce is the headline guarantee**: reproduce replays
  committed answers at the recorded revision (`recopy --vcs-ref=:current:`); for
  multi-template projects the order is frozen into a per-project reproduce recipe.
- Users bring **their own template catalog**; clerk depends on no first-party hub.
- clerk's distinctive value is the **agentic-ecosystem wiring** (APM / MCP /
  SpecKit / ADR), delivered as template content, not tool code.

## Constraints & Decisions

- **C-01 — clerk = skills + templates + minimal glue (not a tool):** the durable
  artifacts are the `SKILL.md` conductor, the `clerk-mod-*` templates, and small
  deterministic helpers (ordering, edge parsing, defaults, dry-run validation,
  reproduce-recipe generation). No published application. _See Constitution I;
  supersedes the earlier tool framing in ADR-0001._
- **C-02 — Two-phase boundary:** skill authors a frozen, documented inputs handoff;
  the deterministic phase executes with zero LLM. Testable without an LLM. _See
  Constitution II._
- **C-03 — Faithful reproduce, distinct upgrade:** `recopy --vcs-ref=:current:`;
  bare recopy (silent upgrade) never exposed; `update` is the explicit upgrade;
  multi-template reproduce order frozen into the project. _See ADR-0001,
  Constitution III._
- **C-04 — Prefer CLI + static config; adapter only IF deprecated surface is
  actually used:** discovery prefers static `copier.yml`/file-tree parsing (safe,
  no code exec); the `Template`/`Worker` adapter + drift test exist only if a helper
  genuinely needs them — not a standing mandate. Pin `copier>=9.16,<10`. _See
  Constitution IV._
- **C-05 — Determinism via pinning; trust by source:** pin ref/copier/tools; forbid
  `jinja2_time`/random; inject `{{ today }}`; trust via `settings.yml` with
  fully-expanded `https://` URLs; deterministic phase never writes trust; CI fails
  loudly without trust. _See ADR-0001/0004, Constitution V._
- **C-06 — Template-author contract, enforced at discovery:** answers-file
  `.jinja` required (else unreproducible → refuse); one repo = one template, clean
  PEP 440 tags; `when:false` edges in `copier.yml`; new `_migrations` format;
  published labels immutable. _See ADR-0002/0006, Constitution VI._
- **C-07 — Hardening per-step, scaled to what ships:** each spec lands its own
  determinism checks, error surfacing, and tests for any glue it adds. _See
  Constitution VII._
- **C-08 — Documented, dry-run-validated handoff (no pydantic seam):** the inputs
  handoff is a documented plain-text format (copier answers/`--data-file` shape
  where possible); validation reuses copier's own dry run (`--pretend`) and answer
  validation. Typed models / JSON-Schema drift tests are NOT introduced until a
  non-agent program consumes the handoff. _See Constitution VIII._
- **C-09 — Authoring monorepo → per-template fan-out + lifecycle:** templates
  authored in one monorepo; cocogitto tags `<name>-vX.Y.Z`; a hand-rolled
  snapshot-mirror CI step fans out to read-only `copier-clerk/clerk-mod-*` repos
  with clean `vX.Y.Z` tags; consumers source the split repos. The authoring
  lifecycle (scaffold via copier meta-template, `check-modules` contract lint,
  generated `catalog.json`, org GitHub App minting short-lived tokens with
  fan-out auto-creating missing repos) reuses the consumer-plane helpers aimed
  inward — no second tool. Submodules rejected (do not satisfy copier's per-repo
  clean-tag rule). _See ADR-0006/0002._
- **C-10 — Validation wraps copier, not re-implements it:** surface copier's own
  validation (`copier.errors.*` AND `builtins.ValueError`); `--pretend`/`--check`
  uses copier's dry run. Cross-module all-gaps preflight is a forward-extension at
  spec 003. _See Constitution VII/VIII._
- **C-11 — Glue is justified only by a copier gap:** new deterministic code is added
  only for a capability copier lacks (chiefly cross-template coordination:
  ordering, edge resolution, catalog parsing, defaults). Otherwise prefer a copier
  invocation, a template feature, or a documented agent step. _See Constitution I._

## Planned Specs

### 001 — Single-template vertical slice  [status: implemented]

- **Description:** Prove the whole conduct→copier→reproduce loop for ONE trusted
  source with ONE template, as **skill + example template + minimal glue** (no
  package).
- **Outcome:** With the skill, a developer inspects `clerk-template-example`,
  supplies answers, generates a rendered + git-initialized project recording its
  template and version, and reproduces it faithfully with no agent — driven by
  copier's CLI plus small helper scripts.
- **Scope (in):**
  - The `clerk-template-example` example template (renders identity → README/.gitignore/
    dirs; hermetic `git init` + LICENSE-via-`gh` tasks, no commit; ships the
    answers-file `.jinja`; tagged `v1.0.0`). _(Impl note: LICENSE is generated by
    a `gh api /licenses` task, not a render file — see [[0006]] rationale; it is
    a task side effect outside the byte-identical reproduce set.)_
  - A `SKILL.md` phase-1 procedure: inspect (read `copier.yml` + check for the
    answers-file `.jinja` + list PEP 440 tags), present questions, collect answer
    values, explain trust + obtain consent, run the init + reproduce commands, hand
    off.
  - Minimal deterministic glue: init = `copier copy --data-file … --defaults
    --overwrite --trust …`; reproduce = a generated `just reproduce` (or script)
    pinning `--vcs-ref=:current: --defaults --overwrite`; a small discovery/
    validation helper only if a bare command cannot (e.g. the answers-file check,
    tag filtering, a `--pretend` dry run). Static `copier.yml` parsing only — no
    Jinja env, no `Template`/`Worker` (so no adapter this slice).
  - Trust onboarding: surface a clear untrusted-source refusal (clerk exit 3,
    naming the exact `clerk trust add <prefix>` remediation); record trust only
    via an explicit consent step writing the expanded-`https://` prefix to
    `settings.yml`.
  - Fix the README + `pyproject.toml` claims (reproduce bare-recopy; "without trust
    / action in clerk"; "never runs `_tasks`") and drop the uvx/PyPI framing.
- **Scope (out):** meta-templates/catalog (002); multi-template/DAG (003); defaults
  (004); secrets (005); upgrade/migrations (006); agentic module (007);
  release/fan-out (008); project-setup port (009). No Python package, no pydantic
  seam, no committed JSON Schema, no adapter unless static parsing proves
  insufficient (it does not, for this template).
- **Depends on:** none.
- **Governed by:** ADR-0001/0002/0004; Constitution I–VIII; C-01..C-08, C-10, C-11.
- **Notes:** the slice ships `clerk-template-example` — a disposable *example*
  template (demonstrates the contract + loop), NOT a shippable module. The real
  `clerk-mod-base` module (collapsing 5 project-setup base modules) is a spec 009
  concern; keeping the example out of the `clerk-mod-*` namespace avoids confusing
  the two. Example hand-published now; the automated authoring/fan-out is 008. One
  marked live smoke test; the rest hermetic/offline via local git fixtures.
- **Completed 2026-07-10** (branch `001-clerk-vertical-slice`): all 35 tasks done;
  `discover`/`init`/`reproduce`/`trust` verbs + `skills/clerk/SKILL.md` +
  `examples/clerk-template-example/`. 35 hermetic tests + 1 network smoke (skips
  until `clerk-template-example` is published); ruff/mypy-strict clean. Still open
  before `verified`: publish `clerk-template-example` to run the live smoke, and a
  roadmap debrief. It is not yet pushed to its own repo (blocks T034 live run and
  real-remote use — the catalog that points at it is spec 002).

### 002 — Catalog + runtime injection  [status: planned]

- **Description:** Point clerk at user-owned source repos and present the available
  templates.
- **Outcome:** A user supplies one or more sources; the skill (with a small parsing
  helper) discovers + verifies their templates and injects the catalog at runtime.
- **Scope (in):** a catalog as a plain file/list of source repos; a
  discovery/parsing helper that statically reads each repo's `copier.yml`; catalog
  injected via `--data catalog=…` into a selector template; full-id
  (`catalog/template`) collision handling. Introduce the `Template`/`Worker` adapter
  **only if** third-party templates need `!include`/inheritance resolution static
  parsing cannot do (C-04) — decide with real templates.
- **Scope (out):** dependency ordering / multi-template execution (003).
- **Depends on:** 001.
- **Governed by:** ADR-0002/0003; C-04, C-06, C-11.

### 003 — Multi-template enablement + dependency ordering  [status: planned]

- **Description:** Select many templates and run them in correct dependency order.
- **Outcome:** clerk computes a topological order from declared edges and drives one
  copier run per template, threading answers; the order is frozen into a per-project
  reproduce recipe.
- **Scope (in):** THIS is where coordination glue is justified (C-11): read
  `when:false` `depends_on`/`run_after`/`run_before` from `copier.yml`; build the
  DAG; issue ordered `copier copy` runs, each with a distinct answers-file; thread
  answers between them; **generate the ordered reproduce recipe** so reproduce stays
  agent-free and needs no live DAG. Forward-deliver the all-gaps preflight (C-10):
  collate every question across enabled templates and `--pretend`-dry-run to report
  all missing answers at once. If the ordering logic exceeds a small helper, that is
  the evidence that justifies crystallizing a minimal tool (Q4).
- **Scope (out):** the agentic module's internal multiselect (007).
- **Depends on:** 002.
- **Governed by:** ADR-0003; C-07, C-10, C-11.

### 004 — Global per-template defaults  [status: planned]

- **Description:** Stop re-entering the same values every run.
- **Outcome:** the skill/helper pre-fills per-template defaults from a user config,
  still overridable.
- **Scope (in):** read a `~/.config/clerk` defaults file; select keys relevant to
  each template; pass as `user_defaults=` (soft) — a small helper or a documented
  skill step, whichever is simpler; optionally fold copier `settings.yml defaults:`.
- **Scope (out):** secret values (005).
- **Depends on:** 003.
- **Governed by:** ADR-0005; C-11.

### 005 — Secrets injection  [status: planned]

- **Description:** Inject secret answers per-run without persisting them.
- **Outcome:** secret questions filled from an external store at run time, never
  written to the answers file, identically at init and reproduce.
- **Scope (in):** detect secret questions (static `copier.yml` read); a thin script
  (e.g. `op read …` → `--data secret=…`) — genuinely bash-shaped; reproduce recipe
  re-fetches secrets the same way.
- **Scope (out):** store implementations beyond a first adapter.
- **Depends on:** 003.
- **Governed by:** ADR-0001 (secrets); C-05, C-11.

### 006 — Upgrade + copier migrations  [status: planned]

- **Description:** Move a generated project to a newer template version safely.
- **Outcome:** an explicit `upgrade` (announced from→to) runs `copier update` (smart
  3-way merge) and the template's version-crossing migrations.
- **Scope (in):** `copier update` invocation (a documented command/recipe, not a
  package); surface `_migrations` (update-only; version-crossing
  `self.version >= current > from`; before/after; trust-gated); enforce the NEW
  format. This is the only place local edits are respected (vs faithful reproduce).
- **Scope (out):** brownfield adoption (deferred).
- **Depends on:** 003.
- **Governed by:** ADR-0001; Constitution III, VI; C-11.

### 007 — Agentic-ecosystem module (template content)  [status: planned]

- **Description:** clerk's distinctive value — wire APM/MCP/SpecKit/ADR into
  generated projects.
- **Outcome:** a project can opt into a fully wired agentic toolchain.
- **Scope (in):** an `apm` copier **template** whose internal skills/agents/bundles/
  mcp multiselect reuses copier's own multiselect; APM install as a trust-gated
  `_task`; SpecKit bridge; steering/ADR scaffolding. This is template + task
  content, not tool code.
- **Scope (out):** base/language templates (009).
- **Depends on:** 003; likely 002.
- **Governed by:** ADR-0001/0003; C-06.

### 008 — Release + fan-out + authoring lifecycle (CI)  [status: planned]

- **Description:** Author templates in one monorepo, distribute as per-template
  read-only repos, and manage the full module lifecycle (scaffold, structure
  lint, derived catalog) beyond version bumps.
- **Outcome:** a monorepo release publishes changed templates to
  `copier-clerk/clerk-mod-*` and refreshes a generated catalog index; new modules
  are scaffolded contract-complete and the family stays structurally in-sync.
- **Scope (in):** cocogitto monorepo tags `<name>-vX.Y.Z`
  (`generate_mono_repository_global_tag=false`, `tag_prefix=v`); one CI job —
  `cog bump` → `push --follow-tags` → `git tag --points-at HEAD` → hand-rolled
  ~25-line snapshot-mirror (cp + commit + strip-prefix tag + push, skip-if-no-diff)
  → regenerate + publish `catalog.json`; direct push. **Authoring lifecycle** (see
  ADR-0006 *Authoring lifecycle*): a copier meta-template scaffolder
  (`just new-module`), a `just check-modules` contract lint (answers-file `.jinja`,
  README/CHANGELOG, directory==cog==catalog parity, label immutability) run in
  pre-commit + `pre_bump_hooks`, and a generated catalog index (`catalog.json` in
  monorepo, served via GitHub Pages). **CI identity:** an org-owned GitHub App
  ("clerk-fanout") minting short-lived tokens with `contents:write` +
  `administration:write`; the fan-out auto-creates missing `clerk-mod-*` repos
  (PAT is the documented fallback). The lint/scaffolder REUSE slice-001 discovery
  (authoring plane = consumer plane aimed inward) — all CI bash + template content,
  no new application code. Distribute the SKILL via APM marketplace; templates via
  their repos.
- **Scope (out):** history-preserving splits (rejected); a standalone catalog repo
  (rejected — index lives in the monorepo).
- **Depends on:** 001 (templates exist), 002 (catalog).
- **Governed by:** ADR-0006/0002; C-09.

### 009 — project-setup module port (templates)  [status: planned]

- **Description:** Re-home the mature ~26-module project-setup capability as copier
  templates.
- **Outcome:** the project-setup module set exists as `clerk-mod-*` templates the
  skill can drive.
- **Scope (in):** port base + languages + apm/mcp/precommit/ci/readme/justfile/etc.
  as `clerk-mod-*` templates (template content, driven by the 002/003 machinery).
- **Scope (out):** new capabilities not in project-setup.
- **Depends on:** 002, 003, 006, 008.
- **Governed by:** ADR-0002/0003/0006.
- **Notes:** a real `clerk-mod-base` module would collapse 5 project-setup base
  modules; 009 may instead ship them as separate `clerk-mod-*` repos — kept
  documented. (001 ships only `clerk-template-example`, a demo — not this module.)

### DEFERRED — Rewrite / brownfield adoption  [status: deferred]

- **Description:** Point clerk at an EXISTING project with no `.copier-answers.yml`,
  reverse-infer answers, adopt a template, and write the answers file to make it
  reproducible.
- **Outcome:** _to be defined._
- **Scope (in):** _to be defined — large, unbounded agentic inference problem; title
  captured so it is not lost, no scope committed._
- **Notes:** distinct from init/reproduce/upgrade; revisit only after 001–006 are
  solid.

## Open Questions

- **Q1 — Secret store adapters:** which store(s) does spec 005 support first (env,
  1Password, both)? Resolved when 005 is scoped.
- **Q2 — 009 base re-split:** keep `clerk-mod-base` as one template or re-split?
  Resolved when 009 is scoped.
- **Q3 — Third-party discovery fidelity:** if static `copier.yml` parsing cannot
  cover some third-party templates (`!include`/inheritance), introduce the contained
  `Template` adapter (C-04). Resolved by evidence post-002.
- **Q4 — When does coordination justify a tool?** 003's ordering/threading is the
  first real coordination code. If it exceeds a small helper (multiple modules,
  stateful), that is the evidence to crystallize a minimal, single-purpose tool —
  built then, with evidence, not speculatively (C-11). Resolved during 003.

## Cross-Cutting Notes

- **Glue-only-when-copier-cannot (C-11):** the default answer to "should this be
  code?" is no — prefer a copier invocation, a template feature, or a documented
  skill step. Code appears for coordination copier lacks.
- **Reproduce is frozen, not recomputed:** multi-template order is baked into a
  per-project reproduce recipe at generation, keeping reproduce deterministic and
  agent-free without shipping a DAG engine to consumers.
- **Distribution:** the SKILL ships via the APM marketplace; templates via their
  own repos + the catalog index. There is no PyPI `clerk` package to publish.

---

**Version**: 2.0.0 | **Ratified**: 2026-07-09 | **Last Amended**: 2026-07-09
