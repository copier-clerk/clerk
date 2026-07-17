# bailiff-mod-dep-updates

Automated dependency hygiene. ONE module with the `dep_update_tool
[renovate, dependabot]` choice axis: same question shape and output contract;
only the rendered syntax differs.

Default is `renovate` (agent/user overridable).

## Outputs (exactly one per init, per the chosen branch)

| Branch | File | Lifecycle |
|---|---|---|
| `renovate` | `renovate.json` | managed |
| `dependabot` | `.github/dependabot.yml` | managed |

Each config carries one entry per active ecosystem from the frozen
`dep_ecosystems` fact.

## Behavior notes

- Never deletes the other tool's file: the module writes only its own branch's
  file. Switching tools on a live project requires manual cleanup.
- Zero `_tasks`: pure managed renders; reproduce needs no toolchain or network.

## Dependencies

Requires `bailiff-mod-base` in the selection (`depends_on: [bailiff-mod-base]`).

## Questions

| Key | Type | Default | Notes |
|---|---|---|---|
| `dep_update_tool` | str | `renovate` | `renovate` or `dependabot` |
| `dep_ecosystems` | yaml | `[]` | frozen ecosystem ids in the chosen tool's vocabulary |

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-dep-updates.git <destination>
```
