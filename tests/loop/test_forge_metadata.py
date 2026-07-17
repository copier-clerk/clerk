"""spec 014 T051 / SC-009: forge metadata cleanup (R12/FR-022/FR-023/FR-024).

Tests:
- base emits NO .github/ files and has no github_host question
- github-repo renders .github/ (CODEOWNERS, ISSUE_TEMPLATE, PULL_REQUEST_TEMPLATE)
- gitlab-repo renders .gitlab/ (CODEOWNERS, issue_templates, merge_request_templates)
- neither leaks the other forge's files
- create_remote=false → metadata rendered, no gh/glab create task run
- dep-updates renders with no github_host input (dep_update_tool defaults to renovate)
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from tests.conftest import (
    _BASE_STUB_TASKS,
    _GH_STUB_TASKS,
    _GLAB_STUB_TASKS,
    _MODULES_DIR,
    TemplateRepo,
    _copy_module_with_stub_tasks,
    _git,
)


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _record(full_id: str, repo: TemplateRepo, questions: list[str]) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=True,
        questions=questions,
    )


def _copy_dep_updates(tmp_path: Path) -> TemplateRepo:
    src = _MODULES_DIR / "bailiff-mod-dep-updates"
    dest_root = tmp_path / "bailiff-mod-dep-updates"
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest_root, dirs_exist_ok=True)
    _git(dest_root, "init", "-q")
    _git(dest_root, "add", "-A")
    _git(dest_root, "commit", "-qm", "module")
    _git(dest_root, "tag", "v1.0.0")
    return TemplateRepo(path=dest_root, tag="v1.0.0")


# ---------------------------------------------------------------------------
# SC-009 AS1: base emits NO .github/ files; no github_host question
# ---------------------------------------------------------------------------


def test_base_emits_no_github_files(tmp_path: Path) -> None:
    """bailiff-mod-base must not render any .github/ files (R12/FR-022)."""
    base = _copy_module_with_stub_tasks(
        "bailiff-mod-base", tmp_path / "bailiff-mod-base", _BASE_STUB_TASKS
    )
    trust.add_trust(base.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=base.url,
        dest=str(dest),
        answers={
            "project_name": "myproj",
            "org": "myorg",
            "description": "A test project.",
            "layout": "single",
        },
    )
    runner.init(spec, today="2026-07-14")

    assert not (dest / ".github").exists(), "base must not render .github/ (R12/FR-022)"


def test_base_copier_yml_has_no_github_host() -> None:
    """bailiff-mod-base copier.yml must not have github_host as a question key (R12/FR-022)."""
    import re

    text = (_MODULES_DIR / "bailiff-mod-base" / "copier.yml").read_text()
    # comments referencing the deleted key are allowed; question key declarations are not.
    assert not re.search(r"^github_host\s*:", text, re.MULTILINE), (
        "github_host must not be a question key in base (R12)"
    )


# ---------------------------------------------------------------------------
# SC-009 AS2: github-repo renders .github/ (create_remote=false = adopt-existing path)
# ---------------------------------------------------------------------------


def test_github_repo_renders_github_metadata(tmp_path: Path) -> None:
    """github-repo renders .github/ CODEOWNERS/ISSUE_TEMPLATE/PR_TEMPLATE (FR-022/FR-024)."""
    base = _copy_module_with_stub_tasks("bailiff-mod-base", tmp_path / "base", _BASE_STUB_TASKS)
    github_repo = _copy_module_with_stub_tasks(
        "bailiff-mod-github-repo", tmp_path / "github-repo", _GH_STUB_TASKS
    )
    for repo in (base, github_repo):
        trust.add_trust(repo.url)

    selection = [
        (
            _record("myorg/bailiff-mod-base", base, ["project_name", "org", "layout"]),
            {"project_name": "myproj", "org": "myorg", "layout": "single"},
        ),
        (
            _record(
                "myorg/bailiff-mod-github-repo",
                github_repo,
                ["create_remote", "visibility", "remote_protocol", "push_after_create", "team"],
            ),
            {"create_remote": False, "visibility": "private"},
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    # Managed .github/ files must render.
    assert (dest / ".github" / "CODEOWNERS").is_file(), ".github/CODEOWNERS missing"
    assert (dest / ".github" / "ISSUE_TEMPLATE" / "bug_report.md").is_file()
    assert (dest / ".github" / "ISSUE_TEMPLATE" / "feature_request.md").is_file()
    assert (dest / ".github" / "PULL_REQUEST_TEMPLATE" / "pull_request_template.md").is_file()

    # CODEOWNERS references the org from base.
    codeowners = (dest / ".github" / "CODEOWNERS").read_text()
    assert "@myorg" in codeowners, "CODEOWNERS must reference the org from base"

    # No .gitlab/ leak.
    assert not (dest / ".gitlab").exists(), "github-repo must not render .gitlab/"


# ---------------------------------------------------------------------------
# SC-009 AS3: gitlab-repo renders .gitlab/ and does NOT render .github/
# ---------------------------------------------------------------------------


def test_gitlab_repo_renders_gitlab_metadata(tmp_path: Path) -> None:
    """gitlab-repo renders .gitlab/ CODEOWNERS/issue_templates/MR_templates (FR-022/FR-024)."""
    base = _copy_module_with_stub_tasks("bailiff-mod-base", tmp_path / "base", _BASE_STUB_TASKS)
    gitlab_repo = _copy_module_with_stub_tasks(
        "bailiff-mod-gitlab-repo", tmp_path / "gitlab-repo", _GLAB_STUB_TASKS
    )
    for repo in (base, gitlab_repo):
        trust.add_trust(repo.url)

    selection = [
        (
            _record("myorg/bailiff-mod-base", base, ["project_name", "org", "layout"]),
            {"project_name": "myproj", "org": "myorg", "layout": "single"},
        ),
        (
            _record(
                "myorg/bailiff-mod-gitlab-repo",
                gitlab_repo,
                ["create_remote", "visibility", "remote_protocol", "push_after_create", "team"],
            ),
            {"create_remote": False, "visibility": "private"},
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    # Managed .gitlab/ files must render.
    assert (dest / ".gitlab" / "CODEOWNERS").is_file(), ".gitlab/CODEOWNERS missing"
    assert (dest / ".gitlab" / "issue_templates" / "bug_report.md").is_file()
    assert (dest / ".gitlab" / "issue_templates" / "feature_request.md").is_file()
    assert (dest / ".gitlab" / "merge_request_templates" / "default.md").is_file()

    # CODEOWNERS references the org from base.
    codeowners = (dest / ".gitlab" / "CODEOWNERS").read_text()
    assert "@myorg" in codeowners, "CODEOWNERS must reference the org from base"

    # No .github/ leak.
    assert not (dest / ".github").exists(), "gitlab-repo must not render .github/"


# ---------------------------------------------------------------------------
# SC-009 AS4: create_remote=false → metadata rendered, no create task run
# ---------------------------------------------------------------------------


def _copy_real(tmp_path: Path, module_name: str, dest_name: str) -> TemplateRepo:
    """Clone a module WITHOUT stubbing tasks (for tests that verify task gating)."""
    src = _MODULES_DIR / module_name
    dest_root = tmp_path / dest_name
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest_root, dirs_exist_ok=True)
    _git(dest_root, "init", "-q")
    _git(dest_root, "add", "-A")
    _git(dest_root, "commit", "-qm", "module")
    _git(dest_root, "tag", "v1.0.0")
    return TemplateRepo(path=dest_root, tag="v1.0.0")


def test_create_remote_false_skips_creation_task(tmp_path: Path) -> None:
    """create_remote=false renders .github/ without running gh tasks (FR-024).

    Uses the real (non-stubbed) github-repo: tasks have ``when: "{{ create_remote }}"``
    so they are entirely skipped when false — no tool invocation, no side-effect files.
    """
    base = _copy_module_with_stub_tasks("bailiff-mod-base", tmp_path / "base", _BASE_STUB_TASKS)
    # Real module — no task stub; tasks are gated by create_remote.
    github_repo = _copy_real(tmp_path, "bailiff-mod-github-repo", "github-repo-real")
    for repo in (base, github_repo):
        trust.add_trust(repo.url)

    selection = [
        (
            _record("myorg/bailiff-mod-base", base, ["project_name", "org", "layout"]),
            {"project_name": "myproj", "org": "myorg", "layout": "single"},
        ),
        (
            _record(
                "myorg/bailiff-mod-github-repo-real",
                github_repo,
                ["create_remote", "visibility", "remote_protocol", "push_after_create", "team"],
            ),
            {"create_remote": False},
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    # Metadata files must exist (rendered unconditionally).
    assert (dest / ".github" / "CODEOWNERS").is_file(), ".github/CODEOWNERS must render"

    # No side-effect files — real tasks are when:false-gated, nothing runs.
    assert not (dest / ".bailiff-gh-preflight").exists(), (
        "gh task marker must not exist when create_remote=false"
    )


# ---------------------------------------------------------------------------
# SC-009 AS5: dep-updates renders without github_host input
# ---------------------------------------------------------------------------


def test_dep_updates_no_github_host_input(tmp_path: Path) -> None:
    """dep-updates renders correctly with no github_host in answers (FR-023/R12)."""
    dep_updates = _copy_dep_updates(tmp_path)
    trust.add_trust(dep_updates.url)
    dest = tmp_path / "proj"
    # No github_host in answers — must render with just dep_update_tool (defaults to renovate).
    spec = runner.RunSpec(
        source=dep_updates.url,
        dest=str(dest),
        answers={"dep_ecosystems": ["uv"]},
    )
    runner.init(spec, today="2026-07-14")

    # Default: renovate.json rendered; dependabot.yml absent.
    assert (dest / "renovate.json").is_file(), "renovate.json must render by default"
    assert not (dest / ".github" / "dependabot.yml").exists()


# ---------------------------------------------------------------------------
# SC-009 AS6: no cross-forge leakage (github+base → only .github/, no .gitlab/)
# ---------------------------------------------------------------------------


def test_no_cross_forge_leakage_github(tmp_path: Path) -> None:
    """github-repo selection must not produce any .gitlab/ path."""
    base = _copy_module_with_stub_tasks("bailiff-mod-base", tmp_path / "base", _BASE_STUB_TASKS)
    github_repo = _copy_module_with_stub_tasks(
        "bailiff-mod-github-repo", tmp_path / "github-repo", _GH_STUB_TASKS
    )
    for repo in (base, github_repo):
        trust.add_trust(repo.url)

    selection = [
        (
            _record("myorg/bailiff-mod-base", base, ["project_name", "org", "layout"]),
            {"project_name": "myproj", "org": "myorg", "layout": "single"},
        ),
        (
            _record(
                "myorg/bailiff-mod-github-repo",
                github_repo,
                ["create_remote", "visibility"],
            ),
            {"create_remote": False},
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    assert (dest / ".github").exists(), ".github/ must exist"
    assert not (dest / ".gitlab").exists(), ".gitlab/ must NOT exist in a GitHub stack"


def test_no_cross_forge_leakage_gitlab(tmp_path: Path) -> None:
    """gitlab-repo selection must not produce any .github/ path."""
    base = _copy_module_with_stub_tasks("bailiff-mod-base", tmp_path / "base", _BASE_STUB_TASKS)
    gitlab_repo = _copy_module_with_stub_tasks(
        "bailiff-mod-gitlab-repo", tmp_path / "gitlab-repo", _GLAB_STUB_TASKS
    )
    for repo in (base, gitlab_repo):
        trust.add_trust(repo.url)

    selection = [
        (
            _record("myorg/bailiff-mod-base", base, ["project_name", "org", "layout"]),
            {"project_name": "myproj", "org": "myorg", "layout": "single"},
        ),
        (
            _record(
                "myorg/bailiff-mod-gitlab-repo",
                gitlab_repo,
                ["create_remote", "visibility"],
            ),
            {"create_remote": False},
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    assert (dest / ".gitlab").exists(), ".gitlab/ must exist"
    assert not (dest / ".github").exists(), ".github/ must NOT exist in a GitLab stack"
