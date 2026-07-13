#!/usr/bin/env bash
# Fan-out one released module from the clerk monorepo to its own
# split repo (spec 008b / ADR-0006 / contracts/fanout.md "Fan-out mechanics").
#
# Snapshot-mirror, NOT a history-preserving split: copier only needs the correct
# tree at each PEP 440 tag, so this is `cp subdir -> commit -> tag -> push`.
#
# Idempotent + re-run-safe: auto-creates the target repo if missing, skips the
# commit when there is no content diff, and skips entirely when the version tag
# already exists on the remote (so re-running failed steps 3-7 is safe).
#
# Inputs (environment):
#   NAME       module dir name, e.g. clerk-mod-base   (the `<name>` before -vX.Y.Z)
#   VERSION    clean PEP 440 tag for the split repo, e.g. v1.2.0
#   APP_TOKEN  GitHub App installation token with contents:write (+ administration:write
#              for auto-create) on the copier-clerk org
# Optional:
#   MODULE_SRC directory holding the module tree (default: templates/${NAME})
#   GITHUB_SHA monorepo release commit (for the audit-trail commit message)
#   TARGET_OWNER  org that owns the split repos (default: copier-clerk)
#
# Exit codes: 0 = mirrored or nothing to do; non-zero = failure.
set -euo pipefail

: "${NAME:?NAME is required (module dir name, e.g. clerk-mod-base)}"
: "${VERSION:?VERSION is required (clean PEP 440 tag, e.g. v1.2.0)}"
: "${APP_TOKEN:?APP_TOKEN is required (GitHub App installation token)}"

MODULE_SRC="${MODULE_SRC:-templates/${NAME}}"
TARGET_OWNER="${TARGET_OWNER:-copier-clerk}"
TARGET="${TARGET_OWNER}/${NAME}"
REMOTE="https://x-access-token:${APP_TOKEN}@github.com/${TARGET}.git"
SHORT_SHA="${GITHUB_SHA:0:8}"

if [[ ! -d "${MODULE_SRC}" ]]; then
  echo "fanout: module source '${MODULE_SRC}' not found" >&2
  exit 1
fi

# 1. Ensure the split repo exists. If it is already present (the normal steady
#    state — repos are created once and reused), we push into it with the App's
#    contents:write and never need to create anything.
#
#    Best-effort auto-create for a brand-new module: try POST /orgs/{org}/repos.
#    NOTE: a GitHub App installation token is frequently NOT authorized to create
#    org repos ("403 Resource not accessible by integration") even with the
#    org-administration permission granted — repo creation is effectively a
#    maintainer action. So a failed create is NOT fatal here: we log it and let
#    the existence check below decide. A maintainer pre-creates a new module's
#    mirror once (see docs/runbooks/fanout-release.md); thereafter this is a no-op.
if GH_TOKEN="${APP_TOKEN}" gh api "/repos/${TARGET}" >/dev/null 2>&1; then
  echo "fanout: ${TARGET} exists; reusing"
else
  echo "fanout: ${TARGET} missing — attempting auto-create (best effort)…"
  if GH_TOKEN="${APP_TOKEN}" gh api -X POST "/orgs/${TARGET_OWNER}/repos" \
      -f name="${NAME}" -F private=false \
      -f description="Mirror of copier-clerk/clerk:templates/${NAME} (generated; do not edit)" \
      >/dev/null 2>&1; then
    echo "fanout: created ${TARGET}"
  elif GH_TOKEN="${APP_TOKEN}" gh api "/repos/${TARGET}" >/dev/null 2>&1; then
    echo "fanout: ${TARGET} now present (created concurrently); reusing"
  else
    echo "fanout: ${TARGET} does not exist and the App token could not create it." >&2
    echo "fanout: a maintainer must pre-create it once (see docs/runbooks/fanout-release.md):" >&2
    echo "        gh repo create ${TARGET} --public" >&2
    exit 1
  fi
fi

# 2. Idempotency pre-check: if the version tag already exists remotely, we are
#    re-running an already-completed fan-out for this version. Nothing to do.
if git ls-remote --tags "${REMOTE}" "refs/tags/${VERSION}" | grep -q .; then
  echo "fanout: ${TARGET} already has tag ${VERSION}; skipping"
  exit 0
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT
SPLIT="${WORKDIR}/split"

# 3. Clone the target. A freshly-created repo is empty; git clone still succeeds
#    but leaves no HEAD, so seed a `main` branch in that case. A just-created repo
#    can briefly 404 before it propagates, so retry the clone a few times.
clone_ok=0
for attempt in 1 2 3 4 5; do
  if git clone --quiet "${REMOTE}" "${SPLIT}" 2>/dev/null; then
    clone_ok=1
    break
  fi
  echo "fanout: clone of ${TARGET} not ready (attempt ${attempt}); retrying…" >&2
  rm -rf "${SPLIT}"
  sleep 3
done
if [[ "${clone_ok}" -ne 1 ]]; then
  echo "fanout: could not clone ${TARGET} after creating it" >&2
  exit 1
fi
git -C "${SPLIT}" config user.name "clerk-fanout[bot]"
git -C "${SPLIT}" config user.email "clerk-fanout[bot]@users.noreply.github.com"

if git -C "${SPLIT}" rev-parse --verify --quiet HEAD >/dev/null; then
  BRANCH="$(git -C "${SPLIT}" symbolic-ref --short HEAD)"
else
  BRANCH="main"
  git -C "${SPLIT}" checkout --quiet -b "${BRANCH}"
fi

# 4. Replace contents with exactly templates/<name>/. (nothing else: no cog.toml,
#    no CI, no sibling modules). Preserve the split repo's .git.
find "${SPLIT}" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -R "${MODULE_SRC}/." "${SPLIT}/"

git -C "${SPLIT}" add -A

# 5. Skip the commit when there is no content diff (re-run safety); still ensure
#    the version tag exists on HEAD so the release is tagged even in that corner.
if git -C "${SPLIT}" diff --cached --quiet && \
   git -C "${SPLIT}" rev-parse --verify --quiet HEAD >/dev/null; then
  echo "fanout: ${TARGET} content unchanged; tagging existing HEAD"
else
  git -C "${SPLIT}" commit --quiet \
    -m "release: ${VERSION} (mirrored from ${TARGET_OWNER}/clerk@${SHORT_SHA})"
fi

# 6. Annotated clean tag (guard against a pre-existing local tag) + push.
if ! git -C "${SPLIT}" rev-parse --verify --quiet "refs/tags/${VERSION}" >/dev/null; then
  git -C "${SPLIT}" tag -a "${VERSION}" -m "${NAME} ${VERSION}"
fi
git -C "${SPLIT}" push --quiet origin "HEAD:${BRANCH}" --follow-tags

echo "fanout: mirrored ${MODULE_SRC} -> ${TARGET} @ ${VERSION}"
