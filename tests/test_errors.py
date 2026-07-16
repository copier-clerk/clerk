"""Unit tests for the CollisionError type (spec 013 T004)."""

from __future__ import annotations

from bailiff.errors import BailiffError, CollisionError


def test_collision_error_carries_path_and_modules() -> None:
    err = CollisionError("src/app.py", ["demo/bailiff-mod-a", "demo/bailiff-mod-b"])
    assert err.path == "src/app.py"
    assert err.modules == ["demo/bailiff-mod-a", "demo/bailiff-mod-b"]


def test_collision_error_message_names_path_and_modules() -> None:
    err = CollisionError("README.md", ["demo/mod-x", "demo/mod-y"])
    msg = str(err)
    assert "README.md" in msg
    assert "demo/mod-x" in msg
    assert "demo/mod-y" in msg
    assert "collision" in msg


def test_collision_error_is_bailiff_error() -> None:
    """Maps to exit 1 via the CLI's generic BailiffError handler."""
    assert issubclass(CollisionError, BailiffError)
