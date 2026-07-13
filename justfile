default:
    @just --list

# Run tests
test:
    uv run pytest

# Lint and format
lint:
    pre-commit run --all-files

# Type-check
types:
    uv run mypy

# Build
build:
    uv build

# Start dev server
dev:
    @echo "INFO: clerk is a CLI/library — no dev server. Use 'just test' or run 'uv run clerk'." && exit 1

# Clean build artifacts
clean:
    rm -rf dist build .pytest_cache .ruff_cache .mypy_cache

# ---------------------------------------------------------------------------
# Module authoring lifecycle (spec 008b)
# ---------------------------------------------------------------------------

# Lint every module in templates/*/ against the contract (spec 008b / FR-006).
# Exits 0 when templates/ is empty (graceful no-op until spec 009 lands).
check-modules:
    @uv run scripts/check_modules.py

# Scaffold a new module stub under templates/<name>/ using the meta-template.
# Usage: just new-module name=clerk-mod-<name>
# Runs copier dogfooding: renders _meta/module-template/ into the monorepo root.
new-module name="":
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -z "{{name}}" ]]; then
        echo "Usage: just new-module name=clerk-mod-<name>" >&2
        exit 2
    fi
    # --trust: the meta-template ships _tasks (module registration); copier refuses
    # to run tasks on an untrusted source (exit 4). This is a first-party in-repo
    # template we author, so trusting it is correct.
    uv run copier copy _meta/module-template/ . --data module_name="{{name}}" --overwrite --defaults --trust

# Generate catalog.json from templates/*/ and split-repo tags.
# Use --dry-run to print without writing.
generate-catalog *args:
    @uv run scripts/generate_catalog.py {{args}}

# ---------------------------------------------------------------------------
# APM packaging (spec 008)
# ---------------------------------------------------------------------------

# BLOCKER-2 guard: vendor MUST run before apm pack because --check-clean only
# diffs manifests, not the vendored copy. `just pack` / `just release` both
# run vendor first so a stale vendored tree can never ship.

VENDOR_DST := "packages/clerk/.apm/skills/clerk/scripts/clerk"
VENDOR_SRC := "src/clerk"

# Copy src/clerk/*.py (by glob, auto-tracks new modules) into the package.
# Also copies scripts/clerk.py and the source SKILL.md into the package layout.
vendor:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p "{{VENDOR_DST}}"
    # Copy all Python modules from src/clerk/ — glob auto-tracks new files.
    cp {{VENDOR_SRC}}/*.py "{{VENDOR_DST}}/"
    # Copy the bundled entrypoint.
    cp scripts/clerk.py packages/clerk/.apm/skills/clerk/scripts/
    # Copy the skill definition.
    cp skills/clerk/SKILL.md packages/clerk/.apm/skills/clerk/
    echo "vendor: copied src/clerk/*.py → {{VENDOR_DST}}/"

# Check that the vendored copy in packages/ matches source — fail on drift.
# Covers the Python modules AND the vendored scripts/clerk.py + SKILL.md, since
# all three are copied by `vendor` and any can drift from source.
# Run this in CI and before apm pack to catch stale vendored code.
check-vendor:
    #!/usr/bin/env bash
    set -euo pipefail
    PKG="packages/clerk/.apm/skills/clerk"
    fail() {
        echo "check-vendor FAILED: $1 differs from source." >&2
        echo "Run 'just vendor' to regenerate." >&2
        exit 1
    }
    TMP=$(mktemp -d)
    trap 'rm -rf "$TMP"' EXIT
    TDST="$TMP/clerk"
    mkdir -p "$TDST"
    cp {{VENDOR_SRC}}/*.py "$TDST/"
    # Python modules.
    diff -rq "$TDST/" "{{VENDOR_DST}}/" || fail "vendored src/clerk/*.py"
    # Bundled entrypoint + skill definition (non-Python, but still vendored).
    diff -q scripts/clerk.py "$PKG/scripts/clerk.py" || fail "vendored scripts/clerk.py"
    diff -q skills/clerk/SKILL.md "$PKG/SKILL.md" || fail "vendored SKILL.md"
    echo "check-vendor: ok — vendored copy matches source (modules + clerk.py + SKILL.md)"

# Build both Claude and Codex marketplace artifacts.
# Always re-vendors first (BLOCKER-2: --check-clean does not cover vendored files).
pack: vendor check-vendor
    apm pack --marketplace=claude,codex

# Dry-run pack (no files written, but validates config + prints output paths).
pack-dry: vendor check-vendor
    apm pack --marketplace=claude,codex --dry-run

# Gated release sequence — catches version/tree drift before publishing.
# apm publish is documented but deferred pending the registries feature (Q-008b).
release: vendor check-vendor
    apm pack --marketplace=claude,codex --check-versions --check-clean
    @echo "release: manifests up to date. To publish (when registries feature is adopted):"
    @echo "  apm publish --package copier-clerk/clerk"
