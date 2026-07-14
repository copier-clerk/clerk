# Contract — clerk-mod-ci (NEW; multi-model, github + gitlab)

Pure managed render (ZERO `_tasks`), sized from agent-frozen `--data`. References
[_cross-cutting.md](./_cross-cutting.md) §5. Both host + both grill verdicts applied.

## Questions
| key | type | choices / default | notes |
|---|---|---|---|
| ci_host | str | [github, gitlab] / github | same model menu, host-specific render |
| ci_model | str | [minimal, standard, optimized, monorepo-affected, merge-queue] / minimal | matrix is NOT a model |
| ci_cache | bool | true | orthogonal; any model |
| ci_concurrency_cancel | bool | true | orthogonal; GH cancel-in-progress / GL auto_cancel+interruptible (coupled unit) |
| ci_os_matrix | yaml | [] (single) | >1 → wrap jobs in matrix |
| ci_matrix_versions | yaml | [] (single) | >1 → matrix |
| ci_oidc_provider | str | none / none | GH id-token:write / GL id_tokens: ; default none. (ci_harden_runner NOT offered) |
| ci_required_gate | bool | true | suppressed automatically on minimal |
| gitlab_tier | str | [free, premium_ultimate] / free | governs merge-queue fallback |
| ci_languages | yaml | [] | AGENT-FROZEN — active languages |
| ci_lang_facts | yaml | {} | AGENT-FROZEN — per-lang manager/version/image/test cmd |
| default_branch | str | "{{ default_branch }}" or main | literal ref for compare_to |
| depends_on/run_after/run_before | yaml when:false | run_after [clerk-mod-base] | sizing via --data, not run-order |

## Models (5 — same menu both hosts)
- **minimal**: ONE job, sequential steps, NO fan-in gate (gate suppressed regardless of ci_required_gate). GH single job; GL single job multi-command script (NOT two needs-chained jobs).
- **standard**: parallel per-language jobs + fan-in gate. GH explicit gate job; GL NO gate job (stage-order + "Pipelines must succeed" IS the gate) — no deploy job, no dead gate stage.
- **optimized**: standard + change-filtering + ci_cache + ci_concurrency_cancel. GH paths-filter + status-shim gate (skipped≠success); GL rules:changes (skipped pipeline = success, no shim). change-gated jobs' `needs:` MUST be `{job:x, optional:true}` (GL pipeline-creation error otherwise).
- **monorepo-affected**: GH dorny/paths-filter or per-package; GL parent-child (strategy:depend) or inline rules:changes. Zero-language guard: emit workflow when `monorepo_tool != none` even if ci_languages empty. Child-pipeline needs a frozen `monorepo_packages` list else inline-only.
- **merge-queue**: GH merge queue (needs confirmed org/GHEC signal); GL merge trains (Premium/Ultimate). `gitlab_tier=free` → render merge-when-pipeline-succeeds fallback + header warning, NOT hard error.

## Outputs / lifecycle
- **managed render** only: `.github/workflows/ci.yml` (github) OR `.gitlab-ci.yml` (gitlab), when ci_languages/ci_commands non-empty OR monorepo_tool!=none.
- Pinned action/image versions (NO `:latest`/`:lts`; upload/download-artifact SAME major); coupled interruptible+auto_cancel; literal `compare_to: refs/heads/{{ default_branch }}` (not a CI var, MR arm omits it); canonical `workflow:rules` duplicate-guard (GitLab, all models); `fallback_keys` on caches; per-language image pinned via ci_lang_facts.
- Per-language job bodies: python (uv/ruff/pytest), ts (bun/pnpm biome/tsc/vitest), go (golangci/test), rust (fmt/clippy/nextest) — from ci_lang_facts + test_runner; coverage on when test_runner != none.

## Tests
render each of 5 models × both hosts with a 2-language ci_languages fact → valid YAML, correct gate semantics (minimal no gate; standard gate; optimized change-filter), no unpinned refs, GitLab needs use optional:true, merge-queue+free = fallback+warning. Pure render → reproduce byte-identical (no tasks).
