"""US3: settings.yml defaults fold (spec 004 / T011).

Tests:
- SC-001 (settings.yml): user_name from copier settings.yml pre-fills when
  defaults.yml is absent or does not mention the key.
- SC-002 (toml wins): bailiff's defaults.yml beats copier's settings.yml on collision.
- Graceful degradation: load_settings raising does not break init.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock, patch

import pytest
import yaml

from bailiff import runner, trust
from tests.conftest import TemplateRepo, build_template_repo

# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))
    monkeypatch.setenv("BAILIFF_DEFAULTS_PATH", str(tmp_path / "defaults.yml"))


def _write_defaults(tmp_path: Path, content: str) -> None:
    (tmp_path / "defaults.yml").write_text(content)


@pytest.fixture
def user_name_template(tmp_path: Path) -> TemplateRepo:
    """Template with a user_name question (matches copier settings.yml convention)."""
    copier_yml = dedent(
        """\
        user_name:
          type: str
        project_name:
          type: str

        _subdirectory: template
        """
    )
    return build_template_repo(
        tmp_path / "tpl-user-name",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "user={{ user_name }} project={{ project_name }}\n",
        },
    )


# ---------------------------------------------------------------------------
# SC-001: settings.yml pre-fills when defaults.yml is absent/silent
# ---------------------------------------------------------------------------


def test_settings_yml_defaults_pre_fill(user_name_template: TemplateRepo, tmp_path: Path) -> None:
    """user_name from copier settings.yml pre-fills when defaults.yml has no entry."""
    trust.add_trust(user_name_template.url)
    # defaults.yml exists but does not mention user_name
    _write_defaults(tmp_path, "")

    mock_settings = MagicMock()
    mock_settings.defaults = {"user_name": "Turing"}

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=user_name_template.url,
        dest=str(dest),
        answers={"project_name": "myproject"},
    )

    with patch("copier.load_settings", return_value=mock_settings):
        runner.init(spec)

    answers = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert answers["user_name"] == "Turing"


# ---------------------------------------------------------------------------
# SC-002: defaults.yml wins over settings.yml on collision
# ---------------------------------------------------------------------------


def test_defaults_yml_beats_settings_yml(user_name_template: TemplateRepo, tmp_path: Path) -> None:
    """bailiff's defaults.yml key wins over copier's settings.yml on the same key."""
    trust.add_trust(user_name_template.url)
    _write_defaults(tmp_path, "user_name: Babbage\n")

    mock_settings = MagicMock()
    mock_settings.defaults = {"user_name": "Turing"}

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=user_name_template.url,
        dest=str(dest),
        answers={"project_name": "myproject"},
    )

    with patch("copier.load_settings", return_value=mock_settings):
        runner.init(spec)

    answers = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert answers["user_name"] == "Babbage"


# ---------------------------------------------------------------------------
# Graceful degradation: load_settings raising does not break init
# ---------------------------------------------------------------------------


def test_load_settings_failure_degrades_gracefully(
    user_name_template: TemplateRepo, tmp_path: Path
) -> None:
    """If copier.load_settings raises, init completes using only the defaults.yml values."""
    trust.add_trust(user_name_template.url)
    _write_defaults(tmp_path, "user_name: Ada\n")

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=user_name_template.url,
        dest=str(dest),
        answers={"project_name": "myproject"},
    )

    with patch("copier.load_settings", side_effect=Exception("settings broken")):
        # Must not raise
        runner.init(spec)

    answers = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    # defaults.yml value should still be used
    assert answers["user_name"] == "Ada"
