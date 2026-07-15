# Contract — bailiff-mod-ci-github + bailiff-mod-ci-gitlab (NEW; TWO modules)

Split into two modules per critique R3 (they share almost no render — a single host-branched module
was the "conditional explosion" the IaC split rejected). BOTH built in 011. Each is a pure managed
render (ZERO `_tasks`), sized from agent-frozen `--data`. References [_cross-cutting.md](./_cross-cutting.md) §5.

## Shared question shape (both modules)
| key | type | choices / default | notes |
|---|---|---|---|
| ci_model | str | [minimal, standard, optimized, monorepo-affected, merge-queue] / minimal | matrix is NOT a model |
| ci_cache | bool | true | orthogonal; any model |
| ci_concurrency_cancel | bool | true | orthogonal |
| ci_os_matrix / ci_matrix_versions | yaml | [] (single) | >1 → matrix wrap |
| ci_oidc_provider | str | none / none | GH id-token:write / GL id_tokens: (ci_harden_runner NOT offered) |
| ci_required_gate | bool | true | suppressed automatically on minimal |
| ci_languages | yaml | [] | AGENT-FROZEN — active languages |
| ci_lang_facts | yaml | {} | AGENT-FROZEN — per-lang manager/version/image/test cmd |
| monorepo_tool | str | none / none | turborepo/nx/pnpm-workspace for monorepo-affected |
| default_branch | str | "{{ default_branch }}" | literal ref |
| run_after | yaml when:false | [bailiff-mod-base] | sizing via --data, not run-order |

**Fail-loud guard (critique R4)**: when the module is selected with `ci_languages==[]` AND
`monorepo_tool==none`, emit a rendered warning comment AND a no-op job that echoes the misuse (NOT a
silent empty file). A human standalone run or an agent that forgot to inject languages is then visible.

## bailiff-mod-ci-github
- **Output**: `.github/workflows/ci.yml` (managed render).
- Models: minimal = ONE job, no gate (gate suppressed regardless of ci_required_gate); standard =
  parallel per-language jobs + explicit fan-in gate job; optimized = standard + dorny/paths-filter +
  **status-shim gate** (skipped≠success on GitHub) + cache + concurrency-cancel; monorepo-affected =
  paths-filter/per-package (zero-language guard: emit when monorepo_tool!=none even if ci_languages
  empty); merge-queue = GitHub merge queue (agent needs a confirmed org/GHEC signal to select it).
- Pins: current action majors; **upload/download-artifact MUST share major** (research flagged a v7/v8
  mismatch — reconcile). No `:latest`. `concurrency: cancel-in-progress` when ci_concurrency_cancel.
- Extra question: `merge_queue_org_confirmed` (bool, false) — the agent sets it only with a real signal.

## bailiff-mod-ci-gitlab
- **Output**: `.gitlab-ci.yml` (managed render).
- Extra question: `gitlab_tier [free, premium_ultimate]=free`.
- Models: minimal = ONE job, multi-command script (NOT two needs-chained jobs); standard = parallel jobs,
  NO explicit gate job + NO deploy job + NO dead 'gate' stage (stage-order + "Pipelines must succeed" IS
  the gate); optimized = standard + rules:changes (skipped pipeline = success → NO status-shim needed) +
  cache + interruptible; monorepo-affected = parent-child (strategy:depend) needs a frozen
  `monorepo_packages` list else inline rules:changes; merge-queue = merge trains, `gitlab_tier=free` →
  render merge-when-pipeline-succeeds fallback + header warning (NOT hard error).
- Grill fixes (all required): change-gated `needs:` use `{job:x, optional:true}` (else pipeline-creation
  error); coupled `interruptible` + `workflow:auto_cancel:on_new_commit` as one unit; literal
  `compare_to: refs/heads/{{ default_branch }}` on branch arm, omitted on MR arm; canonical
  `workflow:rules` duplicate-pipeline guard across ALL models; `fallback_keys` on caches; pinned images
  (thread `<lang>_image` via ci_lang_facts, no `:latest`/`:lts`); `bun.lock` (not `bun.lockb`) cache key.

## Per-language job bodies (both, from ci_lang_facts + test_runner)
python (uv/ruff/pytest), ts (bun|pnpm biome/tsc/vitest), go (golangci/test), rust (fmt/clippy/nextest).
Coverage step emitted when the language's `test_runner != none`.

## Notes
- MI-1 (pin auto-updater) SHOULD land before/with the second host to bound rotating-pin maintenance.
- Each module fanned out as its own mirror (`bailiff-mod-ci-github`, `bailiff-mod-ci-gitlab`).

## Tests
For EACH module: render all 5 models with a 2-language ci_languages fact → **validate with the host's
own linter** (actionlint for github, `gitlab-ci lint`/schema for gitlab — valid YAML ≠ valid workflow,
critique Q); assert gate semantics (minimal no gate, standard gate, optimized change-filter), no
unpinned refs, github artifact majors match, gitlab needs use optional:true; merge-queue+free (gitlab)
= fallback+warning; empty ci_languages + no monorepo_tool = loud warning not silent. Pure render →
reproduce byte-identical (no tasks).
