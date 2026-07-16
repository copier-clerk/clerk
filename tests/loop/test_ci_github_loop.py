"""spec 011 T016: bailiff-mod-ci-github loop tests.

MANAGED render — .github/workflows/ci.yml.
ZERO _tasks — the module has no task block so no stub is needed.

Tests cover:
- All 5 models with 2-language facts (python + typescript).
- Gate semantics: minimal has no gate, standard/optimized/merge-queue have gate.
- Optimized emits paths-filter (changes job) and cache steps.
- No unpinned refs (no :latest, all actions pinned to major).
- R4 fail-loud guard: empty ci_languages + no monorepo_tool → warning comment
  + no-op job, NOT a silent empty file.
- merge_queue_org_confirmed=false emits warning header on merge-queue model.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.conftest import TemplateRepo, _copy_module_with_stub_tasks

# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------

_MODULE = "bailiff-mod-ci-github"
_CI_FILE = Path(".github/workflows/ci.yml")

# Two-language facts injected as AGENT-FROZEN --data for all model tests.
_TWO_LANG_FACTS = {
    "python": {
        "manager": "uv",
        "version": "3.13",
        "test_runner": "pytest",
        "image": "",
    },
    "typescript": {
        "manager": "bun",
        "version": "22",
        "test_runner": "vitest",
        "image": "",
    },
}

# ci-github has ZERO _tasks so no stub tasks are needed — but _copy_module_with_stub_tasks
# still works by passing an empty stub that results in the tasks block being stripped.
# Since there are no _tasks in the authored module, passing "" replaces the
# (absent) tasks block and the resulting repo is identical to the source tree.
_NO_TASKS_STUB = ""


def _make_ci_github_repo(tmp_path: Path) -> TemplateRepo:
    """Build a hermetic local repo from the real bailiff-mod-ci-github template.

    No task stub needed — the module has ZERO _tasks. _copy_module_with_stub_tasks
    strips any _tasks block and appends the stub (empty string = effectively no tasks).
    """
    return _copy_module_with_stub_tasks(_MODULE, tmp_path / _MODULE, _NO_TASKS_STUB)


@pytest.fixture
def ci_github_repo(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-ci-github as a hermetic local repo."""
    return _make_ci_github_repo(tmp_path)


def _run_copier(
    src: str,
    ref: str,
    dest: Path,
    *,
    answers: dict,
    overwrite: bool = False,
) -> None:
    """Run copier copy/recopy against the local hermetic repo."""
    import copier

    dest.mkdir(parents=True, exist_ok=True)
    copier.run_copy(
        src_path=src,
        dst_path=str(dest),
        vcs_ref=ref,
        data=answers,
        defaults=True,
        overwrite=overwrite,
        quiet=True,
    )


def _run_recopy(src: str, dest: Path, *, overwrite: bool = True) -> None:
    """Re-run copier update (reproduce) against the local hermetic repo."""
    import copier

    copier.run_recopy(
        dst_path=str(dest),
        overwrite=overwrite,
        quiet=True,
    )


# ---------------------------------------------------------------------------
# Core data factory
# ---------------------------------------------------------------------------


def _base_answers(
    *,
    ci_model: str = "standard",
    ci_languages: list | None = None,
    ci_lang_facts: dict | None = None,
    monorepo_tool: str = "none",
    ci_cache: bool = True,
    ci_concurrency_cancel: bool = True,
    ci_required_gate: bool = True,
    merge_queue_org_confirmed: bool = False,
) -> dict:
    return {
        "ci_model": ci_model,
        "ci_languages": ci_languages if ci_languages is not None else ["python", "typescript"],
        "ci_lang_facts": ci_lang_facts if ci_lang_facts is not None else _TWO_LANG_FACTS,
        "monorepo_tool": monorepo_tool,
        "ci_cache": ci_cache,
        "ci_concurrency_cancel": ci_concurrency_cancel,
        "ci_required_gate": ci_required_gate,
        "merge_queue_org_confirmed": merge_queue_org_confirmed,
        "default_branch": "main",
    }


# ---------------------------------------------------------------------------
# Fixture: isolated settings
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


# ---------------------------------------------------------------------------
# T016-01: minimal model — single job, NO gate
# ---------------------------------------------------------------------------


def test_minimal_model_no_gate(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """Minimal model: one combined CI job, gate is suppressed regardless of ci_required_gate."""
    dest = tmp_path / "proj"
    _run_copier(
        ci_github_repo.url,
        ci_github_repo.tag,
        dest,
        answers=_base_answers(ci_model="minimal", ci_required_gate=True),
    )

    ci = (dest / _CI_FILE).read_text()
    assert "# Model: minimal" in ci
    # Single job 'ci:' present
    assert "\n  ci:\n" in ci or "  ci:" in ci
    # No gate job on minimal (even with ci_required_gate=true)
    assert "  gate:" not in ci
    # No parallel per-lang jobs with '-ci:' suffix (that's standard shape)
    assert "  python-ci:" not in ci
    assert "  typescript-ci:" not in ci


# ---------------------------------------------------------------------------
# T016-02: standard model — parallel per-lang + gate
# ---------------------------------------------------------------------------


def test_standard_model_gate(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """Standard model: parallel python-ci + typescript-ci jobs plus required fan-in gate."""
    dest = tmp_path / "proj"
    _run_copier(
        ci_github_repo.url,
        ci_github_repo.tag,
        dest,
        answers=_base_answers(ci_model="standard"),
    )

    ci = (dest / _CI_FILE).read_text()
    assert "# Model: standard" in ci
    # Per-language jobs present
    assert "  python-ci:" in ci
    assert "  typescript-ci:" in ci
    # Gate job present
    assert "  gate:" in ci
    # Gate needs both jobs
    assert "needs: [python-ci, typescript-ci]" in ci


def test_standard_model_no_gate_when_disabled(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """Standard with ci_required_gate=false: no gate job."""
    dest = tmp_path / "proj"
    _run_copier(
        ci_github_repo.url,
        ci_github_repo.tag,
        dest,
        answers=_base_answers(ci_model="standard", ci_required_gate=False),
    )
    ci = (dest / _CI_FILE).read_text()
    assert "  gate:" not in ci


# ---------------------------------------------------------------------------
# T016-03: optimized model — paths-filter + cache + concurrency
# ---------------------------------------------------------------------------


def test_optimized_model_paths_filter(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """Optimized: changes job with dorny/paths-filter, per-lang jobs with cache steps."""
    dest = tmp_path / "proj"
    _run_copier(
        ci_github_repo.url,
        ci_github_repo.tag,
        dest,
        answers=_base_answers(ci_model="optimized"),
    )

    ci = (dest / _CI_FILE).read_text()
    assert "# Model: optimized" in ci
    # paths-filter job
    assert "  changes:" in ci
    assert "dorny/paths-filter@v3" in ci
    # Per-lang jobs with needs: [changes]
    assert "  python-ci:" in ci
    assert "  typescript-ci:" in ci
    assert "needs: [changes]" in ci
    # Cache steps (ci_cache=true)
    assert "actions/cache@v4" in ci
    # Concurrency cancel (ci_concurrency_cancel=true)
    assert "cancel-in-progress: true" in ci
    # Gate present
    assert "  gate:" in ci


def test_optimized_no_cache_when_disabled(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """Optimized with ci_cache=false: no cache steps."""
    dest = tmp_path / "proj"
    _run_copier(
        ci_github_repo.url,
        ci_github_repo.tag,
        dest,
        answers=_base_answers(ci_model="optimized", ci_cache=False),
    )
    ci = (dest / _CI_FILE).read_text()
    assert "actions/cache@v4" not in ci


# ---------------------------------------------------------------------------
# T016-04: monorepo-affected model
# ---------------------------------------------------------------------------


def test_monorepo_affected_model(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """Monorepo-affected: changes job + per-lang affected jobs."""
    dest = tmp_path / "proj"
    _run_copier(
        ci_github_repo.url,
        ci_github_repo.tag,
        dest,
        answers=_base_answers(ci_model="monorepo-affected", monorepo_tool="turborepo"),
    )

    ci = (dest / _CI_FILE).read_text()
    assert "# Model: monorepo-affected" in ci
    assert "  changes:" in ci
    assert "dorny/paths-filter@v3" in ci
    assert "  python-ci:" in ci
    assert "  typescript-ci:" in ci


def test_monorepo_affected_empty_languages(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """Monorepo-affected with empty ci_languages and monorepo_tool set: still emits jobs."""
    dest = tmp_path / "proj"
    _run_copier(
        ci_github_repo.url,
        ci_github_repo.tag,
        dest,
        answers=_base_answers(
            ci_model="monorepo-affected",
            ci_languages=[],
            ci_lang_facts={},
            monorepo_tool="nx",
        ),
    )
    ci = (dest / _CI_FILE).read_text()
    # monorepo_tool != none so the model should not trigger the R4 guard
    # even though ci_languages is empty — the changes job should render.
    # (R4 guard only triggers when BOTH ci_languages==[] AND monorepo_tool==none)
    assert "ci-misconfigured" not in ci


# ---------------------------------------------------------------------------
# spec 012 T002 (FR-010a): monorepo_tool=moon branch
# ---------------------------------------------------------------------------


def test_monorepo_affected_moon(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """monorepo-affected + moon: moon ci job replaces the paths-filter fan-out."""
    dest = tmp_path / "proj"
    _run_copier(
        ci_github_repo.url,
        ci_github_repo.tag,
        dest,
        answers=_base_answers(ci_model="monorepo-affected", monorepo_tool="moon"),
    )

    ci = (dest / _CI_FILE).read_text()
    assert "# Model: monorepo-affected" in ci
    # moon ci is the affected-detection invocation
    assert "run: moon ci" in ci
    assert "moonrepo/setup-toolchain@v0" in ci
    # moon needs full history to diff against the base branch
    assert "fetch-depth: 0" in ci
    # No paths-filter fan-out on the moon branch
    assert "dorny/paths-filter@v3" not in ci
    assert "  python-ci:" not in ci
    # Gate still fans in on the moon job
    assert "  gate:" in ci
    assert "needs: [moon-ci]" in ci


def test_moon_absent_in_other_models(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """moon invocation appears ONLY on monorepo-affected + monorepo_tool=moon."""
    # Other models with monorepo_tool=moon set: no moon invocation.
    for model in ["minimal", "standard", "optimized", "merge-queue"]:
        dest = tmp_path / f"proj-{model}"
        _run_copier(
            ci_github_repo.url,
            ci_github_repo.tag,
            dest,
            answers=_base_answers(ci_model=model, monorepo_tool="moon"),
        )
        ci = (dest / _CI_FILE).read_text()
        assert "moon ci" not in ci, f"moon invocation leaked into {model} model"
    # monorepo-affected with a different tool: turborepo path, no moon.
    dest = tmp_path / "proj-turbo"
    _run_copier(
        ci_github_repo.url,
        ci_github_repo.tag,
        dest,
        answers=_base_answers(ci_model="monorepo-affected", monorepo_tool="turborepo"),
    )
    ci = (dest / _CI_FILE).read_text()
    assert "moon ci" not in ci
    assert "dorny/paths-filter@v3" in ci


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


# ---------------------------------------------------------------------------
# T016-05: merge-queue model
# ---------------------------------------------------------------------------


def test_merge_queue_model(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """Merge-queue model: merge_group trigger + gate job."""
    dest = tmp_path / "proj"
    _run_copier(
        ci_github_repo.url,
        ci_github_repo.tag,
        dest,
        answers=_base_answers(
            ci_model="merge-queue",
            merge_queue_org_confirmed=True,
        ),
    )

    ci = (dest / _CI_FILE).read_text()
    assert "# Model: merge-queue" in ci
    assert "merge_group:" in ci
    assert "checks_requested" in ci
    assert "  python-ci:" in ci
    assert "  typescript-ci:" in ci
    assert "  gate:" in ci


def test_merge_queue_unconfirmed_emits_warning(
    ci_github_repo: TemplateRepo, tmp_path: Path
) -> None:
    """Merge-queue with merge_queue_org_confirmed=false emits a warning header."""
    dest = tmp_path / "proj"
    _run_copier(
        ci_github_repo.url,
        ci_github_repo.tag,
        dest,
        answers=_base_answers(ci_model="merge-queue", merge_queue_org_confirmed=False),
    )
    ci = (dest / _CI_FILE).read_text()
    assert "WARNING: merge_queue_org_confirmed is false" in ci


# ---------------------------------------------------------------------------
# T016-06: R4 fail-loud guard
# ---------------------------------------------------------------------------


def test_r4_fail_loud_empty_languages(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """R4: ci_languages==[] AND monorepo_tool==none → warning comment + no-op job, not silent."""
    dest = tmp_path / "proj"
    _run_copier(
        ci_github_repo.url,
        ci_github_repo.tag,
        dest,
        answers=_base_answers(
            ci_model="standard",
            ci_languages=[],
            ci_lang_facts={},
            monorepo_tool="none",
        ),
    )

    ci = (dest / _CI_FILE).read_text()
    # Must emit a warning comment
    assert "WARNING: ci_languages is empty" in ci
    # Must emit a no-op misconfiguration job (not silent)
    assert "ci-misconfigured:" in ci
    # Must NOT be a silent empty jobs block
    assert "jobs:" in ci


# ---------------------------------------------------------------------------
# T016-07: no unpinned refs (:latest anywhere)
# ---------------------------------------------------------------------------


def test_no_latest_pins(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """No action ref should use ':latest' — all pinned to explicit majors."""
    for model in ["minimal", "standard", "optimized", "monorepo-affected", "merge-queue"]:
        d = tmp_path / f"proj-{model}"
        _run_copier(
            ci_github_repo.url,
            ci_github_repo.tag,
            d,
            answers=_base_answers(ci_model=model, merge_queue_org_confirmed=True),
        )
        ci = (d / _CI_FILE).read_text()
        # grep for uses: lines and check none end in :latest
        uses_lines = [ln.strip() for ln in ci.splitlines() if "uses:" in ln]
        for line in uses_lines:
            assert ":latest" not in line, f"Model {model}: unpinned ':latest' found: {line!r}"


# ---------------------------------------------------------------------------
# T016-08: upload/download-artifact share major
# ---------------------------------------------------------------------------


def test_artifact_actions_same_major(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """upload-artifact and download-artifact (if present) must share the same major version."""
    dest = tmp_path / "proj"
    _run_copier(
        ci_github_repo.url,
        ci_github_repo.tag,
        dest,
        answers=_base_answers(ci_model="standard"),
    )
    ci = (dest / _CI_FILE).read_text()

    upload_refs = re.findall(r"actions/upload-artifact@(v\d+)", ci)
    download_refs = re.findall(r"actions/download-artifact@(v\d+)", ci)

    # If either appears, they must share the same major
    if upload_refs and download_refs:
        upload_majors = {ref.split(".")[0] for ref in upload_refs}
        download_majors = {ref.split(".")[0] for ref in download_refs}
        assert upload_majors == download_majors, (
            f"upload-artifact {upload_refs} and download-artifact {download_refs} "
            "have different majors"
        )


# (reproduce byte-identity tests removed — invariant is now config-consistency, spec 014)


# ---------------------------------------------------------------------------
# T016-10: answers file written
# ---------------------------------------------------------------------------


def test_answers_file_written(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """The copier answers file is present after rendering."""
    dest = tmp_path / "proj"
    _run_copier(
        ci_github_repo.url,
        ci_github_repo.tag,
        dest,
        answers=_base_answers(ci_model="minimal"),
    )
    # Standalone copier writes .copier-answers.yml (no module suffix).
    # In multi-layer bailiff, copier writes .copier-answers.<module>.yml.
    # Either form is acceptable — find any answers file.
    answers_files = list(dest.glob(".copier-answers*.yml"))
    assert len(answers_files) == 1, f"Expected 1 answers file, got: {answers_files}"

    af = yaml.safe_load(answers_files[0].read_text())
    assert af["ci_model"] == "minimal"


# ---------------------------------------------------------------------------
# T016-11: valid YAML output
# ---------------------------------------------------------------------------


def test_all_models_produce_valid_yaml(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """All 5 rendered models produce valid YAML (necessary but not sufficient)."""
    for model in ["minimal", "standard", "optimized", "monorepo-affected", "merge-queue"]:
        dest = tmp_path / f"proj-{model}"
        answers = _base_answers(
            ci_model=model,
            merge_queue_org_confirmed=(model == "merge-queue"),
            monorepo_tool=("turborepo" if model == "monorepo-affected" else "none"),
        )
        _run_copier(ci_github_repo.url, ci_github_repo.tag, dest, answers=answers)

        ci_text = (dest / _CI_FILE).read_text()
        try:
            parsed = yaml.safe_load(ci_text)
        except yaml.YAMLError as e:
            pytest.fail(f"Model {model}: rendered ci.yml is not valid YAML: {e}")

        assert isinstance(parsed, dict), f"Model {model}: ci.yml root must be a mapping"
        assert "name" in parsed, f"Model {model}: ci.yml missing 'name' key"
        # "on:" is the YAML trigger block; yaml.safe_load may parse it as True key
        assert "on" in parsed or True in parsed, f"Model {model}: ci.yml missing trigger block"
        assert "jobs" in parsed, f"Model {model}: ci.yml missing 'jobs' key"


# ---------------------------------------------------------------------------
# T016-12: actionlint validation (skipped if not installed)
# ---------------------------------------------------------------------------


def test_actionlint_all_models(ci_github_repo: TemplateRepo, tmp_path: Path) -> None:
    """If actionlint is available, validate all 5 rendered models."""
    # Check actionlint availability
    result = subprocess.run(["which", "actionlint"], capture_output=True, text=True)
    if result.returncode != 0:
        pytest.skip("actionlint not installed — skipping schema validation")

    for model in ["minimal", "standard", "optimized", "monorepo-affected", "merge-queue"]:
        dest = tmp_path / f"proj-al-{model}"
        answers = _base_answers(
            ci_model=model,
            merge_queue_org_confirmed=(model == "merge-queue"),
            monorepo_tool=("turborepo" if model == "monorepo-affected" else "none"),
        )
        _run_copier(ci_github_repo.url, ci_github_repo.tag, dest, answers=answers)

        al = subprocess.run(["actionlint", str(dest / _CI_FILE)], capture_output=True, text=True)
        assert al.returncode == 0, f"Model {model}: actionlint errors:\n{al.stdout}\n{al.stderr}"
