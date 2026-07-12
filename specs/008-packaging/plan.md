# Implementation Plan: clerk skill packaging — installable via APM marketplaces (Claude + Codex)

**Branch**: `008-packaging` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-packaging/spec.md`

## Summary

Make the clerk skill installable into any project via APM, using APM's own tooling
(`apm pack` / `apm publish` / `apm marketplace`) — emitting **both** a Claude and a
Codex marketplace natively. Solve portability: the package **vendors `src/clerk/*`**
(no PyPI `clerk`, per spec 010) and **checks (does not auto-install)** its
third-party deps with an environment-aware install suggestion (no package manager
assumed). The template fan-out / authoring-lifecycle CI is deferred (no
`clerk-mod-*` modules exist until spec 009).

Resolved planning decisions (flagged for review in spec Open Questions):
- **Vendoring** = copy `src/clerk/*.py` into the package skill dir via a `just`
  sync step before `apm pack`, drift-checked (Q-008a: vendored modules, not a
  single-file amalgamation — keeps the readable layout).
- **v1 distribution** = marketplace artifacts via `apm pack` (self-hostable, no
  experimental flag); `apm publish` to a registry deferred until the `registries`
  feature is stable (Q-008b).
- **Manifest hosting** = committed in-repo + served via a stable raw URL / GitHub
  Pages (Q-008c, mirrors ADR-0006's catalog-hosting choice).

## Technical Context

**Language/Version**: Python 3.11+ (the preflight is stdlib-only). APM CLI provides
`pack`/`publish`/`marketplace`. The build/sync + release steps are `just` recipes +
CI (no new application code).

**Primary Dependencies**: no new *runtime* dep. The clerk package's runtime deps
stay `copier>=9.16,<10`, `pyyaml`, `packaging`, `tomli-w` — now declared in a PEP 723
header on `scripts/clerk.py` (single source of truth) AND checked by the preflight.
Tooling: the `apm` CLI (already installed).

**Storage**: Files only. The built marketplace manifests are committed at their
profile-default paths (`.claude-plugin/marketplace.json` +
`.agents/plugins/marketplace.json`; `marketplace.outputs.{claude,codex}` in
`apm.yml`). The vendored `src/clerk` copy lives under the package skill dir
(`packages/clerk/.apm/skills/clerk/`). Nothing is written into a *consumer's* project by
packaging itself.

**Testing**: `pytest` for the preflight/doctor logic (stdlib, hermetic — monkeypatch
PATH to simulate uv/pipx/pip/brew present/absent; monkeypatch import failure).
`apm pack --dry-run` + `apm marketplace validate` in CI as the build gate. A
vendored-drift check (diff shipped `src/clerk` copy vs source). `mypy --strict` +
`ruff` over `src/ tests/ scripts/`. An install-into-scratch-project smoke is
`network`/manual-marked (needs the built marketplace).

**Target Platform**: developer workstations + CI; installs into Claude Code + Codex
+ APM-managed projects (macOS/Linux).

**Project Type**: skill packaging. NOT a published application (a *distributed skill*
is not a PyPI app — C-01). No new module beyond the preflight.

**Performance**: none; correctness only. The preflight is a handful of `importlib`
checks + a PATH probe — negligible per invocation.

**Constraints**: no PyPI `clerk` (spec 010); no assumed package manager (preflight
suggests, never installs — user direction); vendored core drift-checked; both
marketplaces from one config; preflight LLM-free (Constitution II); fan-out/authoring
CI deferred (C-11 — no speculative machinery).

**Scale/Scope**: `apm.yml` `marketplace:` block; a preflight/doctor addition to
`scripts/clerk.py`; a PEP 723 header; a `just` vendoring + release recipe; a portable
SKILL update; docs; tests. NO fan-out, NO cocogitto, NO catalog.json, NO GitHub App,
NO module scaffolder/lint.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution **v2.1.0**. Initial gate: **PASS**.

| Principle | Gate | How this plan satisfies it |
|---|---|---|
| I — Skills + templates + minimal glue | PASS | Ships the durable artifact (the skill) via APM; no published app, no PyPI `clerk` (vendored core). New code is only a stdlib preflight; distribution is APM's `pack`/`publish`, not bespoke tooling. |
| II — Two-phase; agent judges, helpers execute | PASS | The preflight/`doctor` is deterministic, stdlib, LLM-free. Packaging/build/publish are mechanical `apm`/`just`/CI steps. The agent's role is unchanged (author inputs). |
| III — Faithful, agent-free reproduce | PASS (unaffected) | Packaging does not touch the reproduce path. The vendored core is the same code; an installed clerk reproduces identically. |
| IV — Prefer CLI + static config | PASS | Uses `apm` CLI + `apm.yml` static config; preflight is stdlib importlib + PATH probe. No deprecated surface. |
| V — Determinism; trust by source | PASS (unaffected) | No trust/determinism change; the preflight reads nothing executable. |
| VI — Template-author contract | PASS (n/a) | No template change. |
| VII — Hardening per-step | PASS | DoD = preflight tests (present/missing/partial deps × detected manager) + vendored-drift check + `apm pack --dry-run`/`validate` gate + release-gate behavior captured. |
| VIII — Documented handoff | PASS (n/a-ish) | No handoff-format change; the `apm.yml` marketplace block + PEP 723 header are documented plain config. |

**Complexity deviations**: none. The one new code surface (the preflight) is
justified by a real gap — an installed skill on an arbitrary machine has no
guarantee its deps are present, and spec 010 forbids a PyPI package to carry them.
The heavier authoring/fan-out machinery is *removed* from scope (C-11), not added.

Post-design re-check (after Phase 1): **PASS** — distribution is APM-native; the only
bespoke pieces are a stdlib preflight and a `just` vendoring/release recipe.

## Project Structure

### Documentation (this feature)

```text
specs/008-packaging/
├── spec.md              # The packaging spec (fan-out deferred)
├── plan.md              # This file
├── contracts/
│   └── packaging.md     # Phase 1 — apm.yml marketplace block, package layout, preflight/doctor contract, release commands, exit codes
└── tasks.md             # Phase 2 (/speckit.tasks)
```

Phase-0 research is captured inline: the APM mechanism was verified against the
live `apm` CLI via a throwaway spike (`apm pack --marketplace=claude,codex` emits
`.claude-plugin/marketplace.json` + `.agents/plugins/marketplace.json` from
`marketplace.outputs.{claude,codex}`; enabling `codex` hard-requires per-package
`category:`; `apm publish` uploads to a registry; `type: hybrid` from the
`secrets-scan` reference). The verified schema + both manifest shapes are captured in
`contracts/packaging.md`. No separate research.md needed.

### Source Code (repository root)

```text
apm.yml                  # EDIT: add a `marketplace:` block (apm marketplace init) with
                         #   marketplace.outputs.{claude,codex} + build.tagPattern. Declare the clerk package
                         #   (local source ./packages/clerk, version, category: Productivity [codex gate], license).

scripts/clerk.py         # EXTEND: (1) a PEP 723 `# /// script` dependency header (copier/pyyaml/
                         #   packaging/tomli-w) — single source of truth for the dep list;
                         #   (2) an import-preflight run before dispatch: missing dep → environment-aware
                         #   install suggestion (detect uv/pipx/pip/brew on PATH) + clean non-zero exit,
                         #   never a raw ImportError; (3) a `doctor` verb exposing the same check.
                         #   The existing sys.path shim is superseded by the vendored layout at install time
                         #   (works both from-repo and installed).

src/clerk/_preflight.py  # NEW (small): the stdlib dep-check + manager detection + suggestion builder.
                         #   Pure, testable, no third-party import (it runs BEFORE deps are guaranteed).

packages/clerk/          # NEW (the local-source package `source: ./packages/clerk`):
                         #   apm.yml (package metadata: type hybrid, license) + .apm/skills/clerk/
                         #   {SKILL.md, scripts/clerk.py, scripts/clerk/*.py vendored} + .claude-plugin/plugin.json.
                         #   The .apm/skills/clerk layout is GENERATED by the vendoring step, drift-checked vs src/clerk.
                         #   (apm pack writes .claude-plugin/marketplace.json + .agents/plugins/marketplace.json at repo root.)

justfile                 # EXTEND: `just vendor` (copy src/clerk → packages/clerk/.apm/skills/clerk/scripts/clerk/)
                         #   + `just check-vendor` (fail on drift) + `just pack` (apm pack --marketplace=claude,codex)
                         #   + `just release` (vendor → check-vendor → apm pack --check-versions --check-clean → apm publish [deferred]).

skills/clerk/SKILL.md    # EXTEND: portable Prerequisites — document the preflight/`clerk doctor` dep check
                         #   + install-suggestion flow; confirm frontmatter auto-triggers by semantics,
                         #   not repo path. (This is the source SKILL; the packaged copy is vendored.)

.github/workflows/       # NEW (optional, minimal): a pack+validate CI check (apm pack --dry-run +
                         #   apm marketplace validate + check-vendor) on PR. NOT the fan-out pipeline.

README.md                # EXTEND: `## Install` — add the marketplace, install clerk, run doctor.

tests/
├── unit/
│   └── test_preflight.py   # NEW: deps present → ok; one missing → suggestion for detected manager
│                           #   (uv/pipx/pip/brew via monkeypatched PATH); none detected → generic fallback;
│                           #   partial → only missing reported; exit codes. Stdlib-only, hermetic.
└── loop/
    └── test_packaging.py   # NEW: apm.yml has a valid marketplace block (outputs.{claude,codex}, package
                            #   category set); `apm pack --marketplace=claude,codex --dry-run` succeeds;
                            #   vendored-drift check; `clerk doctor` exit codes. (apm-dependent parts marked/guarded.)
```

**Structure Decision**: Distribution is APM-native (`apm.yml` marketplace block +
`apm pack`/`publish`); the only new code is a small stdlib `_preflight.py` +
`clerk doctor` verb (the portability guarantee). The package layout under
`.apm/skills/clerk/` is **generated** by a `just vendor` step from `src/clerk/` and
drift-checked — the readable source stays in `src/`, the shipped copy is derived.

## Complexity Tracking

No constitutional violations. This plan *reduces* the roadmap's 008 scope (defers the
fan-out/cocogitto/catalog.json/GitHub-App/scaffolder machinery — C-11, no templates
to operate on yet) and adds only a stdlib preflight + APM-native config. The three
flagged planning decisions (vendoring mechanism, marketplace-vs-registry, manifest
hosting) are resolved above with defaults + rationale; each is small and reversible.
