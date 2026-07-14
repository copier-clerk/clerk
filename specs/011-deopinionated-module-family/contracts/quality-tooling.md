# Contract — clerk-mod-precommit / -quality / -justfile (NEW)

References [_cross-cutting.md](./_cross-cutting.md). All `run_after: [clerk-mod-base]`.

## clerk-mod-precommit — OWNS the hook_manager threading contract (_cross-cutting §4, M1)
- **Questions**: `hook_manager [pre-commit, lefthook, none]=pre-commit` (drop husky/simple-git-hooks); `enforce_conventional_commits=true`; `enable_typo_check=true`; `precommit_exclude_patterns` (yaml, [] — de-hardwire the SpecKit exclude); `install_hooks=true`; plus `hook_blocks` (yaml) — the AGENT-FROZEN UNION of language hook blocks injected via `--data` (NOT runtime accumulation — the circular case, M1).
- **Outputs**: `.pre-commit-config.yaml` (pre-commit) OR `lefthook.yml` (lefthook) OR nothing (none) — SINGLE WRITER, MANAGED, assembled from the base hygiene hooks + secret scan (gitleaks) + shellcheck + close-keywords commit-msg + the frozen `hook_blocks`. Vendored close-keywords scripts under `.pre-commit-hooks/` (managed). All rev pins hardcoded.
- **Task**: `install_hooks` → trust-gated `pre-commit install` / `lefthook install`, **init-only-guarded** (FR-012a); when manager != none.
- Language modules do NOT write the hook file; the agent freezes `hook_manager` + the `hook_blocks` union up front. justfile's `lint` recipe reads the frozen `hook_manager`.

## clerk-mod-quality — single-writer language list (kept SEPARATE per maintainer)
- **Questions**: `quality_languages` (yaml OPEN list, default [] — NOT a `choices:` dropdown; an AGENT-FROZEN UNION answer the phase-1 agent injects via `--data` from the selected language set — see _cross-cutting M1, the `gitignore_stack` pattern; NOT runtime accumulation).
- **Output**: `.agents/hooks/quality-languages` — sorted-unique, one token per line. MANAGED (reconcile=true, NOT seed-once). Empty list → NO file (the upstream skip). Pure render, no tasks.
- `run_after: [clerk-mod-base]` (+ languages for the list contribution). Single writer, same pattern as gitignore_stack.

## clerk-mod-justfile
- **Questions**: `language [python, ts, go, rust, ""]` (free-text→choices); threaded `js_pkg_manager` (standalone default bun) + `hook_manager` (standalone default pre-commit).
- **Output**: `justfile` — SEED-ONCE (reconcile=false). Fixed recipe set (default/test/lint/build/dev/clean) with per-language idiomatic bodies or fail-loud stubs; `test` recipe uses the threaded `js_pkg_manager` (not hardcoded npm); `lint` recipe uses `hook_manager` (not hardcoded pre-commit); rust build keeps `--release` as a commented escape hatch. just IS the task-runner choice (make/task = future modules).

## Tests
precommit: pre-commit vs lefthook vs none render the right file / no file; threaded language blocks appear once (no double-append); `install_hooks` task stubbed. quality: quality_languages sorted-unique, empty→no file. justfile: recipes use threaded pkg-manager + hook-manager, seed-once preserved on re-run. No secret questions.
