# bailiff-mod-base

The thinned universal scaffold + identity/license for every bailiff project
(spec 011 v1.0.0). Base owns only the always-on minimal scaffold; feature-
specific dirs have been moved to their own modules.

## What it produces

| Output | Lifecycle | Notes |
|---|---|---|
| `docs/` + conditional subdirs | **managed** | `docs/architecture`, `docs/decisions`, `docs/runbooks` when `docs_subdirs=true`. |
| `scripts/`, `tests/` | **managed** | Always present. |
| monorepo targets | **managed** | 15 dirs when `layout=monorepo`. |
| `extra_dirs` entries | **managed** | Freeform append-only dirs. |
| `.github/` | **managed** | Issue/PR templates, CODEOWNERS, dependabot — when `github_host=true`. No `workflows/` (that's bailiff-mod-ci). |
| `.mise.toml` | **managed** | Rendered from frozen `mise_tools` union. Base is the single writer (cross-cutting §2). |
| `AGENTS.md` | **seed-once** (`_skip_if_exists`) | Identity + `branch_strategy` line. Scaffolded once, then project-owned. |
| `.gitignore` | **task-output** (gitnr 0.3.0) | Generated from `gitignore_stack`. Init-only-guarded via `.bailiff-base-init-done`. |
| `LICENSE` | **task-output** (`gh api`) | GitHub Licenses API; `copyright_name`/`today` substituted. Guarded `test -f`. |
| `.git/` + optional commit | **task-output** (git) | `git init` when `run_git_init`; commit when `initial_commit` and `run_git_init`. |
| `.copier-answers.yml` | **managed** | Records `_src_path` + `_commit` for reproduce. |

## Moved out (no longer in base)

| Subtree | Moved to |
|---|---|
| `.agents/` + `.codex/` | bailiff-mod-agentic |
| `infrastructure/` | IaC modules |
| `.github/workflows/` | bailiff-mod-ci |
| `specs/` | bailiff-mod-speckit |
| `archive/`, `assets/` | dropped (use `extra_dirs`) |
| `docs/api`, `docs/engineering`, `docs/operations`, `docs/product`, `docs/research` | dropped (use `extra_dirs`) |

## Prerequisites (FR-007b)

- **mise** — <https://mise.jdx.dev>
- **git** — <https://git-scm.com/downloads>
- **gh** — <https://cli.github.com>; must be authenticated (`gh auth status`)
- **gitnr** — <https://github.com/reemus-dev/gitnr>; pinned to **0.3.0**

## Usage

```sh
uvx bailiff init --run-spec <run-spec.(json|yml)>
```

Copier standalone:

```sh
copier copy --trust https://github.com/bailiff-io/bailiff-mod-base.git <destination>
```
