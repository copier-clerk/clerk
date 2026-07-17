"""spec 011 T011 / spec 014: bailiff-mod-justfile loop tests.

Verifies the justfile module's seed-once lifecycle, threaded axes, and
spec-014 edge/phase model:
- T011-a: python + pre-commit renders idiomatic recipes using the right tool names.
- T011-b: ts + pnpm + lefthook (non-default combo) renders pnpm and lefthook in recipes.
- T011-c: ts + bun + none renders bun test and a native fallback lint (no hook manager).
- T011-d: rust renders cargo recipes with the --release escape-hatch comment.
- T011-e: language="" renders fail-loud stubs for all recipes.
- T011-f: seed-once — user-edited justfile survives reproduce byte-identical.
- T011-g: all 15 lang×hook_manager combos produce syntactically valid justfiles.
- T014-a: depends_on=[bailiff-mod-base]; no run_after/run_before (R7).
- T014-b: _bailiff_phase=normal; no hard dep on precommit/ts (R13).
- T014-c: .mise/conf.d/bailiff-mod-justfile.toml.jinja installs just.

No network or tool tasks: the module only renders a static file, so no stub needed.
"""

from __future__ import annotations

import hashlib
import itertools
import shutil
import subprocess
import tempfile
from pathlib import Path
from textwrap import dedent

import pytest
import yaml
from jinja2.sandbox import SandboxedEnvironment

from bailiff import runner, trust
from tests.conftest import TemplateRepo, _copy_module_with_stub_tasks

_MODULES_DIR = Path(__file__).parent.parent.parent / "templates"

# bailiff-mod-justfile has no _tasks so the stub is an empty no-op placeholder.
_JUSTFILE_STUB_TASKS = dedent(
    """\
    _tasks: []
    """
)

# Path to the Jinja template for direct rendering in the matrix test (avoids
# spawning copier for each of the 15 combos).
_TEMPLATE_PATH = (
    Path(__file__).parent.parent.parent / "templates/bailiff-mod-justfile/template/justfile.jinja"
)

_JUST_BIN: str | None = shutil.which("just")


def _assert_justfile_valid(path: Path) -> None:
    """Assert the file is syntactically valid for just.

    Two checks:
    1. Structural: no blank line immediately after a recipe header (name:) —
       just terminates a recipe on a blank line, so any blank between a
       header and its first indented line is a parse error.
    2. Semantic: ``just --list --justfile <path>`` returns exit 0 when the
       ``just`` binary is present (skipped silently when not installed).
    """
    content = path.read_text()
    lines = content.split("\n")
    for i, line in enumerate(lines):
        # A recipe header: non-empty, not a comment, not indented, ends with ":"
        is_recipe_header = (
            line.endswith(":")
            and line.strip()
            and not line.startswith("#")
            and not line.startswith(" ")
            and not line.startswith("\t")
        )
        if is_recipe_header and i + 1 < len(lines) and lines[i + 1].strip() == "":
            pytest.fail(
                f"Blank line immediately after recipe header {line!r} "
                f"at line {i + 1} — just would reject this as a syntax error."
            )

    if _JUST_BIN is not None:
        proc = subprocess.run(
            [_JUST_BIN, "--list", "--justfile", str(path)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"just --list failed for {path}:\n{proc.stderr.strip()}"


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


@pytest.fixture
def bailiff_mod_justfile(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-justfile template as a hermetic repo (no tasks to stub)."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-justfile", tmp_path / "bailiff-mod-justfile", _JUSTFILE_STUB_TASKS
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
    bailiff_mod_justfile: TemplateRepo, tmp_path: Path
) -> None:
    """Python + pre-commit: justfile uses uv and pre-commit."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_justfile,
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
    _assert_justfile_valid(dest / "justfile")


# ---------------------------------------------------------------------------
# T011-b: ts + pnpm + lefthook (non-default threaded combo)
# ---------------------------------------------------------------------------


def test_ts_pnpm_lefthook_renders_correct_tools(
    bailiff_mod_justfile: TemplateRepo, tmp_path: Path
) -> None:
    """Non-default combo: pnpm + lefthook appear in the rendered recipes."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_justfile,
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
    _assert_justfile_valid(dest / "justfile")


# ---------------------------------------------------------------------------
# T011-c: ts + bun + none (no hook manager → native fallback lint)
# ---------------------------------------------------------------------------


def test_ts_bun_no_hook_manager_uses_native_lint(
    bailiff_mod_justfile: TemplateRepo, tmp_path: Path
) -> None:
    """hook_manager=none: lint falls back to package-manager-native command."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_justfile,
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
    _assert_justfile_valid(dest / "justfile")


# ---------------------------------------------------------------------------
# T011-d: rust — cargo recipes + --release escape hatch comment
# ---------------------------------------------------------------------------


def test_rust_renders_cargo_recipes_with_release_comment(
    bailiff_mod_justfile: TemplateRepo, tmp_path: Path
) -> None:
    """Rust: cargo recipes rendered; --release appears as a commented escape hatch."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_justfile,
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
    _assert_justfile_valid(dest / "justfile")


# ---------------------------------------------------------------------------
# T011-e: language="" → fail-loud stubs
# ---------------------------------------------------------------------------


def test_empty_language_renders_fail_loud_stubs(
    bailiff_mod_justfile: TemplateRepo, tmp_path: Path
) -> None:
    """language=\"\": every recipe body contains an exit 1 so gaps are obvious."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_justfile,
        dest,
        {"language": "", "js_pkg_manager": "bun", "hook_manager": "pre-commit"},
    )

    justfile = (dest / "justfile").read_text()
    # Each stub recipe should emit a message and exit non-zero.
    assert "exit 1" in justfile, "fail-loud stubs must exit 1"
    # All named recipes must be present even as stubs.
    for recipe in ("test:", "lint:", "build:", "dev:", "clean:"):
        assert recipe in justfile, f"recipe {recipe!r} must be present as a stub"
    _assert_justfile_valid(dest / "justfile")


# ---------------------------------------------------------------------------
# T011-f: seed-once — user-edited justfile survives reproduce byte-identical
# ---------------------------------------------------------------------------


def test_seed_once_justfile_survives_reproduce(
    bailiff_mod_justfile: TemplateRepo, tmp_path: Path
) -> None:
    """SEED-ONCE: a user-edited justfile is NOT overwritten on reproduce."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_justfile,
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


# ---------------------------------------------------------------------------
# T011-g: all 15 lang × hook_manager combos are syntactically valid
# ---------------------------------------------------------------------------

_LANGS = ["python", "ts", "go", "rust", ""]
_HOOK_MANAGERS = ["pre-commit", "lefthook", "none"]
_ALL_COMBOS = list(itertools.product(_LANGS, _HOOK_MANAGERS))


@pytest.mark.parametrize(
    "language,hook_manager",
    _ALL_COMBOS,
    ids=[f"{lang or 'empty'}+{hm}" for lang, hm in _ALL_COMBOS],
)
def test_all_combos_produce_valid_justfile(language: str, hook_manager: str) -> None:
    """Every lang×hook_manager combo renders a justfile that just accepts.

    Uses direct Jinja2 rendering (same engine copier uses) to avoid the
    overhead of 15 copier subprocess invocations for a pure-syntax check.
    """
    env = SandboxedEnvironment(keep_trailing_newline=True)
    template = env.from_string(_TEMPLATE_PATH.read_text())
    rendered = template.render(
        language=language,
        hook_manager=hook_manager,
        js_pkg_manager="bun",  # representative; only matters for ts combos
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".just", delete=False) as fh:
        fh.write(rendered)
        tmp_path = Path(fh.name)
    try:
        _assert_justfile_valid(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# T014-a: depends_on=[bailiff-mod-base]; no run_after/run_before (spec 014 R7)
# ---------------------------------------------------------------------------


def test_depends_on_base_no_run_after_or_run_before() -> None:
    """depends_on=[bailiff-mod-base]; run_after and run_before are absent (spec 014 R7)."""
    copier_yml = (_MODULES_DIR / "bailiff-mod-justfile" / "copier.yml").read_text()
    data = yaml.safe_load(copier_yml)
    assert "run_after" not in data, "run_after must be absent (spec 014 R7)"
    assert "run_before" not in data, "run_before must be absent (spec 014 R7)"
    assert data.get("depends_on", {}).get("default") == ["bailiff-mod-base"], (
        "depends_on must be [bailiff-mod-base]"
    )


# ---------------------------------------------------------------------------
# T014-b: _bailiff_phase=normal; no hard dep on precommit/ts (R13)
# ---------------------------------------------------------------------------


def test_phase_normal_and_no_hard_ts_precommit_dep() -> None:
    """_bailiff_phase=normal; hook_manager/js_pkg_manager are agent-fed (R13 — no hard deps)."""
    copier_yml_path = _MODULES_DIR / "bailiff-mod-justfile" / "copier.yml"
    raw = copier_yml_path.read_text()
    data = yaml.safe_load(raw)

    # Phase must be expressed as a top-level YAML key _bailiff_phase.
    assert "_bailiff_phase" in raw, "_bailiff_phase top-level key must be present"
    assert data.get("_bailiff_phase") == "normal", "_bailiff_phase must be 'normal'"

    # Neither bailiff-mod-precommit nor bailiff-mod-ts may appear in depends_on.
    deps = data.get("depends_on", {}).get("default", [])
    assert "bailiff-mod-precommit" not in deps, (
        "bailiff-mod-precommit must not be in depends_on: hook_manager is agent-fed (R13)"
    )
    assert "bailiff-mod-ts" not in deps, (
        "bailiff-mod-ts must not be in depends_on: js_pkg_manager is agent-fed (R13)"
    )


# ---------------------------------------------------------------------------
# T014-c: .mise/conf.d/bailiff-mod-justfile.toml.jinja installs just
# ---------------------------------------------------------------------------


def test_mise_confd_fragment_installs_just() -> None:
    """bailiff-mod-justfile renders .mise/conf.d/bailiff-mod-justfile.toml with just."""
    confd = (
        _MODULES_DIR
        / "bailiff-mod-justfile"
        / "template"
        / ".mise"
        / "conf.d"
        / "bailiff-mod-justfile.toml.jinja"
    )
    assert confd.is_file(), ".mise/conf.d/bailiff-mod-justfile.toml.jinja must exist"
    content = confd.read_text()
    assert "[tools]" in content, "conf.d fragment must have a [tools] section"
    assert "just" in content, "conf.d fragment must declare just as a tool"
