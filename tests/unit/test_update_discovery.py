"""Unit tests for spec 006 discovery extensions.

Tests the static _check_migrations_format check and the has_migrations flag.
These are pure-function tests: no git cloning, no copier calls.
"""

from __future__ import annotations

import pytest

from bailiff.discovery import _check_migrations_format
from bailiff.errors import DeprecatedMigrationFormatError


class TestCheckMigrationsFormat:
    """_check_migrations_format raises on deprecated form; accepts new forms."""

    def test_empty_migrations_ok(self) -> None:
        _check_migrations_format({}, "src")

    def test_no_migrations_key_ok(self) -> None:
        _check_migrations_format({"project_name": {"type": "str"}}, "src")

    def test_new_format_bare_string_ok(self) -> None:
        _check_migrations_format(
            {"_migrations": ["echo hello"]},
            "src",
        )

    def test_new_format_bare_list_ok(self) -> None:
        _check_migrations_format(
            {"_migrations": [["python", "scripts/migrate.py"]]},
            "src",
        )

    def test_new_format_dict_with_command_ok(self) -> None:
        _check_migrations_format(
            {
                "_migrations": [
                    {"command": "echo hello", "version": "v1.1.0"},
                ]
            },
            "src",
        )

    def test_deprecated_before_key_raises(self) -> None:
        with pytest.raises(DeprecatedMigrationFormatError, match="deprecated"):
            _check_migrations_format(
                {
                    "_migrations": [
                        {
                            "version": "v1.1.0",
                            "before": ["echo before"],
                            "after": ["echo after"],
                        }
                    ]
                },
                "my/template",
            )

    def test_deprecated_after_only_raises(self) -> None:
        """An entry with only 'after' (no 'before') is also deprecated form."""
        with pytest.raises(DeprecatedMigrationFormatError):
            _check_migrations_format(
                {"_migrations": [{"version": "v1.1.0", "after": ["echo after"]}]},
                "src",
            )

    def test_deprecated_before_only_raises(self) -> None:
        with pytest.raises(DeprecatedMigrationFormatError):
            _check_migrations_format(
                {"_migrations": [{"version": "v1.1.0", "before": ["echo before"]}]},
                "src",
            )

    def test_error_names_source(self) -> None:
        with pytest.raises(DeprecatedMigrationFormatError, match="my/special-template"):
            _check_migrations_format(
                {"_migrations": [{"version": "v1.1.0", "before": ["x"]}]},
                "my/special-template",
            )

    def test_mixed_entries_one_deprecated_raises(self) -> None:
        """A mix of new-format and deprecated entries still raises."""
        with pytest.raises(DeprecatedMigrationFormatError):
            _check_migrations_format(
                {
                    "_migrations": [
                        "echo ok",  # new format
                        {"version": "v1.1.0", "before": ["echo bad"]},  # deprecated
                    ]
                },
                "src",
            )
