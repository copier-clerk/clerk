"""spec 012 T004: bailiff-mod-editorconfig loop tests (FR-006).

Pure MANAGED render — zero _tasks. Assertions:
- init alone (no language facts) → universal defaults only, no language sections;
- ts_linter=biome frozen → TS section with the linter's 2-space indent convention;
- python facts + ruff_line_length=88 → Python section max_line_length=88, indent 4
  (indentation from the linter convention, NEVER from line width);
- no secret: questions.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from bailiff import runner, trust
from tests.conftest import (
    _MODULES_DIR,
    TemplateRepo,
    _git,
)

_EC_FILE = Path(".editorconfig")

_UNIVERSAL_LINES = [
    "charset = utf-8",
    "end_of_line = lf",
    "insert_final_newline = true",
    "trim_trailing_whitespace = true",
]


def _copy_editorconfig_module(tmp_path: Path) -> TemplateRepo:
    """Clone the real bailiff-mod-editorconfig tree (pure render — no tasks to stub)."""
    src = _MODULES_DIR / "bailiff-mod-editorconfig"
    dest_root = tmp_path / "bailiff-mod-editorconfig"
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest_root, dirs_exist_ok=True)
    _git(dest_root, "init", "-q")
    _git(dest_root, "add", "-A")
    _git(dest_root, "commit", "-qm", "module")
    _git(dest_root, "tag", "v1.0.0")
    return TemplateRepo(path=dest_root, tag="v1.0.0")


@pytest.fixture
def bailiff_mod_editorconfig(tmp_path: Path) -> TemplateRepo:
    return _copy_editorconfig_module(tmp_path)


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> str:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-14")
    ec = dest / _EC_FILE
    assert ec.is_file(), ".editorconfig not rendered"
    return ec.read_text()


# ---------------------------------------------------------------------------
# Universal defaults only (US9 AS1, edge case: no language modules)
# ---------------------------------------------------------------------------


def test_universal_defaults_only(bailiff_mod_editorconfig: TemplateRepo, tmp_path: Path) -> None:
    """No frozen language facts → universal section only, no language sections invented."""
    text = _init(bailiff_mod_editorconfig, tmp_path / "proj", {"ts_linter": ""})

    assert "root = true" in text
    for line in _UNIVERSAL_LINES:
        assert line in text, f"universal default missing: {line}"
    assert "[*.py]" not in text, "Python section invented without frozen facts"
    assert "[*.{js" not in text, "TS section invented without frozen facts"


# ---------------------------------------------------------------------------
# TS section from ts_linter convention (US9 AS1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("linter", ["biome", "eslint-prettier"])
def test_ts_section_from_linter_convention(
    bailiff_mod_editorconfig: TemplateRepo, tmp_path: Path, linter: str
) -> None:
    """ts_linter frozen → TS section uses the linter's 2-space indent convention."""
    text = _init(bailiff_mod_editorconfig, tmp_path / "proj", {"ts_linter": linter})

    ts_section = text.split("[*.{js")[1]
    assert "indent_style = space" in ts_section
    assert "indent_size = 2" in ts_section, f"{linter} convention is 2-space indent"
    # Line width facts never leak into indentation decisions.
    assert "max_line_length" not in ts_section


# ---------------------------------------------------------------------------
# Python section: indent from convention, max_line_length from ruff (US9 AS2)
# ---------------------------------------------------------------------------


def test_python_section_indent_and_line_length(
    bailiff_mod_editorconfig: TemplateRepo, tmp_path: Path
) -> None:
    """python facts frozen → indent 4 (ruff/PEP8 convention) + max_line_length=ruff_line_length."""
    text = _init(
        bailiff_mod_editorconfig,
        tmp_path / "proj",
        {"ts_linter": "", "python_linter": "ruff", "ruff_line_length": "88"},
    )

    assert "[*.py]" in text
    py_section = text.split("[*.py]")[1]
    assert "indent_size = 4" in py_section, "Python indent is the linter convention (4)"
    assert "max_line_length = 88" in py_section

    # Different line length changes ONLY max_line_length, never the indent.
    text_120 = _init(
        bailiff_mod_editorconfig,
        tmp_path / "proj120",
        {"ts_linter": "", "python_linter": "ruff", "ruff_line_length": "120"},
    )
    py_120 = text_120.split("[*.py]")[1]
    assert "max_line_length = 120" in py_120
    assert "indent_size = 4" in py_120, "indentation must never derive from line width"


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


# ---------------------------------------------------------------------------
# Contract: no secret: questions
# ---------------------------------------------------------------------------


def test_no_secret_questions() -> None:
    copier_yml = _MODULES_DIR / "bailiff-mod-editorconfig" / "copier.yml"
    text = copier_yml.read_text()
    assert not re.search(r"^\s+secret\s*:", text, re.MULTILINE), "secret: question found"
