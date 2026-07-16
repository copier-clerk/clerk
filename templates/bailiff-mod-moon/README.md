# bailiff-mod-moon

Monorepo task orchestration via [moon](https://moonrepo.dev) (spec 012 /
FR-010). Renders a managed `.moon/workspace.yml` wired to base's monorepo
package layout, and supplies the `monorepo_tool=moon` answer the CI
modules read for their `monorepo-affected` model (`moon ci` — FR-010a).

Monorepo tools are per-tool **sibling** splits (ratified: "too distinct");
turbo and nx are later siblings, not axes of this module.

## Outputs

| File | Lifecycle | Notes |
|---|---|---|
| `.moon/workspace.yml` | **managed** | config-consistent on reproduce |
| `.mise/conf.d/bailiff-mod-moon.toml` | **managed** | moon tool; mise merges at runtime |

- `monorepo_packages` frozen → explicit `projects:` map (one entry per path).
- monorepo layout without frozen packages → glob discovery over the standard
  base dirs (`apps/*`, `packages/*`, `services/*`, `libs/*`).
- single-package layout → **warn-and-render** (ledger FR-010): the preflight
  warns "moon is primarily a monorepo workspace tool; single-package config
  will be minimal" and renders a valid root-project workspace — never a
  refusal, never a broken file.

## Questions

| Key | Type | Default | Notes |
|---|---|---|---|
| `monorepo_packages` | yaml | `[]` | frozen fact; explicit projects map |
| `monorepo_tool` | str | `moon` | the answer this module supplies (producer for `moon` alias) |

Facts read from base via `_external_data`:

| Fact | Source |
|---|---|
| `layout` | `_external_data.base.layout` |

Tasks: one trust-gated mise preflight, init-only-guarded via the committed
`.bailiff-moon-preflight` sentinel.

Edge: `depends_on: [bailiff-mod-base]`; phase `normal`.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-moon.git <destination>
```
