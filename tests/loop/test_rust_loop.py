"""spec 014 (T023/T035/T039/T045/T049): bailiff-mod-rust loop tests.

Covers:
- Init [base, rust] applies base first, reads project_name via _external_data alias,
  produces managed rust-toolchain.toml, rustfmt.toml, and drop-in fragments.
- .mise/conf.d/bailiff-mod-rust.toml rendered with rust channel + optional nextest.
- .pre-commit.d/bailiff-mod-rust.yaml fragment present when hook_manager=pre-commit.
- .gitignore.d/bailiff-mod-rust static fragment present.
- crate_kind=lib renders the --lib flag expression in the task (verified via the
  copier.yml task body — actual cargo is stubbed offline).
- test_runner=cargo-test vs nextest: answers recorded correctly.
- reproduce: Cargo.toml (seed-once) preserved after edit.
- Standalone render with defaults does not crash.
- No secret: questions present.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
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


def _init_base_rust(
    base: TemplateRepo,
    precommit: TemplateRepo,
    rust: TemplateRepo,
    dest: Path,
    rust_answers: dict[str, Any] | None = None,
) -> None:
    trust.add_trust(base.url)
    trust.add_trust(precommit.url)
    trust.add_trust(rust.url)
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/bailiff-mod-base", base, ["project_name", "license", "layout"]),
            {
                "project_name": "mycrate",
                "org": "acme",
                "license": "mit",
                "layout": "single",
            },
        ),
        (
            _record("demo/bailiff-mod-precommit", precommit, ["hook_manager"]),
            {"hook_manager": "pre-commit"},
        ),
        (
            _record(
                "demo/bailiff-mod-rust",
                rust,
                ["project_name", "rust_channel", "rust_edition", "crate_kind", "test_runner"],
            ),
            rust_answers or {},
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")


# ---------------------------------------------------------------------------
# Init: defaults (bin, nextest, stable, 2024)
# ---------------------------------------------------------------------------


def test_base_rust_defaults(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_rust: TemplateRepo,
    tmp_path: Path,
) -> None:
    """Init [base, precommit, rust] with defaults: managed files and fragments present."""
    dest = tmp_path / "proj"
    _init_base_rust(bailiff_mod_base, bailiff_mod_precommit, bailiff_mod_rust, dest)

    # base rendered.
    assert (dest / "AGENTS.md").is_file(), "base AGENTS.md missing"

    # Managed: rust-toolchain.toml pinned to stable.
    toolchain = (dest / "rust-toolchain.toml").read_text()
    assert 'channel = "stable"' in toolchain, "rust_channel not rendered in rust-toolchain.toml"

    # Managed: rustfmt.toml present with max_width=100.
    rustfmt = (dest / "rustfmt.toml").read_text()
    assert "max_width = 100" in rustfmt, "max_width not in rustfmt.toml"
    assert 'use_small_heuristics = "Max"' in rustfmt, "heuristics not rendered (default Max)"

    # Preflight stub ran (offline marker).
    assert (dest / ".bailiff-rust-preflight").is_file(), "cargo preflight stub marker missing"

    # Fragment: mise conf.d drop-in (T023 / FR-008).
    mise_frag = dest / ".mise" / "conf.d" / "bailiff-mod-rust.toml"
    assert mise_frag.is_file(), ".mise/conf.d/bailiff-mod-rust.toml fragment missing"
    mise_text = mise_frag.read_text()
    assert 'rust = "stable"' in mise_text, "rust_channel not in mise conf.d fragment"
    assert "cargo-nextest" in mise_text, "nextest entry missing from mise conf.d (default=nextest)"

    # Fragment: gitignore drop-in (T049).
    gi_frag = dest / ".gitignore.d" / "bailiff-mod-rust"
    assert gi_frag.is_file(), ".gitignore.d/bailiff-mod-rust fragment missing"
    assert "/target" in gi_frag.read_text(), "/target not in gitignore fragment"

    # Fragment: pre-commit drop-in present (T045).
    pc_frag = dest / ".pre-commit.d" / "bailiff-mod-rust.yaml"
    assert pc_frag.is_file(), ".pre-commit.d/bailiff-mod-rust.yaml fragment missing"

    # Answers recorded: rust-specific answers present; no union keys.
    af = yaml.safe_load((dest / ".copier-answers.bailiff-mod-rust.yml").read_text())
    assert bailiff_mod_rust.url in af["_src_path"]
    assert af["rust_channel"] == "stable"
    assert af["crate_kind"] == "bin"
    assert af["test_runner"] == "nextest"
    # union keys removed in spec 014 — none must survive into the answers file
    assert "hook_blocks" not in af, "hook_blocks must not appear in rust answers (spec 014)"
    assert "mise_tools" not in af, "mise_tools must not appear in rust answers (spec 014)"
    assert "gitignore_stack" not in af, "gitignore_stack must not appear in rust answers (spec 014)"


# ---------------------------------------------------------------------------
# crate_kind=lib (FIX: --lib flag)
# ---------------------------------------------------------------------------


def test_crate_kind_lib_recorded(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_rust: TemplateRepo,
    tmp_path: Path,
) -> None:
    """crate_kind=lib is recorded in the answers file; the task template carries --lib."""
    dest = tmp_path / "proj"
    _init_base_rust(
        bailiff_mod_base,
        bailiff_mod_precommit,
        bailiff_mod_rust,
        dest,
        rust_answers={"crate_kind": "lib"},
    )

    af = yaml.safe_load((dest / ".copier-answers.bailiff-mod-rust.yml").read_text())
    assert af["crate_kind"] == "lib", "crate_kind=lib not recorded"

    # Verify the copier.yml task body contains the --lib conditional expression
    # (the actual cargo new is stubbed, so we inspect the template source).

    copier_yml_path = (
        Path(__file__).resolve().parent.parent.parent
        / "templates"
        / "bailiff-mod-rust"
        / "copier.yml"
    )
    task_text = copier_yml_path.read_text()
    assert "--lib" in task_text, "copier.yml task missing --lib branch (FIX not applied)"
    assert "crate_kind == 'lib'" in task_text, "crate_kind=lib condition missing in task"


# ---------------------------------------------------------------------------
# test_runner=cargo-test
# ---------------------------------------------------------------------------


def test_test_runner_cargo_test(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_rust: TemplateRepo,
    tmp_path: Path,
) -> None:
    """test_runner=cargo-test: recorded; cargo-nextest omitted from mise conf.d fragment."""
    dest = tmp_path / "proj"
    _init_base_rust(
        bailiff_mod_base,
        bailiff_mod_precommit,
        bailiff_mod_rust,
        dest,
        rust_answers={"test_runner": "cargo-test"},
    )

    af = yaml.safe_load((dest / ".copier-answers.bailiff-mod-rust.yml").read_text())
    assert af["test_runner"] == "cargo-test"

    # nextest must be absent from the mise conf.d fragment when test_runner=cargo-test.
    mise_frag = dest / ".mise" / "conf.d" / "bailiff-mod-rust.toml"
    assert mise_frag.is_file(), ".mise/conf.d/bailiff-mod-rust.toml fragment missing"
    assert "cargo-nextest" not in mise_frag.read_text(), (
        "cargo-nextest must not appear in mise conf.d when test_runner=cargo-test"
    )


# ---------------------------------------------------------------------------
# rust_channel variants
# ---------------------------------------------------------------------------


def test_rust_channel_nightly(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_rust: TemplateRepo,
    tmp_path: Path,
) -> None:
    """rust_channel=nightly written into rust-toolchain.toml."""
    dest = tmp_path / "proj"
    _init_base_rust(
        bailiff_mod_base,
        bailiff_mod_precommit,
        bailiff_mod_rust,
        dest,
        rust_answers={"rust_channel": "nightly"},
    )

    toolchain = (dest / "rust-toolchain.toml").read_text()
    assert 'channel = "nightly"' in toolchain


# ---------------------------------------------------------------------------
# rustfmt_heuristics=Off → no use_small_heuristics line
# ---------------------------------------------------------------------------


def test_rustfmt_heuristics_off(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_rust: TemplateRepo,
    tmp_path: Path,
) -> None:
    """rustfmt_heuristics=Off omits the use_small_heuristics line."""
    dest = tmp_path / "proj"
    _init_base_rust(
        bailiff_mod_base,
        bailiff_mod_precommit,
        bailiff_mod_rust,
        dest,
        rust_answers={"rustfmt_heuristics": "Off"},
    )

    rustfmt = (dest / "rustfmt.toml").read_text()
    assert "max_width = 100" in rustfmt
    assert "use_small_heuristics" not in rustfmt, "Off should suppress the heuristics line"


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


# ---------------------------------------------------------------------------
# Seed-once: Cargo.toml preserved on reproduce (edited)
# ---------------------------------------------------------------------------


def test_cargo_toml_preserved_on_reproduce(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_precommit: TemplateRepo,
    bailiff_mod_rust: TemplateRepo,
    tmp_path: Path,
) -> None:
    """Cargo.toml (_skip_if_exists) is NOT overwritten when it already exists."""
    dest = tmp_path / "proj"
    _init_base_rust(bailiff_mod_base, bailiff_mod_precommit, bailiff_mod_rust, dest)

    # Simulate cargo new having produced a Cargo.toml (the stub only writes a marker).
    # Write a synthetic Cargo.toml that looks like project-edited content.
    cargo_edit = dedent(
        """\
        [package]
        name = "mycrate"
        version = "0.2.0"
        edition = "2024"

        [dependencies]
        serde = "1"
        """
    )
    (dest / "Cargo.toml").write_text(cargo_edit)

    runner.reproduce_many(str(dest))

    # Seed-once: project edit must survive reproduce.
    assert (dest / "Cargo.toml").read_text() == cargo_edit, (
        "Cargo.toml was clobbered on reproduce (seed-once violated)"
    )


# ---------------------------------------------------------------------------
# Standalone render (no base layer)
# ---------------------------------------------------------------------------


def test_rust_standalone_renders_with_defaults(
    bailiff_mod_rust: TemplateRepo, tmp_path: Path
) -> None:
    """Overlay renders standalone (no base) without crashing; managed files present."""
    trust.add_trust(bailiff_mod_rust.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_rust.url,
        dest=str(dest),
        answers={"rust_channel": "stable", "rust_edition": "2024", "crate_kind": "bin"},
    )
    runner.init(spec, today="2026-07-14")

    assert (dest / "rust-toolchain.toml").is_file(), "rust-toolchain.toml missing"
    assert (dest / "rustfmt.toml").is_file(), "rustfmt.toml missing"
    assert (dest / ".bailiff-rust-preflight").is_file(), "preflight stub marker missing"


# ---------------------------------------------------------------------------
# No secret: questions
# ---------------------------------------------------------------------------


def test_no_secret_questions() -> None:
    """copier.yml must not contain any 'secret: true' questions (Constitution VI / FR-005)."""
    import subprocess

    # Match 'secret: true' specifically (not comments that mention the word "secret:").
    result = subprocess.run(
        ["grep", "-rE", r"^\s+secret:\s+true", "templates/bailiff-mod-rust/"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent.parent,
    )
    assert result.returncode != 0, (
        f"secret: true question found in bailiff-mod-rust:\n{result.stdout}"
    )
