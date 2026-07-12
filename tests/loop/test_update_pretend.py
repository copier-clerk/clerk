"""US7: --pretend dry-run upgrade writes nothing, reports what would change.

SC-007, FR-011 (spec 006).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from clerk import runner, trust
from tests.conftest import MultiUpgradeFixture, UpgradeFixture

_PATH = __import__("os").environ.get("PATH", "/usr/bin:/bin")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "clerk-test",
            "GIT_AUTHOR_EMAIL": "test@clerk.invalid",
            "GIT_COMMITTER_NAME": "clerk-test",
            "GIT_COMMITTER_EMAIL": "test@clerk.invalid",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "PATH": _PATH,
        },
    )


def _init_git_commit(source_url: str, dest: Path, vcs_ref: str = "v1.0.0") -> None:
    from copier import run_copy

    dest.mkdir(parents=True, exist_ok=True)
    run_copy(
        source_url,
        str(dest),
        data={"project_name": "myproject"},
        vcs_ref=vcs_ref,
        defaults=True,
        overwrite=True,
        quiet=True,
    )
    _git(dest, "init", "-q")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-qm", "initial")


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def test_pretend_writes_nothing(single_upgrade_fixture: UpgradeFixture, tmp_path: Path) -> None:
    """SC-007: --pretend runs without writing; new_file.txt not created."""
    dest = tmp_path / "proj"
    source_url = single_upgrade_fixture.repo.url
    trust.add_trust(source_url)
    _init_git_commit(source_url, dest, vcs_ref="v1.0.0")

    af = next(dest.glob(".copier-answers*.yml"))
    before_commit = yaml.safe_load(af.read_text())["_commit"]

    result = runner.update(dest=str(dest), answers_file=af, vcs_ref="v1.1.0", pretend=True)

    # No new file created
    assert not (dest / "new_file.txt").exists()
    # Answers file not modified
    assert yaml.safe_load(af.read_text())["_commit"] == before_commit
    assert result.pretend is True


def test_pretend_returns_result_with_pretend_true(
    single_upgrade_fixture: UpgradeFixture, tmp_path: Path
) -> None:
    """pretend=True is reflected in the returned RunResult."""
    dest = tmp_path / "proj"
    source_url = single_upgrade_fixture.repo.url
    trust.add_trust(source_url)
    _init_git_commit(source_url, dest, vcs_ref="v1.0.0")

    af = next(dest.glob(".copier-answers*.yml"))
    result = runner.update(dest=str(dest), answers_file=af, pretend=True)

    assert result.pretend is True


def test_pretend_multi_writes_nothing(
    multi_upgrade_fixture: MultiUpgradeFixture, tmp_path: Path
) -> None:
    """SC-007 multi: --pretend on update_many leaves no answers files modified."""
    dest = tmp_path / "proj"
    a_url = str(multi_upgrade_fixture.tpl_a_path)
    b_url = str(multi_upgrade_fixture.tpl_b_path)

    from copier import run_copy

    dest.mkdir(parents=True, exist_ok=True)
    run_copy(
        a_url,
        str(dest),
        data={"project_name": "myproject"},
        vcs_ref="v1.0.0",
        answers_file=".copier-answers.tpl-mu-a.yml",
        defaults=True,
        overwrite=True,
        quiet=True,
    )
    run_copy(
        b_url,
        str(dest),
        data={"project_name": "myproject"},
        vcs_ref="v1.0.0",
        answers_file=".copier-answers.tpl-mu-b.yml",
        defaults=True,
        overwrite=True,
        quiet=True,
    )
    _git(dest, "init", "-q")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-qm", "initial multi")

    before_a = yaml.safe_load((dest / ".copier-answers.tpl-mu-a.yml").read_text())["_commit"]
    before_b = yaml.safe_load((dest / ".copier-answers.tpl-mu-b.yml").read_text())["_commit"]

    results = runner.update_many(str(dest), vcs_ref="v1.1.0", pretend=True)

    # Nothing written
    def _commit_of(name: str) -> str:
        return yaml.safe_load((dest / name).read_text())["_commit"]

    assert _commit_of(".copier-answers.tpl-mu-a.yml") == before_a
    assert _commit_of(".copier-answers.tpl-mu-b.yml") == before_b
    assert all(r.pretend for r in results)


def test_n1_pretend_regression(single_upgrade_fixture: UpgradeFixture, tmp_path: Path) -> None:
    """SC-006/SC-007: N=1 via update_many with pretend=True; no files written."""
    dest = tmp_path / "proj"
    source_url = single_upgrade_fixture.repo.url
    trust.add_trust(source_url)
    _init_git_commit(source_url, dest, vcs_ref="v1.0.0")

    af = next(dest.glob(".copier-answers*.yml"))
    before_commit = yaml.safe_load(af.read_text())["_commit"]

    results = runner.update_many(str(dest), vcs_ref="v1.1.0", pretend=True)

    assert len(results) == 1
    assert results[0].pretend is True
    assert not (dest / "new_file.txt").exists()
    assert yaml.safe_load(af.read_text())["_commit"] == before_commit
