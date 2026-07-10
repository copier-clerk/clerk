---
name: clerk
description: Conduct copier to scaffold a reproducible project from a template. Use when the user wants to generate/scaffold a project from a copier template, "run clerk", init a project from a clerk-mod-* template, or set one up interactively. Phase-1 only — you author the inputs; copier (driven by the `clerk` CLI) does all rendering, and reproduce is agent-free.
---

# clerk — conduct copier

You are the **phase-1 conductor**. copier is a deterministic scaffolding engine;
`clerk` is a thin CLI over copier's public API. Your job is to inspect a template,
help the user answer its questions, obtain trust consent, and hand a frozen
**run-spec** to the deterministic phase (`clerk init`). You author *inputs only*.

**The two-phase boundary — do not cross it:**

- You (the agent) run in phase 1: discover → present questions → collect answers →
  explain + obtain trust consent → write the run-spec → dry-run → generate.
- Everything after the run-spec is deterministic and LLM-free. **You are NEVER in
  the reproduce path** — reproduce replays committed answers at the recorded commit
  with no agent (`clerk reproduce` / `just reproduce`). Never offer to "reproduce
  it for them" by re-authoring answers; point them at `just reproduce`.

## Prerequisites

- `clerk` on PATH (this repo: `uv run clerk …`), and `git`.
- The example template's LICENSE task needs `gh` authenticated (`gh auth status`).

## Procedure

### 1. Inspect the template (no trust needed)

```sh
clerk discover <source> [--ref REF]
```

`<source>` is a fetchable locator — an expanded `https://` URL or a local path.
This prints static JSON (see `contracts/discovery-output.md`); it runs **no**
template code, so it is safe against an untrusted source. From the output, note:

- `reproducible` — if `false`, **stop**: the template ships no answers-file
  template, so a generated project could never be reproduced. `init` will refuse
  it (US5). Tell the user; do not try to work around it.
- `questions` — what you must collect (with `type`, `choices`, `default_raw`,
  `help`, `validator`, `secret`).
- `has_tasks` / `jinja_extensions` — non-empty means the template executes code,
  so trust will be required (step 3).
- `versions` — the available PEP 440 tags; the latest is used unless the user pins.

### 2. Present the questions and collect answers

Show the user each visible question with its help text, type, choices, and
default. Collect a value for each required question. Respect `validator`/`choices`
so the values are valid. **Do not** set `today` — clerk injects the generation
date itself (FR-007). Treat `secret: true` answers as sensitive (see step 4).

### 3. Explain trust, then obtain explicit consent (only if the template takes actions)

If `has_tasks` or `jinja_extensions` is non-empty, the template **executes code**
on the user's machine at generation (and again at reproduce). Before recording
trust, explain this plainly: *"This template runs commands (its `_tasks` / jinja
extensions) — that is arbitrary code execution from `<source>`. Trusting it lets
those run. Only trust sources you control or have reviewed."* Obtain an explicit
yes. Then, and only then:

```sh
clerk trust add <prefix>
```

If you skip this, `init` refuses with exit 3 and prints the exact
`clerk trust add` command — that refusal is the safety gate working, not an error
to route around. Never auto-trust; consent is the user's, per turn.

### 4. Author the run-spec

Write a run-spec file (JSON/YAML) per `contracts/answers-doc.md`:

```yaml
source: "<source>"
ref: "<optional pin>"
dest: "<destination dir>"
answers:
  <key>: <value>
```

Omit `today` (clerk injects it). For `secret: true` questions, do not hard-code
the secret into a committed run-spec — in this slice, prompt for it at run time;
secret injection from a store is a later spec (005). Secrets and hidden `when:false`
edges are never written to the recorded answers regardless (FR-013).

### 5. Dry-run, then generate

```sh
clerk init --run-spec <file> --check   # validates via copier's dry run; writes nothing
clerk init --run-spec <file>           # generates the project + a `just reproduce` recipe
```

`--check` surfaces missing/invalid answers (and any trust refusal) without writing.
Fix anything it reports, then run the real `init`. On success, the project has
rendered files, an initialized git repo, and a `.copier-answers.yml` recording
`_src_path` + `_commit` + answers.

### 6. Hand off

Tell the user the project is generated and how to reproduce it **without you**:

> Reproduce anytime with `just reproduce` (or `clerk reproduce .`) — it replays
> the recorded answers at the recorded version, no agent involved.

Your job ends here. Do not re-run generation as a substitute for reproduce, and
do not edit `.copier-answers.yml` by hand (copier forbids it; reproduce/upgrade
rely on it being copier-authored).

## References

- `specs/001-clerk-vertical-slice/contracts/discovery-output.md` — discover JSON.
- `specs/001-clerk-vertical-slice/contracts/answers-doc.md` — run-spec format.
- `specs/001-clerk-vertical-slice/contracts/commands.md` — the four verbs + exit codes.
