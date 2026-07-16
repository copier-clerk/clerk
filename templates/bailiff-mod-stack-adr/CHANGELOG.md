# Changelog

All notable changes to `bailiff-mod-stack-adr` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial implementation of the stack ADR module (spec 011 T013):
  - `format [simple, adr]=simple`; `adr_dir=docs/decisions`; agent-frozen
    `stack_pins`, `stack_framework`, `rationale` via --data (FR-010 / cross-cutting §6);
  - `run_after: [bailiff-mod-base]` ordering edge (when:false);
  - SEED-ONCE output: `STACK.md` (simple) or `{{ adr_dir }}/0001-stack.md` (adr,
    MADR headings, Status=Accepted, 3-digit ADR number);
  - Jinja-rendered `_exclude` selects the active format's output file;
  - `rationale` written verbatim — no double-render of literal `{{ }}` notation;
  - No reproduce-time agent step (legacy staleness/CVE agent step dropped).

### Breaking changes

- feat!: renamed `framework` question to `stack_framework` to avoid a
  cross-module answer-key collision when layered with `bailiff-mod-python` and
  `bailiff-mod-ts`. The `STACK.md` and `0001-stack.md` templates now render
  `stack_framework`. Callers passing `framework` via --data must pass
  `stack_framework`.

- - -
## bailiff-mod-stack-adr-v0.1.0 - 2026-07-16
#### Features
- rename project clerk → bailiff (PyPI: bailiff, org: bailiff-io) - (52ac605) - Sjors Robroek
#### Documentation
- (**013**) move template README invocations to uvx bailiff (T013 follow-up) - (d8cf603) - Sjors Robroek

- - -

## bailiff-mod-stack-adr-v0.1.0 - 2026-07-15
#### Features
- (**011**) implement bailiff-mod-stack-adr (T013) - (326f611) - Sjors Robroek

- - -

