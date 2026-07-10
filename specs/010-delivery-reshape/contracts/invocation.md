# Contract — clerk invocation after the delivery reshape (spec 010)

Supersedes [`../../001-clerk-vertical-slice/contracts/commands.md`](../../001-clerk-vertical-slice/contracts/commands.md)
for the reshaped surface. clerk's deterministic coordination is a **single bundled
script**, `scripts/clerk.py`, scoped to what copier cannot do itself. Everything
copier already does in one command is invoked as **copier directly** (documented in
the SKILL), so clerk never wraps copier's single-template surface.

There is **no `[project.scripts] clerk` console entry** and **no PyPI package**
(FR-001 / US4 / SC-003).

## Running the bundled script

```sh
./scripts/clerk.py <verb> …          # via the shebang (deps importable on PATH)
uv run scripts/clerk.py <verb> …     # via uv with the project's locked deps
```

Errors print legibly to stderr with a non-zero exit — never a bare stack trace.

### `scripts/clerk.py discover <source> [--ref REF]`

Static, code-free inspection of one template → JSON on stdout. No trust required.
Runs **no** template code (no Jinja env), so it is safe against an untrusted
source. Output shape: [`../../001-clerk-vertical-slice/contracts/discovery-output.md`](../../001-clerk-vertical-slice/contracts/discovery-output.md)
(unchanged). Key fields the SKILL acts on:

- `reproducible` — if `false`, the template ships no answers-file `.jinja`; a
  generated project could never be reproduced. This is the **Constitution VI gate,
  enforced at discovery**: the SKILL MUST stop and refuse (do not init). copier
  would silently write no `.copier-answers.yml` otherwise.
- `questions` — what to collect (`type`, `choices`, `default_raw`, `help`,
  `validator`, `secret`).
- `has_tasks` / `jinja_extensions` — non-empty ⇒ the template executes code ⇒
  trust required before init.
- `versions` — available PEP 440 tags; latest used unless the user pins `--ref`.

Exit: `0` success; non-zero `DiscoveryError` (bad YAML, no usable PEP 440 tag,
missing `copier.yml`).

### `scripts/clerk.py trust add <prefix>` · `trust add --from-source <src>` · `trust list`

Manage copier's `settings.yml` `trust:` — the ONLY writer of trust, invoked on
explicit human consent (Constitution V / FR-019).

- `add <prefix>` — record a fully-expanded `https://` prefix (idempotent; preserves
  existing entries). Stored expanded because copier matches the raw pre-expansion
  URL.
- `add --from-source <src>` — compute the suggested owner-path prefix for `<src>`
  (e.g. `https://github.com/<owner>/`) and record it, so one entry covers a whole
  org's `clerk-mod-*` repos. (Replaces 001's implicit prefix suggestion baked into
  the init refusal.)
- `list` — print trusted prefixes, or `(no trusted sources)`.
- The store path honors `COPIER_SETTINGS_PATH` (isolates tests / CI).

## The direct-copier commands (documented in SKILL, NOT wrapped by clerk)

These are copier's own CLI, run by the agent / a human / CI. clerk contributes
nothing to them beyond documenting them — copier authoritatively validates and
trust-gates.

### init (single template)

```sh
copier copy \
  --data-file <run-spec.yml> \
  [--vcs-ref <ref>] \
  --defaults --overwrite --trust \
  <source> <dest>
```

- `--data-file` is the run-spec the skill authored (see
  [`../../001-clerk-vertical-slice/contracts/answers-doc.md`](../../001-clerk-vertical-slice/contracts/answers-doc.md)).
  `today` is injected as a `--data today=<ISO date>` value the skill sets (it is
  NOT the agent's judgment — a fixed generation date, Constitution V).
- copier refuses an untrusted action-taking source itself; the SKILL's step 3
  (trust consent via `clerk.py trust`) is what unblocks it.
- **Writes NO clerk artifact** — no `justfile`, no recipe. The committed
  `.copier-answers.yml` is the entire reproduce state (FR-002 / SC-002).

### check (dry-run validation)

```sh
copier copy --pretend --data-file <run-spec.yml> --defaults --overwrite <source> <dest>
```

copier's own `--pretend` validates inputs and writes nothing. Surfaces
`copier.errors.*` and the bare `ValueError` (missing required answer) directly.

### reproduce (the copier-only guarantee — no clerk, no just)

```sh
cd <project> && copier recopy --vcs-ref=:current: --defaults --overwrite
```

- Replays the committed answers at the **recorded commit** — never bare `recopy`
  (which resolves the LATEST tag and silently upgrades).
- Runs with **copier alone**: no clerk installed, no `just`, no clerk file in the
  project (US1 / SC-001). This is the documented fallback and also the primary
  reproduce path for a single-template project.
- For a **multi-template** project, reproduce order is **recomputed at runtime** by
  the skill-bundled orchestrator (spec 003) from the committed `.copier-answers*.yml`
  + each template fetched at its pinned `_commit`, topo-sorted with a stable
  tie-break — it emits exactly this `recopy` command per layer, in order. No frozen
  recipe is committed (FR-004 / Constitution III).

## Exit codes (bundled script)

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | a `ClerkError` (bad input, unreproducible template surfaced by discover) |
| 2 | argparse usage error / unknown verb |
| 3 | `UntrustedSourceError` — surfaced when the script is asked to act on an untrusted action-taking source |

The direct-copier commands use **copier's own** exit codes and messages; clerk does
not translate them on that path.
