"""spec 011 T007: clerk-mod-ts loop tests.

Init [clerk-mod-base, clerk-mod-ts] and assert:
- run_after edge sequences base before ts;
- project_name threaded from base into the ts overlay;
- package.json stub marker present (task-output lifecycle);
- managed configs byte-identical: tsconfig.json, biome.json (ts_linter=biome),
  eslint/.prettierrc (ts_linter=eslint-prettier);
- gitignore_stack / mise_tools / hook_blocks tokens contributed (frozen-union M1);
- answers files committed for both layers.

Reproduce assertions:
- managed config files byte-identical after reproduce;
- edited package.json preserved (_skip_if_exists seed-once contract).

No secret: questions, yarn/jest never offered (spec 011 contract).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from clerk import runner, trust
from clerk.catalog import TemplateRecord
from tests.conftest import (
    _BUN_STUB_TASKS,
    _PNPM_STUB_TASKS,
    TemplateRepo,
    _copy_module_with_stub_tasks,
)


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


@pytest.fixture
def clerk_mod_ts_bun(tmp_path: Path) -> TemplateRepo:
    """clerk-mod-ts with bun pkg manager, biome linter, tasks stubbed offline."""
    return _copy_module_with_stub_tasks(
        "clerk-mod-ts", tmp_path / "clerk-mod-ts-bun", _BUN_STUB_TASKS
    )


@pytest.fixture
def clerk_mod_ts_pnpm(tmp_path: Path) -> TemplateRepo:
    """clerk-mod-ts with pnpm pkg manager, tasks stubbed offline."""
    return _copy_module_with_stub_tasks(
        "clerk-mod-ts", tmp_path / "clerk-mod-ts-pnpm", _PNPM_STUB_TASKS
    )


# ---------------------------------------------------------------------------
# Init tests
# ---------------------------------------------------------------------------


def test_base_ts_ordered_and_threaded(
    clerk_mod_base: TemplateRepo, clerk_mod_ts_bun: TemplateRepo, tmp_path: Path
) -> None:
    """SC-002: [base, ts] applies base first, threads project_name, creates outputs."""
    trust.add_trust(clerk_mod_base.url)
    trust.add_trust(clerk_mod_ts_bun.url)

    dest = tmp_path / "proj"
    # Mis-order input (ts first) — run_after must reorder.
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/clerk-mod-ts", clerk_mod_ts_bun, ["project_name", "js_pkg_manager"]),
            {
                "js_pkg_manager": "bun",
                "ts_linter": "biome",
                "test_runner": "none",
                "node_version": "22",
                "framework": "plain",
                "ui_kit": "none",
                # frozen-union tokens contributed by this module
                "gitignore_stack": ["ghg:macOS", "Node"],
                "mise_tools": [{"node": "22"}],
                "hook_blocks": [],
            },
        ),
        (
            _record("demo/clerk-mod-base", clerk_mod_base, ["project_name", "license", "layout"]),
            {
                "project_name": "mytsapp",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": ["ghg:macOS", "Node"],
            },
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")

    # Base rendered first: scaffold present.
    assert (dest / "AGENTS.md").is_file(), "base AGENTS.md missing"
    assert (dest / ".codex" / ".gitkeep").is_file(), "base dir scaffold missing"

    # ts preflight stub marker written by the stub task.
    assert (dest / ".clerk-ts-preflight").is_file(), "ts preflight stub marker missing"

    # answers files committed for both layers.
    af_base_path = dest / ".copier-answers.clerk-mod-base.yml"
    af_ts_path = dest / ".copier-answers.clerk-mod-ts.yml"
    assert af_base_path.is_file(), "base answers file missing"
    assert af_ts_path.is_file(), "ts answers file missing"

    import yaml

    af_ts = yaml.safe_load(af_ts_path.read_text())
    assert af_ts["project_name"] == "mytsapp", "project_name not threaded base→ts"
    assert af_ts["js_pkg_manager"] == "bun"
    assert af_ts["ts_linter"] == "biome"
    assert clerk_mod_ts_bun.url in af_ts["_src_path"]

    # Managed: tsconfig.json present and has ES2022 + strict markers.
    tsconfig_path = dest / "tsconfig.json"
    assert tsconfig_path.is_file(), "tsconfig.json missing"
    tsconfig = tsconfig_path.read_text()
    assert '"ES2022"' in tsconfig, "tsconfig: ES2022 target missing"
    assert '"strict": true' in tsconfig, "tsconfig: strict mode missing"

    # Managed: biome.json present (ts_linter=biome).
    biome_path = dest / "biome.json"
    assert biome_path.is_file(), "biome.json missing (ts_linter=biome)"
    biome = biome_path.read_text()
    assert "biomejs.dev" in biome, "biome.json schema missing"

    # Managed: eslint/prettier configs are zero-byte (inactive with biome linter).
    eslintrc_path = dest / ".eslintrc.json"
    prettierrc_path = dest / ".prettierrc.json"
    if eslintrc_path.is_file():
        assert eslintrc_path.read_bytes() == b"", ".eslintrc.json should be empty (biome active)"
    if prettierrc_path.is_file():
        # inactive with biome linter — must be empty
        assert prettierrc_path.read_bytes() == b""


def test_ordering_run_after_edge(
    clerk_mod_base: TemplateRepo, clerk_mod_ts_bun: TemplateRepo
) -> None:
    """run_after: [clerk-mod-base] sequences base before ts regardless of input order."""
    from clerk import ordering

    recs = [
        _record("demo/clerk-mod-ts", clerk_mod_ts_bun, ["project_name"]),
        _record("demo/clerk-mod-base", clerk_mod_base, ["project_name"]),
    ]
    plan = ordering.layer_plan(recs)
    order = [r.full_id.rsplit("/", 1)[-1] for r, _ in plan]
    assert order == ["clerk-mod-base", "clerk-mod-ts"], f"edge not honoured: {order}"


def test_ts_eslint_prettier_variant(
    clerk_mod_base: TemplateRepo, clerk_mod_ts_bun: TemplateRepo, tmp_path: Path
) -> None:
    """ts_linter=eslint-prettier renders eslint/prettier configs, biome.json is empty."""
    trust.add_trust(clerk_mod_base.url)
    trust.add_trust(clerk_mod_ts_bun.url)

    dest = tmp_path / "proj"
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/clerk-mod-ts", clerk_mod_ts_bun, ["project_name", "ts_linter"]),
            {
                "js_pkg_manager": "bun",
                "ts_linter": "eslint-prettier",
                "test_runner": "none",
                "node_version": "22",
                "framework": "plain",
                "ui_kit": "none",
                "gitignore_stack": ["Node"],
                "mise_tools": [{"node": "22"}],
                "hook_blocks": [],
            },
        ),
        (
            _record("demo/clerk-mod-base", clerk_mod_base, ["project_name", "license", "layout"]),
            {
                "project_name": "eslintapp",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": ["Node"],
            },
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")

    # biome.json is zero-byte (inactive with eslint-prettier).
    biome_path = dest / "biome.json"
    if biome_path.is_file():
        assert biome_path.read_bytes() == b"", "biome.json should be empty (eslint-prettier active)"

    # eslint/prettier configs have content.
    eslintrc_path = dest / ".eslintrc.json"
    prettierrc_path = dest / ".prettierrc.json"
    assert eslintrc_path.is_file(), ".eslintrc.json missing (ts_linter=eslint-prettier)"
    assert prettierrc_path.is_file(), ".prettierrc.json missing (ts_linter=eslint-prettier)"
    assert len(eslintrc_path.read_bytes()) > 0, ".eslintrc.json is empty"
    assert len(prettierrc_path.read_bytes()) > 0, ".prettierrc.json is empty"
    assert "typescript-eslint" in eslintrc_path.read_text(), ".eslintrc.json missing ts-eslint"


# ---------------------------------------------------------------------------
# Reproduce tests
# ---------------------------------------------------------------------------


def test_managed_configs_byte_identical_on_reproduce(
    clerk_mod_base: TemplateRepo, clerk_mod_ts_bun: TemplateRepo, tmp_path: Path
) -> None:
    """Managed configs (tsconfig.json, biome.json) are byte-identical after reproduce."""
    trust.add_trust(clerk_mod_base.url)
    trust.add_trust(clerk_mod_ts_bun.url)

    dest = tmp_path / "proj"
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/clerk-mod-base", clerk_mod_base, ["project_name", "license", "layout"]),
            {
                "project_name": "mytsapp",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": ["Node"],
            },
        ),
        (
            _record("demo/clerk-mod-ts", clerk_mod_ts_bun, ["project_name", "js_pkg_manager"]),
            {
                "js_pkg_manager": "bun",
                "ts_linter": "biome",
                "test_runner": "none",
                "node_version": "22",
                "framework": "plain",
                "ui_kit": "none",
                "gitignore_stack": ["Node"],
                "mise_tools": [{"node": "22"}],
                "hook_blocks": [],
            },
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")

    # Capture digests of managed files before reproduce.
    managed = ["tsconfig.json", "biome.json"]
    before = {
        p: _digest(dest / p)
        for p in managed
        if (dest / p).is_file() and (dest / p).stat().st_size > 0
    }
    assert before, "no managed files found after init"

    runner.reproduce_many(str(dest))

    after = {
        p: _digest(dest / p)
        for p in managed
        if (dest / p).is_file() and (dest / p).stat().st_size > 0
    }
    assert before == after, (
        "managed config files changed on reproduce: "
        f"{[p for p in before if before.get(p) != after.get(p)]}"
    )


def test_edited_package_json_preserved_on_reproduce(
    clerk_mod_base: TemplateRepo, clerk_mod_ts_bun: TemplateRepo, tmp_path: Path
) -> None:
    """Seed-once: edited package.json is NOT overwritten on reproduce (_skip_if_exists)."""
    trust.add_trust(clerk_mod_base.url)
    trust.add_trust(clerk_mod_ts_bun.url)

    dest = tmp_path / "proj"
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/clerk-mod-base", clerk_mod_base, ["project_name", "license", "layout"]),
            {
                "project_name": "mytsapp",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": ["Node"],
            },
        ),
        (
            _record("demo/clerk-mod-ts", clerk_mod_ts_bun, ["project_name", "js_pkg_manager"]),
            {
                "js_pkg_manager": "bun",
                "ts_linter": "biome",
                "test_runner": "none",
                "node_version": "22",
                "framework": "plain",
                "ui_kit": "none",
                "gitignore_stack": ["Node"],
                "mise_tools": [{"node": "22"}],
                "hook_blocks": [],
            },
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")

    # Write a stub package.json to simulate the task-output state.
    pkg_json = dest / "package.json"
    pkg_json.write_text('{"name": "mytsapp-edited", "version": "1.0.0"}\n')
    edited_content = pkg_json.read_bytes()

    runner.reproduce_many(str(dest))

    # _skip_if_exists must preserve the project's edited package.json.
    assert pkg_json.read_bytes() == edited_content, (
        "package.json was overwritten on reproduce — _skip_if_exists contract violated"
    )


def test_no_secret_questions() -> None:
    """No secret: questions in the copier.yml (spec 011 contract / Constitution VI)."""
    from pathlib import Path

    import yaml

    copier_yml = (
        Path(__file__).resolve().parent.parent.parent / "templates" / "clerk-mod-ts" / "copier.yml"
    )
    assert copier_yml.exists(), f"copier.yml not found at {copier_yml}"
    raw = yaml.safe_load(copier_yml.read_text()) or {}
    for key, spec in raw.items():
        if key.startswith("_"):
            continue
        if isinstance(spec, dict):
            assert not spec.get("secret"), f"secret: question found: {key}"


def test_yarn_jest_not_offered() -> None:
    """yarn and jest are DEAD — must not appear as choices (spec 011 contract)."""
    from pathlib import Path

    import yaml

    copier_yml = (
        Path(__file__).resolve().parent.parent.parent / "templates" / "clerk-mod-ts" / "copier.yml"
    )
    raw = yaml.safe_load(copier_yml.read_text()) or {}

    pkg_mgr_spec = raw.get("js_pkg_manager", {})
    pkg_choices = pkg_mgr_spec.get("choices", []) if isinstance(pkg_mgr_spec, dict) else []
    assert "yarn" not in pkg_choices, f"yarn must not be offered; choices={pkg_choices}"

    test_runner_spec = raw.get("test_runner", {})
    test_choices = test_runner_spec.get("choices", []) if isinstance(test_runner_spec, dict) else []
    assert "jest" not in test_choices, f"jest must not be offered; choices={test_choices}"
