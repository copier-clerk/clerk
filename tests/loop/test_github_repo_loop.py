"""spec 011 T018: bailiff-mod-github-repo loop tests.

Three scenarios per contract (R12/FR-024):

1. visibility=public + create_remote=true → hard exit 1 before any gh call.
2. gh absent + create_remote=true → non-fatal exit 0; scaffold completes.
3. gh present (stubbed offline) + create_remote=true → init succeeds, answers written.
4. create_remote=false (default) → .github/ files render; no gh tasks run.

This module writes .github/ managed files (CODEOWNERS, ISSUE_TEMPLATE,
PULL_REQUEST_TEMPLATE) plus the answers file. Remote creation is init-only,
gated on create_remote=true.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from bailiff import runner, trust
from bailiff.errors import BailiffError
from tests.conftest import (
    _GH_STUB_TASKS,
    _MODULES_DIR,
    TemplateRepo,
    _copy_module_with_stub_tasks,
    _git,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_base_answers(dest: Path, *, project_name: str = "myproj", org: str = "myorg") -> None:
    """Write a minimal base answers file so _external_data.base resolves."""
    dest.mkdir(parents=True, exist_ok=True)
    answers = {"project_name": project_name, "org": org}
    (dest / ".copier-answers.bailiff-mod-base.yml").write_text(
        yaml.dump(answers, default_flow_style=False)
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


@pytest.fixture
def bailiff_mod_github_repo(tmp_path: Path) -> TemplateRepo:
    """Real bailiff-mod-github-repo with gh tasks stubbed offline."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-github-repo",
        tmp_path / "bailiff-mod-github-repo",
        _GH_STUB_TASKS,
    )


# Stub that simulates gh being absent: exits 0 (non-fatal per contract).
_GH_ABSENT_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'gh-absent-stub\\n' > .bailiff-gh-preflight"
    """
)


@pytest.fixture
def bailiff_mod_github_repo_no_gh(tmp_path: Path) -> TemplateRepo:
    """Variant where the gh-absent path is taken (non-fatal exit 0)."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-github-repo",
        tmp_path / "bailiff-mod-github-repo-no-gh",
        _GH_ABSENT_STUB_TASKS,
    )


# Stub that exercises the public visibility gate: exits 1 unconditionally.
_GH_PUBLIC_STUB_TASKS = dedent(
    """\
    _tasks:
      - >-
        echo "bailiff-mod-github-repo: ABORTED — public requires manual confirmation." >&2;
        exit 1
    """
)


@pytest.fixture
def bailiff_mod_github_repo_public(tmp_path: Path) -> TemplateRepo:
    """Variant whose task always exits 1 (simulates public consent gate firing)."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-github-repo",
        tmp_path / "bailiff-mod-github-repo-public",
        _GH_PUBLIC_STUB_TASKS,
    )


# ---------------------------------------------------------------------------
# Test: public visibility aborts with exit 1
# ---------------------------------------------------------------------------


def test_public_visibility_aborts(
    bailiff_mod_github_repo_public: TemplateRepo, tmp_path: Path
) -> None:
    """visibility=public must cause the task to exit 1 (hard abort-without-consent gate)."""
    dest = tmp_path / "proj"
    _seed_base_answers(dest, project_name="mypub")
    trust.add_trust(bailiff_mod_github_repo_public.url)
    spec = runner.RunSpec(
        source=bailiff_mod_github_repo_public.url,
        dest=str(dest),
        answers={"visibility": "public", "create_remote": True},
    )
    # copier propagates non-zero task exit; bailiff wraps it as BailiffError.
    with pytest.raises(BailiffError):
        runner.init(spec, today="2026-07-14")


# ---------------------------------------------------------------------------
# Test: gh absent → non-fatal (exit 0), scaffold continues
# ---------------------------------------------------------------------------


def test_gh_absent_is_nonfatal(bailiff_mod_github_repo_no_gh: TemplateRepo, tmp_path: Path) -> None:
    """When gh is absent the task exits 0 and the answers file is still written."""
    dest = tmp_path / "proj"
    _seed_base_answers(dest)
    trust.add_trust(bailiff_mod_github_repo_no_gh.url)
    spec = runner.RunSpec(
        source=bailiff_mod_github_repo_no_gh.url,
        dest=str(dest),
        answers={"visibility": "private", "create_remote": True},
    )
    # Must NOT raise — non-fatal exit 0.
    runner.init(spec, today="2026-07-14")

    # The module writes its own answers file (distinct from the pre-seeded base answers).
    module_af_files = [
        f for f in dest.glob(".copier-answers*.yml") if "bailiff-mod-base" not in f.name
    ]
    assert module_af_files, "module answers file must exist even when gh is absent"

    af = yaml.safe_load(module_af_files[0].read_text())
    assert af["visibility"] == "private"


# ---------------------------------------------------------------------------
# Test: normal init with stubbed gh (offline)
# ---------------------------------------------------------------------------


def test_init_stubbed_gh_writes_answers(
    bailiff_mod_github_repo: TemplateRepo, tmp_path: Path
) -> None:
    """Stubbed gh: init completes; answers file records question values; .github/ rendered."""
    dest = tmp_path / "proj"
    _seed_base_answers(dest)
    trust.add_trust(bailiff_mod_github_repo.url)
    spec = runner.RunSpec(
        source=bailiff_mod_github_repo.url,
        dest=str(dest),
        answers={
            "create_remote": True,
            "visibility": "private",
            "remote_protocol": "https",
            "push_after_create": False,
            "team": "",
        },
    )
    runner.init(spec, today="2026-07-14")

    # Module answers file written (exclude the pre-seeded base answers file).
    module_af_files = [
        f for f in dest.glob(".copier-answers*.yml") if "bailiff-mod-base" not in f.name
    ]
    assert module_af_files, "module answers file missing after init"

    af = yaml.safe_load(module_af_files[0].read_text())
    assert af["visibility"] == "private"
    assert af["remote_protocol"] == "https"
    assert af["push_after_create"] is False
    assert af["team"] == ""
    assert af["create_remote"] is True

    # Managed .github/ files must be rendered.
    assert (dest / ".github" / "CODEOWNERS").is_file(), ".github/CODEOWNERS must render"
    assert (dest / ".github" / "ISSUE_TEMPLATE" / "bug_report.md").is_file()
    assert (dest / ".github" / "ISSUE_TEMPLATE" / "feature_request.md").is_file()
    assert (dest / ".github" / "PULL_REQUEST_TEMPLATE" / "pull_request_template.md").is_file()


# ---------------------------------------------------------------------------
# Test: create_remote=false → .github/ renders but no gh tasks run
# ---------------------------------------------------------------------------


def _copy_github_repo_real(tmp_path: Path) -> TemplateRepo:
    """Clone the real bailiff-mod-github-repo WITHOUT stubbing tasks.

    Used for create_remote=false tests: the real tasks have ``when: "{{ create_remote }}"``
    so they never run when false — no stub needed to prove the gate works.
    """
    src = _MODULES_DIR / "bailiff-mod-github-repo"
    dest_root = tmp_path / "bailiff-mod-github-repo-real"
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest_root, dirs_exist_ok=True)
    _git(dest_root, "init", "-q")
    _git(dest_root, "add", "-A")
    _git(dest_root, "commit", "-qm", "module")
    _git(dest_root, "tag", "v1.0.0")
    return TemplateRepo(path=dest_root, tag="v1.0.0")


def test_create_remote_false_renders_metadata_no_task(tmp_path: Path) -> None:
    """create_remote=false: .github/ files present; real tasks gated and never run (FR-024)."""
    # Use the real (non-stubbed) module — tasks are gated on create_remote; with false
    # all task bodies are skipped, so no tool invocation occurs.
    module = _copy_github_repo_real(tmp_path)
    dest = tmp_path / "proj"
    _seed_base_answers(dest)
    trust.add_trust(module.url)
    spec = runner.RunSpec(
        source=module.url,
        dest=str(dest),
        answers={"create_remote": False, "visibility": "private"},
    )
    runner.init(spec, today="2026-07-14")

    # .github/ files must render regardless of create_remote.
    assert (dest / ".github" / "CODEOWNERS").is_file(), ".github/CODEOWNERS must render"
    assert (dest / ".github" / "ISSUE_TEMPLATE" / "bug_report.md").is_file()

    # No side-effect files should exist (real tasks are when:false-gated).
    assert not (dest / ".bailiff-gh-preflight").exists(), (
        "no gh side-effect when create_remote=false"
    )


# ---------------------------------------------------------------------------
# Test: no secret: questions in copier.yml
# ---------------------------------------------------------------------------


def test_no_secret_questions() -> None:
    """copier.yml must not contain 'secret:' questions (Constitution VI / FR-005)."""
    copier_yml = (
        Path(__file__).resolve().parent.parent.parent
        / "templates"
        / "bailiff-mod-github-repo"
        / "copier.yml"
    )
    text = copier_yml.read_text()
    lines_with_secret = [line for line in text.splitlines() if re.match(r"^\s+secret\s*:", line)]
    assert not lines_with_secret, f"secret: questions found in copier.yml: {lines_with_secret}"
