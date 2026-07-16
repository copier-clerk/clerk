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
    @echo "INFO: bailiff is a CLI/library — no dev server. Use 'just test' or run 'uv run bailiff'." && exit 1

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
# Usage: just new-module name=bailiff-mod-<name>
# Runs copier dogfooding: renders _meta/module-template/ into the monorepo root.
new-module name="":
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -z "{{name}}" ]]; then
        echo "Usage: just new-module name=bailiff-mod-<name>" >&2
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

# Spec 013 (ADR-0008): the deterministic engine ships as the `bailiff` PyPI CLI
# (`uvx bailiff`), so the skill package vendors ONLY SKILL.md — no script, no
# module tree.

vendor:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p packages/bailiff/.apm/skills/bailiff
    cp skills/bailiff/SKILL.md packages/bailiff/.apm/skills/bailiff/
    echo "vendor: copied skills/bailiff/SKILL.md → packages/bailiff/.apm/skills/bailiff/"

# Check that the vendored SKILL.md matches source — fail on drift.
# Run this in CI and before apm pack to catch a stale vendored skill.
check-vendor:
    #!/usr/bin/env bash
    set -euo pipefail
    PKG="packages/bailiff/.apm/skills/bailiff"
    diff -q skills/bailiff/SKILL.md "$PKG/SKILL.md" || {
        echo "check-vendor FAILED: vendored SKILL.md differs from source." >&2
        echo "Run 'just vendor' to regenerate." >&2
        exit 1
    }
    echo "check-vendor: ok — vendored SKILL.md matches source"

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
    @echo "  apm publish --package bailiff-io/bailiff"
