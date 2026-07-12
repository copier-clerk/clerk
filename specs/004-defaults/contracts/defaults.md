# Contract — clerk global per-template defaults (spec 004)

clerk pre-fills copier's soft-default prompt values from a user-owned YAML file.
copier's own `user_defaults=` parameter is the injection point; the precedence
ladder is copier's native one, unmodified. Nothing defaults-related is written
into the generated project (spec 010 invariant).

## Defaults config file

**Path**: `~/.config/clerk/defaults.yml`
(resolved via `user_config_path("clerk", appauthor=False) / "defaults.yml"`)

**Env override**: `CLERK_DEFAULTS_PATH` — must point at an existing file when set;
raises `DefaultsError` if the path does not exist (an explicit override that
silently no-ops is surprising — Q-004c resolved).

**Missing file (default path)**: treated as an empty defaults dict, no error.

### YAML shape

A flat mapping of question key to default value. No per-template sections, no
nesting. Values may be strings, integers, booleans, or lists — any type copier
recognizes for its question types. Parsed with `yaml.safe_load`.

```yaml
# clerk user defaults — ~/.config/clerk/defaults.yml
author_name: Ada Lovelace
author_email: ada@example.com
github_org: acme
license: MIT
python_version: "3.12"
```

Keys that do not appear in the current template's questions are silently ignored.
This is by design: one file works across many templates without requiring per-template
sections or causing errors for unrecognized keys.

## Key-selection algorithm

Before calling `run_copy`, clerk filters the full defaults dict to only the keys
relevant to the current template invocation:

```
selected = {
    key: value
    for key, value in defaults_dict.items()
    if key in template_question_keys          # key present in this template
    and not template_questions[key].secret    # never pre-fill secret questions
    # and optionally: not template_questions[key].when is False  (hidden questions)
}
```

**Secret exclusion** (FR-004, SC-003): any question whose `copier.yml` entry has
`secret: true` is excluded. Spec 005 handles secret injection; defaults MUST NOT
pre-fill secret values from a plaintext YAML file.

**Hidden question exclusion** (FR-004, SHOULD): questions whose `when:` condition
is statically `false` (the dependency-edge sentinel, per Constitution VI) SHOULD be
excluded. Copier silently ignores `user_defaults=` for a `when:false` question, so
the risk is only confusion in the defaults file — not a correctness failure.

**Non-secret, non-hidden questions with no match**: simply absent from `selected` —
no error, no placeholder.

## `settings.yml` defaults fold (best-effort)

If copier's `~/.config/copier/settings.yml` (or the copier-platform path) contains
a `defaults:` mapping, clerk merges it as a LOWER-PRIORITY fallback:

```python
merged = {**copier_settings_defaults, **yaml_defaults}
# yaml_defaults wins on key collision — clerk-managed config outranks copier's flat global
```

The key-selection algorithm runs on `merged`, not on either source alone. This gives
users copier's cross-tool convention (`user_name`, `user_email`) for free.

**Graceful degradation**: if `copier.load_settings()` raises for any reason (absent
file, schema change in a copier upgrade, permissions), clerk logs a debug message and
uses only the YAML defaults. This is best-effort — FR-005. No error is surfaced.

## `user_defaults=` injection point

The filtered dict is passed as `user_defaults=` to every `run_copy` call:

```python
# runner.init (single-template)
user_defaults = defaults.select_keys(defaults_dict, disc.questions)
run_copy(source, dest, data=data, user_defaults=user_defaults, ...)

# runner.init_many (per-layer)
for record, af_name in plan:
    disc = discovery.discover(record.source, record.ref)
    user_defaults = defaults.select_keys(defaults_dict, disc.questions)
    run_copy(record.source, dest, data=accumulated, user_defaults=user_defaults, ...)
```

The defaults dict is loaded ONCE per `init` / `init_many` call and reused across
layers. The key-selection call is once per layer (per-layer independence).

**Why `user_defaults=` not `data=`**: `data=` hard-skips the prompt and records the
value unconditionally; `user_defaults=` pre-fills the prompt and the user can still
override it interactively. The roadmap scope says "soft default, still overridable"
— `user_defaults=` is the correct parameter.

## Precedence ladder (copier native, verified against 9.16.0)

| Priority | Source |
|---|---|
| 1 (highest) | `data=` / `--data` (clerk explicit answers, incl. injected `today`) |
| 2 | Previous answers file (`.copier-answers.yml` / layered) |
| 3 | `user_defaults=` (this feature — from `defaults.yml` + `settings.yml` fold) |
| 4 | `settings.yml defaults:` (copier's own flat global, if NOT folded into 3) |
| 5 (lowest) | Template `copier.yml` question `default:` |

clerk does NOT change this ladder. Passing user defaults as `user_defaults=` places
them at priority 3, which is exactly "soft default — overridable by explicit answers
and by previously recorded answers at reproduce".

**Reproduce behavior**: at reproduce, priority 2 (previous answers file) replays the
answers already recorded — so the defaults file has NO effect at reproduce. Reproduce
is always driven by the committed answers file, not by the current state of
`defaults.yml`. A user who changes `defaults.yml` between init and reproduce sees
no change in reproduce output.

## Exit codes

The defaults module raises `DefaultsError` (a `ClerkError` subclass); the existing
CLI error mapping applies:

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | `DefaultsError` (malformed YAML, explicit-override path missing) or other `ClerkError` |
| 2 | argparse usage error |
| 3 | `UntrustedSourceError` |

`DefaultsError` messages MUST include the offending file path and the reason (parse
error text or "file not found").
