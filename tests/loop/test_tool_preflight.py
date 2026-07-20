"""spec 016: whole-plan tool-preflight gate — fail before any write on a missing tool.

A module declares `_bailiff_requires`; the engine which()-checks each declared tool
BEFORE rendering, so a missing tool never leaves a partial tree (copier renders then
runs _tasks — a _task guard is only the backstop). Covers SC-001..006.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from bailiff.errors import BailiffError
from tests.conftest import TemplateRepo, build_template_repo

# A tool that is guaranteed absent from PATH.
_MISSING = "definitely-not-a-real-tool-xyz"
_MISSING2 = "another-absent-tool-abc"


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _record(name: str, repo: TemplateRepo) -> TemplateRecord:
    return TemplateRecord(
        full_id=f"demo/{name}",
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=["project_name"],
    )


def _mod(tmp_path: Path, name: str, requires_block: str, *, question: str = "") -> TemplateRepo:
    """A minimal reproducible module with a _bailiff_requires block."""
    body = "project_name:\n  type: str\n"
    if question:
        body += question
    body += requires_block + "_subdirectory: template\n"
    return build_template_repo(
        tmp_path / name,
        files={
            "copier.yml": body,
            "template/out.txt.jinja": "{{ project_name }}\n",
            "template/{{ _copier_conf.answers_file }}.jinja": (
                "# {{ _copier_conf.answers_file }}\n{{ _copier_answers|to_nice_yaml }}\n"
            ),
        },
    )


def test_missing_tool_fails_before_any_write(tmp_path: Path) -> None:
    """SC-001: a required tool absent → init fails, dest is left empty/absent."""
    repo = _mod(tmp_path, "needy", f"_bailiff_requires:\n  - {_MISSING}\n")
    trust.add_trust(repo.url)
    dest = tmp_path / "out"
    with pytest.raises(BailiffError, match=_MISSING):
        runner.init_many([(_record("needy", repo), {"project_name": "p"})], str(dest))
    assert not dest.exists() or not any(dest.iterdir()), "no partial tree may be written"


def test_multiple_missing_tools_named_in_one_error(tmp_path: Path) -> None:
    """SC-002: two missing tools → a single error names both."""
    a = _mod(tmp_path, "moda", f"_bailiff_requires:\n  - {_MISSING}\n")
    b = _mod(tmp_path, "modb", f"_bailiff_requires:\n  - {_MISSING2}\n")
    trust.add_trust(a.url)
    trust.add_trust(b.url)
    with pytest.raises(BailiffError) as exc:
        runner.init_many(
            [
                (_record("moda", a), {"project_name": "p"}),
                (_record("modb", b), {"project_name": "p"}),
            ],
            str(tmp_path / "out"),
        )
    msg = str(exc.value)
    assert _MISSING in msg and _MISSING2 in msg


def test_conditional_tool_gated_by_when(tmp_path: Path) -> None:
    """SC-003: a `when`-gated tool is checked only when the answer is truthy."""
    repo = _mod(
        tmp_path,
        "cond",
        f"_bailiff_requires:\n  - tool: {_MISSING}\n    when: install_hooks\n",
        question="install_hooks:\n  type: bool\n  default: true\n",
    )
    trust.add_trust(repo.url)
    # opt-out: tool not required → succeeds
    ok_dest = tmp_path / "ok"
    runner.init_many(
        [(_record("cond", repo), {"project_name": "p", "install_hooks": False})], str(ok_dest)
    )
    assert (ok_dest / "out.txt").is_file()
    # opt-in: tool required + absent → fails
    with pytest.raises(BailiffError, match=_MISSING):
        runner.init_many(
            [(_record("cond", repo), {"project_name": "p", "install_hooks": True})],
            str(tmp_path / "bad"),
        )


def test_check_surfaces_missing_tool_without_writing(tmp_path: Path) -> None:
    """SC-005: --check (preflight) runs the gate too, writing nothing."""
    repo = _mod(tmp_path, "needy", f"_bailiff_requires:\n  - {_MISSING}\n")
    trust.add_trust(repo.url)
    dest = tmp_path / "out"
    with pytest.raises(BailiffError, match=_MISSING):
        runner.init_many([(_record("needy", repo), {"project_name": "p"})], str(dest), check=True)
    assert not dest.exists() or not any(dest.iterdir())


def test_present_tool_passes(tmp_path: Path) -> None:
    """A tool that IS on PATH (git — always present in CI) does not block init."""
    repo = _mod(tmp_path, "hasgit", "_bailiff_requires:\n  - git\n")
    trust.add_trust(repo.url)
    dest = tmp_path / "out"
    runner.init_many([(_record("hasgit", repo), {"project_name": "p"})], str(dest))
    assert (dest / "out.txt").is_file()


def test_reproduce_unaffected_by_tool_gate(tmp_path: Path) -> None:
    """SC-006: reproduce of a project whose tools are present is unchanged."""
    repo = _mod(tmp_path, "hasgit", "_bailiff_requires:\n  - git\n")
    trust.add_trust(repo.url)
    dest = tmp_path / "out"
    runner.init_many([(_record("hasgit", repo), {"project_name": "p"})], str(dest))
    results = runner.reproduce_many(str(dest))
    assert len(results) == 1
