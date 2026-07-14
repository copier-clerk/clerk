# Contract — clerk-mod-readme / -stack-adr / -github-repo / -package-add (NEW)

> **clerk-mod-org-policy DROPPED from 011** (critique R1): it is inert until an org-source-fetch
> module exists (not planned here), so it ships in a future org-governance spec with its only
> consumer, not as a dead module now. Its former contract is removed below.

References [_cross-cutting.md](./_cross-cutting.md). All `run_after: [clerk-mod-base]`.

## clerk-mod-readme
- **Questions**: `readme_style [static-skeleton, agent-draft]=agent-draft`; `confirm_readme_draft` (bool, when agent-draft); `readme_body` (str, agent-frozen via --data when agent-draft); threaded project_name/description/stack facts.
- **Output**: `README.md` — SEED-ONCE (`_skip_if_exists`). static-skeleton = deterministic render from frozen facts (name/desc/stack/license); agent-draft = render the frozen `readme_body`. Uses resolved PM idiom (uv/pnpm) not pip/npm. No agent in reproduce path.

## clerk-mod-stack-adr
- **Questions**: `format [simple, adr]=simple` (OPT-IN module); `adr_dir=docs/decisions` (matches base scaffold); agent-frozen stack facts (`stack_pins`, `framework`, `rationale`) via --data (FR-010 — sorts before language layers, cannot read run-order).
- **Output**: `STACK.md` (simple) or numbered ADR under `adr_dir` (adr) — SEED-ONCE, initial-setup-only (docs drift; never re-rendered). MADR headings, 3-digit ADR padding, Status=Accepted. DROP the reproduce-time staleness/CVE agent step (no Phase-0 runtime, no substitute). Render section strings as pre-computed data (avoid double-render of user Jinja-like content).

## clerk-mod-github-repo
- **Questions**: `visibility [private, public, internal]=private` (replaces public:bool; gate predicate `visibility=='public'`); `remote_protocol [https, ssh]=https`; `push_after_create` (bool, false); `team` (str, ""=omit). default_enabled=false.
- **Output**: NONE (pure side-effect). Trust-gated `_task`: `gh repo create --source . origin`, visibility-flagged. **public keeps the HARD abort-without-consent gate (exit 1)**; tool-missing/creation-failure = non-fatal `exit 0` (upstream warn-and-continue). Token from ambient env (GITHUB_TOKEN; GITHUB_APM_PAT documented legacy). Drop the gh-api.py wrapper (plain gh only). reconcile=false.

## clerk-mod-package-add (monorepo)
- **Questions**: `name` (new package), `lang [ts, python, go, rust]`, `dir` (default packages/); `js_package_manager [bun, pnpm]` / python via `python_pkg_manager`; `resolve_stack` (bool) for agent-injected sibling pin alignment; `rust_edition [2024,2021]=2024`.
- **Behavior**: scaffold the new package DIR + seed manifest, then register it in the workspace via the NATIVE add command (`pnpm add`/`bun add`/`uv add`/`cargo add`/`go work use` as appropriate) — the tool writes `pnpm-workspace.yaml` vs `package.json workspaces[]` itself (FR-007). **Port the 4-condition path-traversal guard EXACTLY** (`/`, `\`, `..`, `.`, empty), BEFORE any mkdir (security-pinned, no relaxation). Gated on base `layout=monorepo`.

## Tests
readme: static vs agent-draft render + seed-once; stack-adr: simple/adr from frozen facts, seed-once, no agent in reproduce; github-repo: public without consent aborts (exit 1), tool-missing non-fatal, task stubbed; package-add: path-traversal guard rejects all 4 bad inputs, native add stubbed, workspace registration. No secret questions.
