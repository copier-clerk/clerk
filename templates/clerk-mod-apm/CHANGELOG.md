# Changelog

All notable changes to `clerk-mod-apm` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial APM dependency layer (spec 007, v1 = APM only per Q1). Wires an APM
  package layer into a generated project:
  - `apm_packages` — a runtime-injected list-typed answer (`type: yaml`, Q2 /
    FR-002); no frozen `choices:` list. Persisted to the answers file so
    reproduce replays the same set.
  - `project_name` threaded from a base layer via `default: "{{ project_name }}"`
    with a standalone fallback (FR-006 / SC-006); `apm_cli_version` (pinned APM
    CLI, FR-009); `today` (clerk-injected, FR-007).
  - a rendered **managed** `apm.yml` (`dependencies.apm[]` from the injected
    set + inline sources; ≥ 1 source guaranteed since ≥ 1 package is required —
    FR-002a / FR-003).
  - empty-set **refusal** via the `apm_packages` validator (Q4 / FR-002b): a
    zero-package render is refused with a "drop this module" message, never an
    empty `apm.yml`.
  - trust-gated tasks: a `uvx` preflight and a version-pinned
    `uvx --from apm-cli==<version> apm install` that writes `apm.lock.yaml` as
    external state (Q3 / FR-004 / FR-009).
  - `depends_on` / `run_after` / `run_before` declared as empty `when:false`
    hidden answers (Q5 / FR-005): no hardcoded base layer; ordering is computed
    by the spec-003 engine from the selected layers' edges.
