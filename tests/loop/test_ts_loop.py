"""spec 011 T007: bailiff-mod-ts loop tests.

Init [bailiff-mod-base, bailiff-mod-ts] and assert:
- run_after edge sequences base before ts;
- project_name threaded from base into the ts overlay;
- package.json stub marker present (task-output lifecycle);
- managed configs present: tsconfig.json, biome.json (ts_linter=biome),
  eslint/.prettierrc (ts_linter=eslint-prettier);
- gitignore_stack / mise_tools / hook_blocks tokens contributed (frozen-union M1);
- answers files committed for both layers.

Reproduce assertions:
- edited package.json preserved (_skip_if_exists seed-once contract).

No secret: questions, yarn/jest never offered (spec 011 contract).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
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


@pytest.fixture
def bailiff_mod_ts_bun(tmp_path: Path) -> TemplateRepo:
    """bailiff-mod-ts with bun pkg manager, biome linter, tasks stubbed offline."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-ts", tmp_path / "bailiff-mod-ts-bun", _BUN_STUB_TASKS
    )


@pytest.fixture
def bailiff_mod_ts_pnpm(tmp_path: Path) -> TemplateRepo:
    """bailiff-mod-ts with pnpm pkg manager, tasks stubbed offline."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-ts", tmp_path / "bailiff-mod-ts-pnpm", _PNPM_STUB_TASKS
    )


# ---------------------------------------------------------------------------
# Init tests
# ---------------------------------------------------------------------------


def test_base_ts_ordered_and_threaded(
    bailiff_mod_base: TemplateRepo, bailiff_mod_ts_bun: TemplateRepo, tmp_path: Path
) -> None:
    """SC-002: [base, ts] applies base first, threads project_name, creates outputs."""
    trust.add_trust(bailiff_mod_base.url)
    trust.add_trust(bailiff_mod_ts_bun.url)

    dest = tmp_path / "proj"
    # Mis-order input (ts first) — run_after must reorder.
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/bailiff-mod-ts", bailiff_mod_ts_bun, ["project_name", "js_pkg_manager"]),
            {
                "js_pkg_manager": "bun",
                "ts_linter": "biome",
                "test_runner": "none",
                "node_version": "22",
                "ts_framework": "plain",
                "ui_kit": "none",
                # frozen-union tokens contributed by this module
                "gitignore_stack": ["ghg:macOS", "Node"],
                "mise_tools": [{"node": "22"}],
                "hook_blocks": [],
            },
        ),
        (
            _record(
                "demo/bailiff-mod-base", bailiff_mod_base, ["project_name", "license", "layout"]
            ),
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

    # Base rendered first: scaffold present (base v1.0.0 thinned: .codex/ moved to agentic).
    assert (dest / "AGENTS.md").is_file(), "base AGENTS.md missing"
    assert (dest / "docs").is_dir(), "base docs/ scaffold missing"

    # ts preflight stub marker written by the stub task.
    assert (dest / ".bailiff-ts-preflight").is_file(), "ts preflight stub marker missing"

    # answers files committed for both layers.
    af_base_path = dest / ".copier-answers.bailiff-mod-base.yml"
    af_ts_path = dest / ".copier-answers.bailiff-mod-ts.yml"
    assert af_base_path.is_file(), "base answers file missing"
    assert af_ts_path.is_file(), "ts answers file missing"

    import yaml

    af_ts = yaml.safe_load(af_ts_path.read_text())
    assert af_ts["project_name"] == "mytsapp", "project_name not threaded base→ts"
    assert af_ts["js_pkg_manager"] == "bun"
    assert af_ts["ts_linter"] == "biome"
    assert bailiff_mod_ts_bun.url in af_ts["_src_path"]

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
    bailiff_mod_base: TemplateRepo, bailiff_mod_ts_bun: TemplateRepo
) -> None:
    """run_after: [bailiff-mod-base] sequences base before ts regardless of input order."""
    from bailiff import ordering

    recs = [
        _record("demo/bailiff-mod-ts", bailiff_mod_ts_bun, ["project_name"]),
        _record("demo/bailiff-mod-base", bailiff_mod_base, ["project_name"]),
    ]
    plan = ordering.layer_plan(recs)
    order = [r.full_id.rsplit("/", 1)[-1] for r, _ in plan]
    assert order == ["bailiff-mod-base", "bailiff-mod-ts"], f"edge not honoured: {order}"


def test_ts_eslint_prettier_variant(
    bailiff_mod_base: TemplateRepo, bailiff_mod_ts_bun: TemplateRepo, tmp_path: Path
) -> None:
    """ts_linter=eslint-prettier renders eslint/prettier configs, biome.json is empty."""
    trust.add_trust(bailiff_mod_base.url)
    trust.add_trust(bailiff_mod_ts_bun.url)

    dest = tmp_path / "proj"
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/bailiff-mod-ts", bailiff_mod_ts_bun, ["project_name", "ts_linter"]),
            {
                "js_pkg_manager": "bun",
                "ts_linter": "eslint-prettier",
                "test_runner": "none",
                "node_version": "22",
                "ts_framework": "plain",
                "ui_kit": "none",
                "gitignore_stack": ["Node"],
                "mise_tools": [{"node": "22"}],
                "hook_blocks": [],
            },
        ),
        (
            _record(
                "demo/bailiff-mod-base", bailiff_mod_base, ["project_name", "license", "layout"]
            ),
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


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


def test_edited_package_json_preserved_on_reproduce(
    bailiff_mod_base: TemplateRepo, bailiff_mod_ts_bun: TemplateRepo, tmp_path: Path
) -> None:
    """Seed-once: edited package.json is NOT overwritten on reproduce (_skip_if_exists)."""
    trust.add_trust(bailiff_mod_base.url)
    trust.add_trust(bailiff_mod_ts_bun.url)

    dest = tmp_path / "proj"
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record(
                "demo/bailiff-mod-base", bailiff_mod_base, ["project_name", "license", "layout"]
            ),
            {
                "project_name": "mytsapp",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": ["Node"],
            },
        ),
        (
            _record("demo/bailiff-mod-ts", bailiff_mod_ts_bun, ["project_name", "js_pkg_manager"]),
            {
                "js_pkg_manager": "bun",
                "ts_linter": "biome",
                "test_runner": "none",
                "node_version": "22",
                "ts_framework": "plain",
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


# ---------------------------------------------------------------------------
# test_runner variant tests (cross-cutting §8: byte-assert all managed renders)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_runner,expect_vitest,expect_playwright",
    [
        ("vitest-node", True, False),
        ("vitest-browser", True, False),
        ("vitest+playwright", True, True),
        ("bun-test", False, False),
        ("playwright-only", False, True),
    ],
)
def test_test_runner_variants(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_ts_bun: TemplateRepo,
    tmp_path: Path,
    test_runner: str,
    expect_vitest: bool,
    expect_playwright: bool,
) -> None:
    """Managed vitest.config.ts / playwright.config.ts rendered correctly per test_runner."""
    trust.add_trust(bailiff_mod_base.url)
    trust.add_trust(bailiff_mod_ts_bun.url)

    dest = tmp_path / f"proj-{test_runner}"
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record(
                "demo/bailiff-mod-base", bailiff_mod_base, ["project_name", "license", "layout"]
            ),
            {
                "project_name": "tstest",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": ["Node"],
            },
        ),
        (
            _record("demo/bailiff-mod-ts", bailiff_mod_ts_bun, ["project_name", "test_runner"]),
            {
                "js_pkg_manager": "bun",
                "ts_linter": "biome",
                "test_runner": test_runner,
                "node_version": "22",
                "ts_framework": "plain",
                "ui_kit": "none",
                "gitignore_stack": ["Node"],
                "mise_tools": [{"node": "22"}],
                "hook_blocks": [],
            },
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")

    vitest_path = dest / "vitest.config.ts"
    playwright_path = dest / "playwright.config.ts"

    if expect_vitest:
        assert vitest_path.is_file(), f"vitest.config.ts missing for test_runner={test_runner}"
        content = vitest_path.read_text()
        assert len(content) > 0, f"vitest.config.ts is empty for test_runner={test_runner}"
        assert "defineConfig" in content, f"vitest.config.ts missing defineConfig ({test_runner})"
        # Verify the branch-specific environment setting is rendered.
        if test_runner == "vitest-node":
            assert '"node"' in content, "vitest-node: environment=node not in config"
        elif test_runner == "vitest-browser":
            assert "browser" in content, "vitest-browser: browser block not in config"
        elif test_runner == "vitest+playwright":
            assert '"node"' in content, "vitest+playwright: node env not in config"
    else:
        # For bun-test and playwright-only, vitest.config.ts must be absent or empty.
        if vitest_path.is_file():
            assert vitest_path.read_bytes() == b"", (
                f"vitest.config.ts should be absent/empty for test_runner={test_runner}"
            )

    if expect_playwright:
        assert playwright_path.is_file(), (
            f"playwright.config.ts missing for test_runner={test_runner}"
        )
        content = playwright_path.read_text()
        assert len(content) > 0, f"playwright.config.ts is empty for test_runner={test_runner}"
        assert "defineConfig" in content, (
            f"playwright.config.ts missing defineConfig ({test_runner})"
        )
    else:
        # For vitest-node, vitest-browser, bun-test, none: playwright.config.ts absent or empty.
        if playwright_path.is_file():
            assert playwright_path.read_bytes() == b"", (
                f"playwright.config.ts should be absent/empty for test_runner={test_runner}"
            )


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


def test_no_secret_questions() -> None:
    """No secret: questions in the copier.yml (spec 011 contract / Constitution VI)."""
    from pathlib import Path

    import yaml

    copier_yml = (
        Path(__file__).resolve().parent.parent.parent
        / "templates"
        / "bailiff-mod-ts"
        / "copier.yml"
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
        Path(__file__).resolve().parent.parent.parent
        / "templates"
        / "bailiff-mod-ts"
        / "copier.yml"
    )
    raw = yaml.safe_load(copier_yml.read_text()) or {}

    pkg_mgr_spec = raw.get("js_pkg_manager", {})
    pkg_choices = pkg_mgr_spec.get("choices", []) if isinstance(pkg_mgr_spec, dict) else []
    assert "yarn" not in pkg_choices, f"yarn must not be offered; choices={pkg_choices}"

    test_runner_spec = raw.get("test_runner", {})
    test_choices = test_runner_spec.get("choices", []) if isinstance(test_runner_spec, dict) else []
    assert "jest" not in test_choices, f"jest must not be offered; choices={test_choices}"
