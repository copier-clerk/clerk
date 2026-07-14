"""spec 011 T011: clerk-mod-justfile loop tests.

Verifies the justfile module's seed-once lifecycle and threaded axes:
- T011-a: python + pre-commit renders idiomatic recipes using the right tool names.
- T011-b: ts + pnpm + lefthook (non-default combo) renders pnpm and lefthook in recipes.
- T011-c: ts + bun + none renders bun test and a native fallback lint (no hook manager).
- T011-d: rust renders cargo recipes with the --release escape-hatch comment.
- T011-e: language="" renders fail-loud stubs for all recipes.
- T011-f: seed-once — user-edited justfile survives reproduce byte-identical.

No network or tool tasks: the module only renders a static file, so no stub needed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from textwrap import dedent

import pytest

from clerk import runner, trust
from tests.conftest import TemplateRepo, _copy_module_with_stub_tasks

# clerk-mod-justfile has no _tasks so the stub is an empty no-op placeholder.
_JUSTFILE_STUB_TASKS = dedent(
    """\
    _tasks: []
    """
)


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


@pytest.fixture
def clerk_mod_justfile(tmp_path: Path) -> TemplateRepo:
    """The real clerk-mod-justfile template as a hermetic repo (no tasks to stub)."""
    return _copy_module_with_stub_tasks(
        "clerk-mod-justfile", tmp_path / "clerk-mod-justfile", _JUSTFILE_STUB_TASKS
    )


def _init(
    repo: TemplateRepo,
    dest: Path,
    answers: dict,
) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-14")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# T011-a: python + pre-commit
# ---------------------------------------------------------------------------


def test_python_precommit_renders_idiomatic_recipes(
    clerk_mod_justfile: TemplateRepo, tmp_path: Path
) -> None:
    """Python + pre-commit: justfile uses uv and pre-commit."""
    dest = tmp_path / "proj"
    _init(
        clerk_mod_justfile,
        dest,
        {"language": "python", "js_pkg_manager": "bun", "hook_manager": "pre-commit"},
    )

    justfile = (dest / "justfile").read_text()
    assert "uv run pytest" in justfile, "python test recipe must use uv"
    assert "pre-commit run --all-files" in justfile, "lint recipe must use pre-commit"
    assert "uv build" in justfile, "build recipe must use uv build"
    assert "uv pip install -e" in justfile, "dev recipe must use uv"
    # No npm/yarn/pnpm/lefthook in a python+pre-commit justfile.
    assert "npm " not in justfile
    assert "lefthook" not in justfile


# ---------------------------------------------------------------------------
# T011-b: ts + pnpm + lefthook (non-default threaded combo)
# ---------------------------------------------------------------------------


def test_ts_pnpm_lefthook_renders_correct_tools(
    clerk_mod_justfile: TemplateRepo, tmp_path: Path
) -> None:
    """Non-default combo: pnpm + lefthook appear in the rendered recipes."""
    dest = tmp_path / "proj"
    _init(
        clerk_mod_justfile,
        dest,
        {"language": "ts", "js_pkg_manager": "pnpm", "hook_manager": "lefthook"},
    )

    justfile = (dest / "justfile").read_text()
    assert "pnpm test" in justfile, "test recipe must use pnpm"
    assert "pnpm run build" in justfile, "build recipe must use pnpm"
    assert "lefthook run pre-commit" in justfile, "lint recipe must use lefthook"
    # Explicit non-occurrence guards: bun and pre-commit must not appear as commands.
    assert "bun " not in justfile
    assert "pre-commit run" not in justfile


# ---------------------------------------------------------------------------
# T011-c: ts + bun + none (no hook manager → native fallback lint)
# ---------------------------------------------------------------------------


def test_ts_bun_no_hook_manager_uses_native_lint(
    clerk_mod_justfile: TemplateRepo, tmp_path: Path
) -> None:
    """hook_manager=none: lint falls back to package-manager-native command."""
    dest = tmp_path / "proj"
    _init(
        clerk_mod_justfile,
        dest,
        {"language": "ts", "js_pkg_manager": "bun", "hook_manager": "none"},
    )

    justfile = (dest / "justfile").read_text()
    assert "bun test" in justfile, "test recipe must use bun"
    # With hook_manager=none the lint recipe must NOT call pre-commit or lefthook.
    assert "pre-commit" not in justfile
    assert "lefthook" not in justfile
    # Should fall back to a native bun run lint or equivalent.
    assert "bun run lint" in justfile, "no-hook lint must delegate to native bun run lint"


# ---------------------------------------------------------------------------
# T011-d: rust — cargo recipes + --release escape hatch comment
# ---------------------------------------------------------------------------


def test_rust_renders_cargo_recipes_with_release_comment(
    clerk_mod_justfile: TemplateRepo, tmp_path: Path
) -> None:
    """Rust: cargo recipes rendered; --release appears as a commented escape hatch."""
    dest = tmp_path / "proj"
    _init(
        clerk_mod_justfile,
        dest,
        {"language": "rust", "js_pkg_manager": "bun", "hook_manager": "pre-commit"},
    )

    justfile = (dest / "justfile").read_text()
    assert "cargo test" in justfile
    assert "cargo build" in justfile
    assert "cargo run" in justfile
    assert "cargo clean" in justfile
    # --release must be a commented escape hatch, not an unconditional flag.
    assert "--release" in justfile, "escape hatch comment must mention --release"
    # The build recipe body itself must NOT unconditionally pass --release.
    build_section = justfile[justfile.find("build:") :]
    first_recipe_end = build_section.find("\n\n")
    build_body = build_section[:first_recipe_end] if first_recipe_end != -1 else build_section
    # The uncommented build command should be `cargo build` without --release.
    assert "cargo build\n" in build_body or "    cargo build\n" in build_body, (
        "default build must not unconditionally pass --release"
    )


# ---------------------------------------------------------------------------
# T011-e: language="" → fail-loud stubs
# ---------------------------------------------------------------------------


def test_empty_language_renders_fail_loud_stubs(
    clerk_mod_justfile: TemplateRepo, tmp_path: Path
) -> None:
    """language=\"\": every recipe body contains an exit 1 so gaps are obvious."""
    dest = tmp_path / "proj"
    _init(
        clerk_mod_justfile,
        dest,
        {"language": "", "js_pkg_manager": "bun", "hook_manager": "pre-commit"},
    )

    justfile = (dest / "justfile").read_text()
    # Each stub recipe should emit a message and exit non-zero.
    assert "exit 1" in justfile, "fail-loud stubs must exit 1"
    # All named recipes must be present even as stubs.
    for recipe in ("test:", "lint:", "build:", "dev:", "clean:"):
        assert recipe in justfile, f"recipe {recipe!r} must be present as a stub"


# ---------------------------------------------------------------------------
# T011-f: seed-once — user-edited justfile survives reproduce byte-identical
# ---------------------------------------------------------------------------


def test_seed_once_justfile_survives_reproduce(
    clerk_mod_justfile: TemplateRepo, tmp_path: Path
) -> None:
    """SEED-ONCE: a user-edited justfile is NOT overwritten on reproduce."""
    dest = tmp_path / "proj"
    _init(
        clerk_mod_justfile,
        dest,
        {"language": "python", "js_pkg_manager": "bun", "hook_manager": "pre-commit"},
    )

    # Simulate a user edit after init.
    edited_content = "# hand-edited justfile\ndefault:\n    @echo 'custom'\n"
    (dest / "justfile").write_text(edited_content)
    digest_before = _digest(dest / "justfile")

    # Reproduce must NOT overwrite the seed-once file.
    runner.reproduce(str(dest))

    assert _digest(dest / "justfile") == digest_before, (
        "seed-once justfile was clobbered by reproduce (_skip_if_exists failed)"
    )
    assert (dest / "justfile").read_text() == edited_content, (
        "justfile content changed on reproduce"
    )
