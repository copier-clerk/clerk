# 0001 — copier is the deterministic engine; bailiff is the agentic conductor

- Status: accepted
- Date: 2026-07-09

## Context

`bailiff` grew out of `project-setup`, a bespoke, stdlib-only, deterministic
scaffolding runner (frozen plan, canonical JSON, hand-rolled TOML emitter,
git-fetched modules, reproduce-from-answers). A formal debate (6 code-grounded
research angles + adversarial challenge; see
`project-setup/research/debate-copier-vs-bespoke-engine.md`) established that the
bespoke engine's determinism goal was ~80% already met, and that migrating to
copier would *relocate* rather than remove the hard problems.

The owner nonetheless chose to build on copier: effort is explicitly **not** the
optimization metric, and copier has already solved the deterministic
render + reproduce + git-ref-pinning problem that the bespoke runner re-invents.
The value bailiff adds is the layer copier structurally lacks — an agentic
conductor.

## Decision

- **copier is the engine.** It owns deterministic rendering, the committed
  answers file, git-ref-pinned remote templates, and the reproduce/update cycle.
- **bailiff is a thin agentic conductor on top.** It owns: an init-time agent that
  selects modules and authors answers (the *inputs*); a thin orchestrator for
  multi-module enablement + topological ordering; and the agentic-ecosystem
  wiring copier has no concept of (APM / MCP / SpecKit / ADR).
- **bailiff imports copier as a pinned library dependency and calls its Python
  API in-process** — `run_copy` / `run_recopy` / `run_update`. These three are
  copier's verified stable public surface (`copier/__init__.py` `__all__`; every
  other member emits a DeprecationWarning on access). The API takes answers as a
  plain `data=` dict (no YAML temp file, no shell-quoting; `--data-file` has no
  API equivalent) and raises a typed `CopierError` hierarchy instead of integer
  exit codes. "Never vendored" is re-scoped: **do not inline copier source into
  bailiff's tree; a declared, pinned dependency is the intended composition.** So
  `uvx bailiff` transitively resolves the pinned copier — no separate `uvx copier`
  whose version would drift independently. Shelling to the CLI is retained only
  as a fallback escape hatch.
- **Trust is configured, not blanket-flagged.** bailiff does NOT default
  `unsafe=True`. Instead users add a `trust:` list to copier's `settings.yml`
  (verified path via platformdirs on macOS: `~/.config/copier/settings.yml` —
  NOT `~/Library/Application Support/...`; override with `COPIER_SETTINGS_PATH`),
  passed to the API via the `settings` param. Trailing-slash entries match as **prefixes** (trust
  all templates under an org path, e.g. `- https://github.com/your-org/`);
  no-slash entries match **exactly**. This bounds trust by source, cleaner than
  a per-invocation catchall.
  - Trust gates ALL of `_tasks`, `migrations`, AND `_jinja_extensions`. So a
    trusted location **is the sanctioned enabler for tasks/migrations to run** —
    a template under a trusted prefix fires its `_tasks` (and migrations, on
    update) with no `unsafe=True` needed. This is the primary mechanism by which
    bailiff's task-bearing modules (`specify init`, `apm install`, …) execute at
    init AND reproduce. `unsafe=True` is NOT the normal path for tasks.
  - `unsafe=True` is reserved for the one narrow case a trusted location does not
    cover: a template whose `_external_data` paths traverse **outside** the
    destination directory (per-template opt-in in the catalog entry, never
    global).
  - **Trust matching (VERIFIED, `_settings.py:135-149`): NO wildcards/globs (yet).**
    Two branches only — entry ending `/` → prefix (`startswith`); else exact
    (`==`). A literal `*` is just a character. Both grains are supported and fine:
    - **Org prefix (one entry, recommended):**
      `trust: ["https://github.com/bailiff-io/"]` — the trailing slash makes it
      a prefix that covers every `bailiff-io/bailiff-mod-*` repo in a single line.
    - **Per-repo exact (also fine):** list each
      `https://github.com/bailiff-io/bailiff-mod-lang-python` (no trailing slash →
      exact). More entries, tighter scope; a legitimate choice.
    - If copier ever adds glob/pattern support, revisit to allow a single
      `.../bailiff-io/bailiff-mod-*` style entry. Not available today.
  - **CONTRACT — trust matches the RAW url bailiff passes, before `gh:`→`https`
    expansion** (the shortcut expands only at clone time; the trust check never
    sees the expanded form). Therefore **bailiff MUST invoke copier with fully
    expanded `https://github.com/bailiff-io/<repo>.git` URLs**, and its "add
    source to trust" onboarding MUST write the matching
    `https://github.com/bailiff-io/` prefix (or the exact per-repo url) derived
    from that same form. A `gh:` trust entry will NOT match an https invocation
    and vice-versa — mismatched forms make trust silently fail.
  - Trust governs the Python API identically: `run_copy(settings=...)`, or
    `SettingsModel.from_file()` when `settings` is omitted. `unsafe=True` is the
    only bypass.
- **`_tasks` run in BOTH init and reproduce** — needed for `specify init`,
  `apm install`, etc. VERIFIED: `run_recopy` delegates to `run_copy` internally,
  which fires `_tasks`. Migrations are **update-only** and out of scope for
  reproduce.
- **The reproduce invariant is "no AGENT", NOT "no side effects".** Reproduce
  (`copier recopy` directly, or via the skill's bundled `scripts/bailiff.py`
  orchestrator for multi-template projects, run by a human or CI — never a
  generated `just reproduce`, dropped by spec 010) replays the committed answers
  and DOES run tasks, but no LLM/agent participates. Reproduce
  is therefore **process-deterministic** (same frozen answers + same pinned
  refs → same commands executed), **not** output-byte-deterministic — tasks like
  `apm install` touch network/external state.
- **Reproduce uses `run_recopy` WITH an explicit `vcs_ref`.** VERIFIED against
  source: bare `run_recopy()` (no `vcs_ref`) resolves the LATEST tag and silently
  upgrades — it does NOT auto-replay the recorded `_commit`. To reproduce the
  original version faithfully bailiff MUST pass `vcs_ref=VcsRef.CURRENT` (which
  reads the `_commit` from the committed answers file) or the literal
  `vcs_ref=answers["_commit"]`. `recopy` fires tasks; `update` does the smart
  3-way merge, which assumes prompt-captured answers — wrong for agent-authored
  ones, so it is reserved for intentional upgrades. Note: `_copier_operation` is
  `'copy'` for BOTH first copy and recopy, so a task cannot distinguish them via
  that variable — gate first-run-only work with a `when:` condition or a sentinel
  file instead.
- **Three operations, three version behaviors** (all source-verified):
  `run_copy` (init) → latest tag (or optional explicit `vcs_ref`); `run_recopy`
  (faithful reproduce) → `vcs_ref=VcsRef.CURRENT` (recorded `_commit`, no drift);
  `run_update` (intentional upgrade) → FROM `_commit` → TO latest. This preserves
  copier's living-template model for init/upgrade while keeping reproduce exact.
- **Secrets are injected per-invocation, never persisted.** Secret questions
  (`secret: true` / `_secret_questions`) are NOT written to `.copier-answers.yml`.
  bailiff inspects `Template.secret_questions` before running, fetches the values
  from an external store (env var / 1Password / etc.), and passes them via
  `data={...}`. This works identically at init and reproduce and keeps secrets
  off disk.

## Constraint — determinism discipline

Because tasks run at reproduce, byte-identity holds only as far as pins hold.
Everything a task consumes MUST be pinned: module `#ref` (tag or sha), `apm.lock`,
and tool versions (incl. the copier version, `copier>=9.16,<10`). Unpinned inputs
make reproduce drift; this is the accepted bargain for supporting `_tasks`.

## Consequences

- Strict "stdlib-only" is given up (copier pulls jinja2, pydantic v2,
  questionary, plumbum, …), accepted because it is a declared pinned dependency,
  not inlined source.
- Determinism now rides on copier + Jinja + the pinned task inputs rather than a
  hand-rolled canonical serializer. See the determinism-discipline constraint
  above.
- The `recopy`-fires-tasks assumption is CONFIRMED against source (was an open
  verification); reproduce correctly re-runs `_tasks`.
- copier's own task execution uses **plumbum**, not pyinvoke; pyinvoke is
  irrelevant to the integration (and unneeded for bailiff's orchestrator until a
  second consumer exists — YAGNI).
- The agentic layer (APM/MCP/SpecKit) has no off-the-shelf analog and stays
  bespoke — this is bailiff's distinctive value.
- Rendering-behavior kwargs (`defaults`/`overwrite`/`quiet`/`exclude`/
  `skip_if_exists`) and jinja-extension policy are recorded separately in
  [[0004-rendering-and-extensions]].

## Related

- Supersedes the "harden the bespoke runner" path for this project.
- See [[0002-catalog-and-answer-model]] and
  [[0003-selector-template-and-runtime-injection]].
