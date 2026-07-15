# 0004 — rendering behavior, file handling, and jinja extensions

- Status: accepted
- Date: 2026-07-09

## Context

Bailiff drives copier **non-interactively** (the agent pre-authors answers). That
changes which copier kwargs and settings are correct, and raises a determinism
hazard around jinja extensions (notably time). This ADR records the canonical
invocation and the extension policy. All facts verified against copier v9.16
docs/source (see the copier-feature research, 2026-07-09).

## Decision — canonical non-interactive API calls

- **init** — `run_copy(src, dst, data=answers, defaults=True, overwrite=True,
  quiet=False, settings=<user settings>)`.
- **reproduce** — `run_recopy(dst, data=answers, defaults=True, overwrite=True,
  quiet=False, settings=<user settings>)`.
- **update** (template evolution, optional) — `run_update(dst, data=answers,
  defaults=True, quiet=False, settings=<user settings>)`.
- `data=` carries every known answer (bypasses prompts, highest priority);
  `defaults=True` is the safety net for anything not in `data`. Use `data=`, NOT
  `user_defaults=` (the latter still prompts).
- **There is no `force=` API kwarg** — `--force` is a CLI alias for
  `defaults + overwrite`. bailiff exposes `defaults`/`overwrite` explicitly, not a
  `force`.
- **Pre-run validation:** every question a template asks must have a `default:`
  or be supplied in `data=`. bailiff validates this before calling copier and
  raises a structured error listing questions missing defaults, rather than
  letting copier raise an interactive-session error.
- Trust comes from `settings.yml` `trust:` (see [[0001-copier-as-engine]]), not a
  blanket `unsafe=True`.

## Decision — file handling (template-author contract)

- **`_exclude`** supports negation: `_exclude: ["*.txt", "!a.txt"]` excludes all
  `.txt` except `a.txt`. The CLI/API `exclude` **extends** (does not replace) the
  template's `_exclude`; bailiff must not pass excludes that strip copier's own
  defaults (`copier.yml`, `.git`, …). (Negation depends on a recent enough
  `pathspec`; ensure the pin guarantees it — open item.)
- **`_skip_if_exists`** is the mechanism for user-owned files bailiff generates once
  and must never overwrite on reproduce (`.env`, seed configs). Distinct from
  `_exclude` (which keeps files out of output entirely).
- **`_preserve_symlinks`** defaults to false; opt-in only for templates that ship
  symlinked shared assets. Document as advanced.
- **`message_after_copy` / `message_after_update` / `message_before_copy`** are
  templated with answers and render to stderr (suppressed by `quiet=True`). bailiff
  runs with `quiet=False` and **captures `message_after_copy` as a structured
  field** to surface as post-step guidance to the agent/user. Template authors
  should write actionable next-steps there using `{{ _copier_conf.dst_path }}`
  and answer vars.

## Decision — jinja extension policy (determinism-gated)

Two tiers, because `_jinja_extensions` are **trust-gated**:

- **Always available, no trust** — `jinja2-ansible-filters` (copier bundles it):
  `regex_*`, `hash`, `to_json`, `to_yaml`, `ternary`, `strftime`, etc.
- **Blessed, but require trust** (`_jinja_extensions` → `unsafe`): the
  `copier-template-extensions` context hook (slug-in-*filename* only, NOT
  metadata — see [[0003-selector-template-and-runtime-injection]]); a slug
  extension; a markdown extension. bailiff's orchestrator must inspect
  `_jinja_extensions` in `copier.yml` before invoking and escalate trust for that
  template accordingly.
- **FORBIDDEN in bailiff-driven templates** (nondeterminism): `jinja2_time`
  (`{% now %}` breaks reproduce byte-stability), and the random filters
  (`random`, `shuffle`, `random_mac`).

### Date-injection pattern (determinism)

Template authors MUST NOT use `jinja2_time` for the current date. Instead bailiff
injects the date from its own clock as an answer — `data={"today": "2026-07-09"}`
— and templates reference `{{ today }}`. This keeps the value frozen in the
answers file so reproduce replays the original date, not today's.

## Open items (verify during build, not blocking the decision)

- Confirm the installed copier's `--force` mapping matches master
  (`defaults OR force`, `overwrite OR force`).
- Confirm `data=`-supplied answers are written to `.copier-answers.yml` even when
  never interactively asked (needed for reproduce).
- Confirm the pinned `pathspec` version supports `_exclude` negation.
- `strftime` from ansible-filters takes epoch seconds — confirm whether a
  trust-free "current date in a template" is possible at all, or whether the
  `data={"today": ...}` injection is the ONLY trust-free option (current
  assumption: injection is required).
- context-hook package name: `copier-template-extensions` (copier-org) vs the
  older `copier-templates-extensions` fork — confirm which, and the in-place
  `hook()` API version, before any template depends on it.

## Related

- [[0001-copier-as-engine]], [[0002-catalog-and-answer-model]],
  [[0003-selector-template-and-runtime-injection]].
