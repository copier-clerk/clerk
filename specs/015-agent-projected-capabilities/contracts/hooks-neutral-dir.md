# Contract — `.hooks.d/` neutral hook dir + manager projection (spec 015)

The manager-agnostic hook-intent surface and how each hook-manager module projects it
into its own config format. Governs FR-013..016. The first proving instance of the
`_agent_tasks` contract (`agent-tasks.md`).

## 1. Two hook surfaces, by design (D1)

| Surface | Shape | Consumer | Tier |
|---|---|---|---|
| `.pre-commit.d/<vendor>-<module>.yaml` | pre-commit-native `repos:` fragment | pre-commit bundler `_post_task` (mechanical) | 2 — no agent |
| `.hooks.d/<module>.yaml` | neutral hook description (§2) | ANY selected hook manager, via `_post_agent_tasks` (agent) | 3 — cross-format |

`.pre-commit.d/` is unchanged from spec 014. `.hooks.d/` is the escalation for hooks
that must reach a non-pre-commit manager. A module MAY write either or both; a module
that only targets pre-commit keeps its `.pre-commit.d/` fragment and need not adopt
`.hooks.d/`. 015 does NOT migrate existing language modules — that churn is a later spec
once ≥2 managers are in wide use.

## 2. Neutral `.hooks.d/<module>.yaml` schema

Descriptive intent, NOT a config superset (a static superset was rejected in spec.md —
it cannot cover unknown third-party managers):

```yaml
# .hooks.d/bailiff-mod-python.yaml — managed by bailiff-mod-python.
# Consumed by whichever hook-manager module is selected (spec 015). Inert if none.
hooks:
  - id: ruff                    # stable hook identifier
    language: python            # informational; the language family the hook serves
    entry: "ruff check --fix"   # the command a local hook runs
    files: "\\.py$"             # regex the hook matches (manager translates as needed)
    stages: [pre-commit]        # lifecycle stages: pre-commit | commit-msg | pre-push
    pass_filenames: true        # optional; default true
```

Fields: `id` (required), `entry` (required), `language`, `files`, `stages`
(default `[pre-commit]`), `pass_filenames`. A manager module's agent task renders these
neutral fields into its backend's block; unknown backends interpret the same fields.
The fragment renders UNCONDITIONALLY (like `.pre-commit.d/`) — it is inert data until a
manager consumes it.

## 3. Manager projection (D3)

Each hook-manager module declares a `_post_agent_tasks` slot that projects ALL
`.hooks.d/*.yaml` entries into its format. It reads `.hooks.d/`, never another manager.

- **`bailiff-mod-precommit`** — `_post_agent_tasks.pre`: project `.hooks.d/` entries into
  pre-commit `repos:` blocks written to a `.pre-commit.d/` fragment BEFORE the mechanical
  bundler `_post_task` runs, so the bundler merges them alongside native fragments. Net:
  `.hooks.d/` and `.pre-commit.d/` both land in `.pre-commit-config.yaml`.
- **`bailiff-mod-lefthook`** (NEW) — `_post_agent_tasks.post`: project `.hooks.d/` entries
  into `lefthook.yml` after the render loop. Ships the reproducibility answers-file
  template; `depends_on: [bailiff-mod-base]`; `_bailiff_phase: normal`.

Exactly one hook manager per stack (they occupy the same capability slot). No manager
selected → nothing reads `.hooks.d/` → no hook config file is written (FR-014 / US2).

## 4. Freeze (from `agent-tasks.md` §4)

The projection is agent work: its output (the rendered `.pre-commit.d/` fragment or
`lefthook.yml`) is frozen into the manager module's `_agent_frozen` record at init and
replayed on reproduce — no agent, deterministic. If a projection writes a MANAGED-render
path, the reproduce-safety lint (§5 of `agent-tasks.md`) requires it be frozen.

## 5. Acceptance (US1/US2/US5 → SC-001/002)

- `[base + python + lefthook]` init → `lefthook.yml` contains the ruff hook translated
  from `.hooks.d/bailiff-mod-python.yaml`; no `.pre-commit-config.yaml`.
- `[base + python + precommit]` init → ruff reaches `.pre-commit-config.yaml` (via either
  the native `.pre-commit.d/` fragment or the projected one — both valid, ruff appears
  once after bundler dedup).
- `[base + python]` (no manager) → neither hook config file exists; `.hooks.d/` present
  and inert.
- Reproduce of any of the above → byte-consistent, no agent invoked.
