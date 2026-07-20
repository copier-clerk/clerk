# Cross-cutting contract — spec 011 / 014

Shared design every per-module contract references. Governed by spec 014
(namespaced keys, private-by-default threading, fragment/merge model).
Where spec.md is silent, the decisions ledger at
`specs/014-namespaced-question-keys/decisions-ledger.md` governs.

## 1. Choice-axis keys (FR-002)

Use these EXACT keys, types, choices, and defaults wherever a module touches
the axis (full table in [data-model.md](../data-model.md)):

| Key | Choices | Default |
|---|---|---|
| `python_pkg_manager` | `uv`, `pdm` | `uv` |
| `js_pkg_manager` | `bun`, `pnpm`, `npm` | `bun` |
| `python_layout` | `flat`, `src` | `src` |
| `ts_linter` | `biome`, `eslint-prettier` | `biome` |
| `ruff_line_length` | — | `88` |
| `ruff_quote_style` | — | `double` |
| `ruff_rule_profile` | `standard`, `strict` | `standard` |

Dead options (pip, pipenv, poetry, yarn, jest, husky, simple-git-hooks,
edition 2015, py<3.11) are not offered.

The hook manager is not a question — it is determined by which hook module is
selected (R13 refinement): selecting `bailiff-mod-precommit` means pre-commit;
future `bailiff-mod-lefthook` means lefthook; neither means no hooks. Do not
declare a `hook_manager` question.

## 2. Fragment/merge model (R1 / FR-008–013)

Each module writes ONLY its own fragment into the relevant `.d/` directory.
No module writes the combined output file, runs a merge, or reads another
module's answers. The merged-file owner performs the combine — either via the
tool's native drop-in merge or via a single `_post_task`.

| Surface | Fragment path | Merge mechanism |
|---|---|---|
| mise tools | `.mise/conf.d/<vendor>-<module>.toml` | native: `mise install` reads all conf.d files |
| pre-commit hooks | `.pre-commit.d/<vendor>-<module>.yaml` | `_post_task` in `bailiff-mod-precommit` runs `scripts/_merge_precommit.py` after the full render loop |
| .gitignore rules | `.gitignore.d/<vendor>-<module>` | `_post_task` in `bailiff-mod-base` does idempotent ordered-concat into `.gitignore` |

Fragment file contents are MANAGED (byte-identical re-render on reproduce).
The combined output files (`.pre-commit-config.yaml`, `.gitignore`) are
config-consistent across reproduce runs — same configuration, not necessarily
same bytes (R config-consistency invariant).

**Naming convention:** fragment file names must be `<vendor>-<module>` (the
module's repo basename). Example: `bailiff-mod-python.toml`,
`bailiff-mod-python.yaml`, `bailiff-mod-python`.

**Pre-commit fragments are unconditional.** A module that contributes hooks
always writes its `.pre-commit.d/` fragment regardless of whether
`bailiff-mod-precommit` is in the selection. The bundler script runs only when
precommit is selected and is inert when no fragments exist.

**Cross-format limitation (014).** The fragment model is pre-commit–format
specific. With `hook_manager=lefthook` (a future module), language-contributed
`.pre-commit.d/` fragments are not automatically projected into `lefthook.yml`.
Cross-format translation is deferred to spec 015 via `_agent_tasks` /
`_post_agent_tasks`. See §9 for the forward pointer.

## 3. Native-command scaffold pattern (FR-007 / ADR-0007)

| Lifecycle | Pattern | Reproduce behaviour |
|---|---|---|
| MANAGED | Template renders file on every run; copier re-renders byte-identically. | Overwrites to current template version. |
| SEED-ONCE | `_skip_if_exists: [<path>]` in copier.yml. | Skips if file exists; renders on a clean tree. |
| TASK-OUTPUT | Init-only-guarded task writes the file (`test -f <sentinel> \|\| <command>`). | Guard is active on a populated tree — reproduce is a no-op; clean tree → re-runs. |
| POST-TASK OUTPUT | `_post_task` writes the file after the render loop. | Re-runs on every reproduce (idempotent design required). |

Per language: `uv init` (python), `bun init`/`pnpm init` (ts), `cargo new`
(rust), `go mod init` (go), `cdk init app --language=` (cdk). Adding
dependencies later uses `package-add` — never hand-edit manifests.

Config bailiff owns and the tool does not generate stays a MANAGED render
(`.tflint.hcl`, `.cfnlintrc.yaml`, CI files, ruff config).

NEVER an irreversible action at scaffold (no `cdk bootstrap`/`deploy`,
`terraform apply`, `sam deploy`; `gh repo create` only behind the
`create_remote` consent gate in the forge modules).

## 4. Cross-module facts — two mechanisms by design (R4 / R6 / R13-GENERALIZED)

There are exactly two mechanisms. Choose based on the litmus: **"Can a valid
stack include the consumer but not the producer?"**

| Answer | Mechanism |
|---|---|
| No — producer is always present | `_external_data` alias + hard `depends_on` |
| Yes — producer is optional | agent-fed `--data` fact with standalone default |

### 4a. `_external_data` aliases (always-present producers only)

Only `bailiff-mod-base` is always present. Base-produced facts:

| Key | Consumers |
|---|---|
| `project_name` | python, ts, api, apm, readme, and others |
| `layout` | ci-github, ci-gitlab, and others |
| `description` | apm, api, mkdocs, python, readme |
| `default_branch` | ci-github, ci-gitlab |
| `org` | github-repo, gitlab-repo (for CODEOWNERS) |

Declare the alias and read facts as shown:

```yaml
_external_data:
  base: .copier-answers.bailiff-mod-base.yml

project_name:
  type: str
  default: "{{ _external_data.base.project_name | default('', true) }}"
```

The `_external_data` declaration is the single source of truth for the data
dependency. bailiff parses it statically (R9: values must be literal
`.copier-answers.<basename>.yml` paths — no Jinja, no traversal). If the
declared producer is absent from the selection, bailiff raises a preflight
`OrderingError` before any write (R6 — there is no fallback).

### 4b. Agent-fed `--data` facts (sometimes-absent producers)

Use when the consumer can be selected without the producer. Examples:

| Key | Producer | Rationale |
|---|---|---|
| `hook_manager` | precommit | deleted as a question; justfile uses standalone default |
| `ts_linter` | ts | editorconfig works without ts |
| `python_linter`, `ruff_line_length` | python | editorconfig works without python |
| `monorepo_tool`, `monorepo_packages` | moon | CI works in non-monorepo stacks |
| `js_pkg_manager` (in package-add) | ts | package-add is language-agnostic |

Declare with a standalone default; the phase-1 agent populates it from the
actual selection via `--data`:

```yaml
ts_linter:
  type: str
  default: ""
  help: "TypeScript linter in use; bailiff injects from selection — leave blank."
```

Do NOT declare `_external_data` for these producers. Do NOT add
`depends_on: [<producer>]` for the fact.

## 5. Dependency ordering (R7 / R8)

### 5a. Single edge type: `depends_on`

`depends_on` is the only ordering edge. `run_after` and `run_before` are
deleted. Declare as a hidden `when: false` answer:

```yaml
depends_on:
  type: yaml
  default:
    - bailiff-mod-base
  when: false
```

An `_external_data` alias implicitly creates the same ordering constraint. If
a module declares `_external_data.base`, it also needs `depends_on: [bailiff-mod-base]`
(the engine enforces both independently).

A dangling edge (target absent from selection) is a preflight `OrderingError`.
There is no soft "order-if-present" option.

### 5b. Phases

| Phase | Value | Who uses it | May depend on |
|---|---|---|---|
| pre | `_bailiff_phase: pre` | `bailiff-mod-base` only | pre only |
| normal | `_bailiff_phase: normal` | all other current modules | pre + normal |
| post | reserved for future use | — | — |

Declare phase as a top-level scalar in `copier.yml`:

```yaml
_bailiff_phase: normal
```

A cross-phase forward edge (pre→normal, pre→post, normal→post) is illegal and
rejected with an error at discovery.

### 5c. `_post_tasks` — deferred work after the full render loop (R11)

A module that must run after ALL other modules have rendered (e.g. the
pre-commit fragment merge, the gitignore concat) declares `_post_tasks` as a
top-level list in `copier.yml`. bailiff runs `_post_tasks` after the entire
render loop, in `depends_on` order, on both init and reproduce.

`_post_tasks` entries use the same shell syntax as copier `_tasks`.

```yaml
_post_tasks:
  - "python3 scripts/_merge_precommit.py"
```

`_post_tasks` is orthogonal to the `_bailiff_phase` module phase. Phase
controls render/ordering of the whole module; `_post_tasks` adds a deferred
work stage for that module without changing its phase.

## 6. Schema marker and migration gate (R10)

bailiff appends `_bailiff_schema: 014` to each `.copier-answers.<basename>.yml`
after rendering. `reproduce_many` refuses with a clear error and re-init
guidance when the marker is absent or carries an older schema. This makes
the SC-006 reproduce guarantee enforceable.

The marker is written by bailiff, not by the template. Do not add it as a
copier question.

## 7. Determinism / trust / secrets (Constitution rules, unchanged)

- No `jinja2_time`; `today` injected as a copier answer (Constitution V).
- No `secret:` questions in `bailiff-mod-*`; tokens from ambient env in tasks
  (Constitution VI / FR-005).
- Code/network steps are trust-gated `_tasks` with the preflight ordered first
  (FR-009).
- Tool versions pinned via `.mise/conf.d/<vendor>-<module>.toml`.
- **Required tools declared in `_bailiff_requires` (spec 016).** A module lists the
  binaries its `_tasks` invoke directly (`[<tool>, {tool: <t>, when: <answer-key>}]`);
  a tool provisioned via the `mise install` chain declares `mise`. bailiff
  `which()`-checks every declared tool across the whole selection BEFORE any render,
  failing fast (no partial tree) — copier renders then runs `_tasks`, so the
  in-`_task` `command -v` guard is the backstop, not the gate. `when` is a truthy
  answer-key check (e.g. `install_hooks`), not an expression.

## 8. Contract-lint and test shape (FR-021 / FR-022)

Every module ships:

- `template/{{ _copier_conf.answers_file }}.jinja` — the reproducibility marker.
- `README.md` — module description and usage.
- `CHANGELOG.md` with `- - -` sentinel.
- Three-way registration parity (copier.yml, cog.toml, catalog-sources.toml).
- `_subdirectory: template` in copier.yml.

Loop test requirements:

- Hermetic init + reproduce; native/network tasks stubbed to offline marker writes
  (`_copy_module_with_stub_tasks` pattern in `tests/conftest.py`).
- Byte-assert MANAGED renders.
- Presence/structure-assert TASK-OUTPUT files.
- `_skip_if_exists`-assert SEED-ONCE files.

## 9. Agent-projected capabilities — spec 015

Spec 015 adds `_agent_tasks` and `_post_agent_tasks` fields to `copier.yml` — each
a map with optional `pre`/`post` NL instructions. Any module (first- or third-party)
declares agent-projected work in this structured, machine-readable form. Execution:
init-only, the phase-1 agent runs once, its `{path: content}` output is frozen into
the producer's answers file (`_agent_frozen`), and reproduce replays it with no agent
(Constitution III). The engine's reproduce-safety lint fails init if an agent-written
path is a managed render that was not frozen.

Use agent projection ONLY for the tier mechanical merge cannot express — cross-format
translation where the target depends on the selected backend. Prefer, in order:
native drop-in merge (`.mise/conf.d/`) > single-format mechanical merge
(`.pre-commit.d/` bundler, `.gitignore.d/` concat) > agent projection.

Shipped 015 instances (the canonical patterns to copy):
- **Neutral hooks:** hook-contributing modules drop `.hooks.d/<module>.yaml` (neutral
  intent); the selected hook manager projects it — `bailiff-mod-precommit`
  (`_post_agent_tasks.pre` → `.pre-commit.d/` fragment before the bundler),
  `bailiff-mod-lefthook` (`_post_agent_tasks.post` → `lefthook.yml`).
- **editorconfig:** `bailiff-mod-editorconfig` writes `.editorconfig` from the selected
  languages via `_post_agent_tasks.post` (no managed `.jinja`, no linter questions).

Full schema + timeline: `specs/015-agent-projected-capabilities/contracts/`.
