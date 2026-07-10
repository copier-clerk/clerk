"""FR-013 / SC-012: secrets and hidden ordering values are not persisted."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from clerk import runner, trust
from tests.conftest import TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def test_secret_and_edge_excluded_from_recorded_answers(
    secret_edge_template: TemplateRepo, tmp_path: Path
) -> None:
    trust.add_trust(secret_edge_template.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=secret_edge_template.url,
        dest=str(dest),
        answers={"project_name": "demo", "api_token": "s3cr3t-should-not-persist"},
    )
    runner.init(spec, today="2026-07-09")

    recorded = (dest / ".copier-answers.yml").read_text()
    answers = yaml.safe_load(recorded)
    # the secret value never lands on disk
    assert "s3cr3t-should-not-persist" not in recorded
    assert "api_token" not in answers
    # the when:false dependency edge is not persisted either
    assert "depends_on" not in answers
    # the ordinary answer is recorded
    assert answers["project_name"] == "demo"
