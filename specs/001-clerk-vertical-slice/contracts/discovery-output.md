# Contract — `clerk discover` output (FR-001, FR-004)

`clerk discover <source> [--ref REF]` prints a single JSON object to stdout: the
**static** description of one template, produced without executing any
template-authored code (FR-004a). The agent reads this to author a run-spec.

## Shape

```json
{
  "source": "https://github.com/copier-clerk/clerk-mod-base.git",
  "ref": "v1.0.0",
  "versions": ["v1.0.0"],
  "reproducible": true,
  "has_tasks": true,
  "jinja_extensions": [],
  "questions": [
    {
      "key": "project_name",
      "type": "str",
      "choices": null,
      "default_raw": null,
      "help": "The project's name (used in the README title and LICENSE).",
      "when": null,
      "validator": null,
      "secret": false
    }
  ],
  "secret_questions": [],
  "dependency_edges": {}
}
```

## Fields

| Field | Meaning |
|---|---|
| `source` | The fetchable locator passed in (echoed verbatim). |
| `ref` | The resolved ref discovery inspected — `--ref` if given, else the latest PEP 440 tag. |
| `versions` | All PEP 440-parseable tags, oldest→newest. Non-PEP-440 tags are dropped (copier ignores them too, FR-016a). |
| `reproducible` | `true` iff the template ships `{{ _copier_conf.answers_file }}.jinja` — the prerequisite for a recorded, reproducible project (FR-016). A `false` here means `init` will refuse (US5). |
| `has_tasks` | `true` if the template declares `_tasks` (code execution → trust required before `init`). |
| `jinja_extensions` | The template's declared `_jinja_extensions` (reported, never imported). A non-empty list is a further code-execution signal. |
| `questions` | One entry per visible question (settings keys `_*` and hidden `when:false` edges excluded). |
| `secret_questions` | Keys of questions marked `secret: true` — never persisted to the answers file (FR-013). |
| `dependency_edges` | The hidden `when:false` `depends_on`/`run_after`/`run_before` values (multi-template ordering; slice 001 reports but does not act on them). |

### Per-question fields

- `key` — the question name.
- `type` — copier type (`str`, `bool`, `int`, `yaml`, …); default `str`.
- `choices` — the allowed values, or `null`.
- `default_raw` — the default **un-rendered** (FR-004a): a default that is a Jinja
  expression is reported as the literal string, never evaluated.
- `help`, `when`, `validator` — copier's native per-question metadata, or `null`.
- `secret` — whether the answer is a secret.

## Guarantees

- **No code execution.** Discovery is `git` + `yaml.safe_load` + `packaging` only;
  it never builds copier's Jinja env or imports `_jinja_extensions`, so it is safe
  against an untrusted source and requires no trust (FR-004a).
- **Refusal.** A source exposing no usable PEP 440 tag is refused (FR-016a); a
  missing/invalid `copier.yml` is a `DiscoveryError`.
