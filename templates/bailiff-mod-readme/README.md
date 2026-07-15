# bailiff-mod-readme

Seeds a `README.md` into a new project (SEED-ONCE — never overwrites user edits).
Supports two styles: a deterministic `static-skeleton` rendered from frozen project
facts, or an `agent-draft` that injects a pre-generated body verbatim.

Runs after `bailiff-mod-base`. Threads `project_name`, `description`, and `stack`
facts from upstream answers.

## Usage

```sh
# static skeleton rendered from frozen facts
copier copy https://github.com/bailiff-io/bailiff-mod-readme.git <destination> \
  --data project_name=myapp \
  --data readme_style=static-skeleton

# agent-draft: supply the pre-generated body via --data
copier copy https://github.com/bailiff-io/bailiff-mod-readme.git <destination> \
  --data project_name=myapp \
  --data readme_style=agent-draft \
  --data readme_body="# myapp\n\n..."
```

## Questions

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `readme_style` | choice | `agent-draft` | `static-skeleton` or `agent-draft` |
| `confirm_readme_draft` | bool | `false` | Confirm draft acceptance (agent-draft only) |
| `readme_body` | str | `""` | Pre-generated README body (agent-frozen via --data) |
| `project_name` | str | threaded | Project name (threaded from bailiff-mod-base) |
| `description` | str | threaded | One-line description (threaded from bailiff-mod-base) |
| `stack` | str | `""` | Stack summary for static-skeleton rendering |

## Output

- `README.md` — SEED-ONCE (`_skip_if_exists`): never overwrites user edits on reproduce.
