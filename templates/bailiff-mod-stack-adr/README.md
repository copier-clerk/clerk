# bailiff-mod-stack-adr

Records the project's technology stack as a SEED-ONCE document. OPT-IN module
that `run_after: [bailiff-mod-base]`. Sorts before language layers — stack facts
are injected by the phase-1 agent via `--data` (cannot read from run-order
accumulator, cross-cutting §6 / FR-010).

## What it produces

| Output | Lifecycle | Notes |
|---|---|---|
| `STACK.md` | **seed-once** (`_skip_if_exists`) | Written when `format=simple`. |
| `{{ adr_dir }}/0001-stack.md` | **seed-once** (`_skip_if_exists`) | Written when `format=adr`. MADR headings, Status=Accepted, 3-digit ADR number. |

Only one file is written per init (controlled by `_exclude`).

## Questions

| Key | Type | Default | Notes |
|---|---|---|---|
| `format` | str choice | `simple` | `simple` = STACK.md; `adr` = numbered ADR. |
| `adr_dir` | str | `docs/decisions` | ADR output directory (matches base scaffold). |
| `stack_pins` | yaml | `[]` | Agent-frozen list of stack entries. |
| `stack_framework` | str | `""` | Primary framework / runtime. |
| `rationale` | str | `""` | Free-text rationale; may contain `{{ }}` notation — written verbatim (no double-render). |

## Agent-frozen facts

`stack_pins`, `stack_framework`, and `rationale` are injected by the phase-1 agent
via `--data` before `bailiff init` runs. This module sorts alphabetically before
language layers (`bailiff-mod-s` precedes `bailiff-mod-typescript` etc.) and
therefore CANNOT read language answers from the run-order accumulator. The agent
assembles the full selection first.

## No reproduce-time agent step

The legacy staleness/CVE agent step is dropped (contract spec 011). Output is
written once at init; reproduce replays frozen answers without any agent call.

## Ordering & threading

- `run_after: [bailiff-mod-base]` (when:false hidden answer).
- `project_name` uses `default: "{{ project_name }}"` threading (FR-010).

## Usage

Prefer bailiff (multi-layer):

```sh
uvx bailiff init --run-spec <run-spec with [bailiff-mod-base, bailiff-mod-stack-adr]>
```

Copier-only (standalone):

```sh
copier copy --trust https://github.com/bailiff-io/bailiff-mod-stack-adr.git <destination>
```
