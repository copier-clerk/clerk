"""spec 011 bailiff-mod-readme loop tests (T012).

Covers:
- static-skeleton style: deterministic render from frozen facts (SEED-ONCE).
- agent-draft style: README.md rendered from frozen readme_body verbatim (SEED-ONCE).
- _skip_if_exists: existing README.md is NOT clobbered on reproduce regardless of style.
- No agent invocation in reproduce path (only frozen answers replayed).

Uses runner.init (single RunSpec) to exercise bailiff-mod-readme standalone —
the run_after: [bailiff-mod-base] edge is a runtime ordering hint, not a hard
dependency that blocks standalone usage (FR-010 self-containment).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bailiff import runner, trust
from tests.conftest import TemplateRepo, _copy_module_with_stub_tasks

# bailiff-mod-readme is a pure render module with no network/tool tasks.
# The stub is a no-op marker so the fixture pattern stays consistent with the suite.
_README_STUB_TASKS = """\
_tasks:
  - "printf 'readme-preflight-ok\\n' > .bailiff-readme-preflight"
"""


@pytest.fixture
def bailiff_mod_readme(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-readme template as a hermetic repo (stub tasks)."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-readme", tmp_path / "bailiff-mod-readme", _README_STUB_TASKS
    )


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


# ---------------------------------------------------------------------------
# static-skeleton style
# ---------------------------------------------------------------------------


def test_static_skeleton_renders_readme(bailiff_mod_readme: TemplateRepo, tmp_path: Path) -> None:
    """static-skeleton: README.md is created with project_name and description."""
    trust.add_trust(bailiff_mod_readme.url)

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_readme.url,
        dest=str(dest),
        answers={
            "project_name": "myapp",
            "description": "A demo application.",
            "stack": "Python/uv",
            "readme_style": "static-skeleton",
        },
    )
    runner.init(spec, today="2026-01-01")

    readme = dest / "README.md"
    assert readme.is_file(), "README.md not created by static-skeleton"
    content = readme.read_text()
    assert "myapp" in content, "project_name not in static-skeleton README"
    assert "A demo application." in content, "description not in static-skeleton README"


def test_static_skeleton_seed_once_on_reproduce(
    bailiff_mod_readme: TemplateRepo, tmp_path: Path
) -> None:
    """static-skeleton: README.md is NOT clobbered on reproduce (_skip_if_exists)."""
    trust.add_trust(bailiff_mod_readme.url)

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_readme.url,
        dest=str(dest),
        answers={
            "project_name": "myapp",
            "description": "Original description.",
            "stack": "",
            "readme_style": "static-skeleton",
        },
    )
    runner.init(spec, today="2026-01-01")

    # Simulate user editing their README after init.
    user_edit = "# myapp\n\nHAND-EDITED — do not clobber.\n"
    (dest / "README.md").write_text(user_edit)

    # Reproduce: _skip_if_exists must preserve the user edit.
    # Single-template init writes the default .copier-answers.yml.
    runner.reproduce(str(dest))

    assert (dest / "README.md").read_text() == user_edit, (
        "README.md was clobbered on reproduce (seed-once violated)"
    )


# ---------------------------------------------------------------------------
# agent-draft style
# ---------------------------------------------------------------------------


def test_agent_draft_renders_body_verbatim(
    bailiff_mod_readme: TemplateRepo, tmp_path: Path
) -> None:
    """agent-draft: README.md is rendered from frozen readme_body verbatim."""
    trust.add_trust(bailiff_mod_readme.url)

    readme_body = "# myapp\n\nThis is the agent-generated README.\n\n## Features\n\n- Fast\n"
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_readme.url,
        dest=str(dest),
        answers={
            "project_name": "myapp",
            "description": "",
            "stack": "",
            "readme_style": "agent-draft",
            "confirm_readme_draft": True,
            "readme_body": readme_body,
        },
    )
    runner.init(spec, today="2026-01-01")

    readme = dest / "README.md"
    assert readme.is_file(), "README.md not created in agent-draft mode"
    content = readme.read_text()
    # The frozen body should appear verbatim in the rendered output.
    assert "agent-generated README" in content, "readme_body not rendered verbatim"
    assert "## Features" in content, "readme_body structure not preserved"


def test_agent_draft_seed_once_on_reproduce(
    bailiff_mod_readme: TemplateRepo, tmp_path: Path
) -> None:
    """agent-draft: README.md is NOT clobbered on reproduce (_skip_if_exists).

    Reproduce replays the frozen answers (including readme_body) but _skip_if_exists
    means the existing file is never touched — no agent invocation in the reproduce path.
    """
    trust.add_trust(bailiff_mod_readme.url)

    readme_body = "# myapp\n\nAgent draft body.\n"
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_readme.url,
        dest=str(dest),
        answers={
            "project_name": "myapp",
            "description": "",
            "stack": "",
            "readme_style": "agent-draft",
            "confirm_readme_draft": True,
            "readme_body": readme_body,
        },
    )
    runner.init(spec, today="2026-01-01")

    # Simulate user editing the README after the agent draft was accepted.
    user_edit = "# myapp\n\nUser edited this after accepting the draft.\n"
    (dest / "README.md").write_text(user_edit)

    # Reproduce: frozen readme_body is replayed but _skip_if_exists wins.
    # Single-template init writes the default .copier-answers.yml.
    runner.reproduce(str(dest))

    assert (dest / "README.md").read_text() == user_edit, (
        "README.md was clobbered on reproduce (agent-draft seed-once violated)"
    )


# ---------------------------------------------------------------------------
# Answers file recorded
# ---------------------------------------------------------------------------


def test_answers_file_recorded(bailiff_mod_readme: TemplateRepo, tmp_path: Path) -> None:
    """Answers file is written and includes the frozen answers."""
    import yaml

    trust.add_trust(bailiff_mod_readme.url)

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_readme.url,
        dest=str(dest),
        answers={
            "project_name": "myproj",
            "description": "desc",
            "stack": "Python/uv",
            "readme_style": "static-skeleton",
        },
    )
    runner.init(spec, today="2026-01-01")

    # Single-template init writes .copier-answers.yml (default copier name).
    af = dest / ".copier-answers.yml"
    assert af.is_file(), "answers file not written"
    data = yaml.safe_load(af.read_text())
    assert data["project_name"] == "myproj"
    assert data["readme_style"] == "static-skeleton"
    assert bailiff_mod_readme.url in data["_src_path"]
