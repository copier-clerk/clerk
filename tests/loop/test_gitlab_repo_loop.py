"""spec 012 T009: bailiff-mod-gitlab-repo loop tests (FR-012).

Exact port of the github-repo test shape (SC-005). Three safety paths:

1. visibility=public → hard exit 1 BEFORE any glab call (no silent public creation).
2. glab absent → non-fatal exit 0 (warn-and-continue); scaffold completes.
3. private + glab present (stubbed offline) → creation task runs, answers written.

This module writes NO project files; the only rendered output is the answers
file. Lifecycle class: pure side-effect (reconcile=false).
"""

from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from bailiff import runner, trust
from bailiff.errors import BailiffError
from tests.conftest import _GLAB_STUB_TASKS, TemplateRepo, _copy_module_with_stub_tasks

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


# Stub that exercises the public visibility gate: replicates the copier.yml
# logic for visibility=public and exits 1 unconditionally.
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
# Safety path 1: public visibility aborts with exit 1 (US6 AS1)
# ---------------------------------------------------------------------------


def test_public_visibility_aborts(
    bailiff_mod_gitlab_repo_public: TemplateRepo, tmp_path: Path
) -> None:
    """visibility=public must cause the task to exit 1 (hard abort-without-consent gate)."""
    trust.add_trust(bailiff_mod_gitlab_repo_public.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_gitlab_repo_public.url,
        dest=str(dest),
        answers={"project_name": "mypub", "visibility": "public"},
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
# Safety path 2: glab absent → non-fatal (exit 0), scaffold continues (US6 AS2)
# ---------------------------------------------------------------------------


def test_glab_absent_is_nonfatal(
    bailiff_mod_gitlab_repo_no_glab: TemplateRepo, tmp_path: Path
) -> None:
    """When glab is absent the task exits 0 and the answers file is still written."""
    trust.add_trust(bailiff_mod_gitlab_repo_no_glab.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_gitlab_repo_no_glab.url,
        dest=str(dest),
        answers={"project_name": "myproj", "visibility": "private"},
    )
    # Must NOT raise — non-fatal exit 0.
    runner.init(spec, today="2026-07-14")

    answers_files = list(dest.glob(".copier-answers*.yml"))
    assert answers_files, "answers file must exist even when glab is absent"

    af = yaml.safe_load(answers_files[0].read_text())
    assert af["project_name"] == "myproj"
    assert af["visibility"] == "private"


# ---------------------------------------------------------------------------
# Safety path 3: private + glab present (stubbed) → creation runs (US6)
# ---------------------------------------------------------------------------


def test_init_stubbed_glab_writes_answers(
    bailiff_mod_gitlab_repo: TemplateRepo, tmp_path: Path
) -> None:
    """Stubbed glab: init completes and the answers file records all question values."""
    trust.add_trust(bailiff_mod_gitlab_repo.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_gitlab_repo.url,
        dest=str(dest),
        answers={
            "project_name": "myproj",
            "visibility": "private",
            "remote_protocol": "https",
            "push_after_create": False,
            "team": "",
        },
    )
    runner.init(spec, today="2026-07-14")

    answers_files = list(dest.glob(".copier-answers*.yml"))
    assert answers_files, "answers file missing after init"

    af = yaml.safe_load(answers_files[0].read_text())
    assert af["visibility"] == "private"
    assert af["remote_protocol"] == "https"
    assert af["push_after_create"] is False
    assert af["team"] == ""

    # No other files written (pure side-effect module).
    rendered = [
        p
        for p in dest.iterdir()
        if p.name != ".bailiff-glab-preflight" and not p.name.startswith(".copier-answers")
    ]
    assert not rendered, f"unexpected files rendered by side-effect module: {rendered}"


# ---------------------------------------------------------------------------
# Contract: no secret: questions; token from ambient env (US6 AS3)
# ---------------------------------------------------------------------------


def test_no_secret_questions() -> None:
    """copier.yml must not contain 'secret:' questions (Constitution VI / FR-005)."""
    from tests.conftest import _MODULES_DIR

    text = (_MODULES_DIR / "bailiff-mod-gitlab-repo" / "copier.yml").read_text()
    lines_with_secret = [line for line in text.splitlines() if re.match(r"^\s+secret\s*:", line)]
    assert not lines_with_secret, f"secret: questions found in copier.yml: {lines_with_secret}"
    # Token must not be requested as a question — ambient GITLAB_TOKEN only.
    assert not re.search(r"^gitlab_token\s*:", text, re.MULTILINE)
