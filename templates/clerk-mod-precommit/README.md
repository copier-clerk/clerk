# clerk-mod-precommit

Copier module that manages Git hook configuration for a project. Single writer
of `.pre-commit-config.yaml` (pre-commit), `lefthook.yml` (lefthook), or nothing
(`none`) — assembled from base hygiene hooks, gitleaks secret scanning,
shellcheck, Conventional Commits enforcement, and a phase-1-agent-frozen union
of language hook blocks.

Implements the `hook_manager` + `hook_blocks` frozen-union single-writer contract
(`_cross-cutting §4, M1`).

## Usage

```sh
copier copy https://github.com/copier-clerk/clerk-mod-precommit.git <destination>
```

## Questions

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `hook_manager` | choice | `pre-commit` | Hook manager: `pre-commit`, `lefthook`, or `none` |
| `enforce_conventional_commits` | bool | `true` | Add Conventional Commits commit-msg hook |
| `enable_typo_check` | bool | `true` | Add typo-check hook |
| `precommit_exclude_patterns` | yaml | `[]` | Extra exclude patterns for `.pre-commit-config.yaml` |
| `install_hooks` | bool | `true` | Run hook manager install on init |
| `hook_blocks` | yaml | `[]` | Agent-frozen union of language hook blocks (injected via `--data`) |

## Outputs

- `.pre-commit-config.yaml` — when `hook_manager=pre-commit` (MANAGED)
- `lefthook.yml` — when `hook_manager=lefthook` (MANAGED)
- `.pre-commit-hooks/check-commit-msg.py` — vendored Conventional Commits validator (MANAGED)

## Dependencies

`run_after: [clerk-mod-base]`
