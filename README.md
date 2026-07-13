# clerk

**An agentic conductor for [copier](https://copier.readthedocs.io).**
The clerk fills in the paperwork; copier makes the copies.

> Status: active development. Design is captured in
> [`docs/decisions/`](docs/decisions/); implementation is spec-driven (SpecKit).

## What clerk is

copier is a superb *deterministic* scaffolding engine: it renders templates from
answers, pins templates to git refs, and reproduces a project byte-for-byte from
a committed answers file. What copier has no concept of is the **agentic layer** —
choosing which templates to apply, authoring the answers for you, and wiring up
AI-agent tooling (APM packages, MCP servers, SpecKit, steering/ADR docs).

clerk is exactly that layer, and nothing more:

- an **init-time agent** that selects modules from a user-owned catalog and
  authors the per-module answer files (the *inputs*);
- a **thin orchestrator** for multi-module enablement + dependency ordering;
- the **agentic-ecosystem wiring** (APM / MCP / SpecKit / ADR) that has no
  off-the-shelf analog.

## What clerk is NOT

- **Not a scaffolder.** copier renders; clerk only decides and fills in.
- **Not in the reproduce path.** Reproduce is agent-free: `scripts/clerk.py
  reproduce` replays the committed answers **at the recorded commit**
  (`recopy --vcs-ref=:current: --defaults --overwrite`), never a bare recopy that
  would silently upgrade — run by a human or CI with no agent. Reproduce also works
  with copier alone (no clerk): `copier recopy --vcs-ref=:current: --defaults
  --overwrite` per answers file.
- **Not a template hub.** The catalog is user-owned; clerk works against any
  copier templates you point it at. See
  [`0002`](docs/decisions/0002-catalog-and-answer-model.md).

## How it works (one line)

The agent (skill) inspects a copier template, collects answers from the user,
records trust consent if the template executes code, and hands the frozen answers
to the bundled deterministic script — `scripts/clerk.py` — which drives copier to
render and initialize the project. Any template that takes actions (its `_tasks` /
migrations / jinja extensions) runs only from a source the user has **trusted** —
copier's `settings.yml` trust list, recorded by an explicit consent step, never a
blanket `unsafe=True`. See [`0003`](docs/decisions/0003-selector-template-and-runtime-injection.md)
and [`0001`](docs/decisions/0001-copier-as-engine.md).

## Install

clerk is distributed as an APM skill package — installable into any
**macOS/Linux/WSL** project that uses Claude Code or Codex. There is no PyPI
`clerk` package; the skill bundles its own Python modules.

### Install into a Claude Code project

```sh
# Add the clerk marketplace (one-time per machine / project):
apm marketplace add copier-clerk/clerk

# Install the clerk skill:
apm install clerk

# Check that runtime deps (copier, pyyaml, packaging, tomli-w) are present:
python "$(apm skill-path clerk)/scripts/clerk.py" doctor
```

### Install into a Codex project

```sh
apm marketplace add --marketplace=codex copier-clerk/clerk
apm install --marketplace=codex clerk
```

### Runtime dependencies

clerk checks its deps at startup. If any are missing or version-incompatible
(esp. `copier>=9.16,<10`), it prints an environment-aware install suggestion
and exits cleanly — no traceback. Run `clerk.py doctor` for an explicit check.

Quick install (choose one):

```sh
uv pip install copier pyyaml packaging tomli-w    # uv (recommended)
pip install copier pyyaml packaging tomli-w        # pip
brew install copier && pip install pyyaml packaging tomli-w   # macOS brew (copier only via brew)
```

Or use `uv run scripts/clerk.py <verb>` — `uv` reads the PEP 723 header and
auto-provisions a hermetic ephemeral environment on every invocation.

---

## Invocation

clerk ships as a **bundled script** (not an installed CLI or PyPI package):

```sh
uv run scripts/clerk.py discover <source> [--ref REF]   # inspect template (static, safe)
uv run scripts/clerk.py trust add <prefix>              # record consent
uv run scripts/clerk.py trust add --from-source <src>   # record org-level consent
uv run scripts/clerk.py init --run-spec <file> [--check] # generate (or dry-run)
uv run scripts/clerk.py reproduce [<dest>]              # faithful reproduce (primary)

# Copier-only fallback (no clerk needed):
cd <project> && copier recopy --vcs-ref=:current: --defaults --overwrite
```

See [`specs/010-delivery-reshape/contracts/invocation.md`](specs/010-delivery-reshape/contracts/invocation.md)
for the full surface, exit codes, and the copier-only fallback.

## Catalog

The catalog is **user-owned configuration**: a plain TOML file listing the source
repos you want to scaffold from. clerk depends on no first-party hub; you bring
your own templates.

```sh
uv run scripts/clerk.py catalog init                       # create the catalog file if absent
uv run scripts/clerk.py catalog add gituser/gitrepo        # add a source (idempotent)
uv run scripts/clerk.py catalog add gituser/mod@v2.1.0     # with a display-version override
uv run scripts/clerk.py catalog remove gituser/gitrepo     # remove a source (idempotent)
uv run scripts/clerk.py catalog list                       # show usable templates + flag unusable sources
uv run scripts/clerk.py catalog list --json                # machine-readable listing
uv run scripts/clerk.py catalog validate demo/my-template  # gate: exit 0 if valid, non-zero if unknown/ambiguous
```

Pass `--catalog PATH` between `catalog` and the subverb to target a non-default
file (e.g. `catalog --catalog PATH list`); the default location follows the same
`platformdirs`/`CLERK_CATALOG_PATH` resolution as `trust.py`. Templates are identified by a **full-id** `<catalog>/<template>`
(where `<catalog>` is the pointer name, defaulting to a sanitized source
basename). The listing is deterministic — same sources at the same pins produce
identical output. A source that is unusable (no PEP 440 tag, bad `copier.yml`,
unreachable) is reported per-source with a reason; the rest of the catalog still
lists.

The skill (step 0 of `skills/clerk/SKILL.md`) manages the catalog on the user's
behalf: ensure → list → pick → validate → init.

### The `copier-clerk` module catalog

The first-party module family (`clerk-mod-*`) is authored in the
`copier-clerk/clerk-templates` monorepo and published as a generated JSON index
served via GitHub Pages at the stable URL:

```
https://copier-clerk.github.io/clerk-templates/catalog.json
```

The index is derived from released modules — a module appears only once it has a
published `vX.Y.Z` tag on its split repo, so the catalog is empty until the first
release fan-out runs. See
[`docs/runbooks/fanout-release.md`](docs/runbooks/fanout-release.md) for the
release/fan-out pipeline and the one-time maintainer setup it requires.

## Multi-template

Select several templates from the catalog and clerk applies them in dependency
order — no manual sequencing. Each template declares its `depends_on`/`run_after`/
`run_before` edges in its `copier.yml`; clerk builds the DAG, validates it (refuses
cycles, dangling edges, and basename collisions before writing anything), and runs
one `copier copy` per layer in topological order, threading earlier layers' answers
into later ones.

Each layer commits its own `.copier-answers.<basename>.yml`. At reproduce, clerk
enumerates those files, fetches each template at its pinned `_commit`, re-reads the
edges, and **recomputes** the same order — no frozen recipe file is committed to the
project. Pinned commits → identical edges → identical order, so reproduce is
deterministic and agent-free.

The copier-only-by-hand fallback (`copier recopy … -a <each answers file>` in
recomputed order) works for any number of layers — nothing about the project requires
clerk to reproduce.

N=1 is the degenerate case: a single-template project runs the same path with a
one-node DAG, no special-casing.

See `skills/clerk/SKILL.md` (multi-template section) and
`specs/003-multi-template/contracts/ordering.md` for the run-spec shape, edge
semantics, and ordering algorithm.

## Upgrade

Move a project from one template version to a newer one:

```bash
# Upgrade all layers to the latest PEP 440 tag (single-layer or multi-layer):
uv run scripts/clerk.py update <project-dir>

# Target a specific version:
uv run scripts/clerk.py update <project-dir> --vcs-ref v1.2.0

# Dry-run preview:
uv run scripts/clerk.py update <project-dir> --pretend
```

Upgrade is the **only** clerk path that advances a template version — reproduce
always stays pinned. copier's 3-way merge handles local edits; clerk supplies the
version announcement, the cross-template ordering, and the conflict report.

- **Multi-layer**: layers are upgraded in dependency order (DAG re-solved at target
  versions). New dependencies introduced in a newer template version are detected and
  refused until the user adds the missing layer.
- **Migrations** (`_migrations` in `copier.yml`): version-crossing migration commands
  run automatically via copier, trust-gated identically to `_tasks`. The new format
  is enforced; the deprecated `before`/`after` dict form is refused at discovery.
- **Conflicts**: if copier's 3-way merge leaves conflict markers, clerk reports the
  conflicted files and exits 4. Resolve and re-run.

Exit codes: `0` ok, `1` error, `3` untrusted source, `4` merge conflicts.

## Design decisions

- [0001 — copier is the engine; clerk is the conductor](docs/decisions/0001-copier-as-engine.md)
- [0002 — user-owned catalog; copier answers carry the state](docs/decisions/0002-catalog-and-answer-model.md)
- [0003 — selector-template + runtime catalog injection](docs/decisions/0003-selector-template-and-runtime-injection.md) *(superseded in part by spec 002 — two-template flow replaced by catalog file + validation gate; `--data catalog=[…]` render-scope fact retained)*
- [0004 — rendering behavior, file handling, and jinja extensions](docs/decisions/0004-rendering-and-extensions.md)
- [0005 — global per-module defaults via `user_defaults=`](docs/decisions/0005-global-per-module-defaults.md)
- [0006 — central authoring monorepo, fan-out to per-template repos](docs/decisions/0006-release-and-split-model.md)

## Development

```bash
uv sync --dev
uv run pytest                         # run the hermetic test suite
uv run pytest -m network -v           # live smoke test (requires gh auth)
uv run ruff check src/ tests/ scripts/
uv run mypy
bash scripts/try-clerk.sh             # interactive end-to-end walkthrough
```

## License

Apache-2.0
