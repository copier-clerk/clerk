# 0008 — PyPI packaging + repositioning: bailiff is the tool, bailiff-mod-* are the modules

- Status: accepted
- Date: 2026-07-15
- Governs: spec 013 (engine: PyPI packaging, capability tags, collision check,
  multi-catalog precedence, listing cache); amends Constitution I (v2.3.0 → v3.0.0 MAJOR).

## Context

Constitution v2.0.0 reframed bailiff as "skills + templates + minimal glue — NOT a
published Python tool," and v2.1.0 made the prohibition explicit: no
`[project.scripts] bailiff` console entry, no `uvx bailiff` PyPI tool; the glue ships
as one bundled script (`scripts/bailiff.py`). That framing solved a real problem (a
YAGNI review found copier already owns the single-template lifecycle), but the bundled
script accumulated its own costs: a dual-mode `sys.path` shim (repo vs APM-installed
layouts), a PEP 723 inline-deps header to maintain in parallel with `pyproject.toml`,
and a version mechanism that had to resolve without distribution metadata.

The 2026-07-14 adjudication session ratified a repositioning: **bailiff is the tool;
bailiff-mod-\* are the modules.** The published CLI is the primary user-facing
invocation path. Spec 013 implements it together with four engine work streams
(capability tags, init-time collision check, multi-catalog precedence, listing cache).

The product was renamed clerk → bailiff on 2026-07-15 (PR #37), which superseded the
ledger's original `copier-clerk` distribution-name resolution.

## Decision

1. **Repositioning.** bailiff ships as a published CLI: the `bailiff` distribution on
   PyPI, `[project.scripts] bailiff = "bailiff.cli:main"`, invoked `uvx bailiff` by
   users and `uv run bailiff` by repo contributors (editable install). The bundled
   `scripts/bailiff.py` is DELETED — greenfield project, zero existing users, so no
   shim or deprecation window is kept. This removes the dual-mode path shim, the
   PEP 723 header, and the bare-checkout version contortion in one move.
2. **Distribution name = `bailiff`.** The product rename made dist name == command
   name, so plain `uvx bailiff` works with no `--from`. The name is already claimed
   and published (0.1.0) on PyPI via OIDC trusted publishing (GitHub environment
   `release`); no squatting window remains.
3. **Constitution I amended (v3.0.0 MAJOR).** Principle I keeps its "skills +
   templates + minimal glue" title; the glue's delivery becomes the packaged CLI.
   This is a redefinition (the same class as v1.0.0 → v2.0.0), hence MAJOR. The C-11
   "glue only for capabilities copier lacks" constraint is scoped to module-authoring
   specs in the roadmap; spec 013 is the governed engine exception. Spec 011's FR-011
   gate ("no new `src/bailiff/` code" within 011's scope) remains textually intact
   and honored for its own scope — 013 is not retroactively applied to 011.
4. **Constitution VIII unlock (FR-019).** VIII forbids heavier handoff machinery
   "until a genuine non-agent program consumes the handoff." That condition is now
   met: the packaged CLI, the collision check, and the capability-warning computation
   are real non-agent consumers. Sanctioned scope: capability fields in catalog
   artifacts and `catalog list --json`. VIII's prohibition remains in force wherever
   a real non-agent consumer does not exist.

## Capability tags: warn, never block

Capability declarations (`_bailiff_provides: [<kebab-case>, …]`,
`_bailiff_exclusive: <bool>` in `copier.yml`) are informational. When a selection (or
an incremental add against an existing project) yields more than one provider of a
capability that any catalog module declares exclusive, `init_many` emits a loud
warning and proceeds. Rationale (ratified): rely on module authors and the selecting
agent for claims; enforce **facts** (file collisions), not **claims** (labels). The
warn→error upgrade is a trivial future change, explicitly out of first-release scope.

By contrast, the init-time **file-collision check is a hard stop** (`CollisionError`,
exit 1, before any write): two modules writing the same destination path is a fact,
observable by rendering each layer into an isolated temp dir (`skip_tasks=True` — a
safety requirement so the read-only scan never executes template tasks).

## The `exclusive_capabilities` frozenset interface

Group-infection semantics require a catalog-wide view: if ANY module in the merged
listing declares `exclusive: true` for a capability, the whole capability group is
treated as select-one. But `init_many` only receives the selected modules. Passing
the full listing would give the runner catalog awareness it doesn't otherwise need;
instead the CLI pre-computes `exclusive_capabilities: frozenset[str]` (all capability
names where any listed provider declares exclusive) and passes it as a parameter.
The frozenset is the minimal interface that correctly implements the group-infection
rule while keeping the runner catalog-agnostic.

## Escape valve: per-pointer infection scoping

The group-infection rule applies across the entire merged catalog listing, not per
catalog pointer. If real-world multi-catalog noise materializes (a third-party
catalog declaring exclusive on a capability you use composably), the designated
fallback is to scope infection per catalog pointer. This is a non-breaking
refinement: the data model stays identical; only the frozenset computation in the
CLI narrows.

## Consequences

- Users install/run bailiff with `uvx bailiff` — no script copying, no path shims.
- Repo contributors use `uv run bailiff`; tests import `bailiff.cli` directly.
- `platformdirs` becomes an explicit runtime dependency (previously transitive);
  `__version__` is single-sourced via `importlib.metadata.version("bailiff")`.
- Publishing is maintainer-gated: OIDC trusted publishing, first-publish confirmed
  by a human (spec 013 SC-010); the constitution amendment gates all publish work.
- The one-script delivery model in ADR-0001's framing and C-01 is superseded; the
  roadmap and constitution were reconciled in the same change.
