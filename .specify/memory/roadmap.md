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
  multi-template projects the order is **recomputed at reproduce time** from the
  committed answers + pinned template fetches (stable tie-break), never frozen into
  a committed recipe (see [[spec 010]] + Constitution III).
- Users bring **their own template catalog**; clerk depends on no first-party hub.
- clerk's distinctive value is the **agentic-ecosystem wiring** (APM / MCP /
  SpecKit / ADR), delivered as template content, not tool code.

## Constraints & Decisions

- **C-01 — clerk = skills + templates + minimal glue (not a tool):** the durable
  artifacts are the `SKILL.md` conductor, the `clerk-mod-*` templates, and small
  deterministic glue bundled as a single script `scripts/clerk.py` (ordering, edge
  parsing, discovery, defaults, dry-run validation) run `./scripts/clerk.py` / `uv
  run scripts/clerk.py`. No published application, no `[project.scripts] clerk`
  console entry. _See Constitution I; supersedes the earlier tool framing in
  ADR-0001 and the "reproduce-recipe generation" glue item (order is recomputed —
  spec 010)._
- **C-02 — Two-phase boundary:** skill authors a frozen, documented inputs handoff;
  the deterministic phase executes with zero LLM. Testable without an LLM. _See
  Constitution II._
- **C-03 — Faithful reproduce, distinct upgrade:** `recopy --vcs-ref=:current:`;
  bare recopy (silent upgrade) never exposed; `update` is the explicit upgrade;
  multi-template reproduce order **recomputed at reproduce time** from committed
  answers + pinned fetches (stable tie-break), not frozen into the project. _See
  ADR-0001, Constitution III, [[spec 010]]._
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

### 001 — Single-template vertical slice  [status: verified]

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
  until `clerk-template-example` is published); ruff/mypy-strict clean.
- **Verified 2026-07-10:** `clerk-template-example` published to its own repo
  (`copier-clerk/clerk-template-example`, tagged `v1.0.0`); the live network smoke
  test passes against it — the full discover→init→reproduce loop confirmed against
  a real remote, not just local fixtures. (Automated authoring/fan-out is 008; the
  catalog that points at published templates is 002.)
- **Follow-up (delivery reshape, next spec):** drop the `clerk` console script +
  generated justfile; bundle the deterministic wrappers (discover/init/reproduce/
  update) as skill scripts invoked via a portable skill, keeping clerk a pure
  copier wrapper (C-01). Multi-template reproduce recomputes the order at runtime
  from the committed answers files (pinned commits → identical edges → stable
  topo-sort), so nothing clerk-specific need be committed to a project. Deps stay
  in each template's `copier.yml` (versioned); no catalog dep-cache.

### 002 — Catalog + runtime injection  [status: implemented]

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
- **Completed 2026-07-10** (branch `002-catalog`): catalog = user-owned TOML
  (`~/.config/clerk/catalog.toml`, overridable via `CLERK_CATALOG_PATH` or
  `--catalog PATH`) managed by `scripts/clerk.py catalog` verbs (`init`, `add`,
  `remove`, `list`, `refresh`, `validate`). Discovery is deterministic and
  LLM-free (reuses `src/clerk/discovery.py`; no template code executed). Templates
  identified by full-id `<catalog>/<template>`; `catalog validate` is the
  selection gate (exit 0 = valid; non-zero = unknown/ambiguous). ADR-0003's
  two-template meta-flow (repos-collector template + selector template) superseded:
  replaced by the plain catalog file + agent presentation + `validate` gate. The
  `--data catalog=[…]` render-scope fact is retained for spec 007's apm module.
  No clerk artifact written into generated projects (010 invariant holds). The
  `SKILL.md` documents the catalog-manage → list → pick → validate → init flow.

### 003 — Multi-template enablement + dependency ordering  [status: implemented]

- **Description:** Select many templates and run them in correct dependency order.
- **Outcome:** clerk computes a topological order from declared edges and drives one
  copier run per template, threading answers; at reproduce the order is **recomputed**
  from the committed answers + pinned fetches (stable tie-break), not frozen into a
  committed recipe (see [[spec 010]]).
- **Scope (in):** THIS is where coordination glue is justified (C-11): read
  `when:false` `depends_on`/`run_after`/`run_before` from `copier.yml`; build the
  DAG; issue ordered `copier copy` runs, each with a distinct answers-file; thread
  answers between them. **Reproduce recomputes the order at runtime** from the
  committed answers files + pinned template fetches with a stable tie-break (per
  [[spec 010]]) — NOT a frozen recipe file committed to the project (this supersedes
  the earlier "generate the ordered reproduce recipe" framing). Forward-deliver the
  all-gaps preflight (C-10): collate every question across enabled templates and
  `--pretend`-dry-run to report all missing answers at once. The orchestrator ships
  bundled with the skill, not as a CLI (spec 010).
- **Scope (out):** the agentic module's internal multiselect (007); a
  project-committed clerk recipe/DAG artifact (rejected — spec 010).
- **Depends on:** 002; delivery contract from 010.
- **Governed by:** ADR-0003; C-07, C-10, C-11; spec 010.
- **Completed 2026-07-10** (branch `003-multi-template`, merged into main):
  `src/clerk/ordering.py` — DAG build from `depends_on`/`run_after`/`run_before`
  edges; topo-sort with stable tie-break by **basename** (basename is the portable
  edge identity inside `copier.yml`; consistent between init and reproduce, which
  reconstructs synthetic `_recorded/<basename>` full-ids); `OrderingError` on cycle,
  dangling edge, or basename collision. `runner.init_many` threads answers via
  `data=` (ADR-0003); `runner.reproduce_many` recomputes order from committed
  `.copier-answers*.yml` + pinned template fetches — no recipe file read or written.
  All-gaps preflight: `--check` collates errors across all layers in one pass.
  N=1 unchanged (uniform loop, spec 010). Q-004 resolved: ordering glue is a small
  helper (one module, pure functions); no crystallized tool needed.

### 004 — Global per-template defaults  [status: implemented]

- **Description:** Stop re-entering the same values every run.
- **Outcome (implemented):** `src/clerk/defaults.py` loads `~/.config/clerk/defaults.yml`
  (YAML, `yaml.safe_load`; env-overridable via `CLERK_DEFAULTS_PATH`); selects keys
  relevant to each template's questions (excluding secrets + `when:false` edges);
  passes as `user_defaults=` (soft default — still overridable). `runner.init` and
  `runner.init_many` each use it: load+fold once per call, select per-layer. Optional
  best-effort fold of copier `settings.yml defaults:` as lower-priority fallback.
  `DefaultsError(ClerkError)` added to `errors.py`. SKILL.md documents the feature.
- **Scope (out):** secret values (005); template-specific sections (YAGNI).
- **Depends on:** 003.
- **Governed by:** ADR-0005 (file is YAML, aligned — no deviation); C-11.

### 005 — Secrets policy + guardrail  [status: implemented]

- **Description:** Handle secrets by POLICY, not a store engine. clerk-authored
  templates avoid `secret: true` questions entirely; the phase-1 agent never
  collects a credential; clerk depends on no secret store.
- **Outcome (implemented):** (a) policy lint test over in-repo templates
  (SC-001); (b) SKILL guardrail documenting out-of-band supply (SC-002);
  (c) `runner.init` + `runner.init_many` mechanically reject a secret key in any
  run-spec on both single and multi-layer paths (`SecretInAnswersError`, SC-003a);
  (d) `discovery` parses both `secret: true` per-question AND `_secret_questions`
  list form (SC-003b); (e) fail-loud on required-secret-no-value in non-interactive
  mode (SC-003c); (f) copier error messages are redacted of any secret values
  (SC-003 / FR-004); (g) `.env.example.jinja` runtime-secret pattern added to the
  example template (SC-005). Roadmap's `op read → --data secret=` store-inject
  model is **superseded** by this policy.
- **Scope (out):** secret-injection engine, resolver chain, store adapters.
  Q1 (which store first) resolves to **none** under this policy — escalation is
  evidence-gated (FR-007 / C-11).
- **Depends on:** 003 (multi-layer path covered).
- **Governed by:** ADR-0001 (secrets); C-05, C-11; Constitution II, V.

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

### 008 — Skill packaging: installable via Claude + Codex APM marketplaces  [status: implemented]

- **Description:** Make the clerk skill installable into any macOS/Linux/WSL project
  via APM, using APM's own tooling (`apm pack` / `apm publish` / `apm marketplace`).
  Solves portability: the package vendors `src/clerk/*` (no PyPI `clerk`) and checks
  its deps (no assumed package manager).
- **Outcome:** A developer can `apm marketplace add copier-clerk/clerk`, `apm install
  clerk`, and drive copier from their own project with the bundled `scripts/clerk.py`.
  Both a Claude (`.claude-plugin/marketplace.json`) and a Codex
  (`.agents/plugins/marketplace.json`) marketplace are built from one `apm.yml` config.
  Dep preflight with environment-aware install suggestion (uv/pipx/pip; brew for copier
  only). `clerk doctor` for explicit readiness check. Release sequence is documented
  and gated (`apm pack --check-versions --check-clean`).
- **Scope (in):** `apm.yml` `marketplace:` block (claude+codex outputs, `category:
  Productivity`); `packages/clerk/` local-source package layout; `src/clerk/_preflight.py`
  (stdlib-only dep check + version pin + environment-aware suggestion); dual-mode
  `sys.path` shim in `scripts/clerk.py` (BLOCKER-1 fix); PEP 723 header (FR-005);
  `doctor` verb; `just vendor`/`check-vendor`/`pack`/`release` recipes (BLOCKER-2 fix);
  CI `pack.yml` gate; portable SKILL.md update; README `## Install` section; roadmap
  split.
- **Scope (out):** fan-out/authoring-lifecycle CI (deferred — see spec 008b below).
  No cocogitto, no catalog.json generation, no GitHub App, no `just new-module` /
  `check-modules`. No `apm publish` to registry (deferred until `registries` feature
  is stable — Q-008b).
- **Completed 2026-07-12** (branch `008-packaging`): all T001–T015 done; 51 new tests
  (34 unit preflight + 17 packaging structural); ruff/mypy-strict clean; full suite
  green. `apm pack` dry-run + validate: deferred — `apm` not installed in CI; marked
  to skip cleanly. Install smoke (T011a): marked `network`, deferred for CI with
  `apm` + network access.
- **Depends on:** 001, 002, 003, 010.
- **Governed by:** Constitution I, II; ADR-0006; spec 010; C-01, C-11.

### 008b — Fan-out + authoring lifecycle (CI)  [status: planned]

- **Description:** Author templates in one monorepo, distribute as per-template
  read-only repos, and manage the full module lifecycle (scaffold, structure
  lint, derived catalog) beyond version bumps. Deferred from spec 008 — no
  `clerk-mod-*` templates exist to fan out until spec 009 (C-11: no speculative
  machinery).
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
  no new application code.
- **Scope (out):** history-preserving splits (rejected); a standalone catalog repo
  (rejected — index lives in the monorepo).
- **Depends on:** 008 (skill packaging), 009 (real clerk-mod-* templates exist).
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

### 010 — Delivery reshape: skill-bundled copier wrapper  [status: implemented]

- **Description:** Reshape clerk's delivery so it is a **pure copier wrapper bundled
  in a portable skill** with **zero clerk-specific artifact committed into generated
  projects** — correcting the transitional CLI/justfile shape 001 shipped to prove
  the loop. Cross-cutting: specs 002–009 must honor it.
- **Outcome:** no `clerk` console script and no generated justfile; deterministic
  helpers ship as the bundled `scripts/clerk.py` invoked via `uv run scripts/clerk.py`;
  a generated project reproduces with **copier alone** (no clerk, no `just`) from its
  committed answers files; multi-template reproduce **recomputes** order at runtime
  from committed answers + pinned template fetches (stable tie-break), never a frozen
  recipe.
- **Scope (in):** drop `[project.scripts] clerk` + justfile generation; bundle
  discover/init/reproduce/check + the multi-template orchestrator with the skill;
  reproduce/update as **portable skills** (semantic auto-trigger), not slash commands;
  document the copier-only reproduce fallback; adapt (not weaken) 001's tests.
- **Scope (out):** the ordering algorithm itself (003 — this spec fixes the
  reproduce-time recompute *contract* it must satisfy); catalog (002); migrations (006).
- **Key contracts for other specs:** deps stay in `copier.yml` (versioned), NOT the
  catalog, no dep-cache (002/003/008); reproduce recomputes from pins, changed deps
  are an `update` concern only (003/006); everything is skill-bundled, no CLI
  (all); distribution = skill via APM + templates via repos (008).
- **Depends on:** 001 (verified). Informs/precedes 002–009.
- **Governed by:** Constitution I/II/III/V/VIII; ADR-0001/0002/0003/0006; C-01, C-02,
  C-11. **Open:** Q-010a (skill namespace `clerk` vs `project-setup:*` — resolve at
  009), Q-010c (answers-file naming for multi-template — resolve at 003).
- **Completed 2026-07-10** (branch `010-delivery-reshape`): delivery contract realized —
  `scripts/clerk.py` is the single bundled entrypoint (discover/trust/init/reproduce);
  `[project.scripts] clerk` removed; justfile generation removed; `cli.py` deleted;
  SKILL.md, try-clerk.sh, and README updated to the bundled-script surface; copier-only
  fallback documented. The reproduce-time recompute contract (FR-004) is fixed here;
  the N>1 ordering implementation is spec 003.

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
  1Password, both)? **Resolved (005):** none — the policy supersedes store
  injection. Escalation is evidence-gated; if a concrete template proves a
  scaffold-time secret is unavoidable, spec a mechanism then (FR-007).
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
- **Reproduce recomputes, deterministically, from committed state (superseded the
  earlier "frozen recipe" note — see [[spec 010]]):** multi-template order is
  recomputed at reproduce from the committed `.copier-answers*.yml` + each template
  fetched at its pinned `_commit`, topo-sorted with a stable tie-break. Pinned
  commits → identical edges → identical order, so it is deterministic and agent-free
  **without** committing any clerk-specific recipe/DAG file into the project (which
  the user could forget to commit). Changed deps are picked up only at `update`.
- **No clerk artifact in generated projects:** the committed copier answers files are
  the entire reproduce state; a project reproduces with copier alone (no clerk, no
  `just`). No generated justfile, no frozen recipe (spec 010).
- **Distribution:** the SKILL (with its bundled deterministic scripts) ships via the
  APM marketplace; templates via their own repos + the catalog index. There is no
  PyPI `clerk` package and no `clerk` console script to publish (C-01, spec 010).

---

**Version**: 2.1.0 | **Ratified**: 2026-07-09 | **Last Amended**: 2026-07-10
