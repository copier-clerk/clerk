# Feature Specification: bailiff global per-template defaults

**Feature Branch**: `004-defaults`

**Created**: 2026-07-10

**Status**: Draft

**Input**: Roadmap spec 004 (Global per-template defaults), governed by the
constitution (I, II, V) and ADR-0005. Consumes spec 003's multi-layer init path
(`runner.init_many`) and the path-resolution pattern established in spec 002
(`src/bailiff/catalog.py`).

## Overview

Specs 001/010 proved the single-template loop; spec 002 added the catalog; spec 003
added multi-template ordering. Users now face a recurring friction: they must supply
the same values — their name, email, GitHub org, preferred license — on every `init`
run, even when those answers never change.

Spec 004 removes that friction. A user populates a YAML defaults file at
`~/.config/bailiff/defaults.yml` (env-overridable), assigning values keyed by
template name or template question. When bailiff drives a `copier copy`, it selects
the keys relevant to that template's questions and passes them as `user_defaults=`
— copier's own soft-default mechanism — so the values pre-fill the prompt while
remaining overridable. No change to precedence; no new mechanism; no bailiff artifact
written into any generated project.

The feature is a small addition to `runner.py` and a new `src/bailiff/defaults.py`
module that mirrors `catalog.py` in structure: the same `platformdirs` path, the
same env-override pattern.

## Motivating decisions

1. **`user_defaults=`, not `data=`.** `data=` hard-skips the prompt (and is only
   correct for values bailiff truly fixes, such as the injected `today`). `user_defaults=`
   pre-fills and remains overridable — exactly what a user-config default should do.
   Verified precedence (ADR-0005, constitution Additional Constraints):
   `data=` > answers-file last > `user_defaults=` > `settings.yml defaults:` >
   `copier.yml default`.

2. **Per-template key selection, not a global blob.** bailiff selects only the keys
   relevant to the current template's questions before passing `user_defaults=`.
   A key in the defaults file that does not appear in a template's questions is
   silently ignored (no error — portability). This gives per-template scoping without
   a per-template config section.

3. **YAML at platformdirs path, env-overridable, aligned to ADR-0005.** ADR-0005
   named the file `defaults.yml`; this spec uses **YAML** for consistency with
   bailiff's other YAML configs (`settings.yml`, catalog answers, trust store) and
   with PyYAML already being a project dependency (used in `runner.py`,
   `discovery.py`, `trust.py`). The resolved decision: **`defaults.yml`
   at `~/.config/bailiff/defaults.yml`** (same `user_config_path("bailiff")` base as
   `catalog.toml`), overridable via `BAILIFF_DEFAULTS_PATH`. The filename and format
   align with ADR-0005 — no deviation; see Q-004a below.

4. **Optionally fold copier `settings.yml defaults:`.** ADR-0005 permits bailiff to
   load copier's native `settings.yml defaults:` and fold well-known fields
   (`user_name`, `user_email`) into the `user_defaults` dict as a final fallback.
   This gives users copier's cross-tool convention for free. Spec 004 includes this
   as an optional enrichment step (see FR-005 and Open Questions for whether it is
   mandatory or best-effort).

5. **Secrets are never defaulted here.** A secret question — one whose `secret: true`
   flag is set in `copier.yml` (discoverable statically) — MUST NOT be pre-filled
   from the defaults file. Spec 005 handles secret injection. This invariant must be
   enforced by the key-selection step.

6. **No bailiff artifact written into the generated project** (spec 010 invariant). The
   defaults file is user-side config; bailiff passes its values as runtime `user_defaults=`
   and they flow through to the answers file as normal copier answers — no bailiff-
   authored file is committed to the project.

## User Scenarios & Testing

### US1 — Pre-fill common answers from a defaults file (Priority: P1)

A developer has a `defaults.yml` with `author_name = "Ada"` and
`author_email = "ada@example.com"`. When they run `init` against a template that
asks for those keys, both are pre-filled as soft defaults — the prompt shows the
default values and the user can override them.

**Why this priority**: the headline feature — the reason the spec exists.

**Independent Test**: local template fixture with questions `author_name` and
`author_email` (both non-secret, no `copier.yml` defaults); a `defaults.yml`
supplying both; run `init` with `check=True` (dry run) + `check=False`; assert the
generated answers file records the defaults, and that overriding `author_name` at the
`data=` level wins (precedence check).

**Acceptance Scenarios**:
1. **Given** `defaults.yml` has `author_name = "Ada"` and the template asks
   `author_name`, **When** `init` with `defaults=True` and no explicit `data` for
   `author_name`, **Then** the answers file records `author_name: Ada`.
2. **Given** `defaults.yml` has `author_name = "Ada"` and the run-spec also passes
   `author_name = "Bob"` in `data=`, **When** `init`, **Then** the answers file
   records `author_name: Bob` (data= wins — precedence FR-002).
3. **Given** `defaults.yml` has `api_key = "secret"` and the template marks
   `api_key` as `secret: true`, **When** `init`, **Then** `api_key` is NOT
   pre-filled from defaults (FR-006).

### US2 — Defaults apply per-layer in multi-template init (Priority: P1)

A developer runs a multi-template init (spec 003 path). The same `defaults.yml`
applies per-layer: each layer's questions are matched independently, so a key present
in two layers pre-fills both.

**Why this priority**: 003's multi-layer path must be covered uniformly (spec 010).

**Independent Test**: two local template fixtures sharing the question `author_name`;
a `defaults.yml` supplying it; run `init_many` for both layers; assert both answers
files record the default, and that a threaded answer from layer 1 into layer 2 still
wins over the default (threading precedence).

**Acceptance Scenarios**:
1. **Given** two layers A and B each asking `author_name`, and `defaults.yml` has
   `author_name = "Ada"`, **When** `init_many([A, B])`, **Then** both layers record
   `author_name: Ada`.
2. **Given** layer A answers `author_name = "Org"` and threads it forward; layer B
   also asks `author_name`; `defaults.yml` has `author_name = "Ada"`, **When**
   `init_many([A, B])`, **Then** B records `author_name: Org` (threaded `data=` wins
   over `user_defaults=`).

### US3 — Defaults from copier settings.yml are folded in (Priority: P2)

A developer who already has `user_name` and `user_email` set in copier's
`~/.config/copier/settings.yml` sees those values pre-filled too, without duplicating
them in `defaults.yml`.

**Why this priority**: convenience; falls back gracefully if settings.yml is absent.

**Independent Test**: create a test `settings.yml` with `defaults: {user_name:
"Turing"}`; assert that a template asking `user_name` sees it pre-filled via the
merged `user_defaults`; assert that `defaults.yml` key wins over `settings.yml` key
if both are present (YAML defaults file takes priority as a bailiff-managed config).

**Acceptance Scenarios**:
1. **Given** `settings.yml` has `defaults: {user_name: "Turing"}` and `defaults.yml`
   is absent or does not mention `user_name`, **When** `init`, **Then** `user_name`
   is pre-filled as `Turing`.
2. **Given** both `defaults.yml` and `settings.yml` supply `user_name`, **Then**
   `defaults.yml` value wins (bailiff's own config takes priority over copier's flat
   global).

### US4 — Missing or empty defaults file is silently no-op (Priority: P1)

A developer who has no `defaults.yml` sees no change in behavior — init runs
identically to pre-004 behavior.

**Independent Test**: run `init` with the defaults path pointing at a nonexistent
file; assert no error is raised and copier receives no `user_defaults`.

### Edge Cases

- **Key in defaults file not in template questions**: silently ignored (no error;
  portability invariant — the same file can be used across many templates).
- **All keys filtered as secrets**: `user_defaults={}` is passed; no error.
- **Malformed YAML in defaults file**: `DefaultsError` with a clear path + reason;
  init refuses rather than silently using an empty dict.
- **`BAILIFF_DEFAULTS_PATH` points at a nonexistent file**: treated as absent (no
  error) unless the path is explicitly set AND the file is expected to exist (flag
  for Open Questions).
- **`user_defaults=` for a key copier considers hidden (`when:false`)**: copier
  silently ignores it; the key is not prompted and is not written to the answers file.
  The key-selection step should skip `when:false` questions to avoid confusion
  (see FR-004).
- **Defaults file contains a non-string value** (e.g. `year = 2024`): pass the
  value as-is; copier will coerce to the question's declared type. Do NOT stringify
  everything — copier handles type matching.

## Requirements

### Functional Requirements

- **FR-001**: bailiff MUST read a defaults YAML file from `~/.config/bailiff/defaults.yml`
  (resolved via `user_config_path("bailiff", appauthor=False)`) or from the path in
  `BAILIFF_DEFAULTS_PATH`. A missing file MUST be treated as an empty defaults dict
  (no error). A malformed YAML file MUST raise `DefaultsError`.
- **FR-002**: The precedence ladder MUST be preserved: `data=` (hard override) >
  answers-file last > `user_defaults=` (soft default from this file) > `settings.yml
  defaults:` > `copier.yml default`. bailiff MUST NOT break this by using `data=`
  for user defaults.
- **FR-003**: bailiff MUST select only the keys relevant to the current template's
  questions (from `discovery.Discovery.questions`) before building the
  `user_defaults=` dict. Keys present in the defaults file but absent from the
  template's questions MUST be silently discarded.
- **FR-004**: Secret questions (those where `discovery.Question.secret is True`,
  read statically from `copier.yml`) MUST be excluded from the `user_defaults=` dict.
  Hidden questions (`when:false`, used for dependency edges) SHOULD also be excluded
  to avoid confusing copier.
- **FR-005**: If copier's `settings.yml defaults:` is present, bailiff SHOULD merge
  it as a lower-priority fallback behind the `defaults.yml` values: the merged
  dict is `{**settings_defaults, **yaml_defaults}` (yaml_defaults wins on collision). This
  enrichment MUST be best-effort: if `copier.load_settings()` fails for any reason,
  bailiff continues with only the YAML defaults (no error).
- **FR-006**: bailiff MUST NOT write any defaults-related file into the generated
  project. The defaults file is user-side config only (spec 010 invariant).
- **FR-007**: The defaults injection MUST apply both to the single-template path
  (`runner.init`) and to each layer of the multi-template path (`runner.init_many`),
  per-layer independently (each layer's questions are matched separately).
- **FR-008**: The defaults injection MUST apply to the `check=True` (dry-run
  preflight) path identically, so the preflight surface uses the same `user_defaults`
  the real init would use.

### Key Entities

- **Defaults file**: a flat YAML mapping of `question_key: value` at a user-config
  path. No per-template sections. Keys are matched by name against the current
  template's question list at runtime.
- **Key selection**: the filtering step that produces the `user_defaults` dict for
  one template invocation. Inputs: the full defaults dict + the template's question
  keys (minus secrets, minus hidden `when:false` keys). Output: a subset dict.
- **`user_defaults=`**: copier's soft-default parameter to `run_copy`. It sits third
  in the precedence ladder (after `data=` and the previous answers file).
- **`DefaultsError`**: a new `BailiffError` subclass for malformed YAML or other
  config-read failures.

## Success Criteria

- **SC-001**: A key present in the defaults file AND in the template's
  (non-secret, non-hidden) questions pre-fills the copier prompt and is recorded in
  the answers file when not overridden.
- **SC-002**: Precedence is intact — `data=` hard overrides a defaults key; a
  threaded answer from an earlier layer overwrites a defaults key in a later layer.
- **SC-003**: A secret question (`secret: true`) is never pre-filled from defaults.
- **SC-004**: A missing or empty defaults file produces no error and no behavior
  change relative to pre-004.
- **SC-005**: The multi-template path applies defaults per-layer; a threaded answer
  wins over the defaults file for the same key in a later layer.
- **SC-006**: A malformed YAML file raises `DefaultsError` with path + reason (never
  silently used as empty).
- **SC-007**: No defaults-related file is ever written into the generated project.

## Out of scope

- Secret values (spec 005 — a secret question is never defaulted from this file).
- Template-specific config sections in the defaults file (per-template scoping is
  achieved by key selection; sections are YAGNI until a second consumer demonstrates
  the need).
- Persisting newly-collected answers back to the defaults file (an explicit
  "save this as a default" verb could be spec 004+1 — deferred).
- Defaults for the `update` path (spec 006 — out of scope here).
- The `BAILIFF_DEFAULTS_PATH` env var raising an error on a nonexistent path (policy
  deferred to Open Questions).

## Open Questions

- **Q-004a — ADR-0005 format alignment**: ADR-0005 names the defaults file
  `defaults.yml`. This spec uses `defaults.yml` (YAML) — **aligned to ADR-0005**,
  for consistency with bailiff's other YAML configs (`settings.yml`, catalog answers,
  trust store) and with PyYAML already a project dependency (imported by `runner.py`,
  `discovery.py`, `trust.py`). No deviation from the ADR; no format reconciliation
  needed. ADR-0005 Consequences section may optionally note the file is YAML.

- **Q-004b — `settings.yml` fallback: mandatory or best-effort?** ADR-0005 says
  "optionally merge". FR-005 makes it best-effort. If the orchestrator wants it
  mandatory (hard error if `load_settings` fails), that changes the spec. Lean:
  best-effort (avoids coupling to copier's internal settings load path; gracefully
  degrades if a copier upgrade changes the API).

- **Q-004c — `BAILIFF_DEFAULTS_PATH` on nonexistent file**: should `BAILIFF_DEFAULTS_PATH`
  pointing at a missing file be silently treated as absent (same as the default path
  missing), or raise an error (the user explicitly named a file that doesn't exist)?
  Lean: **raise `DefaultsError`** when the env var is explicitly set to a path that
  is not a file — an explicit override that silently no-ops is surprising. The default
  platformdirs path being absent remains a no-op.

- **Q-004d — Hidden `when:false` key exclusion**: FR-004 says SHOULD exclude hidden
  questions from `user_defaults=` to avoid confusing copier. Copier silently ignores
  a `user_defaults` key for a `when:false` question, so the only risk is a misleading
  defaults file. The lean is SHOULD (not MUST); flag for orchestrator if the
  distinction matters.

## Governing constitution & ADRs

- Constitution I (minimal glue — the defaults helper is a small addition to
  `runner.py` and a new `defaults.py`; no new dependency — PyYAML is already used;
  copier's own `user_defaults=` mechanism is reused).
- Constitution II (two-phase — defaults loading is deterministic, LLM-free, part of
  the helper layer).
- Constitution V (determinism — user defaults are user-visible answers and appear in
  the committed answers file, so reproduce is not affected; the defaults file is
  user-side config, not project state).
- ADR-0005 (the governing decision — bailiff reads its own config, selects relevant
  keys, passes as `user_defaults=`; file format is YAML, aligned with ADR-0005).
- Constraints: C-11 (the defaults helper is a small extension of the existing runner
  seam; no new copier surface); spec 010 invariant (no bailiff artifact in the
  generated project).
