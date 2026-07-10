# Contract — the run-spec (init inputs doc) (FR-005)

`clerk init --run-spec FILE` reads a **frozen inputs document** the agent authored
in phase 1. It is a plain mapping (JSON or YAML — JSON is valid YAML, so either
parses). This is the two-phase boundary: everything below is deterministic and
runs with no LLM (Constitution II).

## Shape

```yaml
# run-spec.yml
source: "https://github.com/copier-clerk/clerk-mod-base.git"   # required
ref: "v1.0.0"                                                  # optional (pin)
dest: "./my-project"                                           # required
answers:                                                       # optional map
  project_name: acme-widgets
  org: acme
  license: MIT
  description: A widget service.
```

## Fields

| Field | Required | Meaning |
|---|---|---|
| `source` | yes | Fetchable template locator — expanded `https://` URL or local path. Recorded into the generated project's `.copier-answers.yml` as `_src_path`. |
| `dest` | yes | Destination directory for the generated project. |
| `ref` | no | Pin to a specific tag/ref. Omitted → copier resolves the latest PEP 440 tag; the resolved version is recorded as `_commit`. |
| `answers` | no | The answer values keyed by question. Missing required answers are surfaced by `--check`/`init` via copier's own validation (no bespoke validator). |

## Rules

- **`today` is injected by clerk**, not authored here: clerk supplies the
  generation date as the `today` answer so it freezes into the recorded answers
  and replays on reproduce (FR-007). Do not hand-set it.
- **Secrets and hidden edges are never persisted.** A `secret: true` answer and
  any `when:false` `depends_on`/`run_after`/`run_before` value are excluded from
  `.copier-answers.yml` (FR-013).
- **Validation reuses copier.** `init --check` runs copier's `pretend` dry run;
  it writes nothing and reports the same errors a real run would (FR-006, FR-008).
- **Trust precedence.** If the source takes actions and is untrusted, `init`
  (and `--check`) refuse with the exact `clerk trust add <prefix>` remediation and
  a non-zero exit, before any files are written (FR-020, SC-008).

## Malformed input

A non-mapping document, or one missing `source`/`dest`, is refused with
`InvalidRunSpecError` (a legible message, non-zero exit) — no files produced.
