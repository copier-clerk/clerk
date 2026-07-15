---
document_type: security-review
review_type: tasks
assessment_date: 2026-07-14
codebase_analyzed: bailiff-io/bailiff (spec 011 — de-opinionated module family)
total_files_analyzed: 4
total_findings: 4
overall_risk: LOW
critical_count: 0
high_count: 0
medium_count: 1
low_count: 3
informational_count: 0
owasp_categories: [A05, A06, A08]
cwe_ids: [CWE-22, CWE-78, CWE-829]
field_summaries:
  document_type: "Always 'security-review'. Allows indexers to skip non-review documents."
  review_type: "Which command generated this document: audit, branch, staged, plan, tasks, or followup."
  assessment_date: "ISO 8601 date the review was performed (YYYY-MM-DD)."
  overall_risk: "Highest severity tier with active findings (CRITICAL, HIGH, MODERATE, LOW, INFORMATIONAL)."
  critical_count: "Number of Critical findings (CVSS 9.0-10.0)."
  high_count: "Number of High findings (CVSS 7.0-8.9)."
  medium_count: "Number of Medium findings (CVSS 4.0-6.9)."
  low_count: "Number of Low findings (CVSS 0.1-3.9)."
  informational_count: "Number of Informational findings."
  owasp_categories: "OWASP Top 10 2025 categories (A01-A10) that have at least one finding."
  cwe_ids: "CWE identifiers referenced in this document."
  finding_id: "Unique finding identifier (SEC-NNN) for cross-referencing and task linkage."
  location: "File path and line number of the vulnerable code (path/to/file.ext:line)."
  owasp_category: "OWASP Top 10 2025 category for this finding (AXX:2025-Name)."
  cwe: "Common Weakness Enumeration identifier with short name (CWE-NNN: Name)."
  cvss_score: "CVSS v3.1 base score (0.0-10.0). 9.0+=Critical, 7.0-8.9=High, 4.0-6.9=Medium, 0.1-3.9=Low."
  spec_kit_task: "Spec-Kit task ID for backlog tracking and remediation follow-up (TASK-SEC-NNN)."
---

# Security Review — Task Sequencing & Coverage

## Executive Summary

The task list for spec 011 is **well-structured from a security perspective**. The project is a copier template scaffolder (CLI-only, no runtime server, no stored user data), so the attack surface is limited to: trust-gated code execution during scaffolding, path-traversal in user-supplied names, supply-chain pins in generated CI/hook configurations, and accidental secret embedding.

All four security-relevant controls from the spec are explicitly represented in the tasks:

1. **FR-005 / secrets policy** — `test_secrets_policy.py` is checked in T002 baseline and T024 full suite; no `secret:` questions in any module.
2. **FR-009 / trust-gated tasks** — every module with `_tasks` has them explicitly called out with init-only guards.
3. **Path-traversal guard (T019)** — the 4-condition guard is ported exactly.
4. **Public-repo consent gate (T018)** — hard abort-without-consent preserved.

No critical or high findings. One medium and three low observations follow.

## Tasks Reviewed

- `specs/011-deopinionated-module-family/tasks.md` (30 tasks)
- `specs/011-deopinionated-module-family/spec.md` (FRs and SCs)
- `specs/011-deopinionated-module-family/contracts/_cross-cutting.md`
- `specs/011-deopinionated-module-family/agent-assignments.yml`

## Findings

### SEC-001: T019 path-traversal guard runs after native scaffold, not before

- **Severity**: Medium (CVSS 4.3)
- **Location**: specs/011-deopinionated-module-family/tasks.md:96
- **OWASP**: A05:2025-Security Misconfiguration
- **CWE**: CWE-22: Improper Limitation of a Pathname to a Restricted Directory
- **Spec-Kit Task**: TASK-SEC-001

The task description for T019 (`bailiff-mod-package-add`) correctly states the guard must run "BEFORE any mkdir", but it does not explicitly require the guard to run before the native `add` command. The requirement in the body says "scaffold happens only after the guard passes" — this is good, but the loop-test assertion clause should also verify the guard fires before the workspace-registration invocation. This is an implementation-order note rather than a task-ordering gap.

**Recommendation**: When implementing T019, ensure the loop test asserts that a path-traversal attempt produces ZERO side effects (no dir created, no native command invoked, no workspace registration). The task description is adequate; this is a verification-coverage note for the implementing coder.

### SEC-002: Supply-chain pin freshness has no automated gate before release

- **Severity**: Low (CVSS 2.1)
- **Location**: specs/011-deopinionated-module-family/tasks.md:113
- **OWASP**: A06:2025-Vulnerable and Outdated Components
- **CWE**: CWE-829: Inclusion of Functionality from Untrusted Control Sphere

MI-1 (version auto-updater) is explicitly deferred to a separate future spec. The 18 modules hardcode action majors (GitHub Actions), pre-commit hook `rev` pins, tool versions, and CDK versions. Between authoring and the first upstream vulnerability disclosure, there is no automated mechanism to flag stale pins.

**Recommendation**: Already acknowledged in the tasks (MI-1 note in Phase 6). No action needed in this build set — the risk is accepted as low because pins are version-locked (deterministic, not floating), and the maintainer controls the release cadence.

### SEC-003: T014 agentic MCP config renders environment variable references without validation

- **Severity**: Low (CVSS 1.8)
- **Location**: specs/011-deopinionated-module-family/tasks.md:82
- **OWASP**: A05:2025-Security Misconfiguration
- **CWE**: CWE-78: Improper Neutralization of Special Elements used in an OS Command

T014 states MCP server entries use `${VAR}` references (never `secret:` questions). The rendered JSON/TOML files will contain these references as literal strings consumed by the target agent runtime (Claude, Codex, etc.), not by the template engine. However, if the frozen `mcp_servers` list injected via `--data` contains shell metacharacters beyond the `${VAR}` pattern, the rendered config could be malformed.

**Recommendation**: The implementing coder should validate that `mcp_servers` entries match a safe pattern (alphanumeric + `_` + `/` + `${}`) and refuse/escape anything else. This is a defense-in-depth measure; the phase-1 agent controls the input, so the practical risk is minimal.

### SEC-004: Parallel module coders share registration files without explicit merge coordination

- **Severity**: Low (CVSS 1.2)
- **Location**: specs/011-deopinionated-module-family/tasks.md:174
- **OWASP**: A08:2025-Software and Data Integrity Failures
- **CWE**: CWE-829: Inclusion of Functionality from Untrusted Control Sphere

The parallel example notes that `cog.toml` and `catalog-sources.toml` are "append-per-module; coordinate merges or serialize the registration edits." Each parallel-coder works in an isolated worktree and self-commits. When merging worktree branches back, conflicting appends to these shared files need manual resolution. This is not a vulnerability but a data-integrity concern: a bad merge could silently drop a module from the registration surface, causing it to pass `just check-modules` locally (if it re-runs after the bad merge) but fail in CI.

**Recommendation**: The orchestrator should serialize the `just check-modules` run after all worktree merges, which T025 already does. No additional task needed — the existing Phase 6 gates catch this. For the orchestrator: merge worktree branches one at a time and run `just check-modules` incrementally if feasible.

## Confirmed Secure Patterns

| Pattern | Coverage | Task(s) |
|---------|----------|---------|
| No `secret:` questions (FR-005, Constitution VI) | Baseline + full suite | T002, T024 |
| Trust-gated tasks with preflight + init-only guard (FR-009/FR-012a) | Every module with `_tasks` | T004–T009, T014, T016–T022 |
| Public-repo hard abort-without-consent (github-repo) | Explicit port with loop test | T018 |
| Path-traversal 4-condition guard (package-add) | Explicit port with loop test | T019 |
| Never irreversible cloud actions at scaffold time (FR-009) | All IaC + CDK + agentic modules | T014, T020–T022 |
| Pin determinism (no `:latest`, no floating tags) | CI + hook configs | T005, T016, T017, T020 |
| Reconfirm-gated irreversible public actions (SC-009) | Phase 7 entirely maintainer-driven | T026–T030 |
| Secrets from ambient env only, never template questions | All modules | Enforced via `test_secrets_policy.py` |
| Sequencing: governance gate blocks ALL module work | T001 hard-gates Phases 3–7 | T001 |
| Sequencing: base before consumers (dependency root) | Slice ordering A→B→C | T004 first |

## Action Plan & Next Steps

1. **No critical/high findings** — no `/speckit.security-review.followup` needed.
2. **SEC-001** (medium): add a note to the T019 coder prompt ensuring the loop test asserts zero side effects on traversal attempts. No separate remediation task required — it is within the scope of T019's existing DoD.
3. **SEC-002/003/004** (low): accepted risk or already mitigated by existing gates; no action.
4. **No durable memory capture needed** — no systemic vulnerability or reusable security pattern discovered beyond what the spec already mandates.

---

## Memory Hub INDEX.md Row

```text
| specs/011-deopinionated-module-family/security-review-tasks.md | tasks | 2026-07-14 | LOW | C:0 H:0 M:1 L:3 | A05,A06,A08 |
```
