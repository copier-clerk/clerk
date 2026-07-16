# bailiff-mod-devcontainer

Reproducible containerized dev environment (spec 012 / FR-005). Renders
`.devcontainer/devcontainer.json` whose toolchain derives from the **same
frozen `mise_tools` union** that `bailiff-mod-base` pins into `.mise.toml` —
the container and the host install the identical tool set, so there is zero
drift between "works on my machine" and "works in the container".

## Outputs

| File | Lifecycle | Notes |
|---|---|---|
| `.devcontainer/devcontainer.json` | **managed** | config-consistent on reproduce; derived from frozen `mise_tools` |

## Design

- **Fixed base image**: `mcr.microsoft.com/devcontainers/base:ubuntu`. There is
  deliberately no `devcontainer_image` question — the module's value is
  zero-decision reproducibility. Edit the file after scaffold if you need a
  different image.
- **mise feature**: `ghcr.io/devcontainers-extra/features/mise:1` installs mise
  in the container; `postCreateCommand` installs each frozen `mise_tools` entry
  at the exact pinned version.
- **Empty `mise_tools`**: renders a minimal valid `devcontainer.json` (base
  image + mise feature, no install command) — a valid no-op layer.
- **Zero `_tasks`**: pure render; reproduce needs no toolchain or network.
- **Single-writer discipline (M1)**: this module consumes `mise_tools`; it does
  NOT write `.mise.toml` (base is the single writer).

## Questions

| Key | Type | Default | Notes |
|---|---|---|---|
| `project_name` | str | threaded from base | devcontainer `name` field |
| `mise_tools` | yaml | `[]` | agent-frozen union, injected via `--data` |

Edge: `run_after: [bailiff-mod-base]`.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-devcontainer.git <destination>
```
