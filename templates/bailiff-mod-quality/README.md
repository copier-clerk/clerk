# bailiff-mod-quality

Writes `.agents/hooks/quality-languages` — a sorted-unique list of active
language identifiers, one per line. Pure render module: no tasks, no native
commands.

`depends_on: [bailiff-mod-base]`, `phase: normal`.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-quality.git <destination>
```

Or via `bailiff init` with `quality_languages` injected by the phase-1 agent.

## Questions

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `quality_languages` | yaml list | `[]` | Active language identifiers; the phase-1 agent injects the sorted union via `--data`. |

## Output

| Path | Lifecycle | Condition |
|------|-----------|-----------|
| `.agents/hooks/quality-languages` | MANAGED | Omitted when `quality_languages` is empty. |
| `.gitignore.d/bailiff-mod-quality` | MANAGED | Always rendered; folded into `.gitignore` by base's post-task. |
