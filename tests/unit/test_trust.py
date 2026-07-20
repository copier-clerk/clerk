"""Unit tests for trust read/add/list (US4: FR-019, FR-021, FR-022, FR-023b)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "settings.yml"
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(path))
    return path


def test_add_trust_writes_prefix(settings_file: Path) -> None:
    from bailiff import trust

    assert trust.add_trust("https://github.com/bailiff-io/") is True
    assert settings_file.is_file()
    data = yaml.safe_load(settings_file.read_text())
    assert data["trust"] == ["https://github.com/bailiff-io/"]


def test_add_trust_is_idempotent(settings_file: Path) -> None:
    from bailiff import trust

    assert trust.add_trust("https://github.com/bailiff-io/") is True
    assert trust.add_trust("https://github.com/bailiff-io/") is False  # no dupe
    data = yaml.safe_load(settings_file.read_text())
    assert data["trust"] == ["https://github.com/bailiff-io/"]


def test_add_trust_preserves_existing_entries_and_defaults(settings_file: Path) -> None:
    settings_file.write_text(
        yaml.safe_dump(
            {
                "trust": ["https://github.com/existing/"],
                "defaults": {"user_name": "sjors"},
            }
        )
    )
    from bailiff import trust

    trust.add_trust("https://github.com/bailiff-io/bailiff-mod-base")
    data = yaml.safe_load(settings_file.read_text())
    assert "https://github.com/existing/" in data["trust"]
    assert "https://github.com/bailiff-io/bailiff-mod-base" in data["trust"]
    # the unrelated defaults block survives
    assert data["defaults"] == {"user_name": "sjors"}


def test_list_trust_reads_back(settings_file: Path) -> None:
    from bailiff import trust

    trust.add_trust("https://github.com/a/")
    trust.add_trust("https://github.com/b/")
    assert trust.list_trust() == ["https://github.com/a/"] + ["https://github.com/b/"]


def test_is_trusted_prefix_and_exact(settings_file: Path) -> None:
    from bailiff import trust

    trust.add_trust("https://github.com/bailiff-io/")  # trailing slash → prefix
    trust.add_trust("https://github.com/solo/one-repo")  # no slash → exact
    assert trust.is_trusted("https://github.com/bailiff-io/bailiff-mod-base") is True
    assert trust.is_trusted("https://github.com/solo/one-repo") is True
    assert trust.is_trusted("https://github.com/solo/other-repo") is False
    assert trust.is_trusted("https://github.com/untrusted/x") is False


def test_malformed_settings_not_clobbered(settings_file: Path) -> None:
    settings_file.write_text("just a string, not a mapping\n")
    from bailiff import trust

    with pytest.raises(ValueError, match="not a mapping"):
        trust.add_trust("https://github.com/bailiff-io/")


class TestSuggestPrefix:
    """suggest_prefix must resolve a bare owner/repo shorthand to the expanded
    https:// form FIRST, so `trust add --from-source owner/repo` records the same
    org prefix copier matches against — not a non-matching bare string."""

    def test_bare_shorthand_yields_org_prefix(self) -> None:
        from bailiff.trust import suggest_prefix

        assert suggest_prefix("bailiff-io/bailiff-mod-base") == "https://github.com/bailiff-io/"

    def test_full_url_yields_same_org_prefix(self) -> None:
        from bailiff.trust import suggest_prefix

        assert (
            suggest_prefix("https://github.com/bailiff-io/bailiff-mod-base.git")
            == "https://github.com/bailiff-io/"
        )

    def test_local_path_passes_through(self) -> None:
        from bailiff.trust import suggest_prefix

        assert suggest_prefix("/local/path/mod") == "/local/path/mod"
