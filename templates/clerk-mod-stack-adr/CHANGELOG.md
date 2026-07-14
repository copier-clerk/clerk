# Changelog

All notable changes to `clerk-mod-stack-adr` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial implementation of the stack ADR module (spec 011 T013):
  - `format [simple, adr]=simple`; `adr_dir=docs/decisions`; agent-frozen
    `stack_pins`, `framework`, `rationale` via --data (FR-010 / cross-cutting §6);
  - `run_after: [clerk-mod-base]` ordering edge (when:false);
  - SEED-ONCE output: `STACK.md` (simple) or `{{ adr_dir }}/0001-stack.md` (adr,
    MADR headings, Status=Accepted, 3-digit ADR number);
  - Jinja-rendered `_exclude` selects the active format's output file;
  - `rationale` written verbatim — no double-render of literal `{{ }}` notation;
  - No reproduce-time agent step (legacy staleness/CVE agent step dropped).

- - -
