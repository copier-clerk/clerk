"""Unit tests for the capability lint rules in check_modules.py (spec 013 T008).

Offline: builds temp module dirs and calls check_modules() directly, following
the pattern of tests/unit/test_check_modules.py.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest


def _load_check_modules():
    spec = importlib.util.spec_from_file_location(
        "check_modules",
        Path(__file__).parent.parent / "scripts" / "check_modules.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_cm = _load_check_modules()

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "PATH": "/usr/bin:/bin",
}

_ANSWERS_FILE = "{{ _copier_conf.answers_file }}.jinja"


def _make_module(root: Path, name: str, copier_yml: str) -> None:
    mod = root / name
    mod.mkdir(parents=True)
    (mod / "copier.yml").write_text(copier_yml)
    (mod / _ANSWERS_FILE).write_text("{{ _copier_answers|to_nice_yaml }}\n")
    (mod / "README.md").write_text(f"# {name}\n")
    (mod / "CHANGELOG.md").write_text("# Changelog\n\n- - -\n")


def _make_cog_toml(root: Path, packages: list[str]) -> None:
    lines = ["[monorepo.packages]"]
    for pkg in packages:
        lines += [f"[monorepo.packages.{pkg}]", f'path = "templates/{pkg}"', ""]
    (root / "cog.toml").write_text("\n".join(lines))


@pytest.fixture
def mono(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, env=_GIT_ENV)
    (tmp_path / "templates").mkdir()
    return tmp_path


def _run(mono: Path, modules: dict[str, str]) -> int:
    for name, yml in modules.items():
        _make_module(mono / "templates", name, yml)
    _make_cog_toml(mono, list(modules))
    with patch.object(_cm, "_REPO_ROOT", mono):
        return _cm.check_modules(mono / "templates")


def _yml(provides: str | None = None, exclusive: str | None = None) -> str:
    lines = []
    if provides is not None:
        lines.append(f"_bailiff_provides: {provides}")
    if exclusive is not None:
        lines.append(f"_bailiff_exclusive: {exclusive}")
    lines.append(
        dedent(
            """\
            module_name:
              type: str
              default: mymod
            """
        )
    )
    return "\n".join(lines)


def test_well_formed_declarations_pass(mono: Path) -> None:
    assert _run(mono, {"m-a": _yml("[python-project]", "true")}) == 0


def test_absent_declarations_pass(mono: Path) -> None:
    assert _run(mono, {"m-a": _yml()}) == 0


def test_non_list_provides_fails(mono: Path, capsys) -> None:
    assert _run(mono, {"m-a": _yml("python-project")}) == 1
    err = capsys.readouterr().err
    assert "m-a" in err
    assert "_bailiff_provides" in err


def test_non_kebab_case_entry_fails(mono: Path, capsys) -> None:
    assert _run(mono, {"m-a": _yml("[Python_Project]")}) == 1
    err = capsys.readouterr().err
    assert "Python_Project" in err


def test_non_bool_exclusive_fails(mono: Path, capsys) -> None:
    assert _run(mono, {"m-a": _yml("[python-project]", '"yes"')}) == 1
    err = capsys.readouterr().err
    assert "_bailiff_exclusive" in err


def test_consistent_all_exclusive_group_passes(mono: Path) -> None:
    assert (
        _run(
            mono,
            {
                "m-a": _yml("[ci]", "true"),
                "m-b": _yml("[ci]", "true"),
            },
        )
        == 0
    )


def test_consistent_all_non_exclusive_group_passes(mono: Path) -> None:
    assert (
        _run(
            mono,
            {
                "m-a": _yml("[quality]"),
                "m-b": _yml("[quality]", "false"),
            },
        )
        == 0
    )


def test_mixed_exclusivity_group_fails(mono: Path, capsys) -> None:
    assert (
        _run(
            mono,
            {
                "m-a": _yml("[ci]", "true"),
                "m-b": _yml("[ci]"),
            },
        )
        == 1
    )
    err = capsys.readouterr().err
    assert "mixed exclusivity" in err
    assert "m-a" in err
    assert "m-b" in err
