# bailiff-mod-gitlab-repo

GitLab repo-creation parity (spec 012 / FR-012): the **exact semantic port of
`bailiff-mod-github-repo` to `glab`**. Pure side-effect module — writes no
files (`reconcile=false`); a trust-gated task chain creates the GitLab remote.

## Safety semantics (identical to github-repo)

1. **`glab` missing** → warn + exit 0 (non-fatal); the rest of the init
   completes.
2. **`visibility=public` without explicit consent** → **hard exit 1 BEFORE any
   creation** (no silent public repos). Run `glab repo create --public`
   manually after reviewing the scaffold.
3. **Creation failure** (repo exists, no auth, network) → warn + exit 0
   (non-fatal).
4. Optional push gated on `push_after_create`.

Token comes from the ambient `GITLAB_TOKEN` environment (read by glab itself);
there are **no `secret:` questions** (Constitution VI / FR-005).

## Questions (same shape as github-repo)

| Key | Type | Default | Notes |
|---|---|---|---|
| `project_name` | str | threaded from base | repo name |
| `visibility` | str | `private` (`[private, public, internal]`) | public = hard consent gate |
| `remote_protocol` | str | `https` | via `glab config set git_protocol` |
| `push_after_create` | bool | `false` | optional push |
| `team` | str | `""` | GitLab group path (glab counterpart of github-repo's team) |

Tasks are init-only (`reconcile=false`) — never re-run on reproduce.

Edge: `run_after: [bailiff-mod-base]`.

## Usage

```sh
copier copy https://github.com/bailiff-io/bailiff-mod-gitlab-repo.git <destination>
```
