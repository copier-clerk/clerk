"""US6 / FR-006, FR-008: check mode validates via the engine dry run, writes nothing."""

from __future__ import annotations

from pathlib import Path

import pytest

from clerk import runner, trust
from clerk.errors import InvalidRunSpecError, UntrustedSourceError
from tests.conftest import TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def test_check_clean_produces_no_files(base_template: TemplateRepo, tmp_path: Path) -> None:
    trust.add_trust(base_template.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=base_template.url, dest=str(dest), answers={"project_name": "demo"}
    )
    result = runner.init(spec, today="2026-07-09", check=True)
    assert result.pretend is True
    # nothing written
    assert not (dest / "out.txt").exists()


def test_check_missing_answer_reports_and_writes_nothing(
    base_template: TemplateRepo, tmp_path: Path
) -> None:
    trust.add_trust(base_template.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(source=base_template.url, dest=str(dest), answers={})
    with pytest.raises(InvalidRunSpecError):
        runner.init(spec, today="2026-07-09", check=True)
    assert not (dest / "out.txt").exists()


def test_check_untrusted_reports_untrusted_precedence(
    base_template: TemplateRepo, tmp_path: Path
) -> None:
    # untrusted AND missing an answer → untrusted-source condition takes precedence,
    # because the engine (and clerk's pre-check) verify trust before answers.
    dest = tmp_path / "proj"
    spec = runner.RunSpec(source=base_template.url, dest=str(dest), answers={})
    with pytest.raises(UntrustedSourceError):
        runner.init(spec, today="2026-07-09", check=True)
