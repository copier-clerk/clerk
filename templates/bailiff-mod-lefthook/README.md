# bailiff-mod-lefthook

The lefthook hook-manager layer. Selecting this module makes lefthook the
project's git-hook manager (presence-derived — like `bailiff-mod-precommit`).

## What it does

- Consumes the neutral `.hooks.d/*.yaml` fragments that language and tooling
  modules drop (id, entry, files, stages) and projects them into `lefthook.yml`.
- The projection runs as a `_post_agent_tasks.post` step after the full render
  loop, so every fragment is present. The engine freezes the rendered
  `lefthook.yml`; `bailiff reproduce` replays it with no agent.
- Runs `lefthook install` once at init (init-only-guarded via a committed
  sentinel), gated on `install_hooks`.

## Composition

- `depends_on: [bailiff-mod-base]`; phase `normal`.
- Exactly one hook manager per stack — do not select both this and
  `bailiff-mod-precommit`.
- With no `.hooks.d/` fragments present, the projection writes nothing.

## Contract

`specs/015-agent-projected-capabilities/contracts/hooks-neutral-dir.md`.
