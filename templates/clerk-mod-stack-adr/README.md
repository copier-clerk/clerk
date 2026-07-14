# clerk-mod-stack-adr

Records the project's technology stack as a SEED-ONCE document. OPT-IN module
that `run_after: [clerk-mod-base]`. Sorts before language layers — stack facts
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
| `framework` | str | `""` | Primary framework / runtime. |
| `rationale` | str | `""` | Free-text rationale; may contain `{{ }}` notation — written verbatim (no double-render). |

## Agent-frozen facts

`stack_pins`, `framework`, and `rationale` are injected by the phase-1 agent
via `--data` before `clerk init` runs. This module sorts alphabetically before
language layers (`clerk-mod-s` precedes `clerk-mod-typescript` etc.) and
therefore CANNOT read language answers from the run-order accumulator. The agent
assembles the full selection first.

## No reproduce-time agent step

The legacy staleness/CVE agent step is dropped (contract spec 011). Output is
written once at init; reproduce replays frozen answers without any agent call.

## Ordering & threading

- `run_after: [clerk-mod-base]` (when:false hidden answer).
- `project_name` uses `default: "{{ project_name }}"` threading (FR-010).

## Usage

Prefer clerk (multi-layer):

```sh
uv run scripts/clerk.py init --run-spec <run-spec with [clerk-mod-base, clerk-mod-stack-adr]>
```

Copier-only (standalone):

```sh
copier copy --trust https://github.com/copier-clerk/clerk-mod-stack-adr.git <destination>
```
