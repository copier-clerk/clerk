# Changelog

All notable changes to `clerk-mod-go` are documented here. Managed by
cocogitto fan-out (ADR-0006); do not hand-edit released sections.

## [Unreleased]

### Added

- Initial Go language overlay (spec 011 T008):
  - `go_version` (finite modern list: 1.21/1.22/1.23), `app_kind [cli,service,library]=cli`,
    `test_runner [go-test,gotestsum]=go-test`, `use_vendor_mode=false`,
    `golangci_hook_rev` (injectable), threaded `project_name`/`hook_manager`;
  - `run_after: [clerk-mod-base]` edge;
  - trust-gated, init-only-guarded `go mod init` task (FR-012a);
  - seed-once `go.mod` (task-output), `.golangci.yml`, and `cmd/<name>/main.go`
    stub (cli/service only — library drops `cmd/` via `_exclude`);
  - agent-frozen union contributions: Go gitignore token to `gitignore_stack`,
    go version to `mise_tools`, golangci hook block to `hook_blocks` (M1).

<!--
  cocogitto inserts each released version's section ABOVE the `- - -` separator
  below (spec 008b). The separator MUST be present or `cog bump` fails with
  "cannot find default separator '- - -'". Keep it as the last content line.
-->

- - -
