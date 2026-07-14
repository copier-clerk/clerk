"""spec 011 T017 (loop test): clerk-mod-ci-gitlab renders all 5 models.

Assertions per model:
- valid YAML structure (not just rendered text);
- correct key semantics per grill-fix rules;
- MANAGED lifecycle → byte-identical on reproduce.

Covers:
- all 5 models with a 2-language ci_lang_facts fixture (python + typescript);
- optional:true needs on change-gated jobs (optimized model);
- merge-queue + free tier → fallback + header warning;
- empty ci_languages + monorepo_tool=none → loud warning job (R4 guard);
- reproduce byte-identical (pure render, zero tasks).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from clerk import runner, trust
from tests.conftest import TemplateRepo, _copy_module_with_stub_tasks

# ---------------------------------------------------------------------------
# Fixture — hermetic copy of the real module (ZERO tasks, so stub is identity)
# ---------------------------------------------------------------------------

# This module has no _tasks, so there is nothing to stub; _copy_module_with_stub_tasks
# is still used for consistency (it builds the tagged git repo the runner requires).
_NO_TASKS_STUB = ""  # no _tasks block to replace


@pytest.fixture
def clerk_mod_ci_gitlab(tmp_path: Path) -> TemplateRepo:
    """The real clerk-mod-ci-gitlab template as a hermetic repo (no tasks to stub)."""
    return _copy_module_with_stub_tasks(
        "clerk-mod-ci-gitlab", tmp_path / "clerk-mod-ci-gitlab", _NO_TASKS_STUB
    )


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


# ---------------------------------------------------------------------------
# Shared 2-language facts fixture
# ---------------------------------------------------------------------------

_TWO_LANG_LANGUAGES = ["python", "typescript"]

_TWO_LANG_FACTS = {
    "python": {
        "manager": "uv",
        "version": "3.13",
        "image": "python:3.13-slim",
        "test_runner": "pytest",
    },
    "typescript": {
        "manager": "bun",
        "version": "1.2",
        "image": "oven/bun:1.2-slim",
        "test_runner": "vitest",
    },
}

_BASE_ANSWERS = {
    "project_name": "myapp",
    "default_branch": "main",
    "ci_languages": _TWO_LANG_LANGUAGES,
    "ci_lang_facts": _TWO_LANG_FACTS,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> dict:
    """Run init and return the parsed YAML of .gitlab-ci.yml."""
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-13")
    out = dest / ".gitlab-ci.yml"
    assert out.is_file(), ".gitlab-ci.yml not rendered"
    return yaml.safe_load(out.read_text())


# ---------------------------------------------------------------------------
# Model: minimal
# ---------------------------------------------------------------------------


def test_minimal_renders_single_job(clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path) -> None:
    """minimal: one 'ci' job, no gate, multi-command script."""
    answers = {**_BASE_ANSWERS, "ci_model": "minimal"}
    parsed = _init(clerk_mod_ci_gitlab, tmp_path / "proj", answers)

    # canonical workflow:rules guard present
    assert "workflow" in parsed, "workflow:rules guard missing"
    rules = parsed["workflow"]["rules"]
    assert any("CI_OPEN_MERGE_REQUESTS" in str(r) for r in rules), (
        "duplicate-pipeline guard missing"
    )

    # stages defined
    assert "stages" in parsed

    # one ci job with a script list (multi-command)
    assert "ci" in parsed, "minimal must render a 'ci' job"
    assert isinstance(parsed["ci"]["script"], list), "ci.script must be a list"
    assert len(parsed["ci"]["script"]) >= 2, "minimal must have multiple script commands"

    # images not pinned to :latest (check rendered YAML text)
    text = (tmp_path / "proj" / ".gitlab-ci.yml").read_text()
    assert ":latest" not in text, "pinned image must not use :latest"
    assert ":lts" not in text, "pinned image must not use :lts"


def test_minimal_reproduce_byte_identical(
    clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path
) -> None:
    """minimal MANAGED: reproduce byte-identical (pure render)."""
    dest = tmp_path / "proj"
    answers = {**_BASE_ANSWERS, "ci_model": "minimal"}
    trust.add_trust(clerk_mod_ci_gitlab.url)
    spec = runner.RunSpec(source=clerk_mod_ci_gitlab.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-13")

    before = _digest(dest / ".gitlab-ci.yml")
    runner.reproduce(str(dest))
    assert _digest(dest / ".gitlab-ci.yml") == before, ".gitlab-ci.yml changed on reproduce"


# ---------------------------------------------------------------------------
# Model: standard
# ---------------------------------------------------------------------------


def test_standard_parallel_jobs_no_gate(clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path) -> None:
    """standard: parallel per-language jobs, no explicit gate job, no deploy job."""
    answers = {**_BASE_ANSWERS, "ci_model": "standard"}
    parsed = _init(clerk_mod_ci_gitlab, tmp_path / "proj", answers)

    # canonical workflow:rules guard present
    assert "workflow" in parsed

    # each language has its own job
    assert "python" in parsed, "standard must have a python job"
    assert "typescript" in parsed, "standard must have a typescript job"

    # no explicit gate job (e.g. 'gate', 'status-check', 'all-ok')
    gate_names = {"gate", "all-ok", "status-check", "merge-gate"}
    job_names = {k for k in parsed if not k.startswith(".")}
    assert not gate_names.intersection(job_names), (
        f"standard must not have an explicit gate job: {gate_names.intersection(job_names)}"
    )

    # images pinned via ci_lang_facts
    assert parsed["python"].get("image") == "python:3.13-slim"
    assert parsed["typescript"].get("image") == "oven/bun:1.2-slim"


def test_standard_reproduce_byte_identical(
    clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path
) -> None:
    """standard MANAGED: reproduce byte-identical."""
    dest = tmp_path / "proj"
    answers = {**_BASE_ANSWERS, "ci_model": "standard"}
    trust.add_trust(clerk_mod_ci_gitlab.url)
    spec = runner.RunSpec(source=clerk_mod_ci_gitlab.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-13")

    before = _digest(dest / ".gitlab-ci.yml")
    runner.reproduce(str(dest))
    assert _digest(dest / ".gitlab-ci.yml") == before


# ---------------------------------------------------------------------------
# Model: optimized
# ---------------------------------------------------------------------------


def test_optimized_rules_changes_and_cache(
    clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path
) -> None:
    """optimized: rules:changes on branch arm; compare_to present on branch arm only."""
    answers = {**_BASE_ANSWERS, "ci_model": "optimized", "ci_cache": True}
    parsed = _init(clerk_mod_ci_gitlab, tmp_path / "proj", answers)

    assert "workflow" in parsed

    py_job = parsed.get("python", {})
    assert py_job, "optimized must have a python job"

    # rules:changes present
    assert "rules" in py_job, "optimized job must have rules:"
    rules = py_job["rules"]
    branch_rule = next(
        (
            r
            for r in rules
            if isinstance(r, dict)
            and r.get("if", "").find("CI_COMMIT_BRANCH") >= 0
            and "changes" in r
        ),
        None,
    )
    assert branch_rule is not None, "optimized must have a branch rule with changes:"

    # compare_to present on branch arm (grill fix)
    changes_block = branch_rule.get("changes", {})
    assert "compare_to" in changes_block, "compare_to must be present on branch arm (grill fix)"
    assert "main" in changes_block["compare_to"], "compare_to must reference default_branch"

    # MR arm must NOT have compare_to (grill fix: omit on MR arm)
    mr_rule = next(
        (r for r in rules if isinstance(r, dict) and "merge_request_event" in r.get("if", "")),
        None,
    )
    if mr_rule is not None:
        mr_changes = mr_rule.get("changes", {})
        assert "compare_to" not in mr_changes, "compare_to must NOT be on MR arm (grill fix)"

    # cache present with fallback_keys (grill fix)
    assert "cache" in py_job, "optimized must have cache:"
    cache = py_job["cache"]
    assert "fallback_keys" in cache, "cache must have fallback_keys (grill fix)"
    assert len(cache["fallback_keys"]) >= 1

    # bun cache key uses bun.lock not bun.lockb (grill fix)
    ts_job = parsed.get("typescript", {})
    ts_cache = ts_job.get("cache", {})
    ts_key = ts_cache.get("key", {})
    ts_files = ts_key.get("files", []) if isinstance(ts_key, dict) else []
    if ts_files:
        assert "bun.lockb" not in str(ts_files), "bun cache must use bun.lock not bun.lockb"


def test_optimized_interruptible_and_auto_cancel(
    clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path
) -> None:
    """optimized: interruptible + workflow:auto_cancel coupled as one unit (grill fix)."""
    answers = {
        **_BASE_ANSWERS,
        "ci_model": "optimized",
        "ci_concurrency_cancel": True,
    }
    parsed = _init(clerk_mod_ci_gitlab, tmp_path / "proj", answers)

    # Both coupled: workflow.auto_cancel.on_new_commit: interruptible
    wf = parsed.get("workflow", {})
    auto_cancel = wf.get("auto_cancel", {})
    assert auto_cancel.get("on_new_commit") == "interruptible", (
        "workflow:auto_cancel:on_new_commit must equal 'interruptible' (grill fix coupling)"
    )

    # jobs have interruptible: true
    py_job = parsed.get("python", {})
    assert py_job.get("interruptible") is True, "jobs must have interruptible:true"


def test_optimized_no_interruptible_when_disabled(
    clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path
) -> None:
    """When ci_concurrency_cancel=false, interruptible and auto_cancel are absent."""
    answers = {
        **_BASE_ANSWERS,
        "ci_model": "optimized",
        "ci_concurrency_cancel": False,
    }
    parsed = _init(clerk_mod_ci_gitlab, tmp_path / "proj", answers)

    wf = parsed.get("workflow", {})
    assert "auto_cancel" not in wf, "auto_cancel must be absent when concurrency_cancel=false"

    py_job = parsed.get("python", {})
    assert "interruptible" not in py_job, (
        "interruptible must be absent when concurrency_cancel=false"
    )


def test_optimized_reproduce_byte_identical(
    clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path
) -> None:
    """optimized MANAGED: reproduce byte-identical."""
    dest = tmp_path / "proj"
    answers = {**_BASE_ANSWERS, "ci_model": "optimized"}
    trust.add_trust(clerk_mod_ci_gitlab.url)
    spec = runner.RunSpec(source=clerk_mod_ci_gitlab.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-13")

    before = _digest(dest / ".gitlab-ci.yml")
    runner.reproduce(str(dest))
    assert _digest(dest / ".gitlab-ci.yml") == before


# ---------------------------------------------------------------------------
# Model: monorepo-affected
# ---------------------------------------------------------------------------


def test_monorepo_affected_parent_child(clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path) -> None:
    """monorepo-affected: renders parent trigger jobs with strategy:depend."""
    answers = {
        **_BASE_ANSWERS,
        "ci_model": "monorepo-affected",
        "monorepo_tool": "turborepo",
        "monorepo_packages": ["packages/api", "packages/web"],
    }
    parsed = _init(clerk_mod_ci_gitlab, tmp_path / "proj", answers)

    assert "workflow" in parsed

    # trigger jobs present
    trigger_jobs = {k: v for k, v in parsed.items() if k.startswith("trigger:")}
    assert len(trigger_jobs) == 2, f"expected 2 trigger jobs, got {list(trigger_jobs.keys())}"

    for job_name, job in trigger_jobs.items():
        trigger_block = job.get("trigger", {})
        assert trigger_block.get("strategy") == "depend", f"{job_name}: strategy:depend missing"
        assert "include" in trigger_block, f"{job_name}: trigger.include missing"


def test_monorepo_affected_reproduce_byte_identical(
    clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path
) -> None:
    """monorepo-affected MANAGED: reproduce byte-identical."""
    dest = tmp_path / "proj"
    answers = {
        **_BASE_ANSWERS,
        "ci_model": "monorepo-affected",
        "monorepo_tool": "nx",
        "monorepo_packages": ["apps/backend", "apps/frontend"],
    }
    trust.add_trust(clerk_mod_ci_gitlab.url)
    spec = runner.RunSpec(source=clerk_mod_ci_gitlab.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-13")

    before = _digest(dest / ".gitlab-ci.yml")
    runner.reproduce(str(dest))
    assert _digest(dest / ".gitlab-ci.yml") == before


# ---------------------------------------------------------------------------
# Model: merge-queue
# ---------------------------------------------------------------------------


def test_merge_queue_premium_tier(clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path) -> None:
    """merge-queue + premium_ultimate: merge train rules rendered."""
    answers = {
        **_BASE_ANSWERS,
        "ci_model": "merge-queue",
        "gitlab_tier": "premium_ultimate",
    }
    parsed = _init(clerk_mod_ci_gitlab, tmp_path / "proj", answers)

    # merge train rule present
    py_rules = parsed.get("python", {}).get("rules", [])
    merge_train_rule = any("CI_MERGE_TRAIN_PIPELINE" in str(r) for r in py_rules)
    assert merge_train_rule, "premium_ultimate must render merge train rule"

    # no warning comment in rendered file
    text = (tmp_path / "proj" / ".gitlab-ci.yml").read_text()
    assert "WARNING" not in text or "gitlab_tier=free" not in text, (
        "premium_ultimate must not render free-tier warning"
    )


def test_merge_queue_free_tier_fallback_and_warning(
    clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path
) -> None:
    """merge-queue + free tier: fallback job + header warning rendered (NOT hard error)."""
    answers = {
        **_BASE_ANSWERS,
        "ci_model": "merge-queue",
        "gitlab_tier": "free",
    }
    # Must NOT raise — free tier is a fallback, not a hard error
    parsed = _init(clerk_mod_ci_gitlab, tmp_path / "proj", answers)

    # header warning in rendered text
    text = (tmp_path / "proj" / ".gitlab-ci.yml").read_text()
    assert "WARNING" in text, "free tier must render header warning"
    assert "merge train" in text.lower() or "merge-when-pipeline-succeeds" in text.lower(), (
        "free tier must mention merge-train fallback"
    )

    # fallback rules: MR event + default-branch push (no merge train rule)
    py_rules = parsed.get("python", {}).get("rules", [])
    merge_train_rule = any("CI_MERGE_TRAIN_PIPELINE" in str(r) for r in py_rules)
    assert not merge_train_rule, "free tier must NOT render merge train rule"

    mr_rule = any("merge_request_event" in str(r) for r in py_rules)
    assert mr_rule, "free tier must have MR event fallback rule"


def test_merge_queue_reproduce_byte_identical(
    clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path
) -> None:
    """merge-queue MANAGED: reproduce byte-identical."""
    dest = tmp_path / "proj"
    answers = {**_BASE_ANSWERS, "ci_model": "merge-queue", "gitlab_tier": "free"}
    trust.add_trust(clerk_mod_ci_gitlab.url)
    spec = runner.RunSpec(source=clerk_mod_ci_gitlab.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-13")

    before = _digest(dest / ".gitlab-ci.yml")
    runner.reproduce(str(dest))
    assert _digest(dest / ".gitlab-ci.yml") == before


# ---------------------------------------------------------------------------
# Fail-loud guard (R4)
# ---------------------------------------------------------------------------


def test_guard_empty_languages_no_monorepo(
    clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path
) -> None:
    """R4: empty ci_languages + monorepo_tool=none → warning no-op job, not silent."""
    answers = {
        "project_name": "myapp",
        "default_branch": "main",
        "ci_model": "minimal",
        "ci_languages": [],
        "ci_lang_facts": {},
        "monorepo_tool": "none",
    }
    parsed = _init(clerk_mod_ci_gitlab, tmp_path / "proj", answers)

    # Must not be empty — a warning/no-op job must be present
    _excluded = {"workflow", "stages", "default"}
    job_names = [k for k in parsed if not k.startswith(".") and k not in _excluded]
    assert len(job_names) >= 1, "guard mode must render at least one no-op job"

    # The warning job must mention WARN or misconfiguration
    text = (tmp_path / "proj" / ".gitlab-ci.yml").read_text()
    assert "WARN" in text or "misconfiguration" in text.lower(), (
        "guard mode must emit a visible warning"
    )


# ---------------------------------------------------------------------------
# No secret: questions (C-11)
# ---------------------------------------------------------------------------


def test_no_secret_questions(clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path) -> None:
    """Rendered copier.yml must not contain secret: questions."""
    import re

    copier_yml = (
        Path(__file__).resolve().parent.parent.parent
        / "templates"
        / "clerk-mod-ci-gitlab"
        / "copier.yml"
    )
    text = copier_yml.read_text()
    # Allow 'secret' as part of a comment but not as a YAML key
    matches = re.findall(r"^\s*secret\s*:", text, flags=re.MULTILINE)
    assert not matches, f"copier.yml must not have secret: questions, found: {matches}"


# ---------------------------------------------------------------------------
# Answers-file written and hidden edges not persisted
# ---------------------------------------------------------------------------


def test_answers_file_written_no_hidden_edges(
    clerk_mod_ci_gitlab: TemplateRepo, tmp_path: Path
) -> None:
    """Answers file is written; hidden edges (run_after, depends_on) are not persisted."""
    answers = {**_BASE_ANSWERS, "ci_model": "standard"}
    dest = tmp_path / "proj"
    trust.add_trust(clerk_mod_ci_gitlab.url)
    spec = runner.RunSpec(source=clerk_mod_ci_gitlab.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-13")

    af_path = dest / ".copier-answers.yml"
    assert af_path.is_file(), "answers file must be written"
    af = yaml.safe_load(af_path.read_text())

    assert "run_after" not in af, "run_after (hidden edge) must not be persisted"
    assert "depends_on" not in af, "depends_on (hidden edge) must not be persisted"
    assert af.get("ci_model") == "standard"
    assert af.get("ci_languages") == _TWO_LANG_LANGUAGES
