---
name: clerk
description: Conduct copier to scaffold a reproducible project from a template. Use when the user wants to generate/scaffold a project from a copier template, "run clerk", init a project from a clerk-mod-* template, or set one up interactively. Portable (macOS/Linux/WSL) — the deterministic steps run via the bundled script, no clerk CLI on PATH required. Phase-1 only — you author the inputs; copier (driven by `scripts/clerk.py`) does all rendering, and reproduce is agent-free.
---

# clerk — conduct copier

You are the **phase-1 conductor**. copier is a deterministic scaffolding engine;
`scripts/clerk.py` is a thin bundled script over copier's public API. Your job is
to inspect a template, help the user answer its questions, obtain trust consent, and
hand a frozen **run-spec** to the deterministic phase (`scripts/clerk.py init`). You
author *inputs only*.

**The two-phase boundary — do not cross it:**

- You (the agent) run in phase 1: discover → present questions → collect answers →
  explain + obtain trust consent → write the run-spec → dry-run → generate.
- Everything after the run-spec is deterministic and LLM-free. **You are NEVER in
  the reproduce path** — reproduce replays committed answers at the recorded commit
  with no agent (`uv run scripts/clerk.py reproduce`). Never offer to "reproduce
  it for them" by re-authoring answers; point them at `scripts/clerk.py reproduce`.

## Prerequisites

- **Platform:** macOS, Linux, or WSL on Windows.
- `git` on PATH.
- The example template's LICENSE task needs `gh` authenticated (`gh auth status`).
- `scripts/clerk.py` is the bundled script — **invoke it by the path anchored to
  the skill's install location**, not as `./scripts/clerk.py` (the agent's CWD is
  normally the consumer project root, not the skill dir, so a bare relative path
  will not resolve when the skill is installed via APM). Example:

  ```sh
  # When clerk is installed via APM, the skill dir is the resolved base:
  python "$SKILL_DIR/scripts/clerk.py" <verb> …
  # or with uv (frictionless if uv is on PATH — reads the PEP 723 header):
  uv run "$SKILL_DIR/scripts/clerk.py" <verb> …
  ```

  where `$SKILL_DIR` is the directory containing this `SKILL.md`.

- **Third-party deps** (`copier>=9.16,<10`, `pyyaml`, `packaging`, `tomli-w`) must
  be installed. The script checks them at startup and prints an environment-aware
  install suggestion if any are missing or version-incompatible — no traceback.
  Run `scripts/clerk.py doctor` for an explicit readiness check:

  ```sh
  python "$SKILL_DIR/scripts/clerk.py" doctor   # exit 0 = ready; exit 4 = issues
  ```

  Install suggestions (detected automatically):
  - **uv** on PATH: `uv pip install copier pyyaml packaging tomli-w`
  - **pip** on PATH: `pip install copier pyyaml packaging tomli-w`
  - **macOS brew** (copier only): `brew install copier` (then pip/uv for the rest)
  - `uv run "$SKILL_DIR/scripts/clerk.py"` auto-provisions in an ephemeral env
    if you have `uv` — no manual install needed in that case.

## Procedure

### 0. Catalog: ensure, list, pick, validate

> **When this step applies:** whenever the user wants to scaffold from their own
> template library, or does not yet have a specific `<source>` URL in hand. If the
> user names a concrete URL/path directly, skip to step 1.

Discovery and validation (sub-steps 0-a through 0-c) are **LLM-free and
deterministic** — `scripts/clerk.py` drives them. The **pick** (0-b) is your
judgment per Constitution II: you present the listing and collect the user's
choice; you do not guess or auto-select without showing the options first.

**0-a. Ensure the catalog exists and contains the user's sources.**

Check whether a catalog already exists:

```sh
uv run scripts/clerk.py catalog [--catalog PATH] list
```

If the file is absent or empty, create it and populate it:

```sh
# Create the catalog file if absent (idempotent — no-op if it already exists):
uv run scripts/clerk.py catalog [--catalog PATH] init [--name <pointer-name>]

# Add each source the user names (idempotent — duplicate adds are a no-op):
uv run scripts/clerk.py catalog [--catalog PATH] add <source> [--name <pointer-name>]
```

`<source>` is a `gituser/gitrepo` locator or a local path; an optional `@ref`
suffix overrides the display version (`acme/my-template@v2.1.0`). `--name` sets
the catalog-pointer namespace that appears as the `<catalog>` prefix in full-ids.
You manage this file on behalf of the user — never ask them to hand-edit it.

**0-b. Present the verified listing and collect the user's pick.**

```sh
uv run scripts/clerk.py catalog [--catalog PATH] list
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
uv run scripts/clerk.py catalog [--catalog PATH] list --json
```

See `specs/002-catalog/contracts/catalog.md` for the exact JSON shape, full-id
semantics, exit codes, and the `unusable` structure.

**0-c. Validate the chosen full-id before proceeding.**

```sh
uv run scripts/clerk.py catalog [--catalog PATH] validate <full-id>
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
uv run scripts/clerk.py discover <source> [--ref REF]
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
uv run scripts/clerk.py trust add <prefix>
# or, to record the owner-path prefix covering a whole org:
uv run scripts/clerk.py trust add --from-source <source>
```

If you skip this, `init` refuses with exit 3 and prints the exact
`scripts/clerk.py trust add` command — that refusal is the safety gate working,
not an error to route around. Never auto-trust; consent is the user's, per turn.

### 4. Author the run-spec

Write a run-spec file (JSON/YAML) per
`specs/001-clerk-vertical-slice/contracts/answers-doc.md`:

```yaml
source: "<source>"
ref: "<optional pin>"
dest: "<destination dir>"
answers:
  <key>: <value>
```

Omit `today` (the script injects it). For `secret: true` questions, do not
hard-code the secret into a committed run-spec — in this slice, prompt for it at
run time; secret injection from a store is a later spec (005). Secrets and hidden
`when:false` edges are never written to the recorded answers regardless.

### 5. Dry-run, then generate

```sh
uv run scripts/clerk.py init --run-spec <file> --check   # validates via copier's dry run; writes nothing
uv run scripts/clerk.py init --run-spec <file>           # generates the project
```

`--check` surfaces missing/invalid answers (and any trust refusal) without writing.
Fix anything it reports, then run the real `init`. On success, the project has
rendered files, an initialized git repo, and a `.copier-answers.yml` recording
`_src_path` + `_commit` + answers. **No clerk-specific file is written** — the
`.copier-answers.yml` is the entire reproduce state.

---

### Multi-template flow (spec 003) — N≥2 layers in dependency order

> **When this applies:** the user selects more than one template from the catalog
> (e.g. a `clerk-mod-base` + a language layer). N=1 is the degenerate case of this
> flow — behavior is identical to the steps above.

**Your judgment (phase 1):** collect a validated selection (≥1 full-ids from step 0)
and per-layer answers. You author the run-spec; ordering, apply, and reproduce are
LLM-free (Constitution II).

#### 5a. Author the multi-template run-spec

Write a run-spec with the `selection` shape (instead of the single-template `source`
field). List all selected layers with their resolved `source`/`ref` (from step 0-c)
and per-layer answers. `today` is still injected by clerk — omit it:

```yaml
dest: "./my-project"
selection:
  - full_id: "demo/clerk-mod-base"
    source: "https://github.com/copier-clerk/clerk-mod-base.git"
    ref: "v1.2.0"          # optional pin; omit for latest
    answers:
      project_name: acme
      license: MIT
  - full_id: "demo/clerk-mod-python"
    source: "https://github.com/copier-clerk/clerk-mod-python.git"
    ref: null
    answers:
      python_version: "3.12"
```

Input order within `selection` does not affect the output — clerk reorders
layers by dependency. See `specs/003-multi-template/contracts/ordering.md` for
the exact run-spec shape, edge semantics, and exit codes.

#### 5b. Preflight, then generate

```sh
uv run scripts/clerk.py init --run-spec <file> --check   # all-gaps preflight: all layers, writes nothing
uv run scripts/clerk.py init --run-spec <file>           # apply layers in dependency order
```

**How clerk orders and applies layers (LLM-free):**

1. Reads each layer's `copier.yml` statically for `depends_on`/`run_after`/
   `run_before` edges (hidden `when:false` answers, already parsed by discovery).
2. Builds a directed graph and refuses before any write if it finds:
   - a **cycle** (names the cycle members — exit 1);
   - a **dangling edge** (a dependency not in the selection — exit 1, names it);
   - a **basename collision** (two layers with the same repo basename would overwrite
     each other's answers file — exit 1, names the basename).
3. Topologically sorts with a **stable tie-break: lexicographic by template basename**
   among constraint-free layers — deterministic across runs and across init/reproduce.
4. Applies one `copier copy` per layer in that order, threading earlier layers'
   answers into later layers via copier's `data=` parameter (not `_external_data`).
5. Each layer commits its own `.copier-answers.<basename>.yml` recording its
   `_src_path` + `_commit`. **No clerk-authored order or recipe file is committed.**

`--check` (all-gaps preflight) runs all layers with `pretend=True`, collects every
missing or invalid answer across all layers, and reports them in one pass — it never
stops at the first failing layer.

On success, the project has one committed `.copier-answers.<basename>.yml` per
layer. Those files are the entire reproduce state.

#### Reproduce (recomputed, not frozen)

```sh
uv run scripts/clerk.py reproduce <project-dir>
```

clerk enumerates the committed `.copier-answers*.yml` files, fetches each template
at its recorded `_commit`, re-reads the edges, rebuilds the DAG, and topo-sorts with
the same stable tie-break — **recomputing** the order from committed state, never
reading a frozen recipe. Pinned commits → identical edges → identical order, so
reproduce is deterministic and agent-free.

**Copier-only-by-hand fallback** (no clerk required):

```sh
# For each .copier-answers.<name>.yml in the recomputed dependency order:
cd <project-dir>
copier recopy --vcs-ref=:current: --defaults --overwrite -a .copier-answers.<name>.yml
```

The recomputed order is derivable by hand from the same committed `when:false` edges;
nothing about the project *requires* clerk to reproduce.

---

### 6. Hand off

Tell the user the project is generated and how to reproduce it **without you**:

> Reproduce anytime with:
>
> ```sh
> # via the bundled script (primary path — ergonomics over copier):
> uv run scripts/clerk.py reproduce <project-dir>
>
> # copier-only fallback (no clerk, no just — works anywhere copier is installed):
> cd <project-dir> && copier recopy --vcs-ref=:current: --defaults --overwrite
> # multi-template: repeat with -a <each .copier-answers*.yml> in dependency order
> ```
>
> Both paths replay the recorded answers at the recorded version — no agent involved.

Your job ends here. Do not re-run generation as a substitute for reproduce, and
do not edit `.copier-answers.yml` by hand (copier forbids it; reproduce/upgrade
rely on it being copier-authored).

## Reproduce / Update as portable skills

`reproduce` and `update` are **portable skills** (semantic auto-trigger) — not
slash commands. They apply to any project clerk has touched:

- **Reproduce** — `uv run scripts/clerk.py reproduce [<dest>]` — replays committed
  answers at the recorded commit, no agent. Equivalent copier-only fallback:
  `copier recopy --vcs-ref=:current: --defaults --overwrite` (per answers file).
- **Update** — the intentional upgrade to a newer template version (spec 006);
  distinct from reproduce.

## References

- `specs/010-delivery-reshape/contracts/invocation.md` — the canonical invocation
  surface, exact commands, and exit codes for the bundled script.
- `specs/002-catalog/contracts/catalog.md` — catalog file format, listing JSON
  shape, full-id semantics, exit codes, and `unusable` structure.
- `specs/003-multi-template/contracts/ordering.md` — multi-template run-spec shape,
  edge semantics (depends_on/run_after/run_before), ordering algorithm, and exit codes.
- `specs/001-clerk-vertical-slice/contracts/discovery-output.md` — discover JSON.
- `specs/001-clerk-vertical-slice/contracts/answers-doc.md` — run-spec format.
