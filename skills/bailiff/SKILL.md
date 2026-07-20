---
name: bailiff
description: Conduct copier to scaffold a reproducible project from a template. Use when the user wants to generate/scaffold a project from a copier template, "run bailiff", init a project from a bailiff-mod-* template, or set one up interactively. Portable (macOS/Linux/WSL) — the deterministic steps run via `uvx bailiff` (the PyPI CLI). Phase-1 only — you author the inputs; copier (driven by the `bailiff` CLI) does all rendering, and reproduce is agent-free.
---

# bailiff — conduct copier

You are the **phase-1 conductor**. copier is a deterministic scaffolding engine;
the `bailiff` CLI is a thin published tool over copier's public API. Your job is
to inspect a template, help the user answer its questions, obtain trust consent, and
hand a frozen **run-spec** to the deterministic phase (`uvx bailiff init`). You
author *inputs only*.

**The two-phase boundary — do not cross it:**

- You (the agent) run in phase 1: discover → present questions → collect answers →
  explain + obtain trust consent → write the run-spec → dry-run → generate.
- Everything after the run-spec is deterministic and LLM-free. **You are NEVER in
  the reproduce path** — reproduce replays committed answers at the recorded commit
  with no agent (`uvx bailiff reproduce`). Never offer to "reproduce
  it for them" by re-authoring answers; point them at `uvx bailiff reproduce`.

## Prerequisites

- **Platform:** macOS, Linux, or WSL on Windows.
- `git` on PATH.
- The example template's LICENSE task needs `gh` authenticated (`gh auth status`).
- the `bailiff` CLI is the tool on PyPI — no script is bundled with the skill.
  Invoke it as:

  ```sh
  uvx bailiff <verb> …          # ephemeral env; nothing to install
  # repo contributors (editable install):
  uv run bailiff <verb> …
  ```

- **Dependencies** ship with the wheel (`uvx` resolves them automatically). The
  CLI still checks them at startup and prints an environment-aware install
  suggestion if the environment is broken — no traceback. Run
  `uvx bailiff doctor` for an explicit readiness check (exit 0 = ready; exit 4
  = issues).

## User defaults (spec 004)

bailiff pre-fills copier's soft-default prompt values from a YAML file at
`~/.config/bailiff/defaults.yml` (overridable via `BAILIFF_DEFAULTS_PATH`). It is a
flat `question_key: value` mapping — no sections, no nesting. Keys absent from
the current template's questions are silently ignored (one file works across many
templates). Secret questions (`secret: true`) are never pre-filled. The file is
user-side config only — it is never written into the generated project. See
`specs/004-defaults/contracts/defaults.md` for the full contract.

## Procedure

### 0. Catalog: ensure, list, pick, validate

> **When this step applies:** whenever the user wants to scaffold from their own
> template library, or does not yet have a specific `<source>` URL in hand. If the
> user names a concrete URL/path directly, skip to step 1.

Discovery and validation (sub-steps 0-a through 0-c) are **LLM-free and
deterministic** — the `bailiff` CLI drives them. The **pick** (0-b) is your
judgment per Constitution II: you present the listing and collect the user's
choice; you do not guess or auto-select without showing the options first.

**0-a. Ensure the catalog exists and contains the user's sources.**

Check whether a catalog already exists:

```sh
uvx bailiff catalog [--catalog PATH] list
```

If the file is absent or empty, create it and populate it:

```sh
# Create the catalog file if absent (idempotent — no-op if it already exists):
uvx bailiff catalog [--catalog PATH] init [--name <pointer-name>]

# Add each source the user names (idempotent — duplicate adds are a no-op):
uvx bailiff catalog [--catalog PATH] add <source> [--name <pointer-name>]
```

`<source>` is a `gituser/gitrepo` locator or a local path; an optional `@ref`
suffix overrides the display version (`acme/my-template@v2.1.0`). `--name` sets
the catalog-pointer namespace that appears as the `<catalog>` prefix in full-ids.
You manage this file on behalf of the user — never ask them to hand-edit it.

**0-b. Present the verified listing and collect the user's pick.**

```sh
uvx bailiff catalog [--catalog PATH] list
```

The listing is **deterministic** (same sources at same pins → identical output
every run). Each usable template shows its `full_id` (`<catalog>/<template>`),
available versions, the `reproducible` flag, and a questions summary. Unusable
sources (no PEP 440 tag, bad `copier.yml`, unreachable) are reported per-source
with a reason; the rest of the catalog still lists — one bad source is not a
whole failure.

Show the user the usable entries. Ask which one they want. The user's choice is
authoritative — do not substitute your own preference.

For the machine-readable shape (useful when scripting or comparing runs):

```sh
uvx bailiff catalog [--catalog PATH] list --json
```

See `specs/002-catalog/contracts/catalog.md` for the exact JSON shape, full-id
semantics, exit codes, and the `unusable` structure.

**0-c. Validate the chosen full-id before proceeding.**

```sh
uvx bailiff catalog [--catalog PATH] validate <full-id>
```

Exit 0 → the id is valid; extract the resolved `source` and `ref` from the
listing and hand them to step 1 in place of an inline `<source>`.
Non-zero → the id is unknown or ambiguous; the error message lists valid ids.
Present the error to the user and loop back to 0-b.

`validate` is a mechanical gate with no LLM judgment. It refuses:
- unknown ids (naming the valid ones in the error message);
- ambiguous bare names that match more than one catalog pointer (requiring the
  full `<catalog>/<template>` form).

---

### 1. Inspect the template (no trust needed)

```sh
uvx bailiff discover <source> [--ref REF]
```

`<source>` is a fetchable locator — an expanded `https://` URL or a local path.
This prints static JSON (see `contracts/discovery-output.md`); it runs **no**
template code, so it is safe against an untrusted source. From the output, note:

- `reproducible` — if `false`, **stop**: the template ships no answers-file
  template, so a generated project could never be reproduced. `init` will refuse
  it. Tell the user; do not try to work around it.
- `questions` — what you must collect (with `type`, `choices`, `default_raw`,
  `help`, `validator`, `secret`).
- `has_tasks` / `jinja_extensions` — non-empty means the template executes code,
  so trust will be required (step 3).
- `versions` — the available PEP 440 tags; the latest is used unless the user pins.

### 2. Present the questions and collect answers

Show the user each visible question with its help text, type, choices, and
default. Collect a value for each required question. Respect `validator`/`choices`
so the values are valid. **Do not** set `today` — the script injects the generation
date itself. Treat `secret: true` answers as sensitive (see step 4).

### 3. Explain trust, then obtain explicit consent (only if the template takes actions)

If `has_tasks` or `jinja_extensions` is non-empty, the template **executes code**
on the user's machine at generation (and again at reproduce). Before recording
trust, explain this plainly: *"This template runs commands (its `_tasks` / jinja
extensions) — that is arbitrary code execution from `<source>`. Trusting it lets
those run. Only trust sources you control or have reviewed."* Obtain an explicit
yes. Then, and only then:

```sh
uvx bailiff trust add <prefix>
# or, to record the owner-path prefix covering a whole org:
uvx bailiff trust add --from-source <source>
```

If you skip this, `init` refuses with exit 3 and prints the exact
`bailiff trust add` command — that refusal is the safety gate working,
not an error to route around. Never auto-trust; consent is the user's, per turn.

### 4. Author the run-spec — and handle secret questions

Write a run-spec file (JSON/YAML) per
`specs/001-bailiff-vertical-slice/contracts/answers-doc.md`:

```yaml
source: "<source>"
ref: "<optional pin>"
dest: "<destination dir>"
answers:
  <key>: <value>
```

Omit `today` (the script injects it).

**Secrets — do NOT collect, do NOT put in the run-spec (spec 005):**

If discovery reports any key in `secret_questions` (for a third-party template):

- **NEVER ask the user for the value.** Never place it in the run-spec or in any
  field you author. A secret must not enter the LLM context (Constitution II).
- **Explain the situation** and direct **out-of-band supply**:
  - copier's own **masked interactive prompt** at the deterministic step (the
    human types it directly into copier, not to you), OR
  - an environment mechanism the user controls.
- **If the run is non-interactive (reproduce/CI):** a required secret with no
  value supplied **fails loud** naming the question — bailiff does NOT silently
  render copier's placeholder default (Constitution V). The user must supply the
  real value out-of-band before reproducing.
- **bailiff enforces this mechanically.** `uvx bailiff init` rejects any
  run-spec that supplies a value for a discovery-flagged secret key — fail loud,
  naming the key — regardless of what you put in the run-spec. Do not try to
  work around this; it is the security boundary.
- bailiff-authored templates (`bailiff-mod-*`) avoid `secret: true` questions
  entirely; if you encounter one it is a third-party template. See
  `specs/005-secrets/contracts/secrets.md` for the full policy.

Secrets and hidden `when:false` edges are never written to the recorded answers
regardless (copier's own behavior).

### 5. Dry-run, then generate

```sh
uvx bailiff init --run-spec <file> --check   # validates via copier's dry run; writes nothing
uvx bailiff init --run-spec <file>           # generates the project
```

`--check` surfaces missing/invalid answers (and any trust refusal) without writing.
Fix anything it reports, then run the real `init`. On success, the project has
rendered files, an initialized git repo, and a `.copier-answers.yml` recording
`_src_path` + `_commit` + answers. **No bailiff-specific file is written** — the
`.copier-answers.yml` is the entire reproduce state.

---

### Multi-template flow (spec 003) — N≥2 layers in dependency order

> **When this applies:** the user selects more than one template from the catalog
> (e.g. a `bailiff-mod-base` + a language layer). N=1 is the degenerate case of this
> flow — behavior is identical to the steps above.

**Your judgment (phase 1):** collect a validated selection (≥1 full-ids from step 0)
and per-layer answers. You author the run-spec; ordering, apply, and reproduce are
LLM-free (Constitution II).

#### 5a. Author the multi-template run-spec

Write a run-spec with the `selection` shape (instead of the single-template `source`
field). List all selected layers with their resolved `source`/`ref` (from step 0-c)
and per-layer answers. `today` is still injected by bailiff — omit it:

```yaml
dest: "./my-project"
selection:
  - full_id: "demo/bailiff-mod-base"
    source: "https://github.com/bailiff-io/bailiff-mod-base.git"
    ref: "v1.2.0"          # optional pin; omit for latest
    answers:
      project_name: acme
      license: MIT
  - full_id: "demo/bailiff-mod-python"
    source: "https://github.com/bailiff-io/bailiff-mod-python.git"
    ref: null
    answers:
      python_version: "3.12"
```

Input order within `selection` does not affect the output — bailiff reorders
layers by dependency. See `specs/003-multi-template/contracts/ordering.md` for
the exact run-spec shape, edge semantics, and exit codes.

#### 5b. Preflight, then generate

```sh
uvx bailiff init --run-spec <file> --check   # all-gaps preflight: all layers, writes nothing
uvx bailiff init --run-spec <file>           # apply layers in dependency order
```

**How bailiff orders and applies layers (LLM-free):**

1. Reads each layer's `copier.yml` statically for `depends_on` edges and
   `_external_data` aliases (both are hidden `when:false` answers / top-level
   keys, already parsed by discovery). `run_after` and `run_before` are not used
   in spec 014+ modules.
2. Builds a directed graph and refuses before any write if it finds:
   - a **cycle** (names the cycle members — exit 1);
   - a **dangling edge** (a dependency not in the selection — exit 1, names it);
   - a **basename collision** (two layers with the same repo basename would overwrite
     each other's answers file — exit 1, names the basename).
3. Sorts by phase (pre → normal → post), then topologically within each phase,
   with a **stable tie-break: lexicographic by template basename** — deterministic
   across runs and across init/reproduce.
4. Applies one `copier copy` per layer in that order. Cross-module facts flow via
   copier `_external_data` aliases (always-present producers) or via agent-frozen
   `--data` answers (sometimes-absent producers — see §cross-module facts below).
5. After the render loop, runs each layer's `_post_tasks` in `depends_on` order.
6. Each layer commits its own `.copier-answers.<basename>.yml` recording its
   `_src_path` + `_commit`. bailiff appends `_bailiff_schema: 014` to each file.
   **No bailiff-authored order or recipe file is committed.**

`--check` (all-gaps preflight) runs all layers with `pretend=True`, collects every
missing or invalid answer across all layers, and reports them in one pass — it never
stops at the first failing layer.

On success, the project has one committed `.copier-answers.<basename>.yml` per
layer. Those files are the entire reproduce state.

#### Reproduce (recomputed, not frozen)

```sh
uvx bailiff reproduce <project-dir>
```

bailiff enumerates the committed `.copier-answers*.yml` files, fetches each template
at its recorded `_commit`, re-reads the edges, rebuilds the DAG, and topo-sorts with
the same stable tie-break — **recomputing** the order from committed state, never
reading a frozen recipe. Pinned commits → identical edges → identical order, so
reproduce is deterministic and agent-free.

**Copier-only-by-hand fallback** (no bailiff required):

```sh
# For each .copier-answers.<name>.yml in the recomputed dependency order:
cd <project-dir>
copier recopy --vcs-ref=:current: --defaults --overwrite -a .copier-answers.<name>.yml
```

The recomputed order is derivable by hand from the same committed `when:false` edges;
nothing about the project *requires* bailiff to reproduce.

---

### 6. Hand off

Tell the user the project is generated and how to reproduce it **without you**:

> Reproduce anytime with:
>
> ```sh
> # via the bailiff CLI (primary path — ergonomics over copier):
> uvx bailiff reproduce <project-dir>
>
> # copier-only fallback (no bailiff, no just — works anywhere copier is installed):
> cd <project-dir> && copier recopy --vcs-ref=:current: --defaults --overwrite
> # multi-template: repeat with -a <each .copier-answers*.yml> in dependency order
> ```
>
> Both paths replay the recorded answers at the recorded version — no agent involved.

Your job ends here. Do not re-run generation as a substitute for reproduce, and
do not edit `.copier-answers.yml` by hand (copier forbids it; reproduce/upgrade
rely on it being copier-authored).

## The `bailiff-mod-*` module family (spec 009 / 014)

`bailiff-mod-*` are the first-party template modules, fanned out to
`bailiff-io/bailiff-mod-<name>`. They are ordinary bailiff layers — discover →
trust → init → reproduce works exactly as above. Modules follow the spec 014
fragment/merge model: each module writes only its own fragment into the relevant
`.d/` directory; combined output files are produced by native merges or `_post_tasks`.

**Key modules:**

- **`bailiff-mod-base`** — the identity root of every project (`_bailiff_phase: pre`).
  Asks identity questions (`project_name`, `org`, `description`, `layout`,
  `default_branch`, and the 13-SPDX `license`). Renders the directory scaffold
  + a seed-once `AGENTS.md`. Trust-gated tasks generate `.gitignore` (via `gitnr`),
  fetch `LICENSE` (via `gh`), `git init`, and optionally commit. Runs a `_post_task`
  that folds all `.gitignore.d/*` fragments into `.gitignore` (idempotent
  ordered-concat). Produces the base facts all other modules may read:
  `project_name`, `layout`, `description`, `default_branch`, `org`.
- **`bailiff-mod-python`** — Python language overlay (`_bailiff_phase: normal`,
  `depends_on: [bailiff-mod-base]`). Reads `project_name` and `description` from
  base via `_external_data`. Writes `.mise/conf.d/bailiff-mod-python.toml`
  (managed), `.pre-commit.d/bailiff-mod-python.yaml` (managed, unconditional),
  `.gitignore.d/bailiff-mod-python` (managed). Seeds a seed-once `pyproject.toml`
  via `uv init` or `pdm init`.

**Spec 007 adds the APM dependency layer:**

- **`bailiff-mod-apm`** — wires an [APM](https://microsoft.github.io/apm) package
  layer into the project. It renders a **managed** `apm.yml` (config-reproducible)
  and runs a trust-gated, version-pinned `apm install` task that writes
  `apm.lock.yaml`. v1 is **APM only** (Q1); MCP / SpecKit / steering are future
  `bailiff-mod-*` modules.

**The `bailiff-mod-apm` step (spec 007 / FR-010).**

- **When to offer it.** When the user is generating a project and wants an APM
  dependency layer, AND ≥ 1 package is warranted (the module's precondition, Q4).
  Present it as an optional layer after the base template. It threads
  `project_name` from a base layer (or falls back to a default standalone).
- **You build the `apm_packages` list (Q2).** `apm_packages` is a
  **runtime-injected list-typed answer** (`type: yaml`, no frozen `choices:`).
  YOU (phase 1) determine the packages from the user's input + project
  requirements and inject them via `--data apm_packages=[…]`; the user MAY
  override. You may seed suggestions from bailiff's own known set (speckit,
  dep-audit, secrets-scan, …), but the list is not a template choice. Each entry
  is an APM dependency locator (`owner/repo/packages/name#constraint`) — the same
  inline-source shape bailiff's own `apm.yml` uses; APM has no separate consumer
  catalogue block, so each locator IS a source (satisfying the ≥ 1-source rule,
  FR-002a). The list persists to the answers file so reproduce replays it.
- **≥ 1-package precondition + empty-set refusal (Q4).** Do NOT add the module
  when there are no packages. If it is reached with an empty set, its
  `apm_packages` validator **refuses** the render with a "drop this module"
  message (exit 1) — it never writes an empty `apm.yml`.
- **Trust consent.** `has_tasks: true` (the `apm install` task). Always explain
  and obtain explicit consent before `init` (step 3). No APM token is a copier
  answer — the APM CLI reads ambient credentials from the environment (spec 005).
- **Post-init note (Q3).** `apm.yml` is config-reproducible. `apm.lock.yaml` is a
  **task side-effect / external state** — regenerated by the pinned install task
  at reproduce and MAY differ across runs; only `apm.yml` is config-reproducible.
  The task pins the APM CLI version (`apm_cli_version`,
  `uvx --from apm-cli==<version> apm install`) for process-determinism.
- **Handoff shape.** Standard spec-003 multi-template run-spec (one `answers`
  block per layer, `apm_packages` as a `--data` list). See
  `specs/007-agentic-module/contracts/agentic-module.md`.

**Base-selection step.** When the user wants a new project, select
`bailiff-mod-base` as the first layer, then add any language/tooling overlays. The
multi-layer run-spec is the one from *5a*; bailiff orders base before the overlays
from their `depends_on` edges and phase (`base` is `pre`; overlays are `normal`).

**Per-module trust consent.** Both modules run code (`_tasks`), so each needs
trust before init (step 3). Their preflight tasks (ordered first) fail loudly
with install guidance if a required tool is missing:

- `bailiff-mod-base`: **git**, **gh** (authenticated — `gh auth status`),
  **gitnr** (pinned 0.3.0). No token is a copier answer; `gh` reads ambient
  credentials.
- `bailiff-mod-python`: **uv**.

**File lifecycles (what reproduce does).** Managed files (dir scaffold,
`.copier-answers*.yml`) re-render config-consistently. Seed-once files (`AGENTS.md`,
`pyproject.toml`) are scaffolded once, then project-owned — `_skip_if_exists`
protects them from being clobbered on a re-run/update; on a fresh-checkout
reproduce they render normally. Task outputs (`.gitignore`, `LICENSE`) are
process-deterministic and re-run under trust (their guards make them idempotent).

**Agent-steered facts are frozen, never re-decided.** `bailiff-mod-base`'s
architecture section is an *agent* decision made in **phase 1**: you (the agent)
author the section body and editable globs, then freeze them as the
`architecture_md` + `agent_editable_globs` answers (with `write_architecture=true`
to splice them). Reproduce replays those frozen answers deterministically — no
agent is ever in the reproduce path (Constitution II/III).

**Cross-module facts — two mechanisms (spec 014).** When building a multi-module
run-spec, you supply two classes of facts via `--data`:

1. **Always-present producers:** base facts (`project_name`, `layout`,
   `description`, `default_branch`, `org`) flow via `_external_data` aliases
   declared in the consumer's `copier.yml`. The engine reads the producer's
   `.copier-answers.<basename>.yml`; you do not inject these via `--data`.
2. **Sometimes-absent producers:** facts like `hook_manager`, `ts_linter`,
   `python_linter`, `monorepo_tool` have standalone defaults in the consumer's
   `copier.yml`. You inject the correct value via `--data` when the producing
   module IS in the selection (e.g. `--data hook_manager=pre-commit` when
   `bailiff-mod-precommit` is selected). When the producer is absent, leave the
   consumer's default in place.

Never wire a sometimes-absent producer via `_external_data` — if the producer is
absent from the selection, bailiff raises a preflight `OrderingError`.

**How to write a module (spec 014 checklist):**

| Step | What to do |
|---|---|
| 1. Pick a phase | `_bailiff_phase: normal` for most modules; only base uses `pre`. |
| 2. Declare edges | `depends_on: [bailiff-mod-base]` (hidden `when: false`). Add more targets for every side-effect dependency. |
| 3. Read base facts | Declare `_external_data: {base: .copier-answers.bailiff-mod-base.yml}` and use `_external_data.base.<key>` in defaults. |
| 4. Declare agent-fed facts | For sometimes-absent producers, declare the key with a standalone default string. Do not add `_external_data` or `depends_on` for the producer. |
| 5. Write fragments, not combined files | Write `.mise/conf.d/<vendor>-<module>.toml`, `.pre-commit.d/<vendor>-<module>.yaml`, `.gitignore.d/<vendor>-<module>` as MANAGED renders. |
| 6. Deferred work | If work must run after all modules rendered, declare it in `_post_tasks`. |
| 7. Mark lifecycle | Comment each output with its lifecycle (MANAGED / SEED-ONCE / TASK-OUTPUT / POST-TASK OUTPUT). |
| 8. Ship the reproducibility marker | Include `template/{{ _copier_conf.answers_file }}.jinja`. |

**Agent-projected capabilities (spec 015).** Some capabilities cannot be composed
by a mechanical merge because the target format depends on which backend the stack
selected (hooks → pre-commit vs lefthook; `.editorconfig` sized from the selected
languages). These use two manifest fields — `_agent_tasks` and `_post_agent_tasks`,
each a map with optional `pre`/`post` NL instructions. As the phase-1 agent you:

- **Run the projection from the ACTUAL selection.** When bailiff reaches an agent-task
  slot it hands you the instruction plus the selected module basenames and their
  answers files. Read the neutral inputs (e.g. every `.hooks.d/*.yaml` fragment) and
  produce the target file(s) for the selected backend. Invent nothing for a backend or
  language whose module is absent.
- **Return files, not prose.** Your output is a `{path: content}` mapping bailiff
  writes and FREEZES into the producing module's answers file. On `reproduce` bailiff
  replays the frozen files with NO agent — so your projection must be a pure function
  of the selection (deterministic, Constitution III).
- **Never write a MANAGED-render-owned path unless you own it.** bailiff's
  reproduce-safety lint fails init if an agent-written path is also a managed render
  and unfrozen. An agent-projected file (e.g. `.editorconfig`, `lefthook.yml`) must be
  the agent's alone — the module ships no competing `.jinja` for it.
- **Slot timing:** `_agent_tasks.{pre,post}` wrap a module's own render/`_tasks` (own
  context); `_post_agent_tasks.{pre,post}` run around the post-loop mechanical merges
  (full-stack context — use these for cross-module projection like hooks/editorconfig).

Canonical pattern + schema: `specs/015-agent-projected-capabilities/contracts/`
(`agent-tasks.md`, `hooks-neutral-dir.md`).

## Reproduce / Update as portable skills

`reproduce` and `update` are **portable skills** (semantic auto-trigger) — not
slash commands. They apply to any project bailiff has touched:

- **Reproduce** — `uvx bailiff reproduce [<dest>]` — replays committed
  answers at the recorded commit, no agent. Equivalent copier-only fallback:
  `copier recopy --vcs-ref=:current: --defaults --overwrite` (per answers file).
- **Update** — the intentional upgrade to a newer template version (spec 006);
  distinct from reproduce. Procedure below.

### Upgrade sub-procedure (spec 006)

> **When this applies:** the user wants to move a project from one template version
> to a newer one (e.g. `v1.0.0 → v1.2.0`). Upgrade is the ONLY bailiff path that
> advances a template version; reproduce always stays pinned.

**Phase 1 (agent — you):**

1. **Inspect current state**: read the project's `.copier-answers*.yml` — note the
   `_src_path` (template source) and `_commit` (current pinned version) per layer.
2. **Discover available versions**: run
   `uvx bailiff discover <src_path>` and note the `versions` list.
3. **Announce the upgrade**: tell the user the from→to version per layer.
4. **Trust check**: if `has_tasks`, `has_migrations`, or `jinja_extensions` is
   non-empty, explain that the template runs code and obtain explicit consent before
   running upgrade. Then trust the source if not already trusted:
   `uvx bailiff trust add --from-source <src>`.
5. **Clean tree required**: the destination must have no uncommitted changes.
   Upgrade commits each layer between layers (and copier refuses a dirty tree even
   in `--pretend`), so commit or stash first. bailiff refuses up front with a clear
   message otherwise.
6. **Dry-run (optional)**: run with `--pretend` to preview changes without writing
   (still requires a clean tree).

**Phase 2 (deterministic — LLM-free):**

```sh
# Single-layer or multi-layer (N=1 is the degenerate case):
uvx bailiff update <dest> [--vcs-ref <tag>] [--pretend] [--conflict inline|rej]
```

**Exit codes** (see `contracts/upgrade.md` for details):
- `0` — success; all layers upgraded.
- `1` — hard error (dirty working tree, ordering, deprecated migration format, downgrade attempt, etc.).
- `3` — untrusted source with tasks/migrations.
- `4` — merge conflicts present; named in output. Resolve conflicts and re-run upgrade.

**Post-upgrade:**
- On exit 0: committed `.copier-answers*.yml` files now record the new `_commit`.
- On exit 4: files contain inline conflict markers (`<<<<<<< before updating`) or
  `.rej` files (in `--conflict rej` mode). Resolve and re-run.

**Migration awareness:**
- `_migrations` entries run automatically during `run_update` when the version
  condition is met (`target >= entry_version > from_version`). copier executes them;
  bailiff trust-gates them (same as `_tasks`).
- The deprecated `before`/`after` dict form in `_migrations` is refused at discovery
  — template authors must use the new format (see `contracts/upgrade.md`).
- `--skip-tasks` suppresses `_tasks` but NOT `_migrations` (copier limitation:
  migration_tasks() is called unconditionally in _apply_update()).

**Copier-only fallback** (no bailiff required for single layer):
```sh
copier update --vcs-ref <tag> --defaults --overwrite <dest>
# Multi-layer: drive each .copier-answers*.yml in dependency order
```

## References

- `specs/010-delivery-reshape/contracts/invocation.md` — the canonical invocation
  surface, exact commands, and exit codes (spec 013 moved invocation to the
  PyPI CLI: `uvx bailiff`).
- `specs/002-catalog/contracts/catalog.md` — catalog file format, listing JSON
  shape, full-id semantics, exit codes, and `unusable` structure.
- `specs/003-multi-template/contracts/ordering.md` — multi-template run-spec shape,
  edge semantics (`depends_on`, phase), ordering algorithm, and exit codes.
- `specs/001-bailiff-vertical-slice/contracts/discovery-output.md` — discover JSON.
- `specs/001-bailiff-vertical-slice/contracts/answers-doc.md` — run-spec format.
