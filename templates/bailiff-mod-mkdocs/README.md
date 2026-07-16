# bailiff-mod-mkdocs

Documentation site via [mkdocs-material](https://squidfunk.github.io/mkdocs-material/)
(spec 012 / FR-011), scaffolded over base's `docs/` tree. No build or deploy
action at scaffold time. Docs engines are per-engine **sibling** splits;
vitepress is a ratified later sibling, not an axis of this module.

## Outputs

| File | Lifecycle | Notes |
|---|---|---|
| `mkdocs.yml` | **managed** | config-consistent on reproduce; wired to `docs/` |
| `docs/index.md` | **seed-once** | `_skip_if_exists`; project-owned after init |

## Pin strategy (ledger FR-011)

`mkdocs` and `mkdocs-material` pin via the **`mise_tools` frozen union**
regardless of `bailiff-mod-python` co-selection — every non-runtime tool pins
through mise (one mental model). This module contributes the tokens; base is
the single writer of `.mise.toml` (M1).

## Questions

| Key | Type | Default | Notes |
|---|---|---|---|
| `project_name` | str | threaded from base | `site_name` |
| `description` | str | `""` | `site_description` |
| `mise_tools` | yaml | `[]` | frozen union (declared for threading) |

Zero `_tasks`; reproduce needs no toolchain or network.

Edge: `run_after: [bailiff-mod-base]`.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-mkdocs.git <destination>
```
