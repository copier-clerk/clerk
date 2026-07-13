# Contract — `clerk-mod-apm` (spec 007)

`clerk-mod-apm` is a copier template that wires an **APM dependency layer** into a
generated project. It is ONE layer in a multi-template project, driven by the existing
spec-003 ordering engine and spec-010 invocation surface. No new tool code; pure
template + task content.

**Scope (Clarified 2026-07-13, Q1)**: v1 is **APM only**. MCP config, the SpecKit
bridge, and steering/ADR scaffolding are deferred to their own future `clerk-mod-*`
modules with their own specs and contracts — they are NOT part of this module.

**Status**: Reconciled to the clarified APM-only scope. The two T002 facts are now
CONFIRMED against `apm-cli` 0.24.1 (see "Open items" at the bottom): the install verb
is `apm install` (launched pinned via `uvx --from apm-cli==<ver>`), and a consumer
`apm.yml` has no separate catalogue block — each dependency locator carries its own
inline source. Everything else is a stable invariant.

---

## Placement in the multi-template run-spec

`clerk-mod-apm` is a standard entry in the spec-003 multi-template run-spec:

```yaml
dest: "./my-project"
selection:
  - full_id: "demo/clerk-mod-base"   # example base layer (may be a test stub, Q5)
    source: "https://github.com/copier-clerk/clerk-mod-base.git"
    ref: "v1.0.0"
    answers: { project_name: myapp, license: MIT }
  - full_id: "demo/clerk-mod-apm"    # the APM layer
    source: "https://github.com/copier-clerk/clerk-mod-apm.git"
    ref: "v1.0.0"
    answers:
      # Runtime-injected list (Q2 / ADR-0003): the AGENT populates this from user
      # input + project requirements; the user MAY override. Persisted to the
      # answers file so reproduce replays it. NOT a frozen baked-in choices list.
      apm_packages:
        - "srobroek/agentic-packages/packages/speckit#>=5.0.0 <6.0.0"
        - "srobroek/agentic-packages/packages/dep-audit#>=1.0.0 <2.0.0"
      apm_cli_version: "0.24.1"       # pinned APM tool version for the install _task
```

`project_name` is NOT in the APM layer's `answers` — it is threaded from the base layer
via the `data=` accumulator (ADR-0003). The template uses `default: "{{ project_name }}"`
so it picks it up without the user re-answering; a standalone application (no base
layer) falls back to the template default (SC-006).

---

## Dependency edges

`clerk-mod-apm` declares its edge in `copier.yml` as a `when:false` hidden answer
(statically parsed by `discovery.py`; consumed by the spec-003 ordering engine):

```yaml
depends_on:
  when: false
  default: []      # Q5: 007 hardcodes NO base layer. Ordering is computed at
                   # reproduce time by the spec-003 engine from whatever edges the
                   # selected layers declare. Any real adjacency (e.g. a future
                   # project-setup module needing to run before/after apm) is
                   # declared by THAT module, never baked in here.
```

**Key invariant**: if `depends_on` is ever non-empty, it MUST name templates by their
**basename** (repo-name component), not full-id — the portable identity `ordering.py`
matches on. A project selecting a named-but-absent dependency is refused by the
spec-003 dangling-edge check.

---

## Questions (copier.yml shape)

### Stable invariants

- **`project_name`**: `default: "{{ project_name }}"` — threaded from a base layer via
  `data=` (ADR-0003); standalone fallback default for isolated use. Accessed as
  `{{ project_name }}` in `apm.yml.jinja`.
- **`today`**: injected by clerk (`--data today=…`, VI/C-05), frozen into the answers
  file; never `jinja2_time`.
- **`depends_on`**: `when: false`; never persisted; statically read.

### `apm_packages` — runtime-injected list (Q2 / FR-002)

```yaml
apm_packages:
  type: yaml
  default: []
  validator: >-
    {% if apm_packages | length == 0 %}clerk-mod-apm requires at least one APM
    package (FR-002b). …drop it from the layer selection, or inject a non-empty
    apm_packages list via --data.{% endif %}
  help: "APM package locators (agent-populated from project requirements; you may override)."
```

- Populated by the phase-1 AGENT via `--data apm_packages=[…]`; the user MAY override.
- **`type: yaml`, NOT `multiselect`** — verified in impl: copier passes a `data=` list
  straight through to a yaml-typed question, whereas a `multiselect: true` question
  WITHOUT a frozen `choices:` list does not accept injected values. This matches the
  proven injected-list convention in `clerk-mod-base` (`gitignore_stack`,
  `agent_editable_globs`).
- **Persisted** to the answers file (a real `--data` answer, not a `when:false`
  hidden), so reproduce replays the same set (FR-002, FR-008).
- **No frozen `choices:` list** — the module deliberately carries no baked-in package
  catalogue (published-label immutability therefore does not bind this question).
- **Empty set → refuse** (Q4 / FR-002b): the `validator` above fails the render (a
  non-empty validator string aborts before any write). Verified: no `apm.yml` is
  written on refusal.

### `apm_cli_version` — pinned tool version (FR-009)

```yaml
apm_cli_version:
  type: str
  default: "0.24.1"   # the APM CLI version the install _task pins (uvx --from apm-cli==<ver>)
  help: "APM CLI version pinned by the install task for process-determinism."
```

### Empty-set refusal (Q4 / FR-002b)

`clerk-mod-apm` presupposes ≥ 1 package. Phase 1 (the skill) MUST NOT include the module
when no packages are selected. If the module is nonetheless reached with an empty set,
it MUST **refuse** — the `apm_packages` `validator` above fails the render with a message
telling the user to drop the module (surfaced as `InvalidRunSpecError`, exit 1). It MUST
NOT render an empty `apm.yml` (verified: no `apm.yml` is written on refusal).

---

## Rendered file inventory

| File | Condition | Content |
|---|---|---|
| `{{ _copier_conf.answers_file }}.jinja` | always | Answers-file template (required, VI) |
| `apm.yml` | always (empty set already refused by the validator) | Rendered APM config: selected `dependencies.apm[]`, each an inline source (Q2 / FR-002a) |
| `apm.lock.yaml` | install `_task` side-effect | Written by the pinned install `_task`; NOT a `.jinja` render; **external state**, not byte-guaranteed at reproduce (Q3) |

No MCP / `.specify/` / `.claude/` / `docs/decisions/` outputs in v1 (deferred, Q1).

The rendered `apm.yml` mirrors the authoring repo's own `/apm.yml` schema (`name`,
`version`, `description`, `target`, `dependencies.apm[]`). **≥ 1 catalogue/registry
source (FR-002a) — confirmed shape:** a consumer `apm.yml` has NO separate
`sources:`/`registries:`/`marketplaces:` block — each dependency locator carries its
own source inline (`owner/repo/packages/name#constraint`), exactly like the clerk repo's
own `/apm.yml`. So each locator IS a source, and ≥ 1 dependency == ≥ 1 source; since the
empty set is refused, `dependencies.apm[]` is always non-empty (≥ 1 source guaranteed).
The experimental top-level `registries:` block is feature-gated by APM and would break a
plain `apm install`, so it is deliberately NOT emitted; consumer `marketplaces:` are
global CLI config, not project state.

---

## `_tasks` (trust-gated code execution)

`_tasks` run at **both init and reproduce** (Constitution III). The source MUST be
trusted before they run; clerk refuses at exit 3 otherwise
(`runner._require_trust_if_action_taking`).

### APM install task (Q3 / FR-004, FR-009)

```yaml
_tasks:
  # PREFLIGHT (ordered first): fail with install guidance if uvx is missing.
  - >-
    command -v uvx >/dev/null 2>&1 ||
    { echo "clerk-mod-apm: required tool 'uvx' (from uv) not found on PATH." >&2; exit 1; }
  # APM install — confirmed against apm-cli 0.24.1: `apm install` reads apm.yml
  # and writes apm.lock.yaml; it takes no --yes flag and is non-interactive.
  - command: "uvx --from apm-cli=={{ apm_cli_version }} apm install"
    when: "{{ apm_packages | length > 0 }}"
```

Invariants:

- **Pins the APM tool version** via `uvx --from apm-cli=={{ apm_cli_version }}` —
  process-determinism as far as upstream allows (Q3 / FR-009). The APM dist is
  `apm-cli` (executable `apm`); `uv run apm==X.Y.Z` is NOT valid uv syntax — the
  correct pinned launcher is `uvx --from apm-cli==<ver> apm …`. No bare `apm` on
  ambient PATH.
- **Idempotent** — safe to re-run at reproduce.
- **Portable shell command** (macOS/Linux), invoked via `uv` (no undeclared deps).
- Writes `apm.lock.yaml` as **external state** — regenerated at reproduce, NOT asserted
  byte-identical. Only `apm.yml` (rendered) is byte-reproducible (Q3 / Constitution III).

---

## Thread-forward answers contract

Answers available to any subsequent layer that declares `depends_on: [clerk-mod-apm]`
(threaded via the spec-003 `data=` accumulator — no `_external_data` needed):

- `apm_packages` — the installed set (a later layer may key off what was installed).
- `project_name`, `today`, and all other answered questions.

---

## Exit codes

Inherited from the spec-010 invocation surface (no new codes):

| Code | Meaning |
|---|---|
| 0 | success (or `--check` clean) |
| 1 | `ClerkError` (bad run-spec, copier failure, ordering error, empty-set refusal) |
| 2 | argparse usage error |
| 3 | `UntrustedSourceError` — source has `_tasks`; trust not recorded |

---

## Discovery contract

`scripts/clerk.py discover <clerk-mod-apm source>` returns:

```json
{
  "reproducible": true,
  "has_tasks": true,
  "dependency_edges": { "depends_on": [] },
  "secret_questions": [],
  "questions": [
    { "key": "apm_packages", "...": "..." },
    { "key": "apm_cli_version", "...": "..." },
    { "key": "project_name", "...": "..." }
  ]
}
```

`has_tasks: true` means the agent MUST explain trust and obtain consent before `init`.
`secret_questions` MUST be empty (VI secrets rule — no `secret:` questions).

---

## Skill step (SKILL.md addition — FR-010)

`skills/clerk/SKILL.md` gains a section covering:

1. **When to offer `clerk-mod-apm`**: whenever the user is generating a project and
   wants an APM dependency layer, AND ≥ 1 package is warranted (the module's
   precondition, Q4). Present it as an optional layer after the base template.
2. **Building the package list**: the agent determines `apm_packages` from user input +
   project requirements and injects it via `--data`; the user MAY override. It may seed
   suggestions from clerk's own known set (speckit, dep-audit, secrets-scan, …) but the
   list is not a frozen template choice (Q2/Q5).
3. **Empty-set precondition**: do not add the module when there are no packages; a
   module reached empty refuses (Q4).
4. **Trust consent**: `has_tasks: true` → always explain and obtain explicit consent
   before proceeding.
5. **Handoff shape**: reference this contract + the spec-003 multi-template run-spec.
6. **Post-init note**: `apm.lock.yaml` is a task side-effect (external state) and MAY
   differ across runs; only `apm.yml` is byte-reproducible (Q3).

---

## Copier-only fallback (spec-010 invariant)

A project with `clerk-mod-apm` applied can be reproduced without clerk:

```sh
# For each .copier-answers*.yml, in depends_on order:
copier recopy --vcs-ref=:current: --defaults --overwrite -a .copier-answers.clerk-mod-base.yml
copier recopy --vcs-ref=:current: --defaults --overwrite -a .copier-answers.clerk-mod-apm.yml
```

The install `_task` re-runs (trust-gated) at each recopy. Order is derived from
`depends_on` in the recorded answers files' `_src_path` + `_commit`, or by running
`scripts/clerk.py reproduce`.

---

## Open items (pinned during implementation — task T002) — CONFIRMED

Both facts were confirmed against `apm-cli` 0.24.1 (installed locally; verified with
`apm --help`, `apm install --help`, a scaffolded `apm init` project, and a
`apm install --dry-run` against the rendered `apm.yml`):

1. **APM install command form** — `apm install` reads `apm.yml` in the cwd, resolves
   dependencies, and writes `apm.lock.yaml`. It is non-interactive by default and takes
   NO `--yes` flag (that flag is `apm update`'s). `apm install --frozen` reproduces an
   existing lock (CI-safe); `apm lock` writes the lock only. The install task pins the
   CLI via `uvx --from apm-cli=={{ apm_cli_version }} apm install` (default `0.24.1`).
2. **`apm.yml` catalogue/registry-source key** — a consumer `apm.yml` has NO standalone
   catalogue/registry/source block. Each dependency locator under `dependencies.apm[]`
   carries its own inline source (`owner/repo/packages/name#constraint`), matching the
   clerk repo's own `/apm.yml`. So each locator IS a source; ≥ 1 dependency == ≥ 1
   source (FR-002a). The experimental top-level `registries:` block is APM
   feature-gated and would break a plain `apm install`, so it is deliberately NOT
   emitted; consumer `marketplaces:` live in global CLI config, not project state.

No product ambiguity remains — these are interface facts, verified against the tool.
