# Contract — clerk agentic-ecosystem module (spec 007)

`clerk-mod-apm` is a copier template that wires an agentic toolchain (APM / MCP /
SpecKit / steering-ADR) into a generated project. It is ONE layer in a
multi-template project, driven by the existing spec 003 ordering engine and spec 010
invocation surface. No new tool code; pure template + task content.

**Status**: Draft. Sections marked [TBD] depend on open questions in
`spec.md`. The contract documents the stable invariants now; variable sections are
flagged.

---

## Placement in the multi-template run-spec

`clerk-mod-apm` is a standard entry in the spec 003 multi-template run-spec:

```yaml
dest: "./my-project"
selection:
  - full_id: "demo/clerk-mod-base"   # example base layer
    source: "https://github.com/copier-clerk/clerk-mod-base.git"
    ref: "v1.0.0"
    answers: { project_name: myapp, license: MIT }
  - full_id: "demo/clerk-mod-apm"    # agentic-ecosystem layer
    source: "https://github.com/copier-clerk/clerk-mod-apm.git"
    ref: "v1.0.0"
    answers:
      # component selections [TBD shape — depends on OQ-007-a]
      apm_packages: ["srobroek/agentic-packages/packages/speckit#>=5,<6"]
      mcp_servers: []           # deselect MCP
      speckit_enabled: true
      steering_adr_enabled: false
```

`project_name` is NOT in the APM layer's `answers` — it is threaded from the base
layer via the `data=` accumulator (ADR-0003). The template uses
`default: "{{ project_name }}"` so it picks it up without requiring the user to
re-answer.

---

## Dependency edges

`clerk-mod-apm` declares the following in `copier.yml` as `when:false` hidden answers
(statically parsed by `discovery.py`; consumed by the spec 003 ordering engine):

```yaml
# Dependency declaration (hidden, not persisted).
depends_on:
  when: false
  default: []      # [TBD] — will list base layer basenames it must follow.
                   # Example: ["clerk-mod-base"] if that template exists in catalog.
                   # For v1, may be empty (no mandatory base layer).
```

**Key invariant**: if `depends_on` is non-empty, it MUST name templates by their
**basename** (the repo name component), not by full-id — this is the portable name
used inside templates (see `ordering.py` identity-matching contract). A project that
applies `clerk-mod-apm` without the named base layer will be refused by the spec 003
dangling-edge check.

---

## Questions (copier.yml shape)

The exact question set is [TBD — depends on OQ-007-a and OQ-007-b]. The invariants
documented here apply regardless of resolution:

### Stable invariants

- **`project_name`**: NOT a question in this template. Threaded from a base layer
  via `data=` (or the user supplies it in `answers` if applying this template standalone).
  Accessed as `{{ project_name }}` in rendered files.
- **`today`**: NOT a question. Injected by clerk (as for all templates; spec FR-007).
- **Dependency edge questions**: `when: false`; never persisted; statically readable.

### Component-selection questions [TBD shape]

Each component category requires a question whose value controls conditional
rendering. Shape options (depends on OQ-007-a):

**Option A — fixed `choices` (baked in):**
```yaml
apm_packages:
  type: str        # or multiselect if copier supports it natively in this form
  multiselect: true
  choices:
    - "srobroek/agentic-packages/packages/speckit#>=5,<6"
    - "srobroek/agentic-packages/packages/dep-audit#>=1,<2"
    - "srobroek/agentic-packages/packages/secrets-scan#>=1,<2"
    - "srobroek/agentic-packages/packages/steering-pragmatic#>=1,<2"
  default: []
  help: "APM packages to install in the generated project."
```

**Option B — runtime-injected (ADR-0003 mechanism):**
```yaml
apm_packages:
  type: str
  choices: "{{ apm_packages_catalog }}"   # injected via --data at runtime
  multiselect: true
  default: []
  help: "APM packages to install."
```
*(Requires the agent to inject `--data apm_packages_catalog=[…]` before the template
runs. The agent's skill step must build this list from a known source.)*

**SpecKit / MCP / steering-ADR toggles:**
```yaml
speckit_enabled:
  type: bool
  default: true
  help: "Scaffold .specify/ and SpecKit config."

mcp_servers:
  type: str   # [TBD] — multiselect of known MCP server ids, or empty to skip
  choices: [...]
  default: []
  help: "MCP servers to configure."

steering_adr_enabled:
  type: bool
  default: false
  help: "Scaffold steering stubs (.claude/CLAUDE.md) and docs/decisions/."
```

---

## Rendered file inventory [TBD]

The following table is provisional — depends on OQ-007-b (component scope):

| File | Condition | Content |
|---|---|---|
| `{{ _copier_conf.answers_file }}.jinja` | always | Answers-file template (required by VI) |
| `apm.yml` | APM packages selected | Generated APM config with selected package deps |
| `apm.lock.yaml` | task side-effect | Written by the APM install `_task`; NOT a `.jinja` render |
| `.mcp.json` | MCP servers non-empty | MCP server configuration [TBD schema] |
| `.specify/constitution.md` | speckit_enabled | Constitution stub |
| `.specify/extensions.yml` | speckit_enabled | SpecKit extensions config stub |
| `.specify/feature.json` | speckit_enabled | SpecKit integration config stub |
| `.claude/CLAUDE.md` | steering_adr_enabled | Steering stub |
| `docs/decisions/` | steering_adr_enabled | ADR directory with a template `0001-example.md` |

The `apm.yml` shape (when rendered by this template) follows the same schema as
the authoring repo's own `apm.yml` (see `/apm.yml` in this repo for the reference
shape): `name`, `version`, `description`, `author`, `license`, `target`,
`includes`, `dependencies.apm[]`.

---

## `_tasks` (trust-gated code execution)

`_tasks` run at both init and reproduce (Constitution III). The source MUST be
trusted before they run; clerk refuses at exit 3 if not (via
`runner._require_trust_if_action_taking`).

### APM install task [TBD — depends on OQ-007-e]

A shell command that installs the selected APM packages into the generated project.
The exact command form is subject to OQ-007-e (pinning). Invariants:

- MUST pin the APM CLI version to a specific semver range for process-determinism.
- MUST be idempotent (re-running at reproduce produces the same installed state).
- MUST be a shell command (not a Python script), so it runs on macOS/Linux without
  additional dependencies.
- The tool invoked MUST be available via `uv` or be otherwise declared as a
  prerequisite.

**Placeholder form** (to be concretised at planning):
```yaml
_tasks:
  - command: "uv run --with 'apm=={{ apm_version }}' apm install"
    when: "{{ apm_packages | length > 0 }}"
```

*(The `apm` CLI and its `install` subcommand are assumed; the exact interface is TBD.
If `apm` does not have a CLI install command, this task shape must be revised.)*

---

## Thread-forward answers contract

The following answers from `clerk-mod-apm` are available to subsequent layers (those
declared `depends_on: [clerk-mod-apm]`):

- `apm_packages`: the selected list (useful if a later layer wants to know what was
  installed).
- `speckit_enabled`: the SpecKit toggle.
- `steering_adr_enabled`: the steering toggle.
- All other answered questions.

These are threaded via the spec 003 `data=` accumulator — no `_external_data` needed.

---

## Exit codes

Inherited from the spec 010 invocation surface (no new codes):

| Code | Meaning |
|---|---|
| 0 | success (or `--check` clean) |
| 1 | `ClerkError` (bad run-spec, copier failure, ordering error) |
| 2 | argparse usage error |
| 3 | `UntrustedSourceError` — source has `_tasks`/`_jinja_extensions`; trust not recorded |

---

## Discovery contract

`scripts/clerk.py discover <source>` on `clerk-mod-apm` will return:

```json
{
  "reproducible": true,
  "has_tasks": true,
  "dependency_edges": { "depends_on": ["..."] },
  "questions": [
    { "key": "apm_packages", ... },
    { "key": "speckit_enabled", ... },
    ...
  ]
}
```

`has_tasks: true` means the agent MUST explain trust and obtain consent (step 3 of
the skill procedure) before running `init`.

---

## Skill step (SKILL.md addition)

The `skills/clerk/SKILL.md` will be extended with a section covering:

1. **When to offer `clerk-mod-apm`**: whenever the user is generating a project
   and wants agentic toolchain wiring. Present it as an optional layer after the
   base template.
2. **What to present**: the component multiselect(s) — APM packages, MCP servers,
   SpecKit toggle, steering-ADR toggle.
3. **Trust consent**: `has_tasks: true` → always explain and obtain explicit consent
   before proceeding.
4. **Answers doc shape**: reference this contract file and spec 003's multi-template
   run-spec shape.
5. **Post-init note**: the `apm.lock.yaml` is a task side-effect and MAY not be
   byte-identical at reproduce (OQ-007-e outcome to be documented here).

---

## Copier-only fallback (spec 010 invariant)

A project with `clerk-mod-apm` applied can be reproduced without clerk:

```sh
# For each .copier-answers*.yml, in depends_on order:
copier recopy --vcs-ref=:current: --defaults --overwrite -a .copier-answers.clerk-mod-base.yml
copier recopy --vcs-ref=:current: --defaults --overwrite -a .copier-answers.clerk-mod-apm.yml
```

The `_tasks` in `clerk-mod-apm` will re-run (trust-gated) at each recopy. Determine
the order by reading `depends_on` from `.copier-answers.clerk-mod-apm.yml`'s
recorded `_src_path` + `_commit` — or by running `scripts/clerk.py reproduce`.

---

## Open items (tracked here for planning)

The following details in this contract are [TBD] and must be filled before tasks
are generated:

1. **OQ-007-a outcome**: question shape (fixed choices vs runtime injection).
2. **OQ-007-b outcome**: which component categories are in v1 (may reduce or expand
   the rendered file inventory).
3. **OQ-007-c outcome**: SpecKit task depth (`.specify/` render only, or also a
   task).
4. **OQ-007-e outcome**: APM lock file treatment + `_task` pin form.
5. **OQ-007-f outcome**: monolith vs split (determines whether this is one contract
   file or several `clerk-mod-*` contracts).
6. **APM CLI interface**: the exact `apm install` command form (may need upstream
   clarification).
