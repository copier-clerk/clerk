# Contract — clerk catalog (spec 002)

The catalog lets a user point clerk at their **own** source repos and list the
templates they offer. It is user-owned config managed by `scripts/clerk.py`; it is
NOT a copier template and nothing catalog-related is written into a generated
project (the spec-010 invariant). Discovery is static (no template code, no trust).

## The catalog file (TOML)

Default path: `user_config_path("clerk")/catalog.toml` (same `platformdirs`/env
resolution `trust.py` uses); overridable with `--catalog PATH`. Local files only
(spec 002). Plain, hand-editable, and agent-manageable.

```toml
# One or more named catalog pointers. The name namespaces template full-ids.
[[catalog]]
name = "demo"                        # explicit; defaults to a sanitized basename if omitted
sources = [
  "copier-clerk/clerk-template-example",   # gituser/gitrepo — one repo = one template (ADR-0002)
  "acme/clerk-mod-python@v2.1.0",          # optional @ref: a display/standardization override ONLY,
]                                          #   NOT a reproduce pin (that lives in the project answers file)
```

- **Sources, not pins**: no mandatory `#ref`. An optional `@ref` overrides the
  discovery display version for teams standardizing a version; it does not become a
  reproduce pin (ADR-0002 / FR-007).
- **One source = one git repo = one template** (copier's `1 template = 1 repo`).
- **No `catalog.yml` in generated projects, no submodules, no generation CI**
  (ADR-0002/0003).

## `scripts/clerk.py catalog <verb>`

Run `./scripts/clerk.py catalog …` or `uv run scripts/clerk.py catalog …`. All verbs
accept `--catalog PATH` to target a non-default file. Errors print legibly to
stderr with a non-zero exit — never a bare stack trace.

### `catalog init [--name N]`
Create the catalog file if absent (idempotent — existing file is left untouched, a
notice is printed). Establishes an empty `[[catalog]]` with name `N` (or the default
name) so `add` has a home.

### `catalog add <source> [--name N] [--catalog PATH]`
Add `<source>` (locator, optional `@ref`) to catalog pointer `N` (default pointer if
omitted); **creates the file if absent**. Idempotent — a source already present is a
no-op, not a duplicate. Preserves unrelated entries.

### `catalog remove <source> [--name N]`
Remove `<source>` from pointer `N`. Idempotent — absent source is a no-op. Other
sources and file structure survive.

### `catalog list [--json] [--catalog PATH]`
Discover every source (statically) and emit the deterministic listing. Human table
by default; `--json` for the machine/agent shape. Same sources at same pins →
identical output (SC-002). A source that is unusable is reported with a reason and
does NOT appear as usable; other sources still list (FR-005).

### `catalog refresh`
Same discovery as `list` (freshness is explicit/manual — ADR-0002). `refresh` is the
verb the SKILL runs before presenting templates; `list` is its read view. (They may
be the same implementation; `refresh` exists as the documented "go fetch current
state" affordance.)

### `catalog validate <full-id> [<full-id> ...]`
The deterministic **selection gate** (FR-006). Exit 0 iff every id is present in the
discovered catalog. Unknown id → non-zero, message lists valid ids. Ambiguous bare
name (exists under >1 catalog) → non-zero, requires the full-id. No LLM judgment.

## The listing shape (`catalog list --json`)

Deterministic; per template, derived live from each source's static `discover`:

```json
{
  "catalogs": [
    {
      "name": "demo",
      "templates": [
        {
          "full_id": "demo/clerk-template-example",
          "source": "https://github.com/copier-clerk/clerk-template-example.git",
          "ref": "v1.0.0",
          "versions": ["v1.0.0"],
          "reproducible": true,
          "has_tasks": true,
          "questions": ["project_name", "org", "license", "description"]
        }
      ],
      "unusable": [
        { "source": "acme/broken", "reason": "no PEP 440 tag (copier cannot resolve a version)" }
      ]
    }
  ]
}
```

- `full_id` = `<catalog-name>/<template>`. `<template>` is the source repo basename.
- `questions` is the visible-question key list (from `discovery.Discovery.questions`);
  full per-question metadata is available via `scripts/clerk.py discover <source>`
  (spec 001, unchanged) — the listing summarizes, discover details.
- `reproducible: false` sources are listed under `unusable` with the reason (VI gate).

## Full-id + selection

- Identity is always the **full-id** `<catalog>/<template>` (FR-004). One or more
  catalog pointers supported; no unnamespaced first-wins lookup.
- The **agent** (phase 1) presents the listing and collects the user's pick
  (judgment). It then passes the chosen full-id(s) through `catalog validate` before
  init. `validate` is the mechanical gate that makes agent selection safe.
- 002 stops at a *validated selection*. Turning selection into ordered multi-template
  init is spec 003 (the DAG consumes the hidden `depends_on` edges already parsed by
  `discovery.py`). 002 injects nothing into a render; `--data catalog=[…]` (ADR-0003's
  verified render-scope fact) is retained for spec 007's apm module, not used here.

## Exit codes (catalog verbs)

| Code | Meaning |
|---|---|
| 0 | success (or idempotent no-op) |
| 1 | `CatalogError` — missing/malformed catalog file; unknown or ambiguous full-id at `validate` |
| 2 | argparse usage error / unknown verb |
| 3 | (unchanged) `UntrustedSourceError` — not reachable from catalog ops (discovery needs no trust) |
