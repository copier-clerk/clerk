# bailiff-mod-dep-updates

Automated dependency hygiene (spec 012 / FR-008). ONE module with the
`dep_update_tool [renovate, dependabot]` choice axis (FR-001: isomorphic
family — same question shape and output contract; only the rendered syntax
differs). The default **follows the repo host** (FR-004): `dependabot` when
GitHub-hosted, `renovate` otherwise — explicitly overridable.

## Outputs (exactly one per init, per the chosen branch)

| Branch | File | Lifecycle |
|---|---|---|
| `renovate` | `renovate.json` | **managed** |
| `dependabot` | `.github/dependabot.yml` | **managed** |

Each config carries one entry per active ecosystem from the frozen
`dep_ecosystems` fact (renovate: `enabledManagers`; dependabot: `updates`
entries).

## Behavior notes

- **Never deletes the other tool's file**: the module writes only its own
  branch's file. Switching tools on a live project leaves the old config
  behind — remove it manually.
- **dependabot on a non-GitHub host** (`github_host=false`): warn-and-render —
  the file still renders with a warning comment that dependabot only runs on
  GitHub-hosted repos. Renovate is the host-neutral branch.
- **Zero `_tasks`**: pure managed renders; reproduce needs no toolchain or
  network.

## Questions

| Key | Type | Default | Notes |
|---|---|---|---|
| `github_host` | bool | threaded from base | drives the axis default |
| `dep_update_tool` | str | `"{{ 'dependabot' if github_host else 'renovate' }}"` | the axis |
| `dep_ecosystems` | yaml | `[]` | frozen ecosystem ids in the chosen tool's vocabulary |

Edge: `run_after: [bailiff-mod-base]`.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-dep-updates.git <destination>
```
