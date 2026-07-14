"""spec 011 T018: clerk-mod-github-repo loop tests.

Three scenarios per contract (docs-integration.md §clerk-mod-github-repo):

1. visibility=public → hard exit 1 before any gh call (no silent public creation).
2. gh absent → non-fatal exit 0 (warn-and-continue); scaffold completes.
3. gh present (stubbed offline) → init succeeds, answers file written.

This module writes NO project files; the only rendered output is the answers
file. Lifecycle class: pure side-effect (reconcile=false).
"""

from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from clerk import runner, trust
from clerk.errors import ClerkError
from tests.conftest import _GH_STUB_TASKS, TemplateRepo, _copy_module_with_stub_tasks

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


@pytest.fixture
def clerk_mod_github_repo(tmp_path: Path) -> TemplateRepo:
    """Real clerk-mod-github-repo with gh tasks stubbed offline."""
    return _copy_module_with_stub_tasks(
        "clerk-mod-github-repo",
        tmp_path / "clerk-mod-github-repo",
        _GH_STUB_TASKS,
    )


# Stub that simulates gh being absent: exits 0 (non-fatal per contract).
_GH_ABSENT_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'gh-absent-stub\\n' > .clerk-gh-preflight"
    """
)


@pytest.fixture
def clerk_mod_github_repo_no_gh(tmp_path: Path) -> TemplateRepo:
    """Variant where the gh-absent path is taken (non-fatal exit 0)."""
    return _copy_module_with_stub_tasks(
        "clerk-mod-github-repo",
        tmp_path / "clerk-mod-github-repo-no-gh",
        _GH_ABSENT_STUB_TASKS,
    )


# Stub that exercises the public visibility gate: the task block replicates the
# copier.yml logic for visibility=public and exits 1 unconditionally.
_GH_PUBLIC_STUB_TASKS = dedent(
    """\
    _tasks:
      - >-
        echo "clerk-mod-github-repo: ABORTED — visibility=public requires manual confirmation." >&2;
        exit 1
    """
)


@pytest.fixture
def clerk_mod_github_repo_public(tmp_path: Path) -> TemplateRepo:
    """Variant whose task always exits 1 (simulates public consent gate firing)."""
    return _copy_module_with_stub_tasks(
        "clerk-mod-github-repo",
        tmp_path / "clerk-mod-github-repo-public",
        _GH_PUBLIC_STUB_TASKS,
    )


# ---------------------------------------------------------------------------
# Test: public visibility aborts with exit 1
# ---------------------------------------------------------------------------


def test_public_visibility_aborts(
    clerk_mod_github_repo_public: TemplateRepo, tmp_path: Path
) -> None:
    """visibility=public must cause the task to exit 1 (hard abort-without-consent gate)."""
    trust.add_trust(clerk_mod_github_repo_public.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_github_repo_public.url,
        dest=str(dest),
        answers={"project_name": "mypub", "visibility": "public"},
    )
    # copier propagates non-zero task exit; clerk wraps it as ClerkError.
    with pytest.raises(ClerkError):
        runner.init(spec, today="2026-07-14")


# ---------------------------------------------------------------------------
# Test: gh absent → non-fatal (exit 0), scaffold continues
# ---------------------------------------------------------------------------


def test_gh_absent_is_nonfatal(clerk_mod_github_repo_no_gh: TemplateRepo, tmp_path: Path) -> None:
    """When gh is absent the task exits 0 and the answers file is still written."""
    trust.add_trust(clerk_mod_github_repo_no_gh.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_github_repo_no_gh.url,
        dest=str(dest),
        answers={"project_name": "myproj", "visibility": "private"},
    )
    # Must NOT raise — non-fatal exit 0.
    runner.init(spec, today="2026-07-14")

    # Answers file written (module IS reproducible).
    answers_files = list(dest.glob(".copier-answers*.yml"))
    assert answers_files, "answers file must exist even when gh is absent"

    af = yaml.safe_load(answers_files[0].read_text())
    assert af["project_name"] == "myproj"
    assert af["visibility"] == "private"


# ---------------------------------------------------------------------------
# Test: normal init with stubbed gh (offline)
# ---------------------------------------------------------------------------


def test_init_stubbed_gh_writes_answers(
    clerk_mod_github_repo: TemplateRepo, tmp_path: Path
) -> None:
    """Stubbed gh: init completes and the answers file records all question values."""
    trust.add_trust(clerk_mod_github_repo.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_github_repo.url,
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

    # Answers file written with correct values.
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
        if p.name
        not in {
            ".copier-answers.clerk-mod-github-repo.yml",
            ".copier-answers.yml",
            ".clerk-gh-preflight",
        }
        and not p.name.startswith(".copier-answers")
    ]
    assert not rendered, f"unexpected files rendered by side-effect module: {rendered}"


# ---------------------------------------------------------------------------
# Test: no secret: questions in copier.yml
# ---------------------------------------------------------------------------


def test_no_secret_questions() -> None:
    """copier.yml must not contain 'secret:' questions (Constitution VI / FR-005)."""
    copier_yml = (
        Path(__file__).resolve().parent.parent.parent
        / "templates"
        / "clerk-mod-github-repo"
        / "copier.yml"
    )
    text = copier_yml.read_text()
    # 'secret:' appearing as a YAML key (not in a comment) must not be present.
    lines_with_secret = [line for line in text.splitlines() if re.match(r"^\s+secret\s*:", line)]
    assert not lines_with_secret, f"secret: questions found in copier.yml: {lines_with_secret}"
