"""US4: consent before an action-taking template runs (FR-019, FR-020, FR-023)."""

from __future__ import annotations

from pathlib import Path

import pytest

from clerk import runner, trust
from clerk.errors import UntrustedSourceError
from tests.conftest import TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def test_untrusted_action_template_is_refused(base_template: TemplateRepo, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    spec = runner.RunSpec(source=base_template.url, dest=str(dest), answers={"project_name": "x"})

    with pytest.raises(UntrustedSourceError) as excinfo:
        runner.init(spec, today="2026-07-09")

    # names a prefix to trust, and takes no destructive action
    assert excinfo.value.prefix
    assert not dest.exists() or not (dest / "out.txt").exists()


def test_consent_then_success(base_template: TemplateRepo, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    spec = runner.RunSpec(source=base_template.url, dest=str(dest), answers={"project_name": "x"})

    # explicit consent step records trust...
    assert trust.add_trust(base_template.url) is True
    # ...then the same generation succeeds
    runner.init(spec, today="2026-07-09")
    assert (dest / "out.txt").exists()


def test_core_never_writes_trust(base_template: TemplateRepo, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    spec = runner.RunSpec(source=base_template.url, dest=str(dest), answers={"project_name": "x"})
    with pytest.raises(UntrustedSourceError):
        runner.init(spec, today="2026-07-09")
    # the failed run must NOT have recorded trust on its own (FR-019)
    assert trust.list_trust() == []
