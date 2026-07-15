# bailiff-mod-apm

The **APM dependency layer** (spec 007, v1). One copier template that wires an
[APM](https://microsoft.github.io/apm) package layer into a generated project:
it renders a valid `apm.yml` from a runtime-injected package set and runs a
trust-gated, version-pinned `apm install` task that writes `apm.lock.yaml`.

v1 is **APM only** (spec 007 Q1). MCP config, the SpecKit bridge, and
steering/ADR scaffolding are each deferred to their own future `bailiff-mod-*`
modules.

## What it produces

| Output | Lifecycle | Notes |
|---|---|---|
| `apm.yml` | **managed** | Rendered from the injected `apm_packages` list (+ threaded `project_name`). Re-rendered byte-identically at reproduce (Q3). |
| `apm.lock.yaml` | **task-output** (`apm install`) | Written by the pinned `apm install` task. **External state** — regenerated at reproduce, NOT byte-guaranteed (Q3 / Constitution III). |
| `.copier-answers.yml` | **managed** | Records `_src_path` + `_commit` (and the frozen `apm_packages`) for faithful reproduce. |

## The package set is runtime-injected (Q2)

`apm_packages` is a **runtime-injected list-typed answer** (`type: yaml`), not a
frozen `choices:` list. The phase-1 agent determines the packages from user
input + project requirements and injects them via `--data apm_packages=[…]`; the
user MAY override. The answer persists to the answers file so reproduce replays
the same set (FR-002 / FR-008).

Each entry is an APM dependency locator — the same inline-source shape the bailiff
repo's own `apm.yml` uses (APM has no separate consumer catalogue block; each
locator carries its own source):

```
srobroek/agentic-packages/packages/speckit#>=5.0.0 <6.0.0
```

### At least one package is required (Q4)

`bailiff-mod-apm` presupposes **≥ 1 package** (FR-002b). Phase 1 (the skill) must
not add the module when there are no packages. If it is reached with an empty
set, the `apm_packages` validator **refuses** the render with a message telling
the user to drop the module — it never renders an empty `apm.yml`.

## Prerequisites

This template runs trust-gated `_tasks`, so the source must be trusted
(`bailiff trust add …`) before it renders. A preflight task (ordered first) checks
for `uvx` and fails with install guidance if it is missing:

- **uv / uvx** — <https://docs.astral.sh/uv/getting-started/installation/>; the
  install task launches the pinned APM CLI via `uvx --from apm-cli==<version>`.

No APM token is stored in a copier answer — the APM CLI reads ambient
credentials from the environment (spec 005 / Constitution VI).

## Usage

Prefer bailiff (handles trust, ordering, answer threading, `today` injection, and
the injected `apm_packages` list):

```sh
uv run scripts/bailiff.py init --run-spec <run-spec.(json|yml)>
```

Copier-only (single layer; inject the package list via `--data`):

```sh
copier copy --trust \
  --data apm_packages='["srobroek/agentic-packages/packages/speckit#>=5.0.0 <6.0.0"]' \
  https://github.com/bailiff-io/bailiff-mod-apm.git <destination>
```

## Reproduce notes (Q3)

Reproduce re-renders `apm.yml` **byte-identically** from the committed answers +
pinned commit. The install task re-runs under trust and regenerates
`apm.lock.yaml`; that lock is **external state** and MAY differ across runs
(upstream resolution can change) — only `apm.yml` is byte-reproducible. The task
pins the APM CLI version (`apm_cli_version`) to make resolution as deterministic
as upstream allows.

## Independence (Q5)

007 does **not** depend on spec 009 and is not a prerequisite of it.
`bailiff-mod-apm` declares its dependency edges as empty `when:false` hidden
answers; the spec-003 ordering engine computes any ordering at reproduce time
from whatever edges the selected layers declare. The module renders standalone
(no base layer) with a default `project_name` (SC-006).
