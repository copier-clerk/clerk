# Contract — bailiff-mod-base (REVISE)

Thinned universal scaffold + identity/license. References [_cross-cutting.md](./_cross-cutting.md).

## Questions
| key | type | choices / default | notes |
|---|---|---|---|
| project_name | str | (required) | identity root; threaded to all layers |
| org | str | acme | LICENSE/repo owner |
| description | str | "" | AGENTS.md header |
| layout | str | [single, monorepo] / single | monorepo adds the 15 monorepo dirs |
| license | str | 13 SPDX / apache-2.0 | KEEP full set (gh Licenses API) |
| copyright_name | str | "{{ org }}" | NEW — LICENSE holder distinct from org slug |
| branch_strategy | str | [feature-branches-squash-merge, trunk-based, gitflow, feature-branches-merge-commit] / first | NEW — one AGENTS.md line |
| docs_subdirs | bool | true | NEW — creates lean core subdirs only (architecture/decisions/runbooks) |
| github_host | bool | true | NEW — gates a minimal `.github/` (issue/PR templates, CODEOWNERS; ~~dependabot~~ moved to bailiff-mod-dep-updates, FR-009 spec 012) — NOT workflows |
| extra_dirs | yaml | [] | NEW — freeform append-only dir list (replaces extra_monorepo_dirs) |
| run_git_init | bool | true | NEW — gates the git init task (opt out for existing repos) |
| write_architecture | bool | false | KEEP — gates AGENTS.md arch splice from frozen architecture_md |
| architecture_md / agent_editable_globs | str / yaml | "" / [] | KEEP — frozen agent facts |
| gitignore_stack | yaml | [] | KEEP — gitnr tokens; language modules inject |
| today | str | "" | injected |
| depends_on/run_after/run_before | yaml when:false | [] | base is root, no edges |

## Outputs / lifecycle
- **always managed dirs** (`.gitkeep`): `docs/` + (if docs_subdirs) `docs/architecture` + `docs/decisions` + `docs/runbooks`; `scripts/`; `tests/`. `extra_dirs` entries appended (managed). monorepo layout adds its 15 dirs (managed, gated).
- **minimal `.github/`** (managed, when `github_host`): issue/PR templates, CODEOWNERS — NO `workflows/` (that's bailiff-mod-ci). ~~dependabot~~ moved to bailiff-mod-dep-updates (FR-009, spec 012).
- **AGENTS.md** — seed-once (`_skip_if_exists`); arch splice from frozen `architecture_md` iff `write_architecture`.
- **`.mise.toml`** — managed skeleton (base owns it; language modules inject `[tools]` tokens — see cross-cutting §2).
- **task-output**: `.gitignore` (gitnr, pinned), `LICENSE` (gh api, `copyright_name`/`today`), `.git/` + optional commit.
- **MOVED OUT (base no longer scaffolds)**: `.agents/`+`.codex/`→agentic, `infrastructure/`→IaC, `.github/workflows/`→ci, `specs/`→speckit. **DROPPED**: `archive/`, `assets/`, the 5 extra docs subdirs (api/engineering/operations/product/research → available via extra_dirs).

## Tasks (order)
1. preflight: mise present + `mise install` (for git/gh/gitnr via .mise.toml, or command -v fallback for these ubiquitous tools).
2. gitnr → `.gitignore` (pinned).
3. gh → `LICENSE` (guarded `test -f`).
4. `git init --quiet` — gated `when: run_git_init`.
5. `git add -A && git commit` — gated `when: initial_commit` (existing) AND run_git_init.

## Tests
init (single + monorepo) asserts thinned dir set present, moved-out/dropped dirs ABSENT, `github_host=false`→no `.github/`, docs_subdirs lean core only, AGENTS.md substituted, LICENSE via copyright_name; reproduce config-consistent for managed, task-output present.
