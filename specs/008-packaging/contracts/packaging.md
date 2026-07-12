# Contract — clerk skill packaging + APM marketplaces (spec 008)

clerk is distributed as an APM package (a skill + bundled deterministic script +
vendored core), installable into Claude Code, Codex, or an APM-managed project. This
uses APM's own `pack`/`publish`/`marketplace` tooling — no bespoke mechanism.

## `apm.yml` — the marketplace block (VERIFIED against the live `apm` CLI, 2026-07-10)

Scaffolded by `apm marketplace init --name clerk --owner copier-clerk`, then edited.
The real schema (captured from a throwaway spike) is a nested
`marketplace.outputs.{claude,codex}` map — NOT `marketplace.claude/codex`:

```yaml
name: clerk
version: 0.1.0
description: Agentic conductor for copier — skill + bundled scripts.
license: Apache-2.0              # REQUIRED — else the SBOM records NOASSERTION (pack warns)

marketplace:
  owner:
    name: copier-clerk
    url: https://github.com/copier-clerk
  build:
    tagPattern: "v{version}"     # default version-range resolution
  outputs:
    claude: {}                   # → .claude-plugin/marketplace.json (profile default path)
    codex: {}                    # → .agents/plugins/marketplace.json (the Codex target)
  packages:
    - name: clerk
      description: Agentic conductor for copier — a skill + bundled deterministic scripts.
      source: ./packages/clerk   # LOCAL-path source: clerk ships itself (not a remote git tag)
      version: 0.1.0
      category: Productivity      # HARD REQUIREMENT when outputs includes codex (pack errors without it)
      # tag_pattern: "{name}-v{version}"   # per-package tag (monorepo); omit for repo-wide lockstep
      # subdir: path/inside/repo           # optional
```

**Verified facts (spike):**
- Enabling `codex` in `outputs` makes `category:` **mandatory on every package** —
  `apm pack` exits with `marketplace config error: packages must define 'category'`
  otherwise. This is the one hard gate for the Codex target.
- Output paths are profile defaults: **claude → `.claude-plugin/marketplace.json`**,
  **codex → `.agents/plugins/marketplace.json`**. Override per output with a `path:`
  key under `outputs.<name>`.
- `source: ./packages/clerk` (local path) is a first-class package source — the right
  shape for clerk shipping *itself* rather than resolving from a remote tag.
- Missing `license:` only warns (SBOM NOASSERTION); missing Codex `category:`
  hard-errors.

## Build command (VERIFIED)

```sh
apm pack --marketplace=claude,codex            # build both (long form; -m is the short flag)
apm pack --marketplace=claude,codex --dry-run  # preview: prints each target → output-path
apm pack --marketplace=claude,codex --json     # machine-readable: .marketplace.outputs[].path
```

Dry-run and real build both confirmed writing the two manifests to the paths above.

## Package layout (what installs into a consumer project)

Mirrors the `secrets-scan` reference package:

```text
.apm/skills/clerk/
  SKILL.md                    # the portable phase-1 conductor (auto-triggers by semantics)
  scripts/
    clerk.py                  # the bundled entrypoint (PEP 723 header + preflight)
    clerk/                    # VENDORED src/clerk/*.py — discovery, runner, catalog,
      discovery.py            #   ordering, trust, errors, _preflight
      runner.py catalog.py ordering.py trust.py errors.py _preflight.py
.claude-plugin/plugin.json    # { name, version, description, author, license, skills: "./.apm/skills" }
apm.yml                       # package metadata
CHANGELOG.md
```

- **No PyPI `clerk`**: `import clerk.*` resolves from the vendored copy next to the
  script (the script inserts its own dir on `sys.path`, or the vendored package sits
  importably beside it). Spec 010 invariant held.
- The vendored `clerk/` is **generated** from `src/clerk/` at pack time (`just
  vendor`) and **drift-checked** (`just check-vendor` fails if it diverges).

## Generated manifest shapes (VERIFIED — they differ per target)

`apm pack` emits two structurally different manifests; clerk does NOT hand-write
either — but the contract records them so the `apm.yml` is authored to produce the
right content. **Claude** (`.claude-plugin/marketplace.json`) — flat `source` string:

```json
{
  "name": "clerk",
  "owner": { "name": "copier-clerk", "url": "https://github.com/copier-clerk" },
  "plugins": [
    { "name": "clerk", "description": "…", "version": "0.1.0", "source": "./packages/clerk" }
  ]
}
```

**Codex** (`.agents/plugins/marketplace.json`) — structured `source` object + a
`policy` block + the required `category`:

```json
{
  "name": "clerk",
  "interface": { "displayName": "clerk" },
  "plugins": [
    {
      "name": "clerk",
      "source": { "source": "local", "path": "./packages/clerk" },
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
      "category": "Productivity"
    }
  ]
}
```

The `description`/`displayName` come from the package + marketplace config; the
`policy` defaults are APM-generated. Consumer install steps vary per assistant —
see APM's "publish to a marketplace / consume from any assistant" docs.

## Dependency preflight (`scripts/clerk.py` startup + `clerk doctor`)

clerk's third-party runtime deps: `copier>=9.16,<10`, `pyyaml`, `packaging`,
`tomli-w`. On any invocation, before dispatch:

1. Try importing each. All present → proceed silently.
2. Any missing → print a clear message naming the missing dep(s) + an
   **environment-aware install suggestion**, then exit non-zero (do NOT run, do NOT
   auto-install, never surface a raw `ImportError`/traceback).
3. Manager detection (first on PATH wins, documented order): `uv` → `uv pip install
   <deps>` (or `uv add` in a project); `pipx`; `pip`/`pip3`; `brew` (only if the dep
   is brew-installable) → suggest the matching command. None detected → generic
   `pip install <deps>` + a pointer to install uv/pipx.

`clerk doctor` runs the same check explicitly and reports readiness (exit 0 ready /
non-zero with the suggestion). Deterministic, stdlib-only, no LLM.

### PEP 723 header (opt-in ergonomics)

`scripts/clerk.py` carries:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["copier>=9.16,<10", "pyyaml", "packaging", "tomli-w"]
# ///
```

So `uv run scripts/clerk.py …` auto-provisions in an ephemeral env for uv users.
The header's dependency list and the preflight's checked list share ONE source of
truth (the preflight reads/derives from the same constant), so they cannot drift.

## Build + release (documented, gated)

```sh
just vendor            # copy src/clerk → packages/clerk/.apm/skills/clerk/scripts/clerk/
just check-vendor      # fail if the vendored copy drifts from src/clerk
apm pack --marketplace=claude,codex          # build both manifests to their profile paths
apm marketplace validate .claude-plugin/marketplace.json   # validate each manifest
apm marketplace validate .agents/plugins/marketplace.json

# release (gated):
apm pack --marketplace=claude,codex --check-versions --check-clean   # exit 3 = version drift, 4 = stale output
apm publish --package copier-clerk/clerk                             # (when the registries feature is adopted; deferred v1)
```

- The generated manifests (`.claude-plugin/marketplace.json` +
  `.agents/plugins/marketplace.json`) are **committed** and served via a stable raw
  URL (Q-008c) — consumers add the marketplace by that URL.
- `--check-versions` (exit 3) enforces the configured versioning strategy;
  `--check-clean` (exit 4) fails if a committed manifest is stale vs a fresh
  regenerate (working-tree drift).
- v1 ships marketplace **artifacts** (self-hostable); `apm publish` to a registry is
  adopted when the experimental `registries` feature is stable (Q-008b).

## Exit codes

| Surface | Code | Meaning |
|---|---|---|
| `clerk.py` preflight / `clerk doctor` | 0 | all deps present / ready |
| | non-zero (documented, e.g. 1) | a dep is missing — suggestion printed, no run |
| `apm pack --check-versions` | 3 | package version misaligned with strategy |
| `apm pack --check-clean` | 4 | committed marketplace output is stale |
| existing clerk verbs | 0/1/2/3 | unchanged (spec 010/002/003) |

## Out of scope (deferred — see spec.md "Deferred")

Template fan-out to `clerk-mod-*` repos, cocogitto monorepo release, `catalog.json`
generation + hosting, the "clerk-fanout" GitHub App, and the `new-module` /
`check-modules` authoring tooling. Those operate on templates that do not exist
until spec 009; ADR-0006 keeps their design binding for that later spec.
