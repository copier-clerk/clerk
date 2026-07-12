"""US3: multi-layer upgrade in dependency order; new dep detection (Q-006b).

SC-003, FR-003, FR-009 (spec 006).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from clerk import runner
from clerk.errors import OrderingError
from tests.conftest import MultiUpgradeFixture, NewDepUpgradeFixture

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


def _init_layer(source_url: str, dest: Path, vcs_ref: str, af_name: str) -> None:
    """Init one layer into dest with a specific answers-file name."""
    from copier import run_copy

    dest.mkdir(parents=True, exist_ok=True)
    run_copy(
        source_url,
        str(dest),
        data={"project_name": "myproject"},
        vcs_ref=vcs_ref,
        answers_file=af_name,
        defaults=True,
        overwrite=True,
        quiet=True,
    )


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _init_multi_and_commit(
    dest: Path, a_url: str, b_url: str, a_tag: str = "v1.0.0", b_tag: str = "v1.0.0"
) -> None:
    """Init both layers A and B, then git-init and commit the whole project."""
    _init_layer(a_url, dest, vcs_ref=a_tag, af_name=".copier-answers.tpl-mu-a.yml")
    _init_layer(b_url, dest, vcs_ref=b_tag, af_name=".copier-answers.tpl-mu-b.yml")
    _git(dest, "init", "-q")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-qm", "initial multi")


def test_multi_upgrade_in_dependency_order(
    multi_upgrade_fixture: MultiUpgradeFixture, tmp_path: Path
) -> None:
    """US3-AS1: both layers upgraded in dependency order (A before B); both answers updated."""
    dest = tmp_path / "proj"
    a_url = str(multi_upgrade_fixture.tpl_a_path)
    b_url = str(multi_upgrade_fixture.tpl_b_path)
    # Neither template has tasks/migrations → no trust needed
    _init_multi_and_commit(dest, a_url, b_url)

    results = runner.update_many(str(dest), vcs_ref="v1.1.0")

    assert len(results) == 2

    af_a = dest / ".copier-answers.tpl-mu-a.yml"
    af_b = dest / ".copier-answers.tpl-mu-b.yml"
    assert af_a.exists()
    assert af_b.exists()

    raw_a = yaml.safe_load(af_a.read_text())
    raw_b = yaml.safe_load(af_b.read_text())
    assert raw_a["_commit"] == "v1.1.0"
    assert raw_b["_commit"] == "v1.1.0"

    # v1.1.0 files should have the updated content
    assert "v1.1" in (dest / "a_out.txt").read_text()
    assert "v1.1" in (dest / "b_out.txt").read_text()


def test_multi_upgrade_result_order_matches_dag(
    multi_upgrade_fixture: MultiUpgradeFixture, tmp_path: Path
) -> None:
    """US3-AS1 (ordering): results list has A before B (B depends_on A)."""
    dest = tmp_path / "proj"
    a_url = str(multi_upgrade_fixture.tpl_a_path)
    b_url = str(multi_upgrade_fixture.tpl_b_path)
    _init_multi_and_commit(dest, a_url, b_url)

    results = runner.update_many(str(dest), vcs_ref="v1.1.0")

    # The first result should be A (no deps), second B (depends_on A)
    basenames = [r.src.rstrip("/").rsplit("/", 1)[-1] for r in results]
    assert basenames.index("tpl-mu-a") < basenames.index("tpl-mu-b")


def test_new_dep_in_upgraded_template_refused(
    new_dep_upgrade_fixture: NewDepUpgradeFixture, tmp_path: Path
) -> None:
    """US3-AS2 / US5: v1.1.0 adds depends_on C which is not in project → OrderingError.

    Q-006b resolution: refuse with a clear remediation message (same as spec 003
    dangling-edge policy).  Nothing is written.
    """
    dest = tmp_path / "proj"
    b_url = str(new_dep_upgrade_fixture.tpl_b_path)

    # Init only template B at v1.0.0 (no depends_on yet)
    from copier import run_copy

    dest.mkdir(parents=True, exist_ok=True)
    run_copy(
        b_url,
        str(dest),
        data={"project_name": "myproject"},
        vcs_ref="v1.0.0",
        defaults=True,
        overwrite=True,
        quiet=True,
    )
    _git(dest, "init", "-q")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-qm", "initial")

    # b_out.txt should exist at v1.0.0 content
    before_content = (dest / "b_out.txt").read_text()

    with pytest.raises(OrderingError, match="tpl-nd-c"):
        runner.update_many(str(dest), vcs_ref="v1.1.0")

    # Nothing should have been written (refuse before any run_update)
    assert (dest / "b_out.txt").read_text() == before_content


def test_n1_via_multi_path_no_regression(
    multi_upgrade_fixture: MultiUpgradeFixture, tmp_path: Path
) -> None:
    """SC-006: single-layer project through update_many works (N=1 uniform loop)."""
    dest = tmp_path / "proj"
    a_url = str(multi_upgrade_fixture.tpl_a_path)

    # Init only template A (single layer)
    from copier import run_copy

    dest.mkdir(parents=True, exist_ok=True)
    run_copy(
        a_url,
        str(dest),
        data={"project_name": "myproject"},
        vcs_ref="v1.0.0",
        defaults=True,
        overwrite=True,
        quiet=True,
    )
    _git(dest, "init", "-q")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-qm", "initial")

    results = runner.update_many(str(dest), vcs_ref="v1.1.0")

    assert len(results) == 1
    af = next(dest.glob(".copier-answers*.yml"))
    raw = yaml.safe_load(af.read_text())
    assert raw["_commit"] == "v1.1.0"
