"""spec 014 T018 / SC-003: mise conf.d drop-in model.

Each tool-contributing module renders its own .mise/conf.d/<vendor>-<module>.toml;
NO module writes .mise.toml; the collision check passes (distinct paths).

Tests:
- N modules → N distinct .mise/conf.d/*.toml, NO .mise.toml
- Collision check: two modules with disjoint conf.d paths → no BasenameCollisionError
- Single-module reproduce is byte-identical (managed lifecycle)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from tests.conftest import build_template_repo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _record(
    full_id: str,
    repo,
) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=["project_name"],
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_tool_module(
    root: Path,
    name: str,
    tools: dict[str, str],
    *,
    depends_on: str | None = None,
    phase: str = "normal",
) -> object:
    """Build a synthetic tool module that contributes a .mise/conf.d/<name>.toml."""
    tools_lines = "\n".join(f'{tool} = "{version}"' for tool, version in tools.items())
    conf_d_content = f"# managed by {name}\n[tools]\n{tools_lines}\n"

    parts = ["project_name:\n  type: str\n"]
    if depends_on:
        parts.append(f'depends_on:\n  type: yaml\n  default: ["{depends_on}"]\n  when: false\n')
    parts.append(f"_subdirectory: template\n_bailiff_phase: {phase}\n")
    copier_yml = "\n".join(parts)

    return build_template_repo(
        root / name,
        files={
            "copier.yml": copier_yml,
            f"template/.mise/conf.d/{name}.toml.jinja": conf_d_content,
        },
    )


# ---------------------------------------------------------------------------
# SC-003 AS1: N tool modules → N distinct .mise/conf.d/*.toml, NO .mise.toml
# ---------------------------------------------------------------------------


def test_n_modules_produce_n_confd_files(tmp_path: Path) -> None:
    """Three tool modules each render their own .mise/conf.d/<name>.toml; no .mise.toml written."""
    dest = tmp_path / "proj"
    base = _make_tool_module(tmp_path / "repos", "bailiff-mod-base", {}, phase="pre")
    python = _make_tool_module(
        tmp_path / "repos",
        "bailiff-mod-python",
        {"python": "3.13"},
        depends_on="bailiff-mod-base",
    )
    ts = _make_tool_module(
        tmp_path / "repos",
        "bailiff-mod-ts",
        {"node": "22"},
        depends_on="bailiff-mod-base",
    )

    for repo in (base, python, ts):
        trust.add_trust(repo.url)

    selection = [
        (_record("myorg/bailiff-mod-base", base), {"project_name": "myproj"}),
        (_record("myorg/bailiff-mod-python", python), {"project_name": "myproj"}),
        (_record("myorg/bailiff-mod-ts", ts), {"project_name": "myproj"}),
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")

    # Each module's conf.d file must be present.
    assert (dest / ".mise" / "conf.d" / "bailiff-mod-base.toml").is_file(), (
        "bailiff-mod-base conf.d file missing"
    )
    assert (dest / ".mise" / "conf.d" / "bailiff-mod-python.toml").is_file(), (
        "bailiff-mod-python conf.d file missing"
    )
    assert (dest / ".mise" / "conf.d" / "bailiff-mod-ts.toml").is_file(), (
        "bailiff-mod-ts conf.d file missing"
    )

    # NO root .mise.toml.
    assert not (dest / ".mise.toml").exists(), ".mise.toml must NOT exist (spec 014)"


def test_confd_files_have_correct_tool_sections(tmp_path: Path) -> None:
    """Each conf.d file contains only its own module's tools."""
    dest = tmp_path / "proj"
    python = _make_tool_module(
        tmp_path / "repos",
        "bailiff-mod-python",
        {"python": "3.13"},
        phase="pre",
    )
    ts = _make_tool_module(
        tmp_path / "repos",
        "bailiff-mod-ts",
        {"node": "22"},
        phase="normal",
    )

    for repo in (python, ts):
        trust.add_trust(repo.url)

    selection = [
        (_record("myorg/bailiff-mod-python", python), {"project_name": "myproj"}),
        (_record("myorg/bailiff-mod-ts", ts), {"project_name": "myproj"}),
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")

    py_toml = (dest / ".mise" / "conf.d" / "bailiff-mod-python.toml").read_text()
    assert "python" in py_toml and "3.13" in py_toml, "python tool missing from its conf.d"
    assert "node" not in py_toml, "node must not appear in python's conf.d"

    ts_toml = (dest / ".mise" / "conf.d" / "bailiff-mod-ts.toml").read_text()
    assert "node" in ts_toml and "22" in ts_toml, "node tool missing from ts conf.d"
    assert "python" not in ts_toml, "python must not appear in ts's conf.d"


# ---------------------------------------------------------------------------
# Collision check: two modules with distinct conf.d paths pass the 013 check
# ---------------------------------------------------------------------------


def test_confd_paths_disjoint_no_collision(tmp_path: Path) -> None:
    """Two tool modules with disjoint conf.d paths trigger no basename collision."""
    dest = tmp_path / "proj"
    mod_a = _make_tool_module(tmp_path / "repos", "bailiff-mod-alpha", {"node": "22"}, phase="pre")
    mod_b = _make_tool_module(
        tmp_path / "repos",
        "bailiff-mod-beta",
        {"python": "3.13"},
        phase="normal",
        depends_on="bailiff-mod-alpha",
    )

    for repo in (mod_a, mod_b):
        trust.add_trust(repo.url)

    selection = [
        (_record("myorg/bailiff-mod-alpha", mod_a), {"project_name": "myproj"}),
        (_record("myorg/bailiff-mod-beta", mod_b), {"project_name": "myproj"}),
    ]
    # Must not raise BasenameCollisionError or any ordering error.
    runner.init_many(selection, str(dest), today="2026-07-14")

    assert (dest / ".mise" / "conf.d" / "bailiff-mod-alpha.toml").is_file()
    assert (dest / ".mise" / "conf.d" / "bailiff-mod-beta.toml").is_file()


# ---------------------------------------------------------------------------
# Single-module reproduce is byte-identical (managed lifecycle)
# ---------------------------------------------------------------------------


def test_single_module_confd_reproduce_byte_identical(tmp_path: Path) -> None:
    """Single-module .mise/conf.d/<name>.toml reproduce is byte-identical (MANAGED)."""
    dest = tmp_path / "proj"
    mod = _make_tool_module(
        tmp_path / "repos", "bailiff-mod-python", {"python": "3.13"}, phase="pre"
    )
    trust.add_trust(mod.url)

    selection = [
        (_record("myorg/bailiff-mod-python", mod), {"project_name": "myproj"}),
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")

    confd = dest / ".mise" / "conf.d" / "bailiff-mod-python.toml"
    digest_init = _digest(confd)

    runner.reproduce_many(str(dest))

    assert _digest(confd) == digest_init, (
        ".mise/conf.d/bailiff-mod-python.toml changed on reproduce (MANAGED must be byte-identical)"
    )
