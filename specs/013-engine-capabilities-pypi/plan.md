# Implementation Plan: bailiff engine — PyPI packaging, multi-catalog, listing cache, collision check, capability tags (spec 013)

**Branch**: `013-engine-capabilities-pypi` (spec dir `013-engine-capabilities-pypi`) |
**Date**: 2026-07-14 | **Spec**: [spec.md](./spec.md)

**Input**: [spec.md](./spec.md) + the ratified decision ledger
(`specs/013-engine-capabilities-pypi/decisions-ledger.md` — FR-021 prerequisite).
Governed by the constitution (**v2.3.0** at plan time; this plan amends it to **v3.0.0**
per FR-018) and ADRs 0001–0007 + the new **ADR-0008** (PyPI packaging + repositioning).

## Summary

Deliver five interrelated engine work streams:

1. **Constitution amendment** (v2.3.0 → v3.0.0 MAJOR): lift the current prohibition in
   Principle I on `[project.scripts] bailiff` and `uvx bailiff PyPI tool`; scope C-11 in
   the roadmap to module-authoring specs; write ADR-0008 recording the repositioning
   (bailiff = the tool; bailiff-mod-* = the modules). This is a MAJOR version bump because
   Principle I is being redefined, not materially expanded — the same class as v1.0.0 →
   v2.0.0. **Release gate for all PyPI publish** (FR-018).

2. **CLI packaging**: extract the verb dispatch from `scripts/bailiff.py` into
   `src/bailiff/cli.py` and add `[project.scripts] bailiff = "bailiff.cli:main"` to
   `pyproject.toml`; declare `platformdirs` as an explicit runtime dependency; single-
   source `bailiff.__version__` via `importlib.metadata` with a bare-checkout fallback.

3. **Capability tags** (informational, warn-only): static YAML parsing of
   `_bailiff_provides` and `_bailiff_exclusive` in `discovery._describe()`, threaded through
   `Discovery` → `TemplateRecord` → `FullListing`; `generate_catalog.py` emits the
   fields; `check_modules.py` lints well-formedness + first-party mixed-group; the
   `init_many()` capability-conflict warning (group-infection semantics, incremental-add
   path).

4. **Init-time file-collision check**: pre-render overlap scan in `init_many()` before
   any real write; new `CollisionError` in the `BailiffError` hierarchy; renders each
   selected layer into an isolated temp dir, compares file sets, hard-stops on overlap.

5. **Multi-catalog precedence + listing cache**: first-listed-wins bare-name resolution
   in `validate_selection()` (replacing the ambiguity `CatalogError`); `shadowed` field
   on `TemplateRecord`; persisted listing under the platformdirs cache dir; `bailiff
   catalog refresh` writes the cache; `list` and `validate` read the cache.

Stack presets (FR-017) are OPTIONAL SCOPE: flagged in the NEEDS CLARIFICATION section
below; the plan is written to accommodate them in a named extension task without
blocking any other work stream.

## Technical Context

**Language/Version**: Python 3.11+. Engine code in `src/bailiff/`. No new third-party
libraries beyond `platformdirs` (already imported in `src/bailiff/`, now made explicit);
the collision-check approach (isolated temp-dir renders) reuses `run_copy` which is
already in-tree.

**Primary Dependencies**: `copier>=9.16,<10` (unchanged); `platformdirs` (newly
declared explicit runtime dep — was transitive via copier); `packaging>=26.2`;
`pyyaml>=6.0.3`; `tomli-w>=1.2.0`; `importlib.metadata` (stdlib, 3.10+). Build backend:
`hatchling` (unchanged).

**Storage**: persisted listing cache at
`user_cache_path("bailiff", appauthor=False) / "listing.json"` (platformdirs). Nothing is
written into generated project trees.

**Testing**: existing `pytest` suite under `tests/`; new unit tests for each new
function (capability parsing, collision scan, precedence, cache). The collision scan
uses `run_copy` into isolated temp dirs — the test harness stubs the `run_copy` call
(or uses an in-repo fixture template) so the suite stays hermetic and offline. SC-003
is the regression gate: existing loop tests MUST pass unmodified.

**Target Platform**: macOS/Linux/WSL; the packaged `bailiff` console command works from any
Python environment where the wheel is installed (system Python, venv, `uvx` ephemeral env).

**Constraints**:
- `runner.py` stays copier-public-API-only and subprocess-free (FR-020 / Constitution IV).
- Discovery never executes template code (capability parsing is static YAML reading,
  extending the existing `_bailiff_provides` pattern in `_describe()` — same safety class
  as `_tasks` / `_migrations` reading).
- `reproduce`, `reproduce_many`, `update`, `update_many` MUST NOT consult capability
  data or the collision scan (FR-012 / SC-008).
- Trust remains read-only in the deterministic core; no agent in any reproduce path.
- No PyPI publish before the FR-018 governance gate (SC-009).
- First publish is irreversible and maintainer-confirmed (SC-010).
- MI-1 stays out of scope; nothing here may preclude it (FR-022).

**Scale/Scope**: ~12 source files touched (errors.py, discovery.py, catalog.py,
cli.py NEW, \_\_init\_\_.py, runner.py, scripts/bailiff.py, generate\_catalog.py,
check\_modules.py, pyproject.toml, release CI workflow); ~8 new test files; 2 governance
documents (constitution.md, ADR-0008); 1 roadmap.md amendment.

## Constitution Check

*GATE: evaluated before Phase 0; re-checked after design. Constitution amended to
**v3.0.0** by this plan (FR-018) — the check below is against the amended text.*

| Principle | Verdict | How spec 013 satisfies it |
|---|---|---|
| **I — bailiff Is Skills + Templates + Minimal Glue (C-11)** | PASS (amended) | This spec IS the governed exception: FR-018 amends Principle I to permit the published CLI. C-11 scoped to module-authoring specs in the same amendment. CLI code belongs in `src/bailiff/` (the glue bucket, not a new architectural layer). |
| **II — Two-Phase; the Skill Conducts, Deterministic Helpers Execute** | PASS | Capability warnings, collision checks, and cache reads are all phase-2 mechanics in `init_many()` and `catalog.*`. No agent involvement. |
| **III — Reproduce Is Faithful and Agent-Free** | PASS | `reproduce`, `reproduce_many`, `update`, `update_many` are untouched. FR-012 explicitly prohibits capability/collision logic on those paths. |
| **IV — Prefer copier's CLI + Static Config** | PASS | Collision scan uses `run_copy` (public API). Capability parsing is static YAML reading (same safety class as `has_tasks`, `has_migrations`). No Template/Worker introduced. |
| **V — Determinism via Pinning; Trust by Source** | PASS | Cache is user-controlled (refresh). Capability declarations are statically parsed. Trust never written in deterministic core. |
| **VI — Template-Author Contract** | PASS | `_bailiff_provides`/`_bailiff_exclusive` are optional informational keys, never enforced semantically. No new required keys. |
| **VII — Hardening Is a Per-Step Mandate** | PASS | Every new function (capability parsing, CollisionError, collision scan, precedence warning, cache read/write, cli.py) ships with tests. SC-003 gate: existing loop tests pass unmodified. |
| **VIII — Documented, Dry-Run-Validated Handoff** | PASS (unlocked) | FR-019: Constitution VIII's own unlock clause is triggered — the packaged CLI, the collision check, and the capability-tag warning are genuine non-agent consumers of the handoff. Capability fields in catalog artifacts and `catalog list --json` are sanctioned. |

**No unjustified violations.** The single principle *redefined* is I (MAJOR bump
2.3.0 → 3.0.0), recorded in ADR-0008 and the sync-impact report embedded in the
amended constitution per the established governance pattern.

## Project Structure

### Governance documents (spec 013 — authored in this plan phase)

```text
specs/013-engine-capabilities-pypi/
├── spec.md                 # source of truth
├── plan.md                 # this file
├── decisions-ledger.md     # FR-021 prerequisite (must exist before plan phase)
└── tasks.md                # task list (companion to this plan)

.specify/memory/constitution.md        # amended I + sync-impact → v3.0.0
.specify/memory/roadmap.md             # C-11 scoped to module-authoring specs
docs/decisions/0008-pypi-packaging-repositioning.md  # NEW ADR
```

### Source files touched

```text
# Engine
src/bailiff/__init__.py            # single-source __version__ via importlib.metadata
src/bailiff/cli.py                 # NEW: extracted dispatch from scripts/bailiff.py
src/bailiff/errors.py              # add CollisionError
src/bailiff/discovery.py           # _describe() reads _bailiff_provides/_bailiff_exclusive; Discovery gains provides + exclusive
src/bailiff/catalog.py             # TemplateRecord + listing extension; cache funcs; precedence fix
src/bailiff/runner.py              # init_many: capability warning + collision scan (pre-render); NO change to reproduce/update paths

# Packaging
pyproject.toml                   # [project.scripts]; platformdirs dep; version stays 0.1.0 until publish

# Bundled script
scripts/bailiff.py                 # thin shim → bailiff.cli.main() (end-state: NEEDS CLARIFICATION — see below)

# CI tooling
scripts/generate_catalog.py      # emit provides + exclusive fields
scripts/check_modules.py         # capability lint (well-formedness + mixed-group)

# Release workflow
.github/workflows/release.yml    # add uv build + PyPI publish step (OIDC preferred)
```

### Test files

```text
tests/
├── test_discovery_capabilities.py   # T005 unit tests
├── test_catalog_capabilities.py     # T006 unit tests
├── test_catalog_precedence.py       # T011 unit tests
├── test_catalog_cache.py            # T012 unit tests
├── test_runner_capability_warning.py # T009 unit tests
├── test_runner_collision.py          # T010 unit tests
├── test_cli_packaging.py             # T013 wheel-install integration test
└── test_check_modules_capabilities.py # T008 unit tests
```

## Cross-cutting design

### Work stream 1 — Constitution amendment (FR-018)

Constitution I currently reads: "there is no `[project.scripts] bailiff` console entry,
no `uvx bailiff` PyPI tool." This is the explicit prohibition spec 013 overrides.

Amendment specifics:
- **Principle I rewritten**: replaces the three-item glue enumeration with one that
  names the packaged CLI as the THIRD form of glue alongside skill + templates — "the
  tool" repositioning. The "skills + templates + minimal glue" title stays; the text
  gains a paragraph permitting and scoping the published CLI. The bundled
  `scripts/bailiff.py` invocation path is retained (its end-state is NEEDS
  CLARIFICATION — see below) with a forward reference to FR-006 / ADR-0008.
- **C-11 scoped**: the roadmap's "New glue is justified only by a capability copier
  lacks" constraint is retained but scoped to module-authoring specs; spec 013 is the
  governed engine exception.
- **ADR-0008**: records the repositioning decision, the tradeoff (ergonomics of `uvx
  <dist-name> bailiff` vs prior skill-only model), the distribution-name situation
  (`bailiff` taken on PyPI — NEEDS CLARIFICATION on final choice), the FR-019
  Constitution VIII unlock scope, and the binding "11-zero decision" that capability
  declarations warn, never block.
- **Sync-impact report** embedded in constitution.md header comments (established
  pattern from v2.1.0, v2.3.0 amendments): bumps v2.3.0 → v3.0.0, MAJOR rationale,
  reconciled files list.
- **Retroactive 011 honor**: spec 011's FR-011 gate ("no new `src/bailiff/` code") stays
  textually intact for its own scope; ADR-0008 records that 013 is the governed
  exception not retroactively applicable to 011's deliverables.

### Work stream 2 — CLI packaging

**`src/bailiff/cli.py`**: extract the full `main()` function and all inner helpers
(`_build_parser`, `_run_preflight_or_exit`, `_cmd_doctor`, `_deferred_dispatch`,
`_real_dispatch`, `_print_catalog_table`) from `scripts/bailiff.py` verbatim, minus:
  - The dual-mode `sys.path` shim block (PEP 723 header + `_here`/`_vendored_pkg`
    path logic) — not needed in a proper package module.
  - The `if __name__ == "__main__": raise SystemExit(main())` guard.
  - The prog string changes from `"bailiff.py"` to `"bailiff"`.

`cli.py` imports `from bailiff._preflight import ...` and third-party modules exactly as
the script does now. The preflight-deferred dispatch pattern is preserved unchanged.

**`scripts/bailiff.py`**: **DELETED** (decisions-ledger FR-006 resolution, 2026-07-15).
Greenfield project with zero existing users — the PyPI CLI is the sole invocation path.
Skill uses `uvx bailiff`; repo contributors use `uv run bailiff` (editable
install). The PEP 723 header, dual-mode sys.path shim, and bare-checkout fallback are all
eliminated.

**`pyproject.toml`**:
- Add `[project.scripts] bailiff = "bailiff.cli:main"`.
- Add `"platformdirs"` to `[project.dependencies]` (currently only transitive via
  copier; directly imported in `catalog.py:37`, `trust.py`, `defaults.py`).
- `version` stays at `"0.1.0"` until the first publish; the pre-publish version-bump
  is a separate maintainer-gated step.

**Single-source `__version__`** (`src/bailiff/__init__.py`):
```python
from importlib.metadata import version as _version
__version__: str = _version("bailiff")
```
No bare-checkout fallback is needed: the script is deleted, so `__version__` is only
accessed from an installed context (editable or wheel). If `importlib.metadata` raises
(broken install), the ImportError surfaces cleanly — better than silently reporting a
stale `"0.1.0"`.

**Distribution name** (FR-005): `bailiff` (decisions-ledger resolution, 2026-07-15).
The console command is `bailiff`. An explicit re-verification task runs immediately
before first publish regardless of which name is chosen.

### Work stream 3 — Capability tags

**`discovery._describe()` extension** (`src/bailiff/discovery.py:157`):
Read `_bailiff_provides` and `_bailiff_exclusive` from the raw YAML dict before
the existing key-iteration loop (same pattern as `has_tasks = bool(raw.get("_tasks"))`):
```python
provides: list[str] = list(raw.get("_bailiff_provides") or [])
exclusive: bool = bool(raw.get("_bailiff_exclusive", False))
```
Malformed values on third-party catalogs (non-list, non-bool, non-kebab-case entries)
are warned and treated as absent — never hard failures here. Add `provides` and
`exclusive` fields to the `Discovery` dataclass.

**`TemplateRecord` extension** (`src/bailiff/catalog.py:275`):
```python
provides: list[str] = field(default_factory=list)
exclusive: bool = False
shadowed: bool = False
```
`build_listing()` populates `provides`/`exclusive` from `disc.provides`/`disc.exclusive`
and sets `shadowed=True` for entries whose bare name has already appeared in an
earlier pointer (tracked in a `seen_bare_names: set[str]` across the pointer loop —
see work stream 5 for details).

`FullListing.to_dict()` extended to include `provides`, `exclusive`, `shadowed` per template.

**`generate_catalog.py`**: reads `_bailiff_provides` and `_bailiff_exclusive` from
each module's `copier.yml` (static read, already done for name/description) and emits
them in the module's `catalog.json` entry alongside the existing fields.

**`check_modules.py`** — two new lint rules for first-party modules only:
1. `_bailiff_provides` must be a list of strings matching `^[a-z][a-z0-9-]*$`
   (kebab-case); `_bailiff_exclusive` must be a boolean. Any violation → exit 1, naming
   the module and the malformed value.
2. Mixed exclusivity within one first-party capability group: if N≥2 first-party
   modules share a capability and only a strict subset declares `_bailiff_exclusive: true`,
   that group is flagged as an author-time error. All siblings of a pick-one family
   must declare it consistently.

**Capability conflict warning** (`src/bailiff/runner.py` — `init_many`):
A new `_check_capability_conflicts()` function, called from `init_many()` AFTER
`layer_plan()` and BEFORE the render loop:

```python
def _check_capability_conflicts(
    records: list[TemplateRecord],
    dest: str,
    exclusive_capabilities: frozenset[str],
) -> None:
```

Algorithm:
1. Collect the `provides` list from every record in `records` (the current selection).
2. Read existing `.copier-answers.*.yml` files in `dest` (if any); discover each
   recorded source at its `_commit` ref to get its `provides` list. These represent
   already-installed modules (incremental-add path).
3. Build a combined mapping: `capability → list[module_basename]` across both sets.
4. For each capability with >1 provider in the combined set: if the capability name
   is in `exclusive_capabilities` (i.e., ANY module in the merged catalog listing
   declares `exclusive: true` for it), emit the loud warning.

`exclusive_capabilities` is computed by the CLI before calling `init_many`: iterate
the full listing, collect all capability names where `any(t.exclusive for t in ...)`.
This ensures the group-infection rule uses the catalog-wide view, not just the
selected modules.

`init_many` signature gains an optional parameter:
`exclusive_capabilities: frozenset[str] = frozenset()`.

**FR-012 scope enforcement**: `reproduce`, `reproduce_many`, `update`, `update_many`
do NOT call `_check_capability_conflicts` — these functions are not touched.

### Work stream 4 — Init-time file-collision check

**`CollisionError`** added to `src/bailiff/errors.py`:
```python
class CollisionError(BailiffError):
    """Two selected modules would write the same managed destination path."""
    def __init__(self, path: str, modules: list[str]) -> None:
        self.path = path
        self.modules = modules
        super().__init__(
            f"file collision: modules {', '.join(modules)!r} would both write "
            f"{path!r}. Resolve the conflict before running init."
        )
```

**Pre-render overlap scan** in `init_many()`, called after the capability check and
BEFORE the main render loop (raising before any real write):

```python
def _scan_init_collisions(
    plan: list[tuple[TemplateRecord, str]],
    dest: str,
    accumulated: dict[str, Any],
    answers_map: dict[str, dict[str, Any]],
) -> None:
```

Mechanism: for each layer in `plan`, render into an isolated `tempfile.mkdtemp()`
directory using `run_copy(pretend=False, skip_tasks=True)`. The `skip_tasks=True`
parameter is a SAFETY REQUIREMENT: without it, task-bearing modules would execute their
`_tasks` (including `gh repo create`, git init, network calls) during the scan — the
scan must be side-effect-free. Collect the written file set (all files under the temp
dir, relative paths, excluding `.copier-answers*.yml`). Raise `CollisionError` on the
FIRST path seen in more than one layer's file set, naming the colliding path and both
module full-ids. Temp dirs are cleaned up regardless of outcome. Reuses the same
`run_copy` call shape already in `init_many`, same answers + trust + secrets pre-checks
(the layer already passed those before reaching this scan).

Rationale for full render vs. template-tree glob: a static glob of the template's
source tree would miss Jinja conditionals in filenames (e.g.
`{% if add_tests %}tests/{% endif %}conftest.py`). The isolated render is the only
approach that correctly observes conditional file generation. The cost (one extra
render pass per selected layer, to a temp dir) is tolerable for an interactive
`init` gate; the renders are discarded immediately after comparison.

**FR-013 scope**: collision scan runs ONLY in the non-check branch of `init_many`
(actual init). The `check=True` (preflight) branch already uses `pretend=True` and
writes nothing; the isolated-render scan cannot meaningfully run in pretend mode.
The check branch reports answer errors; the real-run branch checks file collisions.

### Work stream 5 — Multi-catalog precedence + listing cache

**Bare-name precedence** (`src/bailiff/catalog.py:validate_selection`):
Replace the bare-name ambiguity branch (catalog.py:462-466):

```python
# OLD: raise CatalogError("bare name ... is ambiguous")
# NEW: first-listed-wins with loud shadow warning
if len(matches) > 1:
    winner = matches[0]  # first in file order = first pointer
    shadowed = [t.full_id for t in matches[1:]]
    warnings.warn(
        f"SHADOW WARNING: bare name {fid!r} resolves to {winner.full_id!r} "
        f"(first pointer wins). Shadowed: {', '.join(shadowed)}. "
        f"Use full-ids to select shadowed entries directly.",
        stacklevel=2,
    )
    resolved.append(winner)
    continue
```

Uses `warnings.warn` (stdlib) rather than `print(..., file=sys.stderr)` so the warning
is always visible but suppressible in tests without redirection gymnastics. The CLI
surfaces it via the default warnings filter (visible to users).

**Shadowed entries in listings** (`build_listing()`):
Track seen bare names across pointers with `seen_bare_names: set[str]`. For each
template, derive `bare_name = full_id.split("/", 1)[-1]`; if already seen, set
`shadowed=True` on the record and DO NOT add it to `seen_bare_names` again (the first
pointer wins for bare-name resolution, but all entries appear in the listing).

**Listing cache** (`src/bailiff/catalog.py`):
New functions:
```python
def listing_cache_path() -> Path:
    """Return the platformdirs cache path for the persisted listing JSON."""
    return user_cache_path("bailiff", appauthor=False) / "listing.json"

def persist_listing(listing: FullListing, cache_path: Path | None = None) -> None:
    """Serialize listing to JSON at the cache path (mkdir -p parent)."""

def load_listing_cache(cache_path: Path | None = None) -> FullListing | None:
    """Deserialize the cached listing, or None if absent/corrupt."""
```

`build_listing()` is unchanged (it remains the expensive discovery call). A new
`build_and_cache_listing(catalog_path: Path) -> FullListing` composes them.

**`catalog refresh` verb**: calls `build_and_cache_listing()`, prints the path, exits 0.

**`catalog list` and `catalog validate` verbs**: call `load_listing_cache()` first;
if None, auto-build once (call `build_and_cache_listing()`), print a notice to stderr
so the user knows a slow operation ran. The per-call re-clone regime ends.

**Cache invalidation**: `catalog add`/`remove` do NOT automatically invalidate the
cache (documenting the stale-cache risk in a comment). `catalog refresh` always
rebuilds. This is the simplest correct behavior that ends the per-call re-clone regime;
`add`/`remove` followed by `refresh` is the documented workflow.

**`_print_catalog_table`** extended (in `cli.py`) to show capability tags and shadow marks:
```
  demo/bailiff-mod-python [tasks]
    provides:  python-project [exclusive]
    source:    https://...
    ...

  internal/bailiff-mod-python [tasks] [shadowed by demo/bailiff-mod-python]
    provides:  python-project [exclusive]
    ...
```

## How each governance deliverable is realized

- **FR-018 — Constitution amendment (v2.3.0 → v3.0.0)**: This is a MAJOR bump. Principle I
  is redefined (the v1.0.0 → v2.0.0 MAJOR established the "no published package" nature;
  v3.0.0 replaces it with the "bailiff is the tool" positioning). The amendment, the ADR
  (ADR-0008), the roadmap C-11 scope fix, and the sync-impact report ALL land in one
  change. **Gate: no `[project.scripts]` addition or PyPI publish before this change merges.**
  Engine code (capability tags, collision check, precedence, cache) may proceed on the
  branch without waiting for the amendment — none of those changes require the amended
  constitution — but the packaging changes ([project.scripts], first publish) are blocked.

- **FR-019 — Constitution VIII unlock**: ADR-0008 records the scope: the typed/JSON
  outputs (capability fields in catalog artifacts, `catalog list --json`) are sanctioned
  because genuine non-agent programs (the packaged CLI, the collision check, the capability
  warning computation) now consume the handoff. VIII's prohibition remains in force
  everywhere a real non-agent consumer does not exist.

- **FR-021 — Decisions ledger**: `specs/013-engine-capabilities-pypi/decisions-ledger.md`
  must exist BEFORE the plan phase begins (spec prerequisite, checked in T001).

## Build / test / release sequencing

1. **Phase 0 — Prerequisites** (T001-T002): Verify decisions-ledger.md exists. Verify
   green baseline (pytest, mypy, lint). Hard gates — nothing proceeds on red.

2. **Phase 1 — Governance** (T003): Constitution amendment + ADR-0008 + roadmap C-11
   scope + sync-impact report. **Gate for all PyPI publish** (not for engine code).

3. **Phase 2 — Engine subsystems** (T004-T012, parallel-eligible within groups):
   - T004 `CollisionError` in errors.py (prerequisite for T010)
   - T005 `Discovery.provides`/`exclusive` (prerequisite for T006, T009)
   - T006 `TemplateRecord` + `build_listing()` extension (prereq for T009, T012)
   - T007 `generate_catalog.py` capabilities (independent)
   - T008 `check_modules.py` capability lint (independent)
   - T009 capability warning in `init_many` (depends on T005, T006)
   - T010 collision scan in `init_many` + `CollisionError` (depends on T004)
   - T011 bare-name precedence + `shadowed` (independent)
   - T012 listing cache + refresh verb (depends on T006 for full TemplateRecord)

4. **Phase 3 — CLI packaging** (T013-T014): Extract `cli.py`, add `[project.scripts]`,
   `platformdirs` dep, single-source version. **Depends on Phase 1 governance gate
   (sanctioning `[project.scripts]`).** T013 also integrates the updated
   `_print_catalog_table` from work stream 5 (capability/shadow display).

5. **Phase 4 — Integration + verification** (T015-T016): Full test suite green. Wheel
   build + clean-venv install verification. `deptry`-style declared-dependency audit.

6. **Phase 5 — Release workflow** (T017): Add `uv build` + PyPI publish step to the
   release CI (OIDC trusted-publisher preferred). The step is added but NOT triggered
   until the maintainer-gated publish.

7. **Phase 6 — Maintainer-confirmed publish** (T018-T020, each reconfirm-gated):
   Re-verify name availability, resolve NEEDS CLARIFICATION items (distribution name,
   scripts/bailiff.py end-state, stack-presets scope), first publish. Irreversible.

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| Constitution v3.0.0 MAJOR bump | Principle I is being redefined (from "no published package" to "bailiff is the tool") — same redefinition class as v1.0.0 → v2.0.0 | A MINOR bump would misrepresent a principle redefinition as a guidance expansion; the versioning policy is explicit (MAJOR for backward-incompatible principle removals or redefinitions). |
| Isolated-temp-dir render for collision scan | Jinja conditionals in filenames can make static template-tree globs incorrect (a file may only be written under certain conditions) | Template-tree static glob misses conditional paths; copier `pretend=True` does not expose a file manifest; isolated renders are the correct observable output. |
| `exclusive_capabilities: frozenset[str]` as a caller-supplied parameter to `init_many` | Group-infection requires catalog-wide view (ANY provider in the listing declares exclusive = whole capability is select-1), but `init_many` only receives the selected modules | Passing the full listing object to `init_many` would give it catalog awareness it doesn't otherwise need; a pre-computed frozenset is the minimal interface that correctly implements FR-008 semantics. |
| Auto-build-once cache fallback | Users running `bailiff catalog list` for the first time get results without needing to know about `refresh` | "Instruct user to run refresh" is the simpler behavior but creates a confusing first-run experience; auto-build-once with an stderr notice is minimal extra complexity for a materially better UX. |

## NEEDS CLARIFICATION — RESOLVED (maintainer-ratified 2026-07-15)

All three items are resolved in `decisions-ledger.md` (§ NEEDS CLARIFICATION resolutions).
No task is blocked. Summary:

1. **FR-005 — Distribution name**: `bailiff` (status quo). Re-verify availability
   immediately before first publish (T018).
2. **FR-006 — Bundled-script end-state**: DELETE `scripts/bailiff.py`. The PyPI CLI is the
   sole invocation path. Skill uses `uvx bailiff`; repo contributors use
   `uv run bailiff`. T013/T014 updated accordingly.
3. **FR-017 — Stack presets**: DEFERRED to a follow-up spec. T021 is out of scope for first
   release. All other tasks proceed unchanged.
