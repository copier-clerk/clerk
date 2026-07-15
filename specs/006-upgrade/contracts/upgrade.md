# Contract — bailiff upgrade invocation + migrations + multi-layer ordering (spec 006)

bailiff drives `copier update` per layer in dependency order (DAG re-solved at
target versions). copier owns the 3-way merge and migration execution; bailiff
supplies the version announcement, the cross-template ordering, and the conflict
report. Nothing bailiff-authored is committed to encode the upgrade state; the new
`_commit` in each layer's answers file is the complete record.

---

## Prerequisites

- **Clean git working tree.** Before any clone or write, bailiff checks `dest` with
  `git status --porcelain`; if it is dirty, bailiff raises `DirtyWorktreeError`
  (exit 1) and does nothing. Two reasons converge on this: (1) a multi-layer upgrade
  commits each layer between layers via `git add -A`, which would otherwise sweep the
  user's unrelated uncommitted work into a bailiff commit; (2) copier's own
  `run_update` refuses a dirty tree even in `pretend` mode. Checking up front lets
  bailiff surface one clear "commit or stash first" message instead of copier's cryptic
  mid-run "repository is dirty" error. A path that is not a git repo is not bailiff's
  precondition to enforce (copier surfaces that itself).

---

## The upgrade run-spec

An extension of the spec 003 multi-template run-spec shape. Single-layer is the N=1
case (same code path).

```yaml
dest: "./my-project"          # required; must have ≥1 .copier-answers*.yml
vcs_ref: "v1.2.0"             # optional; null = latest PEP 440 tag per layer
pretend: false                 # dry-run: no writes; report what would change
conflict: "inline"             # "inline" (default) or "rej"
skip_tasks: false              # suppress _tasks during update (see Q-006c below)
```

Single-layer projects: `dest` is sufficient; `vcs_ref` targets the single layer.
Multi-layer projects: `vcs_ref` (if set) applies to ALL layers (Q-006d: per-layer
ref map is a future extension; use the run-spec for now if per-layer targeting is
needed).

The skill authors this from the announced from→to decision + trust consent. The
deterministic phase (`scripts/bailiff.py update`) executes it LLM-free.

---

## run_update canonical invocation (per layer)

```python
from copier import run_update

run_update(
    dst_path=dest,
    data=answers,            # threaded accumulated answers (prior layers + layer-own)
    answers_file=rel_answers, # layer's answers file, relative to dest
    vcs_ref=vcs_ref_or_none, # target version (None = latest); string or VcsRef
    defaults=True,           # safety net for un-supplied answers
    overwrite=True,          # overwrite non-conflict files
    quiet=True,
    conflict=conflict,       # 'inline' or 'rej'
    pretend=pretend,
    settings=settings,       # from copier settings.yml trust: list (NOT unsafe=True)
)
```

**Trust**: `settings=` carries the user's trust list (same mechanism as init/
reproduce, ADR-0001). `unsafe=True` is NOT used. An untrusted source with
`_migrations` or `_tasks` raises `UntrustedSourceError` (exit 3) before any
`run_update` call.

**Answers threading**: same as spec 003's init — accumulated `data=` dict carries
prior layers' answers into later layers. At upgrade the accumulated dict starts
from the COMMITTED answers (read from each layer's `.copier-answers*.yml`) plus any
per-layer overrides in the run-spec.

---

## Migration format + trust gating

### New format (required)

Each entry in `_migrations` is one of:

```yaml
_migrations:
  # Form 1: bare command (string) — runs at 'after' stage by default
  - "echo 'migration ran'"

  # Form 2: bare command list — runs at 'after' stage
  - ["python", "scripts/migrate.py"]

  # Form 3: dict with optional version + condition + working_directory
  - command: "python scripts/migrate_to_v1_1.py"
    version: "v1.1.0"          # version-crossing filter (optional)
    when: "{{ _stage == 'after' }}"   # Jinja condition (optional; default = after)
    working_directory: "."     # relative to dest (optional; default ".")
```

**Version-crossing filter** (when `version:` present): copier runs this migration
only if `target_version >= entry_version > from_version`. bailiff's discovery
validates the format statically but does NOT evaluate the version condition —
copier applies it at runtime.

### Deprecated format (REJECTED)

```yaml
# REJECTED — bailiff refuses this at discovery; do not author
_migrations:
  - version: "v1.1.0"
    before:
      - "echo before"
    after:
      - "echo after"
```

The deprecated form has `before` or `after` as dict keys (not a `command:` key).
`discovery.py` checks for this pattern in the static `copier.yml` parse and raises
`DeprecatedMigrationFormatError` (exit 1) before `run_update` is called.

**Detection rule**: any `_migrations` entry that contains a `before` or `after`
key is the deprecated form. This is a static YAML check — no copier runtime call.

### Trust gating

Migrations run code → trust-gated identically to `_tasks`. `discovery.discover`
already checks `has_tasks` and `jinja_extensions` for trust pre-checks.
`_check_migrations_format` adds: also check `has_migrations` (template has any
`_migrations` entries). If `has_migrations` is true and the source is untrusted →
`UntrustedSourceError` before `run_update`.

This means: a template with `_migrations` in an untrusted source is refused at the
pre-check stage (same exit 3 as `_tasks`). The user must trust the source first.

---

## Multi-layer update ordering

### DAG re-solution (distinct from reproduce-time recomputation)

At upgrade, the DAG is rebuilt against the **target template versions** (not the
committed pinned versions used at reproduce-time):

1. For each committed answers file in `dest`, read `_src_path`.
2. Discover each template at the **target version** (`vcs_ref` if given, else
   latest PEP 440 tag via `discovery.list_versions`).
3. Read `dependency_edges` from that discovery (same static parse).
4. Call `ordering.build_dag(records, edges_by_basename)` + `ordering.topo_sort` —
   same functions, same stable tie-break as spec 003.
5. Upgrade layers in that topological order.

This means: if template B at v1.1.0 adds `depends_on: [A]` that was not present
at v1.0.0, the new edge IS reflected in the re-solved DAG (i.e. A upgrades before
B when both are being upgraded).

### New dependency (Q-006b — resolved: refuse)

If the re-solved DAG contains a dependency on a template that is NOT in the current
project (no committed answers file for that template), bailiff MUST:

1. Detect the dangling edge in `ordering.build_dag` (same `OrderingError` as init).
2. Surface a clear message: "Template `<B>` at version `<v1.1.0>` now depends on
   `<C>`, which is not in this project. Add `<C>` first (`scripts/bailiff.py init …`)
   before upgrading `<B>`."
3. Exit 1 (same as other `OrderingError` cases).
4. Write nothing.

This is the same policy as spec 003's dangling-edge handling (refuse + name it),
consistent with the principle of no surprise layers.

---

## Conflict surfacing

After each `run_update` call, bailiff scans the destination tree for conflict markers
and reports them.

**Detection**: scan all files in `dest` (recursively, excluding `.git`) for the
line pattern `<<<<<<< ` (the standard git/copier conflict marker prefix). If found,
collect the relative paths of all conflicted files.

**Behaviour**:
- `conflict='inline'` (default): copier writes inline `<<<<<<< / ======= / >>>>>>>`
  markers. Bailiff detects them post-update, names the files, and raises
  `MergeConflictError` → exit 4.
- `conflict='rej'`: copier writes `.rej` files instead. Bailiff detects `.rej` files
  post-update, names them, raises `MergeConflictError` → exit 4.

In either case the project is left in the partially-upgraded state so the user can
resolve the conflicts and rerun. Bailiff does NOT auto-resolve conflicts or revert.

---

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success (clean upgrade, or `--pretend` preview complete) |
| 1 | `BailiffError` / `DirtyWorktreeError` / `OrderingError` / `DeprecatedMigrationFormatError` / `DowngradeError` / other bailiff error |
| 2 | argparse usage error |
| 3 | `UntrustedSourceError` — source has migrations/tasks and is untrusted |
| 4 | `MergeConflictError` — upgrade completed but conflicts remain; named paths in output |

Exit code 4 is distinct from exit 1 so callers (CI, skill steps) can distinguish
"hard failure" from "soft: conflicts to resolve."

---

## Announced output format

Before any `run_update` call, bailiff writes to stdout (one line per layer):

```
Upgrading <layer-basename>: <from_commit> → <to_version>
```

Example for a multi-layer upgrade:
```
Upgrading bailiff-mod-base: abc1234 → v1.2.0
Upgrading bailiff-mod-python: def5678 → v1.2.0
```

Where `from_commit` is the short `_commit` SHA from the answers file and
`to_version` is the target version string.

On completion (per layer, in order):
```
  ✓ bailiff-mod-base upgraded to v1.2.0
  ✓ bailiff-mod-python upgraded to v1.2.0
```

On conflict:
```
  ✗ bailiff-mod-python: merge conflict in src/main.py — resolve and re-run upgrade
```

---

## Copier-only fallback

A user without bailiff can upgrade a single layer manually:

```bash
# Single-layer project
copier update --vcs-ref v1.2.0 --defaults --overwrite ./my-project

# Multi-layer: upgrade each layer in dependency order (derivable from copier.yml edges)
copier update --vcs-ref v1.2.0 --defaults --overwrite \
  -a .copier-answers.bailiff-mod-base.yml ./my-project
copier update --vcs-ref v1.2.0 --defaults --overwrite \
  -a .copier-answers.bailiff-mod-python.yml ./my-project
```

bailiff automates the ordering; nothing about the project *requires* bailiff for the
upgrade — the committed answers files carry the layer state and copier's own
`update` command works per-layer.

---

## Open question references (for implementers)

- **Q-006c**: verify whether copier's `skip_tasks=True` also suppresses
  `_migrations` in `run_update`. Source-check `copier/_main.py` Worker.run_update
  path: look for whether `migration_tasks` is called only when `not skip_tasks` or
  unconditionally. If separate, expose `--skip-migrations` as a distinct flag.
- **Q-006d**: per-layer `vcs_ref` mapping. For now, a single `--vcs-ref` applies
  to all layers. Add per-layer support only when a user needs it (YAGNI).
