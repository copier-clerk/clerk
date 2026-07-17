# bailiff-mod-github-repo

Renders GitHub forge metadata for a scaffolded project and, optionally, creates
the GitHub remote.

**Managed files** (reconcile on reproduce):

- `.github/CODEOWNERS` — wildcard rule assigning `@<org>` as default reviewer
- `.github/ISSUE_TEMPLATE/bug_report.md` — bug-report template
- `.github/ISSUE_TEMPLATE/feature_request.md` — feature-request template
- `.github/PULL_REQUEST_TEMPLATE/pull_request_template.md` — PR checklist

**Init-only side effect** (runs once, gated on `create_remote=true`):

- Calls `gh repo create` to create the GitHub remote (non-fatal: `gh` absent or
  creation failure → warn and continue, `exit 0`)
- Hard gate: `visibility=public` → `exit 1` before any creation; create a public
  repo manually via `gh repo create` after reviewing the scaffold

`create_remote=false` (default): the `.github/` files render without creating
any remote (adopt-an-existing-repo path).

## Dependencies

Requires `bailiff-mod-base` in the selection (`depends_on: [bailiff-mod-base]`).
Reads `project_name` and `org` from base via `_external_data`.

## Questions

| Key | Type | Choices | Default | Description |
|---|---|---|---|---|
| `create_remote` | bool | — | false | Run `gh repo create` on init |
| `visibility` | str | private, public, internal | private | Repository visibility |
| `remote_protocol` | str | https, ssh | https | Remote URL protocol |
| `push_after_create` | bool | — | false | Push HEAD to origin after creation |
| `team` | str | — | "" | GitHub team slug (omitted when empty) |

Token sourced from ambient `GITHUB_TOKEN` (or legacy `GITHUB_APM_PAT`); no
`secret:` questions.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-github-repo.git <destination>
```
