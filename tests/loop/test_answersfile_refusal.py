"""US5 / FR-016: refuse a template that cannot record its own answers."""

from __future__ import annotations

from pathlib import Path

import pytest

from clerk import discovery, runner, trust
from clerk.errors import NotReproducibleError
from tests.conftest import TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def test_discovery_reports_not_reproducible(no_answers_file_template: TemplateRepo) -> None:
    assert discovery.discover(no_answers_file_template.url).reproducible is False


def test_init_refuses_non_reproducible_template(
    no_answers_file_template: TemplateRepo, tmp_path: Path
) -> None:
    trust.add_trust(no_answers_file_template.url)  # trusted, but still refused
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=no_answers_file_template.url, dest=str(dest), answers={"project_name": "x"}
    )
    with pytest.raises(NotReproducibleError):
        runner.init(spec, today="2026-07-09")
    # nothing produced
    assert not (dest / "out.txt").exists()
