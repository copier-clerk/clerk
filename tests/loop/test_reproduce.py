"""US2: faithful, agent-free reproduce (SC-002, FR-015, FR-015a, FR-017, FR-018)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from clerk import runner, trust
from tests.conftest import TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _tree_digest(root: Path, *, include_git: bool = False) -> dict[str, str]:
    """Hash of every rendered file, keyed by relative path.

    The enumerated comparison set (SC-002): all files under the project EXCEPT the
    `.git` working metadata (which is the task's side effect, not rendered output).
    The exclusion allowlist is exactly `.git/**` and nothing else.
    """
    digests: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if not include_git and rel.parts and rel.parts[0] == ".git":
            continue
        digests[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def _init(base_template: TemplateRepo, dest: Path) -> None:
    trust.add_trust(base_template.url)
    spec = runner.RunSpec(
        source=base_template.url, dest=str(dest), answers={"project_name": "demo"}
    )
    runner.init(spec, today="2026-07-09")


def test_reproduce_is_byte_identical(base_template: TemplateRepo, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    _init(base_template, dest)
    before = _tree_digest(dest)

    runner.reproduce(str(dest))
    after = _tree_digest(dest)

    # byte-identical over the enumerated set, empty exclusion beyond .git metadata
    assert before == after


def test_reproduce_overwrites_local_edits_in_place(
    base_template: TemplateRepo, tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    _init(base_template, dest)

    rendered = dest / "out.txt"
    rendered.write_text("HAND EDITED — should be reverted\n")
    unrelated = dest / "my_notes.md"
    unrelated.write_text("keep me\n")

    runner.reproduce(str(dest))

    # rendered file reverts (FR-015a); unrelated file survives
    assert "HAND EDITED" not in rendered.read_text()
    assert rendered.read_text().strip().startswith("name=demo")
    assert unrelated.exists()


def test_reproduce_requires_answers_file(tmp_path: Path) -> None:
    from clerk.errors import ClerkError

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ClerkError, match="nothing to reproduce"):
        runner.reproduce(str(empty))
