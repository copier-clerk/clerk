# bailiff-mod-ci-gitlab

Renders a `.gitlab-ci.yml` CI pipeline file for GitLab. Pure managed render —
zero `_tasks`, reproduces byte-identically.

## Models

| `ci_model` | Description |
|---|---|
| `minimal` | One job, multi-command script — no gate, no matrix |
| `standard` | Parallel jobs by language; stage order is the gate |
| `optimized` | Standard + `rules:changes` + cache + `interruptible` |
| `monorepo-affected` | Parent-child pipelines (`strategy:depend`) |
| `merge-queue` | Merge trains; `gitlab_tier=free` → fallback + warning |

## Key questions

| Question | Default | Notes |
|---|---|---|
| `ci_model` | `minimal` | Pipeline shape |
| `gitlab_tier` | `free` | `premium_ultimate` enables merge trains |
| `ci_languages` | `[]` | Agent-frozen active language list |
| `ci_lang_facts` | `{}` | Per-language manager/version/image/test-cmd |
| `ci_cache` | `true` | Enable language caches |
| `ci_concurrency_cancel` | `true` | `workflow:auto_cancel` when `interruptible` |
| `ci_oidc_provider` | `none` | `gitlab` → renders `id_tokens:` block |
| `monorepo_tool` | `none` | `turborepo`/`nx`/`pnpm-workspace` for monorepo model |

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-ci-gitlab.git <destination>
```
