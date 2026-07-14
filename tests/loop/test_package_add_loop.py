"""T019: clerk-mod-package-add loop tests.

Verifies:
  - SEC-001 path-traversal guard: bad name/dir inputs exit 1 with ZERO side effects
    (no dir created, no marker, no workspace registration).
  - Monorepo gate: layout='single' is a no-op (no error, no dir created).
  - Happy-path: layout='monorepo' scaffolds the package dir + writes the marker.
  - seed-once: manifest not overwritten on reproduce when it already exists.

All native tool calls (bun/pnpm/uv/cargo/go) are stubbed offline via the
clerk_mod_package_add fixture (tests/conftest.py _PACKAGE_ADD_STUB_TASKS).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clerk import runner, trust
from clerk.errors import ClerkError
from tests.conftest import TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-13")


# ---------------------------------------------------------------------------
# SEC-001: path-traversal guard — ZERO side effects on bad inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_name",
    [
        "",  # empty name
        "/absolute",  # leading /
        "a/b",  # embedded /
        "../evil",  # dot-dot slash
        "..",  # bare dot-dot
        ".",  # single dot (current dir)
        "a\\b",  # backslash — SEC-001 4th condition
    ],
)
def test_guard_rejects_bad_name(
    clerk_mod_package_add: TemplateRepo, tmp_path: Path, bad_name: str
) -> None:
    """SEC-001: bad name is rejected — no directory created, no marker written."""
    dest = tmp_path / "proj"
    dest.mkdir()

    with pytest.raises((ClerkError, SystemExit, Exception)):
        _init(
            clerk_mod_package_add,
            dest,
            {"name": bad_name, "lang": "python", "layout": "monorepo", "dir": "packages/"},
        )

    # ZERO side effects: no package dir under packages/
    pkg_root = dest / "packages"
    assert not pkg_root.exists() or not any(pkg_root.iterdir()), (
        f"guard failed: packages/ has contents for bad name {bad_name!r}"
    )
    # ZERO side effects: no marker written
    assert not (dest / ".clerk-package-add-preflight").exists(), (
        f"guard failed: preflight marker written for bad name {bad_name!r}"
    )


@pytest.mark.parametrize(
    "bad_dir",
    [
        "../escape",     # traversal in dir
        "a/../b",        # embedded traversal
        "../../etc",     # deep traversal
        "..",            # bare dot-dot (bypassed old regex)
        ".",             # bare dot (bypassed old regex)
        "a\\b",          # backslash — SEC-001 4th condition
        "packages/..",   # trailing dot-dot after legitimate prefix
        "../",           # trailing-slash traversal variant
    ],
)
def test_guard_rejects_bad_dir(
    clerk_mod_package_add: TemplateRepo, tmp_path: Path, bad_dir: str
) -> None:
    """SEC-001: bad dir is rejected — no directory created, no marker written."""
    dest = tmp_path / "proj"
    dest.mkdir()

    with pytest.raises((ClerkError, SystemExit, Exception)):
        _init(
            clerk_mod_package_add,
            dest,
            {"name": "mypkg", "lang": "python", "layout": "monorepo", "dir": bad_dir},
        )

    # ZERO side effects: no dir created anywhere under dest, no marker written.
    # Use rglob to catch any directory the guard might have let mkdir create.
    created_dirs = [p for p in dest.rglob("*") if p.is_dir()]
    assert created_dirs == [], (
        f"guard failed: dirs created for bad dir {bad_dir!r}: {created_dirs}"
    )
    assert not (dest / ".clerk-package-add-preflight").exists(), (
        f"guard failed: preflight marker written for bad dir {bad_dir!r}"
    )


# ---------------------------------------------------------------------------
# Monorepo gate: single layout is a clean no-op (no error, no dir)
# ---------------------------------------------------------------------------


def test_single_layout_is_noop(clerk_mod_package_add: TemplateRepo, tmp_path: Path) -> None:
    """layout='single' — tasks exit 0, no package dir is created, no marker written."""
    dest = tmp_path / "proj"
    dest.mkdir()

    # Must NOT raise — the gate exits 0, not 1.
    _init(
        clerk_mod_package_add,
        dest,
        {"name": "mypkg", "lang": "python", "layout": "single", "dir": "packages/"},
    )

    # Gate skipped all work — no package dir, no marker.
    assert not (dest / "packages" / "mypkg").exists(), (
        "monorepo gate failed: package dir created for single layout"
    )
    assert not (dest / ".clerk-package-add-preflight").exists(), (
        "monorepo gate failed: preflight marker written for single layout"
    )


# ---------------------------------------------------------------------------
# Happy path: valid inputs scaffold the package dir + marker
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["ts", "python", "go", "rust"])
def test_happy_path_scaffolds_package_dir(
    clerk_mod_package_add: TemplateRepo, tmp_path: Path, lang: str
) -> None:
    """Valid monorepo inputs: package dir is created and marker is written."""
    dest = tmp_path / "proj"
    dest.mkdir()

    answers: dict = {
        "name": "mypkg",
        "lang": lang,
        "layout": "monorepo",
        "dir": "packages/",
    }
    if lang == "ts":
        answers["js_pkg_manager"] = "bun"

    _init(clerk_mod_package_add, dest, answers)

    # Package directory created.
    pkg_dir = dest / "packages" / "mypkg"
    assert pkg_dir.is_dir(), f"package dir not created for lang={lang}"

    # Preflight marker written by stub (confirms tasks ran past the guard).
    marker = dest / ".clerk-package-add-preflight"
    assert marker.is_file(), f"preflight marker not written for lang={lang}"
    assert f"lang={lang}" in marker.read_text(), f"marker content missing lang={lang}"
    assert "name=mypkg" in marker.read_text(), "marker missing name=mypkg"


# ---------------------------------------------------------------------------
# Answers file: recorded questions are present, hidden edges absent
# ---------------------------------------------------------------------------


def test_answers_file_recorded(clerk_mod_package_add: TemplateRepo, tmp_path: Path) -> None:
    """Visible answers are persisted; hidden edges (run_after, depends_on) are not."""
    import yaml

    dest = tmp_path / "proj"
    dest.mkdir()

    _init(
        clerk_mod_package_add,
        dest,
        {
            "name": "mypkg",
            "lang": "python",
            "layout": "monorepo",
            "dir": "packages/",
            "python_pkg_manager": "uv",
            "resolve_stack": False,
        },
    )

    # Single-template init writes .copier-answers.yml (not the multi-template
    # per-module name); the template dir basename determines the answers-file
    # path only in init_many runs.
    af_path = dest / ".copier-answers.yml"
    assert af_path.is_file(), "answers file not written"
    af = yaml.safe_load(af_path.read_text())

    assert af["name"] == "mypkg"
    assert af["lang"] == "python"
    # layout is hidden (when: false) — copier does not persist hidden answers.
    assert "layout" not in af, "hidden layout must not be persisted"
    # Hidden edges must NOT appear in answers (FR-004 / FR-013).
    assert "run_after" not in af, "run_after must not be persisted"
    assert "depends_on" not in af, "depends_on must not be persisted"


# ---------------------------------------------------------------------------
# Seed-once: manifest not overwritten on reproduce when it already exists
# ---------------------------------------------------------------------------


def test_seed_once_manifest_not_overwritten_on_reproduce(
    clerk_mod_package_add: TemplateRepo, tmp_path: Path
) -> None:
    """_skip_if_exists manifest files are preserved on reproduce (cross-cutting §8).

    After init, the seed manifest (pyproject.toml) is hand-edited. A reproduce
    run must NOT clobber the edited file because _skip_if_exists is in effect.
    """
    dest = tmp_path / "proj"
    dest.mkdir()

    _init(
        clerk_mod_package_add,
        dest,
        {"name": "mypkg", "lang": "python", "layout": "monorepo", "dir": "packages/"},
    )

    # Create a seed manifest with hand-edited content (simulating project ownership).
    pkg_dir = dest / "packages" / "mypkg"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    hand_edited = '[project]\nname = "mypkg"\ndependencies = ["fastapi"]  # hand-edited\n'
    manifest = pkg_dir / "pyproject.toml"
    manifest.write_text(hand_edited)

    # Reproduce must not overwrite the seed-once file.
    runner.reproduce(str(dest))

    assert manifest.read_text() == hand_edited, (
        "seed-once pyproject.toml was clobbered on reproduce (_skip_if_exists violated)"
    )
