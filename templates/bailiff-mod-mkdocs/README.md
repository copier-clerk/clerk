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
| `.mise/conf.d/bailiff-mod-mkdocs.toml` | **managed** | mkdocs + mkdocs-material tool pins; mise merges conf.d at runtime |

## Questions

| Key | Type | Default | Notes |
|---|---|---|---|
| `project_name` | str | `_external_data.base.project_name` | `site_name`; read from base via `_external_data` |
| `description` | str | `_external_data.base.description` | `site_description`; read from base via `_external_data` |

`_external_data: {base: .copier-answers.bailiff-mod-base.yml}` — reads facts from base's answers
file (hard dependency; bailiff enforces base is present and ordered before mkdocs).

Zero `_tasks`; reproduce needs no toolchain or network.

Edge: `depends_on: [bailiff-mod-base]`, `phase: normal`.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-mkdocs.git <destination>
```
