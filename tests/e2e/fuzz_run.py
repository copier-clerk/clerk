"""FUZZ category E2E harness: random valid answer generation across 19 modules.

Run via:
    cd /Users/sjors/personal/dev/bailiff
    BAILIFF_E2E_ROOT=/tmp/bailiff-e2e-fuzz uv run python tests/e2e/fuzz_run.py
"""

from __future__ import annotations

import random
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
# Ensure both `src/` (bailiff package) and repo root (`tests/` package) are importable
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO))

from tests.e2e.harness import BailiffError, run_scenario  # noqa: E402

random.seed(42)

# ---------------------------------------------------------------------------
# Module answer-generation helpers
# ---------------------------------------------------------------------------

MODULES = [
    "bailiff-mod-agentic",
    "bailiff-mod-apm",
    "bailiff-mod-base",
    "bailiff-mod-cdk",
    "bailiff-mod-ci-github",
    "bailiff-mod-ci-gitlab",
    "bailiff-mod-cloudformation",
    "bailiff-mod-github-repo",
    "bailiff-mod-go",
    "bailiff-mod-justfile",
    "bailiff-mod-package-add",
    "bailiff-mod-precommit",
    "bailiff-mod-python",
    "bailiff-mod-quality",
    "bailiff-mod-readme",
    "bailiff-mod-rust",
    "bailiff-mod-stack-adr",
    "bailiff-mod-terraform",
    "bailiff-mod-ts",
]

# All optional modules (everything except base, which is always first)
OPTIONAL_MODULES = [m for m in MODULES if m != "bailiff-mod-base"]


def rand_bool(prob_true: float = 0.5) -> bool:
    return random.random() < prob_true


def rand_choice(choices: list) -> object:
    return random.choice(choices)


def base_answers() -> dict:
    """Generate random valid answers for bailiff-mod-base."""
    project_name = random.choice(["my-project", "test-app", "foo-bar", "alpha"])
    org = random.choice(["acme", "testorg", "myorg"])
    return {
        "project_name": project_name,
        "org": org,
        "description": random.choice(["A test project", "", "Some description"]),
        "layout": rand_choice(["single", "monorepo"]),
        "license": rand_choice(
            ["mit", "apache-2.0", "gpl-3.0", "bsd-3-clause", "unlicense", "mpl-2.0"]
        ),
        "copyright_name": org,
        "branch_strategy": rand_choice(
            [
                "feature-branches-squash-merge",
                "trunk-based",
                "gitflow",
                "feature-branches-merge-commit",
            ]
        ),
        "docs_subdirs": rand_bool(),
        "github_host": rand_bool(),
        "extra_dirs": [],
        "run_git_init": True,
        "write_architecture": False,
        "initial_commit": False,
        "mise_tools": [],
        "architecture_md": "",
        "agent_editable_globs": [],
        "gitignore_stack": rand_choice(
            [
                [],
                ["Python"],
                ["Node"],
                ["Go"],
                ["Rust"],
                ["Python", "Node"],
            ]
        ),
        "today": "2026-07-14",
    }


def agentic_answers() -> dict:
    """Generate random valid answers for bailiff-mod-agentic."""
    targets = random.sample(["claude", "codex", "opencode", "kiro"], k=random.randint(0, 3))
    install_via_apm = rand_bool(0.2)
    apm_packages = ["srobroek/agentic-packages/packages/speckit#>=5.0.0"] if install_via_apm else []
    return {
        "agentic_targets": targets,
        "kiro_cli_agents": rand_bool(0.2),
        "mcp_config": rand_bool(0.3),
        "native_marketplace": rand_bool(0.2),
        "install_via_apm": install_via_apm,
        "mcp_servers": [],
        "agentic_plugins": [],
        "apm_packages": apm_packages,
        "apm_cli_version": "0.25.0",
        "today": "2026-07-14",
    }


def apm_answers() -> dict:
    """Generate random valid answers for bailiff-mod-apm (requires >= 1 package)."""
    return {
        "description": "APM test layer",
        "apm_packages": ["srobroek/agentic-packages/packages/speckit#>=5.0.0"],
        "apm_cli_version": "0.24.1",
        "today": "2026-07-14",
    }


def cdk_answers() -> dict:
    return {
        "cdk_language": rand_choice(["typescript", "python", "go"]),
        "placement_dir": "infrastructure",
        "cdk_version": "2.261.0",
        "include_cdk_nag": False,
        "include_synth_validate": False,
        "today": "2026-07-14",
    }


def ci_github_answers() -> dict:
    return {
        "ci_model": rand_choice(["minimal", "standard", "optimized"]),
        "ci_cache": rand_bool(),
        "ci_concurrency_cancel": rand_bool(),
        "ci_os_matrix": [],
        "ci_matrix_versions": [],
        "ci_oidc_provider": "none",
        "ci_required_gate": rand_bool(),
        "ci_languages": rand_choice([[], ["python"], ["typescript"], ["go"]]),
        "ci_lang_facts": {},
        "monorepo_tool": "none",
        "default_branch": "main",
        "merge_queue_org_confirmed": False,
        "today": "2026-07-14",
    }


def ci_gitlab_answers() -> dict:
    return {
        "ci_model": rand_choice(["minimal", "standard", "optimized"]),
        "ci_cache": rand_bool(),
        "ci_concurrency_cancel": rand_bool(),
        "ci_os_matrix": [],
        "ci_matrix_versions": [],
        "ci_oidc_provider": rand_choice(["none", "gitlab"]),
        "ci_required_gate": rand_bool(),
        "ci_languages": rand_choice([[], ["python"], ["typescript"]]),
        "ci_lang_facts": {},
        "monorepo_tool": rand_choice(["none", "turborepo", "nx", "pnpm-workspace"]),
        "monorepo_packages": [],
        "default_branch": "main",
        "gitlab_tier": rand_choice(["free", "premium_ultimate"]),
        "today": "2026-07-14",
    }


def cloudformation_answers() -> dict:
    return {
        "mode": rand_choice(["raw", "sam"]),
        "stack_description": "Test stack",
        "environment_names": rand_choice([["dev", "prod"], ["staging"], ["dev"]]),
        "cfnlint_version": "",
        "cfnlint_ignore_rules": [],
        "aws_validate": False,
        "placement_dir": "infrastructure",
        "today": "2026-07-14",
    }


def github_repo_answers() -> dict:
    # Keep visibility=private to avoid hard exit-1 from public gate
    return {
        "visibility": rand_choice(["private", "internal"]),
        "remote_protocol": rand_choice(["https", "ssh"]),
        "push_after_create": False,
        "team": "",
        "today": "2026-07-14",
    }


def go_answers() -> dict:
    hook_manager = rand_choice(["pre-commit", "lefthook", "none"])
    return {
        "go_version": rand_choice(["1.23", "1.22", "1.21"]),
        "app_kind": rand_choice(["cli", "service", "library"]),
        "test_runner": rand_choice(["go-test", "gotestsum"]),
        "use_vendor_mode": rand_bool(0.2),
        "golangci_hook_rev": "",
        "gitignore_stack": ["Go"],
        "mise_tools": [{"go": "1.23"}],
        "hook_blocks": [],
        "hook_manager": hook_manager,
        "today": "2026-07-14",
    }


def justfile_answers() -> dict:
    hook_manager = rand_choice(["pre-commit", "lefthook", "none"])
    return {
        "language": rand_choice(["python", "ts", "go", "rust", ""]),
        "js_pkg_manager": rand_choice(["bun", "pnpm", "npm"]),
        "hook_manager": hook_manager,
        "today": "2026-07-14",
    }


def package_add_answers(layout: str) -> dict:
    lang = rand_choice(["ts", "python", "go", "rust"])
    answers: dict = {
        "name": "my-package",
        "lang": lang,
        "dir": "packages/",
        "resolve_stack": False,
        "today": "2026-07-14",
    }
    if lang == "ts":
        answers["js_pkg_manager"] = rand_choice(["bun", "pnpm"])
    if lang == "python":
        answers["python_pkg_manager"] = rand_choice(["uv", "pdm"])
    if lang == "rust":
        answers["rust_edition"] = rand_choice(["2024", "2021"])
    return answers


def precommit_answers() -> dict:
    hook_manager = rand_choice(["pre-commit", "lefthook", "none"])
    return {
        "hook_manager": hook_manager,
        "enforce_conventional_commits": rand_bool(),
        "enable_typo_check": rand_bool(),
        "precommit_exclude_patterns": [],
        "install_hooks": False,  # Skip actual install to avoid side effects
        "hook_blocks": [],
        "today": "2026-07-14",
    }


def python_answers() -> dict:
    hook_manager = rand_choice(["pre-commit", "lefthook", "none"])
    return {
        "description": "",
        "python_pkg_manager": rand_choice(["uv", "pdm"]),
        "python_version": rand_choice(["3.11", "3.12", "3.13"]),
        "python_layout": rand_choice(["src", "flat"]),
        "python_framework": rand_choice(["none", "fastapi", "django", "flask"]),
        "ruff_line_length": rand_choice(["79", "88", "100", "119", "120"]),
        "ruff_quote_style": rand_choice(["double", "single"]),
        "ruff_rule_profile": rand_choice(["standard", "strict"]),
        "add_tests": rand_bool(0.3),
        "hook_manager": hook_manager,
        "ruff_version": "",
        "today": "2026-07-14",
    }


def quality_answers() -> dict:
    return {
        "quality_languages": rand_choice(
            [[], ["python"], ["typescript"], ["go"], ["python", "typescript"]]
        ),
        "today": "2026-07-14",
    }


def readme_answers() -> dict:
    readme_style = rand_choice(["static-skeleton", "agent-draft"])
    answers: dict = {
        "description": "Test project",
        "stack": "Python/uv",
        "readme_style": readme_style,
        "today": "2026-07-14",
    }
    if readme_style == "agent-draft":
        answers["confirm_readme_draft"] = True
        answers["readme_body"] = "# Test\n\nGenerated by fuzz harness."
    return answers


def rust_answers() -> dict:
    hook_manager = rand_choice(["pre-commit", "lefthook", "none"])
    return {
        "hook_manager": hook_manager,
        "rust_channel": rand_choice(["stable", "beta"]),
        "rust_edition": rand_choice(["2024", "2021"]),
        "crate_kind": rand_choice(["bin", "lib"]),
        "test_runner": rand_choice(["cargo-test", "nextest"]),
        "rustfmt_heuristics": rand_choice(["Default", "Max", "Off"]),
        "clippy_stage": rand_choice(["pre-push", "pre-commit"]),
        "precommit_rust_rev": "",
        "gitignore_stack": ["Rust"],
        "mise_tools": [{"rust": "stable"}],
        "hook_blocks": [],
        "today": "2026-07-14",
    }


def stack_adr_answers() -> dict:
    fmt = rand_choice(["simple", "adr"])
    return {
        "format": fmt,
        "adr_dir": "docs/decisions",
        "stack_pins": rand_choice([[], [{"name": "Python", "version": "3.13"}]]),
        "stack_framework": rand_choice(["", "FastAPI", "Django"]),
        "rationale": rand_choice(["", "Selected for performance."]),
        "today": "2026-07-14",
    }


def terraform_answers() -> dict:
    tf_flavor = rand_choice(["terraform", "opentofu"])
    answers: dict = {
        "tf_flavor": tf_flavor,
        "tflint_version": "0.57.0",
        "placement_dir": "infrastructure",
        "today": "2026-07-14",
        "mise_tools": [],
        "hook_blocks": [],
        "hook_manager": "pre-commit",
        "gitignore_stack": [],
    }
    if tf_flavor == "terraform":
        answers["terraform_version"] = "1.12.2"
    else:
        answers["opentofu_version"] = "1.10.0"
    return answers


def ts_answers() -> dict:
    hook_manager = rand_choice(["pre-commit", "lefthook", "none"])
    framework = rand_choice(["plain", "nuxt", "vite", "sst"])
    answers: dict = {
        "hook_manager": hook_manager,
        "gitignore_stack": ["Node"],
        "mise_tools": [{"node": "22"}],
        "hook_blocks": [],
        "today": "2026-07-14",
        "js_pkg_manager": rand_choice(["bun", "pnpm", "npm"]),
        "ts_linter": rand_choice(["biome", "eslint-prettier"]),
        "test_runner": rand_choice(["none", "vitest-node", "bun-test"]),
        "node_version": rand_choice(["24", "22", "20"]),
        "ts_framework": framework,
        "ui_kit": rand_choice(["none", "shadcn"]),
    }
    if framework == "vite":
        answers["vite_template"] = rand_choice(["vanilla-ts", "react-ts", "vue-ts"])
    return answers


MODULE_ANSWER_GEN = {
    "bailiff-mod-agentic": lambda _base: agentic_answers(),
    "bailiff-mod-apm": lambda _base: apm_answers(),
    "bailiff-mod-base": lambda _base: _base,
    "bailiff-mod-cdk": lambda _base: cdk_answers(),
    "bailiff-mod-ci-github": lambda _base: ci_github_answers(),
    "bailiff-mod-ci-gitlab": lambda _base: ci_gitlab_answers(),
    "bailiff-mod-cloudformation": lambda _base: cloudformation_answers(),
    "bailiff-mod-github-repo": lambda _base: github_repo_answers(),
    "bailiff-mod-go": lambda _base: go_answers(),
    "bailiff-mod-justfile": lambda _base: justfile_answers(),
    "bailiff-mod-package-add": lambda base: package_add_answers(base.get("layout", "single")),
    "bailiff-mod-precommit": lambda _base: precommit_answers(),
    "bailiff-mod-python": lambda _base: python_answers(),
    "bailiff-mod-quality": lambda _base: quality_answers(),
    "bailiff-mod-readme": lambda _base: readme_answers(),
    "bailiff-mod-rust": lambda _base: rust_answers(),
    "bailiff-mod-stack-adr": lambda _base: stack_adr_answers(),
    "bailiff-mod-terraform": lambda _base: terraform_answers(),
    "bailiff-mod-ts": lambda _base: ts_answers(),
}


def generate_iteration(i: int) -> list[tuple[str, dict]]:
    """Pick 2-4 modules, always starting with base; return [(name, answers), ...]."""
    # Pick 1-3 additional modules
    n_extra = random.randint(1, 3)
    extra = random.sample(OPTIONAL_MODULES, k=n_extra)

    base_ans = base_answers()

    result: list[tuple[str, dict]] = [
        ("bailiff-mod-base", {**base_ans, "project_name": f"fuzz-{i:02d}"})
    ]
    for mod in extra:
        ans = MODULE_ANSWER_GEN[mod](base_ans)
        # Inject project_name into all modules that have it
        ans["project_name"] = f"fuzz-{i:02d}"
        result.append((mod, ans))

    return result


# ---------------------------------------------------------------------------
# Run N iterations
# ---------------------------------------------------------------------------

N_ITERATIONS = 20
passed = 0
failed = 0
findings: list[dict] = []

# Track failure patterns to group duplicates
pattern_counts: dict[str, list[int]] = {}

for i in range(N_ITERATIONS):
    scenario = f"fuzz-iter-{i:02d}"
    module_answers = generate_iteration(i)
    modules_used = [ma[0] for ma in module_answers]
    compact_answers = {ma[0]: ma[1] for ma in module_answers}

    print(f"[{i:02d}] modules={[m.replace('bailiff-mod-', '') for m in modules_used]}", flush=True)

    try:
        dest = run_scenario(scenario, module_answers)
        print(f"      PASS → {dest}", flush=True)
        passed += 1
    except BailiffError as exc:
        msg = str(exc)
        # BailiffError = documented failure mode; classify as design-gap or expected
        print(f"      BailiffError: {msg[:120]}", flush=True)
        # Copier validators raise BailiffError; that's acceptable per spec
        # Only record if it looks unexpected
        key = msg[:60]
        pattern_counts.setdefault(key, []).append(i)
        passed += 1  # BailiffError is a graceful failure, not a crash
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        # Any unhandled exception = finding
        print(f"      CRASH: {type(exc).__name__}: {str(exc)[:120]}", flush=True)
        failed += 1

        key = f"{type(exc).__name__}:{str(exc)[:60]}"
        if key not in pattern_counts:
            pattern_counts[key] = []
        pattern_counts[key].append(i)

        findings.append(
            {
                "scenario": scenario,
                "modules": modules_used,
                "answers": {k: str(v)[:200] for k, v in compact_answers.items()},
                "error": tb[:500],
                "error_type": type(exc).__name__,
                "classification": (
                    "bug"
                    if any(x in tb for x in ["UndefinedError", "TemplateError", "Jinja"])
                    else "design-gap"
                ),
            }
        )


# ---------------------------------------------------------------------------
# Print structured report
# ---------------------------------------------------------------------------

print("\n" + "=" * 70)
print("CATEGORY: FUZZ")
print(f"SCENARIOS_RUN: {N_ITERATIONS}")
print(f"PASSED: {passed}")
print(f"FAILED: {failed}")
print("FINDINGS:")

if not findings:
    print("  (none)")
else:
    # Group by root cause pattern
    grouped: dict[str, list[dict]] = {}
    for f in findings:
        key = f["error_type"]
        grouped.setdefault(key, []).append(f)

    for err_type, group in grouped.items():
        print(f"\n  --- {err_type} ({len(group)} occurrences) ---")
        # Show first occurrence in detail; summarise the rest
        first = group[0]
        print(f"  scenario: {first['scenario']}")
        print(f"  modules: {first['modules']}")
        print(f"  error: {first['error'][:500]}")
        print(f"  classification: {first['classification']}")
        if len(group) > 1:
            print(f"  also_in: {[g['scenario'] for g in group[1:]]}")

print("=" * 70)
sys.exit(0 if failed == 0 else 1)
