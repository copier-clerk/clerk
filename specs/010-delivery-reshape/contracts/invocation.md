# Contract — bailiff invocation after the delivery reshape (spec 010)

Supersedes [`../../001-bailiff-vertical-slice/contracts/commands.md`](../../001-bailiff-vertical-slice/contracts/commands.md)
for the reshaped surface. bailiff's deterministic coordination is a **single bundled
script**, `scripts/bailiff.py`, that drives the **full lifecycle** —
`discover`/`trust`/`init`/`reproduce` — through **one uniform path for 1..N
templates**. A single-template project is simply the **N=1** case: there is no
separate single-template code path, and no verb that is meaningful only for
multiple templates. The script drives copier's public surface once per template
layer; it never re-implements copier.

Because `bailiff.py` only ever issues plain `copier` commands, a machine with copier
but no bailiff can reproduce a project by running those commands by hand — the
documented **copier-only fallback** (and the US1 guarantee), not a competing
primary path.

There is **no `[project.scripts] bailiff` console entry** and **no PyPI package**
(FR-001 / US4 / SC-003).

## Running the bundled script

```sh
./scripts/bailiff.py <verb> …          # via the shebang (deps importable on PATH)
uv run scripts/bailiff.py <verb> …     # via uv with the project's locked deps
```

Errors print legibly to stderr with a non-zero exit — never a bare stack trace.

### `scripts/bailiff.py discover <source> [--ref REF]`

Static, code-free inspection of one template → JSON on stdout. No trust required.
Runs **no** template code (no Jinja env), so it is safe against an untrusted
source. Output shape: [`../../001-bailiff-vertical-slice/contracts/discovery-output.md`](../../001-bailiff-vertical-slice/contracts/discovery-output.md)
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

### `scripts/bailiff.py trust add <prefix>` · `trust add --from-source <src>` · `trust list`

Manage copier's `settings.yml` `trust:` — the ONLY writer of trust, invoked on
explicit human consent (Constitution V / FR-019).

- `add <prefix>` — record a fully-expanded `https://` prefix (idempotent; preserves
  existing entries). Stored expanded because copier matches the raw pre-expansion
  URL.
- `add --from-source <src>` — compute the suggested owner-path prefix for `<src>`
  (e.g. `https://github.com/<owner>/`) and record it, so one entry covers a whole
  org's `bailiff-mod-*` repos. (Replaces 001's implicit prefix suggestion baked into
  the init refusal.)
- `list` — print trusted prefixes, or `(no trusted sources)`.
- The store path honors `COPIER_SETTINGS_PATH` (isolates tests / CI).

### `scripts/bailiff.py init --run-spec <file> [--check]`

Generate a project from a frozen run-spec (see
[`../../001-bailiff-vertical-slice/contracts/answers-doc.md`](../../001-bailiff-vertical-slice/contracts/answers-doc.md)),
driving copier once per template layer (N=1 = one layer).

- Injects the frozen `today`; refuses an **unreproducible** template (no
  answers-file `.jinja`, VI) and an **untrusted action-taking** source (naming the
  prefix to trust) before writing anything.
- Drives copier's **public API** per layer — equivalent to
  `copier copy --data-file <file> [--vcs-ref <ref>] --defaults --overwrite --trust
  <source> <dest>`. copier authoritatively validates + trust-gates.
- `--check` uses copier's own `--pretend` dry run: validates inputs, **writes
  nothing**. Surfaces `copier.errors.*` and the bare `ValueError` (missing required
  answer).
- **Writes NO bailiff artifact** — no `justfile`, no recipe. The committed
  `.copier-answers*.yml` is the entire reproduce state (FR-002 / SC-002).

### `scripts/bailiff.py reproduce [DEST]`

Faithfully reproduce an existing project (default `DEST` = cwd), through the uniform
1..N path.

- Enumerates the committed `.copier-answers*.yml` file(s) and drives, per layer:
  `run_recopy(vcs_ref=VcsRef.CURRENT, defaults=True, overwrite=True)` — equivalent
  to `copier recopy --vcs-ref=:current: --defaults --overwrite`. Replays at the
  **recorded commit** — never bare `recopy` (which resolves the LATEST tag and
  silently upgrades).
- At **N=1** this is one answers file → one `recopy`. At **N>1**, reproduce order
  is **recomputed at runtime** (spec 003) from the committed answers + each template
  fetched at its pinned `_commit`, topo-sorted with a stable tie-break; the loop
  emits exactly this `recopy` per layer, in order. No frozen recipe committed
  (FR-004 / Constitution III).
- Agent-free (Constitution III).

## The copier-only fallback (documented in SKILL; no bailiff, no just)

`bailiff.py reproduce` only ever issues plain `copier recopy` commands, so the same
result is reproducible by hand with **copier alone** — no bailiff installed, no
`just`, no bailiff file in the project (US1 / SC-001):

```sh
# once per committed answers file, in the project dir
cd <project> && copier recopy --vcs-ref=:current: --defaults --overwrite
# multi-template: repeat with -a <each .copier-answers*.yml> in dependency order
```

This is the reproducibility guarantee and the documented fallback — not a competing
primary path. The primary path for everyone is `scripts/bailiff.py reproduce`.

## Exit codes (bundled script)

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | a `BailiffError` (bad run-spec, copier failure, unreproducible template) |
| 2 | argparse usage error / unknown verb |
| 3 | `UntrustedSourceError` — source takes actions and is not trusted |

`bailiff.py` translates copier's `CopierError`/`ValueError` into legible bailiff errors
on the verbs it drives; the by-hand fallback uses copier's own exit codes/messages.
