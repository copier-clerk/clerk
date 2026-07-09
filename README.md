# clerk

**An agentic conductor for [copier](https://copier.readthedocs.io).**
The clerk fills in the paperwork; copier makes the copies.

> Status: early scaffolding. Design is captured in
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
- **Not in the reproduce path.** Reproduce is agent-free: a plain
  `copier recopy --defaults` (or `just reproduce`) run by a human or CI replays
  the committed answers with no agent involvement.
- **Not a template hub.** The catalog is user-owned; clerk works against any
  copier templates you point it at. See
  [`0002`](docs/decisions/0002-catalog-and-answer-model.md).

## How it works (one line)

The agent fetches a catalog of copier templates, injects it into a copier
**selector template** at runtime (`run_copy(data={"catalog": [...]})`), the user
picks modules, clerk writes the answer files, and copier renders — without
`--trust`, so all action-taking stays in clerk's orchestrator. See
[`0003`](docs/decisions/0003-selector-template-and-runtime-injection.md).

## Design decisions

- [0001 — copier is the engine; clerk is the conductor](docs/decisions/0001-copier-as-engine.md)
- [0002 — user-owned catalog; copier answers carry the state](docs/decisions/0002-catalog-and-answer-model.md)
- [0003 — selector-template + runtime catalog injection](docs/decisions/0003-selector-template-and-runtime-injection.md)
- [0004 — rendering behavior, file handling, and jinja extensions](docs/decisions/0004-rendering-and-extensions.md)
- [0005 — global per-module defaults via `user_defaults=`](docs/decisions/0005-global-per-module-defaults.md)
- [0006 — central authoring monorepo, fan-out to per-template repos](docs/decisions/0006-release-and-split-model.md)

## Development

```bash
uv sync --dev
just test     # pytest
just lint     # pre-commit run --all-files
just types    # mypy
```

## License

Apache-2.0
