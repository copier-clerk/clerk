# clerk-mod-quality

Single writer of `.agents/hooks/quality-languages` — a sorted-unique list of
active language identifiers, one per line. The phase-1 agent freezes the
`quality_languages` union and injects it via `--data`; this module renders the
file deterministically (spec 011, _cross-cutting §5).

Pure render module: no tasks, no native commands. `run_after: [clerk-mod-base]`.

## Usage

```sh
copier copy https://github.com/copier-clerk/clerk-mod-quality.git <destination>
```

Or via `clerk init` with `quality_languages` injected by the phase-1 agent.

## Questions

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `quality_languages` | yaml list | `[]` | Sorted active language identifiers, injected by the agent via `--data`. |

## Output

- `.agents/hooks/quality-languages` — MANAGED, sorted-unique language tokens one per line. Omitted when list is empty.
