# bailiff-mod-devcontainer

Renders `.devcontainer/devcontainer.json` for a reproducible containerized dev environment.

## Outputs

| File | Lifecycle | Notes |
|---|---|---|
| `.devcontainer/devcontainer.json` | **managed** | config-consistent on reproduce |

## Design

- **Fixed base image**: `mcr.microsoft.com/devcontainers/base:ubuntu`. No `devcontainer_image` question — edit the file after scaffold for a different image.
- **mise feature**: `ghcr.io/devcontainers-extra/features/mise:1` installs mise in the container.
- **Bare `postCreateCommand`**: runs `mise trust && mise install` without an explicit tool list. mise reads the merged `.mise/conf.d/` drop-ins written by base and language modules, so the container installs the same tool set as the host.
- **Zero `_tasks`**: pure render; reproduce needs no toolchain or network.

## Questions

| Key | Type | Default | Notes |
|---|---|---|---|
| `project_name` | str | read from base answers | devcontainer `name` field |

`project_name` is read from `_external_data.base.project_name` (`.copier-answers.bailiff-mod-base.yml`). Base must be present in any stack that includes this module.

Edge: `depends_on: [bailiff-mod-base]`, `phase: normal`.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-devcontainer.git <destination>
```
