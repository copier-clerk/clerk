# bailiff-mod-github-repo

Creates the GitHub remote for a scaffolded project. Pure side-effect module —
writes no files to the project tree; the only output is the remote repository
and the recorded answers file.

## Behaviour

- **default_enabled=false** — must be opted in explicitly.
- Runs after `bailiff-mod-base` (the project must exist before the remote is created).
- **private** (default) and **internal** repos are created non-fatally: if `gh`
  is absent or repo creation fails, a warning is printed and the scaffold
  continues (`exit 0`).
- **public** always aborts with `exit 1` — there is no runtime confirmation
  question, so a public repo must be created manually via `gh repo create`.
- Token sourced from ambient `GITHUB_TOKEN` (or legacy `GITHUB_APM_PAT`);
  no `secret:` questions.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-github-repo.git <destination>
```

## Questions

| Key | Type | Choices | Default | Description |
|-----|------|---------|---------|-------------|
| `visibility` | str | private, public, internal | private | Repository visibility |
| `remote_protocol` | str | https, ssh | https | Remote URL protocol |
| `push_after_create` | bool | — | false | Push HEAD to origin after creation |
| `team` | str | — | "" | GitHub team slug (omitted when empty) |
