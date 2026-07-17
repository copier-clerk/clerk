# bailiff-mod-gitlab-repo

Renders GitLab forge metadata for a scaffolded project and, optionally, creates
the GitLab remote.

**Managed files** (reconcile on reproduce):

- `.gitlab/CODEOWNERS` — wildcard rule assigning `@<org>` as default reviewer
- `.gitlab/issue_templates/bug_report.md` — bug-report template
- `.gitlab/issue_templates/feature_request.md` — feature-request template
- `.gitlab/merge_request_templates/default.md` — MR checklist

**Init-only side effect** (runs once, gated on `create_remote=true`):

- Calls `glab repo create` to create the GitLab remote (non-fatal: `glab` absent
  or creation failure → warn and continue, `exit 0`)
- Hard gate: `visibility=public` → `exit 1` before any creation; create a public
  repo manually via `glab repo create` after reviewing the scaffold

`create_remote=false` (default): the `.gitlab/` files render without creating
any remote (adopt-an-existing-repo path).

## Safety semantics

1. `glab` missing → warn + exit 0 (non-fatal); the rest of the init completes.
2. `visibility=public` → hard exit 1 before any creation.
3. Creation failure → warn + exit 0 (non-fatal).

## Dependencies

Requires `bailiff-mod-base` in the selection (`depends_on: [bailiff-mod-base]`).
Reads `project_name` and `org` from base via `_external_data`.

## Questions

| Key | Type | Choices | Default | Description |
|---|---|---|---|---|
| `create_remote` | bool | — | false | Run `glab repo create` on init |
| `visibility` | str | private, public, internal | private | Repository visibility |
| `remote_protocol` | str | https, ssh | https | Remote URL protocol |
| `push_after_create` | bool | — | false | Push HEAD to origin after creation |
| `team` | str | — | "" | GitLab group path (empty = personal namespace) |

Token sourced from ambient `GITLAB_TOKEN`; no `secret:` questions.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-gitlab-repo.git <destination>
```
