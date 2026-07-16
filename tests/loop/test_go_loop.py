"""spec 014 T022/T035/T039/T045/T049: bailiff-mod-go overlay loop tests.

Tests:
- init [base, precommit, go]: base first, project_name read from
  _external_data.base, hook_manager read from _external_data.precommit,
  go conf.d fragment present, .golangci.yml present (seed-once),
  cmd/<name>/main.go present for cli, gitignore fragment contributed.
- app_kind=library: cmd/ entirely absent (no empty dir).
- use_vendor_mode=true: vendor/ token present in gitignore fragment.
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


def _init_base_precommit_go(
    base: TemplateRepo,
    precommit: TemplateRepo,
    go: TemplateRepo,
    dest: Path,
    *,
    project_name: str = "mygoapp",
    app_kind: str = "cli",
    use_vendor_mode: bool = False,
    golangci_hook_rev: str = "v1.64.8",
    hook_manager: str = "pre-commit",
) -> None:
    """Init [base, precommit, go].

    precommit is required because go reads hook_manager via _external_data.
    """
    trust.add_trust(base.url)
    trust.add_trust(precommit.url)
    trust.add_trust(go.url)
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/bailiff-mod-base", base, ["project_name", "license", "layout"]),
            {
                "project_name": project_name,
                "org": "acme",
                "license": "mit",
                "layout": "single",
            },
        ),
        (
            _record(
                "demo/bailiff-mod-precommit",
                precommit,
                ["hook_manager"],
            ),
            {"hook_manager": hook_manager},
        ),
        (
            _record("demo/bailiff-mod-go", go, ["project_name", "go_version", "app_kind"]),
            {
                "go_version": "1.23",
                "app_kind": app_kind,
                "test_runner": "go-test",
                "use_vendor_mode": use_vendor_mode,
                "golangci_hook_rev": golangci_hook_rev,
            },
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")


def test_base_go_ordered_and_threaded(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_go: TemplateRepo,
    tmp_path: Path,
) -> None:
    """Init [base, precommit, go]: base first, project_name from _external_data, fragments present."""  # noqa: E501
    dest = tmp_path / "proj"
    _init_base_precommit_go(bailiff_mod_base, bailiff_mod_precommit, bailiff_mod_go, dest)

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

    # T022: mise conf.d fragment rendered (not .mise.toml union).
    mise_fragment = dest / ".mise" / "conf.d" / "bailiff-mod-go.toml"
    assert mise_fragment.is_file(), ".mise/conf.d/bailiff-mod-go.toml missing"
    mise_content = mise_fragment.read_text()
    assert "go" in mise_content, "go tool not in mise fragment"
    assert "1.23" in mise_content, "go_version not in mise fragment"

    # T045: pre-commit.d fragment rendered.
    precommit_fragment = dest / ".pre-commit.d" / "bailiff-mod-go.yaml"
    assert precommit_fragment.is_file(), ".pre-commit.d/bailiff-mod-go.yaml missing"
    precommit_content = precommit_fragment.read_text()
    assert "golangci" in precommit_content, "golangci not in precommit fragment"
    assert "v1.64.8" in precommit_content, "golangci_hook_rev not in precommit fragment"

    # T049: gitignore.d fragment rendered.
    gitignore_fragment = dest / ".gitignore.d" / "bailiff-mod-go"
    assert gitignore_fragment.is_file(), ".gitignore.d/bailiff-mod-go missing"
    gitignore_content = gitignore_fragment.read_text()
    assert "*.exe" in gitignore_content, "Go build output not in gitignore fragment"


def test_app_kind_library_no_cmd(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_go: TemplateRepo,
    tmp_path: Path,
) -> None:
    """app_kind=library: cmd/ is excluded entirely (no empty dir)."""
    dest = tmp_path / "proj"
    _init_base_precommit_go(
        bailiff_mod_base, bailiff_mod_precommit, bailiff_mod_go, dest, app_kind="library"
    )

    # cmd/ must not exist at all — not even an empty directory.
    assert not (dest / "cmd").exists(), "cmd/ should not exist for library app_kind"


def test_use_vendor_mode_fragment(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_go: TemplateRepo,
    tmp_path: Path,
) -> None:
    """use_vendor_mode=true adds vendor/ to the gitignore fragment."""
    dest = tmp_path / "proj"
    _init_base_precommit_go(
        bailiff_mod_base, bailiff_mod_precommit, bailiff_mod_go, dest, use_vendor_mode=True
    )

    af = yaml.safe_load((dest / ".copier-answers.bailiff-mod-go.yml").read_text())
    assert af["use_vendor_mode"] is True, "use_vendor_mode not recorded in answers"

    gitignore_fragment = dest / ".gitignore.d" / "bailiff-mod-go"
    assert gitignore_fragment.is_file(), ".gitignore.d/bailiff-mod-go missing"
    assert "vendor/" in gitignore_fragment.read_text(), "vendor/ not in gitignore fragment"


def test_empty_golangci_rev_no_precommit_fragment(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_go: TemplateRepo,
    tmp_path: Path,
) -> None:
    """golangci_hook_rev='' renders an empty pre-commit fragment (no hook block)."""
    dest = tmp_path / "proj"
    _init_base_precommit_go(
        bailiff_mod_base, bailiff_mod_precommit, bailiff_mod_go, dest, golangci_hook_rev=""
    )

    precommit_fragment = dest / ".pre-commit.d" / "bailiff-mod-go.yaml"
    assert precommit_fragment.is_file(), ".pre-commit.d/bailiff-mod-go.yaml missing"
    content = precommit_fragment.read_text().strip()
    # Empty or whitespace only — no hook block rendered when rev is absent.
    assert "golangci" not in content, "golangci fragment rendered without a rev"


def test_test_runner_gotestsum_in_mise_fragment(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_go: TemplateRepo,
    tmp_path: Path,
) -> None:
    """test_runner=gotestsum adds gotestsum to the mise conf.d fragment."""
    trust.add_trust(bailiff_mod_base.url)
    trust.add_trust(bailiff_mod_precommit.url)
    trust.add_trust(bailiff_mod_go.url)
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/bailiff-mod-base", bailiff_mod_base, ["project_name"]),
            {"project_name": "myapp", "org": "acme", "license": "mit", "layout": "single"},
        ),
        (
            _record("demo/bailiff-mod-precommit", bailiff_mod_precommit, ["hook_manager"]),
            {"hook_manager": "pre-commit"},
        ),
        (
            _record("demo/bailiff-mod-go", bailiff_mod_go, ["project_name"]),
            {
                "go_version": "1.23",
                "app_kind": "cli",
                "test_runner": "gotestsum",
                "use_vendor_mode": False,
                "golangci_hook_rev": "",
            },
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    mise_fragment = dest / ".mise" / "conf.d" / "bailiff-mod-go.toml"
    assert mise_fragment.is_file()
    content = mise_fragment.read_text()
    assert "gotestsum" in content, "gotestsum not in mise fragment for gotestsum runner"


def test_ordering_depends_on_edge(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_go: TemplateRepo,
    tmp_path: Path,
) -> None:
    """depends_on + _external_data edges sequence base before go regardless of input order."""
    from bailiff import ordering

    # go declares depends_on: [base] and _external_data aliases for base + precommit,
    # so all three must be in the selection; verify base precedes go.
    recs = [
        _record("demo/bailiff-mod-go", bailiff_mod_go, ["project_name"]),
        _record("demo/bailiff-mod-precommit", bailiff_mod_precommit, ["hook_manager"]),
        _record("demo/bailiff-mod-base", bailiff_mod_base, ["project_name"]),
    ]
    plan = ordering.layer_plan(recs)
    order = [r.full_id.rsplit("/", 1)[-1] for r, _ in plan]
    base_idx = order.index("bailiff-mod-base")
    go_idx = order.index("bailiff-mod-go")
    assert base_idx < go_idx, f"base must precede go; got order: {order}"


def test_golangci_seed_once_preserved_on_reproduce(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_go: TemplateRepo,
    tmp_path: Path,
) -> None:
    """Seed-once .golangci.yml is NOT overwritten when it already exists on reproduce."""
    dest = tmp_path / "proj"
    _init_base_precommit_go(bailiff_mod_base, bailiff_mod_precommit, bailiff_mod_go, dest)

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
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_go: TemplateRepo,
    tmp_path: Path,
) -> None:
    """go.mod is _skip_if_exists: if present before reproduce, it is preserved."""
    dest = tmp_path / "proj"
    _init_base_precommit_go(bailiff_mod_base, bailiff_mod_precommit, bailiff_mod_go, dest)

    # Simulate go.mod having been created (real init would call `go mod init`).
    go_mod = dest / "go.mod"
    go_mod.write_text("module mygoapp\n\ngo 1.23\n")
    digest_before = _digest(go_mod)

    runner.reproduce_many(str(dest))

    assert go_mod.is_file(), "go.mod disappeared on reproduce"
    assert _digest(go_mod) == digest_before, "go.mod was overwritten on reproduce"


def test_cmd_main_go_seed_once_preserved_on_reproduce(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_go: TemplateRepo,
    tmp_path: Path,
) -> None:
    """cmd/<name>/main.go is _skip_if_exists: edits survive reproduce."""
    dest = tmp_path / "proj"
    _init_base_precommit_go(
        bailiff_mod_base, bailiff_mod_precommit, bailiff_mod_go, dest, app_kind="cli"
    )

    main_go = dest / "cmd" / "mygoapp" / "main.go"
    assert main_go.is_file(), "cmd stub missing before reproduce"

    edited = main_go.read_text() + "\n// user code\n"
    main_go.write_text(edited)
    digest_before = _digest(main_go)

    runner.reproduce_many(str(dest))

    assert _digest(main_go) == digest_before, "cmd/main.go was overwritten on reproduce"


def test_mise_fragment_byte_identical_on_reproduce(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_go: TemplateRepo,
    tmp_path: Path,
) -> None:
    """Managed .mise/conf.d/bailiff-mod-go.toml is byte-identical on reproduce."""
    dest = tmp_path / "proj"
    _init_base_precommit_go(bailiff_mod_base, bailiff_mod_precommit, bailiff_mod_go, dest)

    mise_fragment = dest / ".mise" / "conf.d" / "bailiff-mod-go.toml"
    digest_before = _digest(mise_fragment)

    runner.reproduce_many(str(dest))

    assert _digest(mise_fragment) == digest_before, "mise fragment changed on reproduce"


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
