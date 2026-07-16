# Decisions Ledger — spec 013 (engine, capabilities, PyPI)

**Source**: Ratified maintainer decisions from the 2026-07-14 adjudication session, plus
the 2026-07-15 maintainer resolution of this spec's NEEDS CLARIFICATION items. This file
is the in-tree authoritative record per the spec's FR-021 prerequisite: where spec.md is
silent, this ledger governs; where this ledger is silent, the item is out of scope for 013.

## Core positioning decision (ratified 2026-07-14)

**bailiff is the tool; bailiff-mod-\* are the modules.** The published CLI
(`uvx bailiff`) is the primary user-facing invocation path. The
`scripts/bailiff.py` bundled script is DELETED (see FR-006 resolution below) — the PyPI
package is the sole invocation mechanism; repo contributors use `uv run bailiff` via the
editable install. Constitution I must be amended (v3.0.0 MAJOR) to permit this.

## Capability design decisions (ratified 2026-07-14)

| Decision | Rationale |
|---|---|
| Capabilities are informational, warn-only, never block | Rely on module authors + selecting agent; enforce facts (collisions), not claims (labels) |
| Group-infection semantics for exclusivity | Err on the side of caution; one correct declaration catches absent-declaration mistakes in the sibling set |
| No closed vocabulary | Any kebab-case string is a valid capability name; no vocabulary governance needed |
| `_bailiff_exclusive` is self-referential only | Module descriptions must not name siblings (goes stale); exclusivity is a property of MY slot |
| Mixed exclusivity in first-party = author-time error (CI lint) | All siblings of a pick-one family should declare consistently |
| Capabilities apply at `init_many` only | `reproduce`/`update` never consult them (SC-008); a committed tree always reproduces regardless of tag changes |

### Group-infection design note

The group-infection rule applies across the entire merged catalog listing (not per-pointer).
If real-world multi-catalog noise materializes (a third-party declaring exclusive on a
capability you use composably), the designated fallback is to scope infection per catalog
pointer — a non-breaking refinement (the data model stays identical; only the frozenset
computation in the CLI narrows). This escape valve is recorded in ADR-0008.

## Collision check decisions (ratified 2026-07-14)

| Decision | Rationale |
|---|---|
| Pre-render overlap scan (isolated temp-dir renders with `skip_tasks=True`) | Static globs miss Jinja conditionals in filenames; the render is the only correct observable output. Tasks MUST be skipped to avoid side-effect execution during the scan. |
| Hard stop (`CollisionError`, exit 1) before any write | Fact-based enforcement; no escape hatch needed |
| init-only (never reproduce/update) | Committed trees always reproduce; collision is a selection-time concern |

### Performance note

Benchmarked at ~80ms per layer on the in-repo templates. At 30 modules (extreme case) the
scan adds ~2.4s to an interactive `init`. Acceptable — and the scan never runs on
reproduce/update.

### Safety requirement: `skip_tasks=True`

The collision-scan renders MUST pass `skip_tasks=True` to `run_copy`. Without it, task-
bearing modules would execute their `_tasks` (including `gh repo create`, git init, network
calls) during what should be a read-only overlap check. This is both a correctness
requirement (scan must be side-effect-free) and a safety requirement (scan must not create
external resources). copier's `run_copy` API supports this parameter (verified in copier
>=9.16).

## Multi-catalog decisions (ratified 2026-07-14)

| Decision | Rationale |
|---|---|
| First-listed-wins bare-name resolution | Replaces the ambiguity CatalogError; enables organizational overlay of internal catalogs |
| Shadow warning (loud, always) | Nobody should be surprised which module resolved |
| Shadowed entries stay in listings | Shadowing affects bare-name resolution, not visibility |
| Persisted listing cache with explicit `catalog refresh` | Ends the per-call re-clone regime; user controls staleness |
| Auto-build-once fallback when no cache exists | Better first-run UX than "run refresh first"; stderr notice prevents confusion |

## Constitution amendment (ratified 2026-07-14)

| Item | Decision |
|---|---|
| Bump class | MAJOR (v2.3.0 → v3.0.0) — Principle I is redefined, not expanded |
| C-11 scope | Scoped to module-authoring specs; spec 013 is the governed engine exception |
| ADR-0008 | Records repositioning, distribution-name rationale, FR-019 unlock, warn-not-block design, group-infection escape valve (per-pointer scoping) |
| 011 retroactive | Spec 011's FR-011 gate remains textually intact for its own scope |

## NEEDS CLARIFICATION resolutions (maintainer-ratified 2026-07-15)

| Item | Decision | Rationale |
|---|---|---|
| FR-005 distribution name | **`bailiff`** (invoked `uvx bailiff`) | Superseded by product rename (clerk → bailiff, 2026-07-15): the original `copier-clerk` resolution no longer applies. Distribution name is `bailiff`, already claimed and published (0.1.0) on PyPI via OIDC trusted publisher; matches the GitHub org (`bailiff-io`) and the console command. |
| FR-006 bundled-script end-state | **Delete `scripts/bailiff.py`** | Greenfield project with zero existing users. Skill uses `uvx bailiff`; repo contributors use `uv run bailiff` (editable install provides the entry point). Eliminating the script removes: the dual-mode sys.path shim, PEP 723 header maintenance, the "version must resolve without dist metadata" contortion, and Constitution I needing to bless two parallel invocation paths. |
| FR-017 stack presets | **Deferred** to a follow-up spec (013a or 014) | 013 already has 5 work streams and 21 tasks. No multi-pointer catalog exists in the wild yet — presets serve an audience that doesn't exist until multi-catalog ships and gets adopted. Presets are pure additive (optional TOML table; absence = current behavior exactly); deferring costs nothing and breaks nothing. |

## Plan amendments from NEEDS CLARIFICATION resolutions

1. **FR-006 (script deletion)**: T013 changes from "reduce script to thin shim" to "delete
   `scripts/bailiff.py`, update SKILL.md invocations to use `uvx bailiff`,
   simplify version mechanism (remove bare-checkout fallback guard)." T014 simplifies: no
   PEP 723 inline-deps maintenance, no bare-checkout version resolution test.
2. **`skip_tasks=True` on collision scan**: T010 implementation must pass `skip_tasks=True`
   to every `run_copy` call in `_scan_init_collisions`. Added to the plan's Work stream 4
   design and T010's task description.
3. **FR-017 deferred**: T021 (optional) is explicitly out of scope for first release.

## Out of scope for 013

- MI-1 version auto-updater (separate future spec; 013 must not preclude it)
- Stack presets (deferred — see above)
- warn→error upgrade for capabilities (trivial change; explicitly not first-release scope)
- Template content (012's scope; fully decoupled from 013)
- Product rename — RESOLVED outside this spec: clerk → bailiff landed on main (PR #37);
  distribution name `bailiff` is live on PyPI (0.1.0, trusted publishing)
