"""US2: migration version crossing — fires at correct boundary; deprecated form refused.

SC-002, FR-004, FR-005 (spec 006).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from bailiff import runner, trust
from bailiff.errors import DeprecatedMigrationFormatError
from tests.conftest import TemplateRepo, UpgradeFixture

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


def _init_git_commit(source_url: str, dest: Path, vcs_ref: str) -> None:
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


def test_migration_fires_at_correct_version_crossing(
    single_upgrade_fixture: UpgradeFixture, tmp_path: Path
) -> None:
    """US2-AS1: v1.0.0→v1.1.0 with version:v1.1.0 entry → migration command runs.

    The fixture's v1.1.0 migration runs ``touch .migrated``, so we check for that file.
    """
    dest = tmp_path / "proj"
    source_url = single_upgrade_fixture.repo.url
    trust.add_trust(source_url)
    _init_git_commit(source_url, dest, vcs_ref="v1.0.0")

    af = next(dest.glob(".copier-answers*.yml"))
    runner.update(dest=str(dest), answers_file=af, vcs_ref="v1.1.0")

    # The migration command ``touch .migrated`` should have created this sentinel
    assert (dest / ".migrated").exists(), ".migrated sentinel not created — migration did not fire"


def test_migration_does_not_refire_outside_version_window(
    single_upgrade_fixture: UpgradeFixture, tmp_path: Path
) -> None:
    """US2-AS2: already at v1.1.0, upgrading to latest (still v1.1.0) → no re-run.

    The already-at-target check returns early — run_update is never called.
    """
    dest = tmp_path / "proj"
    source_url = single_upgrade_fixture.repo.url
    trust.add_trust(source_url)
    _init_git_commit(source_url, dest, vcs_ref="v1.1.0")

    # Remove the sentinel if it exists (it shouldn't for a fresh init, but be explicit)
    sentinel = dest / ".migrated"
    if sentinel.exists():
        sentinel.unlink()

    af = next(dest.glob(".copier-answers*.yml"))
    # Upgrading to the same version we're already at → already-at-target early return
    runner.update(dest=str(dest), answers_file=af, vcs_ref="v1.1.0")

    # Sentinel should NOT have been created (no run_update was called)
    assert not sentinel.exists(), ".migrated was created but migration should not have re-fired"


def test_deprecated_migrations_format_refused_before_update(
    deprecated_migrations_fixture: TemplateRepo, tmp_path: Path
) -> None:
    """US2-AS3: deprecated {version, before, after} form → DeprecatedMigrationFormatError.

    The check happens before run_update; the project is NOT mutated.
    """
    dest = tmp_path / "proj"
    source_url = deprecated_migrations_fixture.url
    # Even with trust, the format check fires first
    trust.add_trust(source_url)

    # Init at v1.0.0 — the deprecated format is in that version
    from copier import run_copy

    dest.mkdir(parents=True, exist_ok=True)
    run_copy(
        source_url,
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

    af = next(dest.glob(".copier-answers*.yml"))

    with pytest.raises(DeprecatedMigrationFormatError, match="deprecated"):
        runner.update(dest=str(dest), answers_file=af)
