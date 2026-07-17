"""spec 012 T009: bailiff-mod-gitlab-repo loop tests (FR-012 / R12).

Four scenarios per contract:

1. visibility=public + create_remote=true → hard exit 1 before any glab call.
2. glab absent + create_remote=true → non-fatal exit 0; scaffold completes.
3. private + glab present (stubbed) + create_remote=true → creation runs; answers written.
4. create_remote=false (default) → .gitlab/ files render; no glab tasks run.

This module writes .gitlab/ managed files (CODEOWNERS, issue_templates,
merge_request_templates) plus the answers file. Remote creation is init-only,
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
    _GLAB_STUB_TASKS,
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
def bailiff_mod_gitlab_repo(tmp_path: Path) -> TemplateRepo:
    """Real bailiff-mod-gitlab-repo with glab tasks stubbed offline."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-gitlab-repo",
        tmp_path / "bailiff-mod-gitlab-repo",
        _GLAB_STUB_TASKS,
    )


# Stub that simulates glab being absent: exits 0 (non-fatal per contract).
_GLAB_ABSENT_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'glab-absent-stub\\n' > .bailiff-glab-preflight"
    """
)


@pytest.fixture
def bailiff_mod_gitlab_repo_no_glab(tmp_path: Path) -> TemplateRepo:
    """Variant where the glab-absent path is taken (non-fatal exit 0)."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-gitlab-repo",
        tmp_path / "bailiff-mod-gitlab-repo-no-glab",
        _GLAB_ABSENT_STUB_TASKS,
    )


# Stub that exercises the public visibility gate: exits 1 unconditionally.
_GLAB_PUBLIC_STUB_TASKS = dedent(
    """\
    _tasks:
      - >-
        echo "bailiff-mod-gitlab-repo: ABORTED — public requires manual confirmation." >&2;
        exit 1
    """
)


@pytest.fixture
def bailiff_mod_gitlab_repo_public(tmp_path: Path) -> TemplateRepo:
    """Variant whose task always exits 1 (simulates public consent gate firing)."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-gitlab-repo",
        tmp_path / "bailiff-mod-gitlab-repo-public",
        _GLAB_PUBLIC_STUB_TASKS,
    )


# ---------------------------------------------------------------------------
# Safety path 1: public visibility aborts with exit 1
# ---------------------------------------------------------------------------


def test_public_visibility_aborts(
    bailiff_mod_gitlab_repo_public: TemplateRepo, tmp_path: Path
) -> None:
    """visibility=public must cause the task to exit 1 (hard abort-without-consent gate)."""
    dest = tmp_path / "proj"
    _seed_base_answers(dest, project_name="mypub")
    trust.add_trust(bailiff_mod_gitlab_repo_public.url)
    spec = runner.RunSpec(
        source=bailiff_mod_gitlab_repo_public.url,
        dest=str(dest),
        answers={"visibility": "public", "create_remote": True},
    )
    with pytest.raises(BailiffError):
        runner.init(spec, today="2026-07-14")


def test_authored_gate_fires_before_creation() -> None:
    """In the AUTHORED template, the public exit-1 gate precedes glab repo create."""
    from tests.conftest import _MODULES_DIR

    copier_yml = (_MODULES_DIR / "bailiff-mod-gitlab-repo" / "copier.yml").read_text()
    gate_pos = copier_yml.index("visibility == 'public'")
    create_pos = copier_yml.index("glab repo create\n")
    assert gate_pos < create_pos, "consent gate must run BEFORE glab repo create"


# ---------------------------------------------------------------------------
# Safety path 2: glab absent → non-fatal (exit 0), scaffold continues
# ---------------------------------------------------------------------------


def test_glab_absent_is_nonfatal(
    bailiff_mod_gitlab_repo_no_glab: TemplateRepo, tmp_path: Path
) -> None:
    """When glab is absent the task exits 0 and the answers file is still written."""
    dest = tmp_path / "proj"
    _seed_base_answers(dest)
    trust.add_trust(bailiff_mod_gitlab_repo_no_glab.url)
    spec = runner.RunSpec(
        source=bailiff_mod_gitlab_repo_no_glab.url,
        dest=str(dest),
        answers={"visibility": "private", "create_remote": True},
    )
    # Must NOT raise — non-fatal exit 0.
    runner.init(spec, today="2026-07-14")

    module_af_files = [
        f for f in dest.glob(".copier-answers*.yml") if "bailiff-mod-base" not in f.name
    ]
    assert module_af_files, "module answers file must exist even when glab is absent"

    af = yaml.safe_load(module_af_files[0].read_text())
    assert af["visibility"] == "private"


# ---------------------------------------------------------------------------
# Safety path 3: private + glab present (stubbed) → creation runs
# ---------------------------------------------------------------------------


def test_init_stubbed_glab_writes_answers(
    bailiff_mod_gitlab_repo: TemplateRepo, tmp_path: Path
) -> None:
    """Stubbed glab: init completes; answers file records question values; .gitlab/ rendered."""
    dest = tmp_path / "proj"
    _seed_base_answers(dest)
    trust.add_trust(bailiff_mod_gitlab_repo.url)
    spec = runner.RunSpec(
        source=bailiff_mod_gitlab_repo.url,
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

    # Managed .gitlab/ files must be rendered.
    assert (dest / ".gitlab" / "CODEOWNERS").is_file(), ".gitlab/CODEOWNERS must render"
    assert (dest / ".gitlab" / "issue_templates" / "bug_report.md").is_file()
    assert (dest / ".gitlab" / "issue_templates" / "feature_request.md").is_file()
    assert (dest / ".gitlab" / "merge_request_templates" / "default.md").is_file()


# ---------------------------------------------------------------------------
# Safety path 4: create_remote=false → .gitlab/ renders but no glab tasks run
# ---------------------------------------------------------------------------


def _copy_gitlab_repo_real(tmp_path: Path) -> TemplateRepo:
    """Clone the real bailiff-mod-gitlab-repo WITHOUT stubbing tasks.

    Used for create_remote=false tests: the real tasks have ``when: "{{ create_remote }}"``
    so they never run when false — no stub needed to prove the gate works.
    """
    src = _MODULES_DIR / "bailiff-mod-gitlab-repo"
    dest_root = tmp_path / "bailiff-mod-gitlab-repo-real"
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest_root, dirs_exist_ok=True)
    _git(dest_root, "init", "-q")
    _git(dest_root, "add", "-A")
    _git(dest_root, "commit", "-qm", "module")
    _git(dest_root, "tag", "v1.0.0")
    return TemplateRepo(path=dest_root, tag="v1.0.0")


def test_create_remote_false_renders_metadata_no_task(tmp_path: Path) -> None:
    """create_remote=false: .gitlab/ files present; real tasks gated and never run (FR-024)."""
    module = _copy_gitlab_repo_real(tmp_path)
    dest = tmp_path / "proj"
    _seed_base_answers(dest)
    trust.add_trust(module.url)
    spec = runner.RunSpec(
        source=module.url,
        dest=str(dest),
        answers={"create_remote": False, "visibility": "private"},
    )
    runner.init(spec, today="2026-07-14")

    # .gitlab/ files must render regardless of create_remote.
    assert (dest / ".gitlab" / "CODEOWNERS").is_file(), ".gitlab/CODEOWNERS must render"
    assert (dest / ".gitlab" / "issue_templates" / "bug_report.md").is_file()

    # No side-effect files should exist (real tasks are when:false-gated).
    assert not (dest / ".bailiff-glab-preflight").exists(), (
        "no glab side-effect when create_remote=false"
    )


# ---------------------------------------------------------------------------
# Contract: no secret: questions; token from ambient env
# ---------------------------------------------------------------------------


def test_no_secret_questions() -> None:
    """copier.yml must not contain 'secret:' questions (Constitution VI / FR-005)."""
    from tests.conftest import _MODULES_DIR

    text = (_MODULES_DIR / "bailiff-mod-gitlab-repo" / "copier.yml").read_text()
    lines_with_secret = [line for line in text.splitlines() if re.match(r"^\s+secret\s*:", line)]
    assert not lines_with_secret, f"secret: questions found in copier.yml: {lines_with_secret}"
    # Token must not be requested as a question — ambient GITLAB_TOKEN only.
    assert not re.search(r"^gitlab_token\s*:", text, re.MULTILINE)
