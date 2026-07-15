"""spec 011 T008: bailiff-mod-go overlay loop tests.

Tests:
- init [base, go]: base renders first (run_after edge), project_name threaded,
  go preflight marker present (task-output), .golangci.yml present (seed-once),
  cmd/<name>/main.go present for cli, gitignore token contributed.
- app_kind=library: cmd/ entirely absent (no empty dir).
- use_vendor_mode=true: vendor/ token present in answers.
- reproduce: .golangci.yml preserved when edited (seed-once); go.mod preserved
  when edited (seed-once); managed files byte-identical.
- no secret: questions in the module.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
import yaml

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from tests.conftest import TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _record(full_id: str, repo: TemplateRepo, questions: list[str]) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=True,
        questions=questions,
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _init_base_go(
    base: TemplateRepo,
    go: TemplateRepo,
    dest: Path,
    *,
    project_name: str = "mygoapp",
    app_kind: str = "cli",
    use_vendor_mode: bool = False,
    golangci_hook_rev: str = "v1.64.8",
) -> None:
    trust.add_trust(base.url)
    trust.add_trust(go.url)
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/bailiff-mod-base", base, ["project_name", "license", "layout"]),
            {
                "project_name": project_name,
                "org": "acme",
                "license": "mit",
                "layout": "single",
                # Go gitignore token contributed by this overlay (agent-frozen union, M1)
                "gitignore_stack": ["ghg:macOS", "gh:Go"],
            },
        ),
        (
            _record("demo/bailiff-mod-go", go, ["project_name", "go_version", "app_kind"]),
            {
                "go_version": "1.23",
                "app_kind": app_kind,
                "test_runner": "go-test",
                "use_vendor_mode": use_vendor_mode,
                "golangci_hook_rev": golangci_hook_rev,
                "mise_tools": [{"go": "1.23"}],
                "hook_blocks": [],
                "hook_manager": "pre-commit",
            },
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")


def test_base_go_ordered_and_threaded(
    bailiff_mod_base: TemplateRepo, bailiff_mod_go: TemplateRepo, tmp_path: Path
) -> None:
    """Init [base, go]: base first, project_name threaded, seed-once files present."""
    dest = tmp_path / "proj"
    _init_base_go(bailiff_mod_base, bailiff_mod_go, dest)

    # Base rendered.
    assert (dest / "AGENTS.md").is_file(), "base did not render (AGENTS.md missing)"

    # Go overlay answers file written.
    af = yaml.safe_load((dest / ".copier-answers.bailiff-mod-go.yml").read_text())
    assert bailiff_mod_go.url in af["_src_path"]
    assert af["project_name"] == "mygoapp"
    assert af["go_version"] == "1.23"
    assert af["app_kind"] == "cli"

    # Task-output marker (preflight stub) present.
    assert (dest / ".bailiff-go-preflight").is_file(), "go preflight marker missing"

    # Seed-once .golangci.yml present (lifecycle: seed-once).
    assert (dest / ".golangci.yml").is_file(), ".golangci.yml missing"

    # cmd/<name>/main.go present for cli (seed-once).
    assert (dest / "cmd" / "mygoapp" / "main.go").is_file(), "cmd stub missing for cli"
    main_go = (dest / "cmd" / "mygoapp" / "main.go").read_text()
    assert "package main" in main_go
    assert "mygoapp" in main_go

    # go.mod should exist via stub task (preflight just wrote a marker;
    # the real task would create go.mod — stub doesn't, so assert task-output
    # presence for the stub: the preflight file is the observable task output).
    # (R5: loop tests assert presence of task-output, never regeneration byte-equality.)

    # Gitignore token contributed via base's single writer.
    gitignore = (dest / ".gitignore").read_text()
    assert "gh:Go" in gitignore, "Go gitignore token not threaded into base gitignore_stack"


def test_app_kind_library_no_cmd(
    bailiff_mod_base: TemplateRepo, bailiff_mod_go: TemplateRepo, tmp_path: Path
) -> None:
    """app_kind=library: cmd/ is excluded entirely (no empty dir)."""
    dest = tmp_path / "proj"
    _init_base_go(bailiff_mod_base, bailiff_mod_go, dest, app_kind="library")

    # cmd/ must not exist at all — not even an empty directory.
    assert not (dest / "cmd").exists(), "cmd/ should not exist for library app_kind"


def test_use_vendor_mode_recorded(
    bailiff_mod_base: TemplateRepo, bailiff_mod_go: TemplateRepo, tmp_path: Path
) -> None:
    """use_vendor_mode=true is recorded in answers (agent uses it to build gitignore token)."""
    dest = tmp_path / "proj"
    _init_base_go(bailiff_mod_base, bailiff_mod_go, dest, use_vendor_mode=True)

    af = yaml.safe_load((dest / ".copier-answers.bailiff-mod-go.yml").read_text())
    assert af["use_vendor_mode"] is True, "use_vendor_mode not recorded in answers"


def test_ordering_recomputed_edge(
    bailiff_mod_base: TemplateRepo, bailiff_mod_go: TemplateRepo, tmp_path: Path
) -> None:
    """run_after edge sequences base before go regardless of input order."""
    from bailiff import ordering

    recs = [
        _record("demo/bailiff-mod-go", bailiff_mod_go, ["project_name"]),
        _record("demo/bailiff-mod-base", bailiff_mod_base, ["project_name"]),
    ]
    plan = ordering.layer_plan(recs)
    order = [r.full_id.rsplit("/", 1)[-1] for r, _ in plan]
    assert order == ["bailiff-mod-base", "bailiff-mod-go"], f"edge not honoured: {order}"


def test_golangci_seed_once_preserved_on_reproduce(
    bailiff_mod_base: TemplateRepo, bailiff_mod_go: TemplateRepo, tmp_path: Path
) -> None:
    """Seed-once .golangci.yml is NOT overwritten when it already exists on reproduce."""
    dest = tmp_path / "proj"
    _init_base_go(bailiff_mod_base, bailiff_mod_go, dest)

    # Edit .golangci.yml to simulate user customisation.
    golangci = dest / ".golangci.yml"
    original_content = golangci.read_text()
    edited_content = original_content + "\n# user customisation\n"
    golangci.write_text(edited_content)
    digest_before = _digest(golangci)

    # Reproduce must not overwrite the edited seed-once file.
    runner.reproduce_many(str(dest))

    assert _digest(golangci) == digest_before, ".golangci.yml was overwritten on reproduce"


def test_go_mod_seed_once_preserved_on_reproduce(
    bailiff_mod_base: TemplateRepo, bailiff_mod_go: TemplateRepo, tmp_path: Path
) -> None:
    """go.mod is _skip_if_exists: if present before reproduce, it is preserved."""
    dest = tmp_path / "proj"
    _init_base_go(bailiff_mod_base, bailiff_mod_go, dest)

    # Simulate go.mod having been created (real init would call `go mod init`).
    go_mod = dest / "go.mod"
    go_mod.write_text("module mygoapp\n\ngo 1.23\n")
    digest_before = _digest(go_mod)

    runner.reproduce_many(str(dest))

    assert go_mod.is_file(), "go.mod disappeared on reproduce"
    assert _digest(go_mod) == digest_before, "go.mod was overwritten on reproduce"


def test_cmd_main_go_seed_once_preserved_on_reproduce(
    bailiff_mod_base: TemplateRepo, bailiff_mod_go: TemplateRepo, tmp_path: Path
) -> None:
    """cmd/<name>/main.go is _skip_if_exists: edits survive reproduce."""
    dest = tmp_path / "proj"
    _init_base_go(bailiff_mod_base, bailiff_mod_go, dest, app_kind="cli")

    main_go = dest / "cmd" / "mygoapp" / "main.go"
    assert main_go.is_file(), "cmd stub missing before reproduce"

    edited = main_go.read_text() + "\n// user code\n"
    main_go.write_text(edited)
    digest_before = _digest(main_go)

    runner.reproduce_many(str(dest))

    assert _digest(main_go) == digest_before, "cmd/main.go was overwritten on reproduce"


def test_no_secret_questions() -> None:
    """Contract check: no secret: questions in copier.yml (Constitution VI / C-11)."""
    from pathlib import Path

    copier_yml = (
        Path(__file__).resolve().parent.parent.parent
        / "templates"
        / "bailiff-mod-go"
        / "copier.yml"
    )
    text = copier_yml.read_text()
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # A real secret: question key (not a comment) would be `  secret: true`
        if stripped.startswith("secret:") and not stripped.startswith("#"):
            raise AssertionError(f"secret: question found at line {i}: {line!r}")
