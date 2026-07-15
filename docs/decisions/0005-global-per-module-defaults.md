# 0005 — global per-module defaults via `user_defaults=` injection

- Status: accepted
- Date: 2026-07-09

## Context

Users should not re-enter the same values (their template source repo, name, org,
etc.) on every run. bailiff needs a way to store GLOBAL, PER-MODULE default answers
that a module picks up — while the user can still override them interactively.
Facts verified against copier v9.16.0 source.

## Options considered

1. **copier `settings.yml` `defaults:`** — native, but a FLAT global dict with no
   per-module scoping; two modules with a same-named question collide. Path is
   `~/.config/copier/settings.yml` (platformdirs; not `~/Library/...`).
2. **`_external_data` reading a user-global YAML** — requires `unsafe=True` for
   paths outside the destination dir (enforcement is version-dependent: present
   v9.15+), does not auto-expand `~` (needs the `expanduser` Jinja filter), and
   couples the template to a bailiff-specific path (kills portability).
3. **bailiff injects via the API** — bailiff reads its own config and passes values
   to `run_copy`. Two sub-variants: `data=` (HARD override, skips the prompt) vs
   `user_defaults=` (SOFT default, pre-fills the prompt, user can still change).

Verified precedence at the prompt (`_user_data.py:get_default()`):
`data=` > `.copier-answers.yml` last > `user_defaults=` > `settings.defaults` >
template `copier.yml` default.

## Decision

- **bailiff reads its own config (`~/.config/bailiff/defaults.yml` or equivalent),
  selects the keys relevant to the module being invoked, and passes them as
  `user_defaults={...}` to the copier API.**
- **Use `user_defaults=`, NOT `data=`, for user-changeable defaults** — soft
  defaults pre-fill and remain overridable; `data=` would hard-skip the prompt
  (correct only for values bailiff truly fixes, e.g. computed/derived answers).
- **Optionally merge copier's native `settings.yml defaults:`** as a fallback:
  bailiff may `copier.load_settings()` and fold well-known fields (`user_name`,
  `user_email`) into the `user_defaults` dict, giving users copier's cross-tool
  convention for free.

## Why this over the alternatives

- **No `unsafe=True`, no template changes, per-module scoping** — all under
  bailiff's control; templates stay portable with zero bailiff coupling.
- Beats `settings.yml defaults:` (flat-global, no per-module scoping) and
  `_external_data` (needs unsafe for outside-dst + version-dependent enforcement
  + couples the template to a bailiff path).

## Consequences

- bailiff owns a small user-config store (`~/.config/bailiff/`) and a mapping of
  which default keys apply to which module.
- Defaults are per-module scopable because bailiff decides which keys to pass per
  invocation — copier never sees the whole set.
- The defaults file is **YAML** (`defaults.yml`, parsed with `yaml.safe_load`),
  consistent with bailiff's other YAML configs (`settings.yml`, catalog answers,
  trust store) and with PyYAML already a project dependency (no new import).

## Related

- [[0001-copier-as-engine]], [[0003-selector-template-and-runtime-injection]].
