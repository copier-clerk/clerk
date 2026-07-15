"""US1: single-layer upgrade — answers file updated, new file present, guards fire.

SC-001, SC-005, FR-009, FR-011, FR-012 (spec 006).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from bailiff import runner, trust
from bailiff.errors import DowngradeError, UntrustedSourceError
from tests.conftest import UpgradeFixture

_PATH = __import__("os").environ.get("PATH", "/usr/bin:/bin")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "bailiff-test",
            "GIT_AUTHOR_EMAIL": "test@bailiff.invalid",
            "GIT_COMMITTER_NAME": "bailiff-test",
            "GIT_COMMITTER_EMAIL": "test@bailiff.invalid",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "PATH": _PATH,
        },
    )


def _init_and_git_commit(source_url: str, dest: Path, vcs_ref: str = "v1.0.0") -> None:
    """Init a project from source at vcs_ref, then commit everything to a git repo.

    copier's run_update requires the destination to be a git repo with no dirty state
    (it checks ``subproject.vcs == 'git'`` and ``not subproject.is_dirty()``).
    """
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
    # Wrap in a git repo so copier's run_update can apply the 3-way merge.
    _git(dest, "init", "-q")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-qm", "initial")


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def test_single_upgrade_new_file_present(
    single_upgrade_fixture: UpgradeFixture, tmp_path: Path
) -> None:
    """US1-AS1: v1.0.0 → v1.1.0; new file present; answers _commit updated."""
    dest = tmp_path / "proj"
    source_url = single_upgrade_fixture.repo.url
    # v1.1.0 has _migrations → trust required
    trust.add_trust(source_url)
    _init_and_git_commit(source_url, dest, vcs_ref="v1.0.0")

    # Confirm new_file.txt is not yet present
    assert not (dest / "new_file.txt").exists()

    # Read the pre-upgrade answers file
    af = next(dest.glob(".copier-answers*.yml"))
    before_raw = yaml.safe_load(af.read_text())
    assert before_raw["_commit"] == "v1.0.0"

    # Run upgrade to latest (v1.1.0)
    result = runner.update(dest=str(dest), answers_file=af)

    # new_file.txt from v1.1.0 should now be present
    assert (dest / "new_file.txt").exists()

    # answers file _commit should be updated
    after_raw = yaml.safe_load(af.read_text())
    assert after_raw["_commit"] == "v1.1.0"

    assert result.ref == "v1.1.0"
    assert not result.pretend


def test_single_upgrade_explicit_vcs_ref(
    single_upgrade_fixture: UpgradeFixture, tmp_path: Path
) -> None:
    """US1-AS2: --vcs-ref v1.1.0 explicitly targets that version."""
    dest = tmp_path / "proj"
    source_url = single_upgrade_fixture.repo.url
    trust.add_trust(source_url)
    _init_and_git_commit(source_url, dest, vcs_ref="v1.0.0")

    af = next(dest.glob(".copier-answers*.yml"))
    result = runner.update(dest=str(dest), answers_file=af, vcs_ref="v1.1.0")

    after_raw = yaml.safe_load(af.read_text())
    assert after_raw["_commit"] == "v1.1.0"
    assert result.ref == "v1.1.0"


def test_already_at_target_is_noop(single_upgrade_fixture: UpgradeFixture, tmp_path: Path) -> None:
    """Already-at-target: upgrading to the current version returns early, no change."""
    dest = tmp_path / "proj"
    source_url = single_upgrade_fixture.repo.url
    trust.add_trust(source_url)
    _init_and_git_commit(source_url, dest, vcs_ref="v1.1.0")

    af = next(dest.glob(".copier-answers*.yml"))
    before_mtime = af.stat().st_mtime

    result = runner.update(dest=str(dest), answers_file=af, vcs_ref="v1.1.0")

    # File should not have been rewritten (no-op)
    assert af.stat().st_mtime == before_mtime
    assert result.ref == "v1.1.0"


def test_untrusted_source_with_migrations_raises(
    single_upgrade_fixture: UpgradeFixture, tmp_path: Path
) -> None:
    """US1-AS3: untrusted source + migrations → UntrustedSourceError before run_update."""
    dest = tmp_path / "proj"
    source_url = single_upgrade_fixture.repo.url

    # Init at v1.0.0 (no migrations) — trust needed at v1.1.0 only
    _init_and_git_commit(source_url, dest, vcs_ref="v1.0.0")
    af = next(dest.glob(".copier-answers*.yml"))

    # Do NOT add trust; v1.1.0 has _migrations → should refuse
    with pytest.raises(UntrustedSourceError):
        runner.update(dest=str(dest), answers_file=af, vcs_ref="v1.1.0")

    # Confirm new_file.txt was NOT written (no run_update call happened)
    assert not (dest / "new_file.txt").exists()


def test_downgrade_raises(single_upgrade_fixture: UpgradeFixture, tmp_path: Path) -> None:
    """FR-012: targeting an older version refuses with DowngradeError."""
    dest = tmp_path / "proj"
    source_url = single_upgrade_fixture.repo.url
    trust.add_trust(source_url)
    _init_and_git_commit(source_url, dest, vcs_ref="v1.1.0")

    af = next(dest.glob(".copier-answers*.yml"))
    with pytest.raises(DowngradeError):
        runner.update(dest=str(dest), answers_file=af, vcs_ref="v1.0.0")


def test_update_many_single_layer(single_upgrade_fixture: UpgradeFixture, tmp_path: Path) -> None:
    """SC-006: N=1 via update_many behaves identically to direct update (uniform loop)."""
    dest = tmp_path / "proj"
    source_url = single_upgrade_fixture.repo.url

    # Must trust (v1.1.0 has migrations)
    trust.add_trust(source_url)
    _init_and_git_commit(source_url, dest, vcs_ref="v1.0.0")

    results = runner.update_many(str(dest), vcs_ref="v1.1.0")

    assert len(results) == 1
    assert (dest / "new_file.txt").exists()
    af = next(dest.glob(".copier-answers*.yml"))
    after_raw = yaml.safe_load(af.read_text())
    assert after_raw["_commit"] == "v1.1.0"
