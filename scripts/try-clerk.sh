#!/usr/bin/env bash
# try-clerk.sh — walk the whole clerk slice-1 loop, one step at a time, pausing
# so you can inspect the result of each stage.
#
# It builds a REAL tagged git repo from examples/clerk-template-example (copier treats a
# local path exactly like a remote), then drives the four verbs through the
# bundled script (scripts/clerk.py):
#
#     discover → trust → init (--check, then real) → reproduce
#
# The finale demonstrates the copier-only reproduce — no clerk, no just.
#
# Nothing touches your real config: trust is written to a scratch
# COPIER_SETTINGS_PATH, and everything lives under a temp dir printed at the end.
#
# Requirements: git, uv, and gh (authenticated: `gh auth status`) — the example
# template's LICENSE task calls `gh api /licenses`.
#
# Usage:
#     bash scripts/try-clerk.sh            # pause between steps (press Enter)
#     bash scripts/try-clerk.sh --no-pause # run straight through
#     KEEP=1 bash scripts/try-clerk.sh     # keep the temp dir on exit

set -euo pipefail

# --- locate the clerk repo (this script lives in <repo>/scripts) ---------------
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

PAUSE=1
[[ "${1:-}" == "--no-pause" ]] && PAUSE=0

step() {
  echo
  echo "════════════════════════════════════════════════════════════════════"
  echo "▶ $*"
  echo "════════════════════════════════════════════════════════════════════"
}
run()  { echo "\$ $*"; "$@"; }          # echo a command, then run it
pause() { [[ $PAUSE -eq 1 ]] && read -rp $'\n(press Enter to continue) '; return 0; }

# --- preflight -----------------------------------------------------------------
step "Preflight: check git / uv / gh"
run command -v git >/dev/null && echo "git: ok"
run command -v uv  >/dev/null && echo "uv: ok"
if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  echo "gh: ok (authenticated)"
else
  echo "WARNING: gh missing or not authenticated — the LICENSE task will fail."
  echo "Run 'gh auth login' first, or the init step will error on task 2."
fi
pause

# --- scratch workspace ---------------------------------------------------------
WORK="$(mktemp -d "${TMPDIR:-/tmp}/clerk-try.XXXXXX")"
export COPIER_SETTINGS_PATH="$WORK/settings.yml"   # isolate trust store
TPL="$WORK/clerk-template-example"
DEST="$WORK/my-project"
echo "Workspace: $WORK"
echo "Trust store (scratch): $COPIER_SETTINGS_PATH"

cleanup() {
  if [[ "${KEEP:-0}" == "1" ]]; then
    echo; echo "KEEP=1 — leaving workspace at: $WORK"
  else
    rm -rf "$WORK"; echo; echo "Cleaned up $WORK (set KEEP=1 to keep it)."
  fi
}
trap cleanup EXIT

# --- build a real, tagged template repo from the bundled example ---------------
step "Build a local git template repo from examples/clerk-template-example (tagged v1.0.0)"
cp -R "$REPO/examples/clerk-template-example" "$TPL"
export GIT_AUTHOR_NAME=clerk-try GIT_AUTHOR_EMAIL=try@clerk.invalid
export GIT_COMMITTER_NAME=clerk-try GIT_COMMITTER_EMAIL=try@clerk.invalid
run git -C "$TPL" init -q
run git -C "$TPL" add -A
run git -C "$TPL" commit -qm "clerk-template-example v1.0.0"
run git -C "$TPL" tag v1.0.0
echo "Template repo ready at $TPL"
pause

# --- 1) discover ---------------------------------------------------------------
step "1) discover — static JSON (tags, questions, reproducible flag; no code runs)"
run uv run scripts/clerk.py discover "$TPL"
pause

# --- 2) trust + init -----------------------------------------------------------
step "2a) The template runs tasks (git init + LICENSE) → it must be trusted first"
echo "First, try WITHOUT trust to see the refusal (expected exit 3):"
set +e
uv run scripts/clerk.py init --run-spec /dev/stdin <<YML
source: "$TPL"
dest: "$DEST"
answers: { project_name: hello-clerk, org: acme corp, license: Apache-2.0, description: my first clerk project }
YML
echo "(exit $?)"
set -e
pause

step "2b) Grant trust with an explicit consent step, then list it"
run uv run scripts/clerk.py trust add "$TPL"
run uv run scripts/clerk.py trust list
echo "--- scratch settings.yml written by the script ---"
cat "$COPIER_SETTINGS_PATH"
pause

# write the run-spec to a file for the remaining steps
cat > "$WORK/run-spec.yml" <<YML
source: "$TPL"
dest: "$DEST"
answers: { project_name: hello-clerk, org: acme corp, license: Apache-2.0, description: my first clerk project }
YML

step "2c) init --check — validates inputs, writes NOTHING (copier dry run)"
run uv run scripts/clerk.py init --run-spec "$WORK/run-spec.yml" --check
echo "dest exists after --check? $([[ -e "$DEST" ]] && echo YES || echo 'no (correct)')"
pause

step "2d) init — generate the project for real"
run uv run scripts/clerk.py init --run-spec "$WORK/run-spec.yml"
echo "--- generated tree ---"; find "$DEST" -type f -not -path '*/.git/*' | sort
echo "--- README.md ---";            cat "$DEST/README.md"
echo "--- LICENSE (head, via gh) ---"; head -4 "$DEST/LICENSE"
echo "--- .copier-answers.yml (note _src_path + _commit + frozen today) ---"
cat "$DEST/.copier-answers.yml"
echo
echo "NOTE: no justfile or clerk-specific file was written."
echo "The .copier-answers.yml is the entire reproduce state."
pause

# --- 3) reproduce via the bundled script ---------------------------------------
step "3a) reproduce via scripts/clerk.py — corrupt a rendered file, replay, confirm restore"
echo "Before (checksums):"; ( cd "$DEST" && { shasum README.md out.txt 2>/dev/null || shasum README.md; } )
echo "Corrupting README.md and deleting .gitignore..."
echo "CORRUPTED BY HAND" > "$DEST/README.md"
rm -f "$DEST/.gitignore"
run uv run scripts/clerk.py reproduce "$DEST"
echo "After (checksums — README restored, .gitignore back):"
( cd "$DEST" && shasum README.md .gitignore )
echo "--- README.md restored content ---"; head -3 "$DEST/README.md"
echo
echo "NOTE: LICENSE is generated by a task from GitHub's LIVE license database"
echo "(not pinned to the recorded commit), so — like .git — it is a side effect"
echo "intentionally OUTSIDE the byte-identical reproduce set."
pause

# --- 4) copier-only reproduce (no clerk, no just) ------------------------------
step "4) Copier-only reproduce — the fallback: no clerk, no just"
echo "scripts/clerk.py reproduce only issues plain 'copier recopy' commands."
echo "Here is the exact fallback — works on any machine with copier installed:"
echo
echo "  cd \$DEST && copier recopy --vcs-ref=:current: --defaults --overwrite"
echo
echo "Corrupting README.md again to prove it..."
echo "CORRUPTED AGAIN" > "$DEST/README.md"
( cd "$DEST" && copier recopy --vcs-ref=:current: --defaults --overwrite )
echo "--- README.md after copier-only reproduce ---"; head -3 "$DEST/README.md"
echo
echo "The .copier-answers.yml is the entire reproduce state."
echo "No clerk on PATH, no justfile, no clerk-specific file needed."
pause

step "Done"
echo "You drove the full loop: discover → trust → init → reproduce."
echo "And confirmed the copier-only fallback works without clerk."
echo "Workspace: $WORK"
