"""Unit tests for bailiff.defaults (spec 004, T006).

Tests: path resolution, load, select_keys, fold_settings_defaults.
All hermetic — no copier calls, no network.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from bailiff.defaults import defaults_path, fold_settings_defaults, load, select_keys
from bailiff.discovery import Question
from bailiff.errors import DefaultsError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _q(key: str, *, secret: bool = False, when: Any = True) -> Question:
    return Question(
        key=key,
        type="str",
        choices=None,
        default_raw=None,
        help=None,
        when=when,
        validator=None,
        secret=secret,
    )


# ---------------------------------------------------------------------------
# defaults_path()
# ---------------------------------------------------------------------------


class TestDefaultsPath:
    def test_env_unset_returns_platformdirs_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BAILIFF_DEFAULTS_PATH", raising=False)
        p = defaults_path()
        assert p.name == "defaults.yml"
        assert "bailiff" in str(p)

    def test_env_set_to_existing_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        target = tmp_path / "my_defaults.yml"
        target.write_text("author_name: Ada\n")
        monkeypatch.setenv("BAILIFF_DEFAULTS_PATH", str(target))
        assert defaults_path() == target

    def test_env_set_to_missing_file_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        missing = tmp_path / "nonexistent.yml"
        monkeypatch.setenv("BAILIFF_DEFAULTS_PATH", str(missing))
        with pytest.raises(DefaultsError, match="not found"):
            defaults_path()


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------


class TestLoad:
    def test_missing_file_returns_empty_dict(self, tmp_path: Path) -> None:
        assert load(tmp_path / "absent.yml") == {}

    def test_empty_file_returns_empty_dict(self, tmp_path: Path) -> None:
        p = tmp_path / "defaults.yml"
        p.write_text("")
        assert load(p) == {}

    def test_valid_flat_yaml_returns_dict(self, tmp_path: Path) -> None:
        p = tmp_path / "defaults.yml"
        p.write_text("author_name: Ada\nauthor_email: ada@example.com\n")
        result = load(p)
        assert result == {"author_name": "Ada", "author_email": "ada@example.com"}

    def test_malformed_yaml_raises_defaults_error(self, tmp_path: Path) -> None:
        p = tmp_path / "defaults.yml"
        p.write_text("key: [unclosed bracket\n")
        with pytest.raises(DefaultsError, match="not valid YAML"):
            load(p)

    def test_malformed_yaml_error_includes_path(self, tmp_path: Path) -> None:
        p = tmp_path / "defaults.yml"
        p.write_text("key: [unclosed bracket\n")
        with pytest.raises(DefaultsError, match=str(p)):
            load(p)

    def test_non_mapping_top_level_raises_defaults_error(self, tmp_path: Path) -> None:
        p = tmp_path / "defaults.yml"
        p.write_text("- item1\n- item2\n")
        with pytest.raises(DefaultsError, match="mapping"):
            load(p)

    def test_integer_values_preserved(self, tmp_path: Path) -> None:
        p = tmp_path / "defaults.yml"
        p.write_text("year: 2024\n")
        assert load(p) == {"year": 2024}

    def test_boolean_values_preserved(self, tmp_path: Path) -> None:
        p = tmp_path / "defaults.yml"
        p.write_text("enable_ci: true\n")
        assert load(p) == {"enable_ci": True}


# ---------------------------------------------------------------------------
# select_keys()
# ---------------------------------------------------------------------------


class TestSelectKeys:
    def test_includes_matching_non_secret_key(self) -> None:
        questions = [_q("author_name"), _q("org")]
        result = select_keys({"author_name": "Ada", "extra": "ignored"}, questions)
        assert result == {"author_name": "Ada"}

    def test_excludes_key_not_in_questions(self) -> None:
        questions = [_q("project_name")]
        result = select_keys({"project_name": "my-proj", "unknown_key": "x"}, questions)
        assert "unknown_key" not in result

    def test_excludes_secret_question(self) -> None:
        questions = [_q("author_name"), _q("api_key", secret=True)]
        result = select_keys({"author_name": "Ada", "api_key": "s3cr3t"}, questions)
        assert "api_key" not in result
        assert result == {"author_name": "Ada"}

    def test_excludes_when_false_question(self) -> None:
        questions = [_q("author_name"), _q("depends_on", when=False)]
        result = select_keys({"author_name": "Ada", "depends_on": ["base"]}, questions)
        assert "depends_on" not in result

    def test_includes_when_truthy_string_question(self) -> None:
        # when="some_jinja_expr" is not False, so we include it
        questions = [_q("conditional_q", when="{{ some_var }}")]
        result = select_keys({"conditional_q": "val"}, questions)
        assert result == {"conditional_q": "val"}

    def test_empty_defaults_returns_empty(self) -> None:
        questions = [_q("author_name")]
        assert select_keys({}, questions) == {}

    def test_empty_questions_returns_empty(self) -> None:
        assert select_keys({"author_name": "Ada"}, []) == {}

    def test_all_keys_secret_returns_empty(self) -> None:
        questions = [_q("api_key", secret=True), _q("token", secret=True)]
        result = select_keys({"api_key": "s3", "token": "tok"}, questions)
        assert result == {}

    def test_multiple_matching_keys(self) -> None:
        questions = [_q("author_name"), _q("author_email"), _q("org")]
        result = select_keys(
            {"author_name": "Ada", "author_email": "ada@x.com", "org": "acme"}, questions
        )
        assert result == {"author_name": "Ada", "author_email": "ada@x.com", "org": "acme"}


# ---------------------------------------------------------------------------
# fold_settings_defaults()
# ---------------------------------------------------------------------------


class TestFoldSettingsDefaults:
    def test_toml_wins_on_collision(self) -> None:
        mock_settings = MagicMock()
        mock_settings.defaults = {"user_name": "copier-value", "user_email": "copier@x.com"}
        with patch("copier.load_settings", return_value=mock_settings):
            result = fold_settings_defaults({"user_name": "bailiff-value"})
        assert result["user_name"] == "bailiff-value"
        assert result["user_email"] == "copier@x.com"

    def test_settings_keys_merged_when_absent_from_toml(self) -> None:
        mock_settings = MagicMock()
        mock_settings.defaults = {"user_name": "Turing"}
        with patch("copier.load_settings", return_value=mock_settings):
            result = fold_settings_defaults({})
        assert result == {"user_name": "Turing"}

    def test_load_settings_exception_returns_toml_unchanged(self) -> None:
        with patch("copier.load_settings", side_effect=Exception("settings broken")):
            result = fold_settings_defaults({"author_name": "Ada"})
        assert result == {"author_name": "Ada"}

    def test_empty_settings_defaults_returns_toml(self) -> None:
        mock_settings = MagicMock()
        mock_settings.defaults = {}
        with patch("copier.load_settings", return_value=mock_settings):
            result = fold_settings_defaults({"author_name": "Ada"})
        assert result == {"author_name": "Ada"}

    def test_none_settings_defaults_returns_toml(self) -> None:
        mock_settings = MagicMock()
        mock_settings.defaults = None
        with patch("copier.load_settings", return_value=mock_settings):
            result = fold_settings_defaults({"author_name": "Ada"})
        assert result == {"author_name": "Ada"}
