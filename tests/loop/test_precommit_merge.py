"""spec 014 SC-004: pre-commit fragment bundler tests (_fragment-merge.md Surface 2).

Tests:
- Order-independence: same fragment set in any order → config-consistent output
- Deduplication: same repo from two fragments → merged once
- Rev-pin conflict: HIGHEST-WINS + WARN (never abort, spec 014 R2)
- Inert when precommit absent from stack
- Inert when no .pre-commit.d fragments exist (bundler always runs; inert on empty dir)
- Config-consistent reproduce (SC-004): same hooks on reproduce, no duplication

Strategy: tests invoke the bundler script (_merge_precommit.py) directly by
writing fragments to a tmp dir and running the script, plus end-to-end tests
using init_many with stub modules that contribute fragment files.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from tests.conftest import (
    _MODULES_DIR,
    TemplateRepo,
    _git,
    build_template_repo,
)


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record(
    full_id: str,
    repo,
    *,
    has_tasks: bool = False,
    questions: list[str] | None = None,
) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=has_tasks,
        questions=questions or ["project_name"],
    )


def _write_fragment(dest: Path, name: str, repos: list[dict]) -> None:
    """Write a .pre-commit.d/<name>.yaml fragment with the given repo entries."""
    frag_dir = dest / ".pre-commit.d"
    frag_dir.mkdir(parents=True, exist_ok=True)
    (frag_dir / f"{name}.yaml").write_text(yaml.dump({"repos": repos}, default_flow_style=False))


def _run_bundler(dest: Path, bundler_path: Path) -> tuple[int, str]:
    """Run the bundler script at bundler_path in dest; return (returncode, stderr)."""
    result = subprocess.run(
        [sys.executable, str(bundler_path)],
        cwd=dest,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stderr


def _get_bundler_path() -> Path:
    """Return path to the bundler script inside the precommit module template."""
    return (
        _MODULES_DIR
        / "bailiff-mod-precommit"
        / "template"
        / "scripts"
        / "_merge_precommit.py.jinja"
    )


# ---------------------------------------------------------------------------
# Unit tests for the bundler script directly (no copier, no bailiff engine)
# These exercise the pure Python logic via subprocess.
# ---------------------------------------------------------------------------


def test_bundler_empty_fragments_is_inert(tmp_path: Path) -> None:
    """Bundler exits 0 and writes nothing when no .pre-commit.d/*.yaml exist."""
    bundler = _get_bundler_path()
    rc, stderr = _run_bundler(tmp_path, bundler)
    assert rc == 0, f"bundler exited {rc}: {stderr}"
    assert not (tmp_path / ".pre-commit-config.yaml").exists()


def test_bundler_single_fragment(tmp_path: Path) -> None:
    """Bundler emits .pre-commit-config.yaml from a single fragment."""
    _write_fragment(
        tmp_path,
        "mod-a",
        [
            {
                "repo": "https://github.com/pre-commit/pre-commit-hooks",
                "rev": "v5.0.0",
                "hooks": [{"id": "trailing-whitespace"}],
            }
        ],
    )
    bundler = _get_bundler_path()
    rc, stderr = _run_bundler(tmp_path, bundler)
    assert rc == 0, f"bundler failed: {stderr}"

    out_path = tmp_path / ".pre-commit-config.yaml"
    assert out_path.exists()
    config = yaml.safe_load(out_path.read_text())
    assert "repos" in config
    urls = [r["repo"] for r in config["repos"]]
    assert "https://github.com/pre-commit/pre-commit-hooks" in urls


def test_bundler_order_independence(tmp_path: Path) -> None:
    """Same repos from fragments in different name-order → config-consistent output.

    Fragment set: mod-alpha contributes ruff, mod-beta contributes mypy.
    Verify both hooks appear regardless of filesystem sort order.
    """
    _write_fragment(
        tmp_path,
        "mod-alpha",
        [
            {
                "repo": "https://github.com/astral-sh/ruff-pre-commit",
                "rev": "v0.6.9",
                "hooks": [{"id": "ruff"}],
            }
        ],
    )
    _write_fragment(
        tmp_path,
        "mod-beta",
        [
            {
                "repo": "https://github.com/pre-commit/mirrors-mypy",
                "rev": "v1.11.2",
                "hooks": [{"id": "mypy"}],
            }
        ],
    )

    bundler = _get_bundler_path()
    rc, _ = _run_bundler(tmp_path, bundler)
    assert rc == 0

    config = yaml.safe_load((tmp_path / ".pre-commit-config.yaml").read_text())
    urls = {r["repo"] for r in config["repos"]}
    assert "https://github.com/astral-sh/ruff-pre-commit" in urls
    assert "https://github.com/pre-commit/mirrors-mypy" in urls


def test_bundler_dedup_same_repo(tmp_path: Path) -> None:
    """Two fragments referencing the same repo URL → merged into one entry."""
    _write_fragment(
        tmp_path,
        "mod-a",
        [
            {
                "repo": "https://github.com/astral-sh/ruff-pre-commit",
                "rev": "v0.6.9",
                "hooks": [{"id": "ruff"}],
            }
        ],
    )
    _write_fragment(
        tmp_path,
        "mod-b",
        [
            {
                "repo": "https://github.com/astral-sh/ruff-pre-commit",
                "rev": "v0.6.9",
                "hooks": [{"id": "ruff-format"}],
            }
        ],
    )

    bundler = _get_bundler_path()
    rc, _ = _run_bundler(tmp_path, bundler)
    assert rc == 0

    config = yaml.safe_load((tmp_path / ".pre-commit-config.yaml").read_text())
    ruff_entries = [r for r in config["repos"] if "ruff-pre-commit" in r["repo"]]
    assert len(ruff_entries) == 1, (
        f"ruff repo appeared {len(ruff_entries)} times, expected 1 after dedup"
    )
    hook_ids = {h["id"] for h in ruff_entries[0]["hooks"]}
    assert "ruff" in hook_ids
    assert "ruff-format" in hook_ids


def test_bundler_rev_pin_conflict_highest_wins_and_warns(tmp_path: Path) -> None:
    """Rev-pin conflict: bundler picks highest rev, emits a warning, exits 0 (R2).

    Two fragments pin the same repo at different revs. Must NOT abort.
    Higher rev wins.
    """
    _write_fragment(
        tmp_path,
        "mod-old",
        [
            {
                "repo": "https://github.com/astral-sh/ruff-pre-commit",
                "rev": "v0.5.0",
                "hooks": [{"id": "ruff"}],
            }
        ],
    )
    _write_fragment(
        tmp_path,
        "mod-new",
        [
            {
                "repo": "https://github.com/astral-sh/ruff-pre-commit",
                "rev": "v0.6.9",
                "hooks": [{"id": "ruff"}],
            }
        ],
    )

    bundler = _get_bundler_path()
    rc, stderr = _run_bundler(tmp_path, bundler)

    # Must NOT abort (exit 0)
    assert rc == 0, f"bundler aborted on rev-pin conflict (exit {rc}): {stderr}"

    # Must warn
    assert "conflict" in stderr.lower() or "warn" in stderr.lower() or "v0.5.0" in stderr, (
        f"expected a rev-pin conflict warning in stderr, got: {stderr!r}"
    )

    # Must pick the HIGHEST rev
    config = yaml.safe_load((tmp_path / ".pre-commit-config.yaml").read_text())
    ruff_entries = [r for r in config["repos"] if "ruff-pre-commit" in r["repo"]]
    assert len(ruff_entries) == 1
    assert ruff_entries[0]["rev"] == "v0.6.9", (
        f"expected highest rev v0.6.9, got {ruff_entries[0]['rev']!r}"
    )


def test_bundler_rev_pin_conflict_is_exit_zero(tmp_path: Path) -> None:
    """Rev-pin conflict never causes a non-zero exit (open-ecosystem premise, R2)."""
    _write_fragment(
        tmp_path,
        "first-party",
        [
            {
                "repo": "https://github.com/crate-ci/typos",
                "rev": "v1.28.4",
                "hooks": [{"id": "typos"}],
            }
        ],
    )
    _write_fragment(
        tmp_path,
        "third-party",
        [
            {
                "repo": "https://github.com/crate-ci/typos",
                "rev": "v1.20.0",
                "hooks": [{"id": "typos"}],
            }
        ],
    )

    bundler = _get_bundler_path()
    rc, _ = _run_bundler(tmp_path, bundler)
    assert rc == 0, "rev-pin conflict must exit 0 (highest-wins+warn, not abort)"


def test_bundler_non_dict_fragment_raises_clear_error(tmp_path: Path) -> None:
    """Bare list fragment must cause a non-zero exit with a clear error message.

    A fragment that is a top-level YAML list (not a mapping) is a malformed
    authoring error; the bundler must fail loudly rather than crash with an
    AttributeError.
    """
    frag_dir = tmp_path / ".pre-commit.d"
    frag_dir.mkdir()
    # Write a bare list — the malformed shape that triggered the bug
    (frag_dir / "bad.yaml").write_text(
        "- repo: https://github.com/pre-commit/pre-commit-hooks\n"
        "  rev: v5.0.0\n"
        "  hooks:\n"
        "  - id: trailing-whitespace\n"
    )

    bundler = _get_bundler_path()
    rc, stderr = _run_bundler(tmp_path, bundler)

    assert rc != 0, "bundler must exit non-zero for a non-dict fragment"
    assert "bad.yaml" in stderr, f"error must name the offending file; got: {stderr!r}"
    assert "repos" in stderr.lower() or "mapping" in stderr.lower(), (
        f"error must mention expected shape; got: {stderr!r}"
    )


def test_bundler_deterministic_output(tmp_path: Path) -> None:
    """Same fragment set → identical .pre-commit-config.yaml bytes on repeated runs."""
    _write_fragment(
        tmp_path,
        "mod-a",
        [
            {
                "repo": "https://github.com/pre-commit/pre-commit-hooks",
                "rev": "v5.0.0",
                "hooks": [{"id": "trailing-whitespace"}],
            }
        ],
    )
    _write_fragment(
        tmp_path,
        "mod-b",
        [
            {
                "repo": "https://github.com/gitleaks/gitleaks",
                "rev": "v8.21.2",
                "hooks": [{"id": "gitleaks"}],
            }
        ],
    )

    bundler = _get_bundler_path()
    _run_bundler(tmp_path, bundler)
    first = (tmp_path / ".pre-commit-config.yaml").read_text()

    # Remove and re-run
    (tmp_path / ".pre-commit-config.yaml").unlink()
    _run_bundler(tmp_path, bundler)
    second = (tmp_path / ".pre-commit-config.yaml").read_text()

    assert first == second, "bundler must produce identical output on repeated runs"


# ---------------------------------------------------------------------------
# Integration: end-to-end with the full precommit module + contributor modules
# ---------------------------------------------------------------------------

# Stub tasks for precommit module: skip install, only write preflight marker.
# No _post_tasks stub — the real bundler post-task from copier.yml is preserved.
_PRECOMMIT_MERGE_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'pre-commit-preflight-ok\\n' > .bailiff-precommit-preflight"
    """
)


def _build_precommit_merge_fixture(root: Path) -> TemplateRepo:
    """Build a hermetic precommit module repo: real template + stubbed tasks.

    Stubs _tasks (offline) and removes the depends_on: bailiff-mod-base edge so
    integration tests can run without base in the stack.
    """
    src = _MODULES_DIR / "bailiff-mod-precommit"
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, root, dirs_exist_ok=True)

    copier_yml = root / "copier.yml"
    text = copier_yml.read_text()
    # Strip _tasks block
    text = re.sub(r"\n_tasks:.*\Z", "\n", text, flags=re.DOTALL)
    text = text.rstrip() + "\n\n" + _PRECOMMIT_MERGE_STUB_TASKS
    # Remove depends_on: bailiff-mod-base so tests don't need base in selection
    _dep_pat = (
        r"\ndepends_on:\s*\n\s+type: yaml\s*\n\s+default:\s*\n"
        r"\s+- bailiff-mod-base\s*\n\s+when: false"
    )
    text = re.sub(
        _dep_pat,
        "\ndepends_on:\n  type: yaml\n  default: []\n  when: false",
        text,
    )
    copier_yml.write_text(text)

    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "module")
    _git(root, "tag", "v1.0.0")
    return TemplateRepo(path=root, tag="v1.0.0")


def _build_hook_contributor(
    root: Path,
    *,
    basename: str,
    repo_url: str,
    rev: str,
    hook_id: str,
) -> TemplateRepo:
    """Build a minimal module that contributes a .pre-commit.d fragment."""
    fragment_content = yaml.dump(
        {"repos": [{"repo": repo_url, "rev": rev, "hooks": [{"id": hook_id}]}]},
        default_flow_style=False,
    )
    return build_template_repo(
        root,
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                depends_on:
                  type: yaml
                  default: ["bailiff-mod-precommit"]
                  when: false
                _subdirectory: template
                """
            ),
            f"template/.pre-commit.d/{basename}.yaml.jinja": fragment_content,
        },
    )


def test_integration_bundler_runs_after_contributors(tmp_path: Path) -> None:
    """Bundler post-task runs after contributor fragments are rendered (R11 ordering).

    Stack: precommit + python-contributor + ts-contributor
    Both contributors write fragments. Bundler assembles them.
    """
    precommit = _build_precommit_merge_fixture(tmp_path / "bailiff-mod-precommit")
    python_mod = _build_hook_contributor(
        tmp_path / "bailiff-mod-python",
        basename="bailiff-mod-python",
        repo_url="https://github.com/astral-sh/ruff-pre-commit",
        rev="v0.6.9",
        hook_id="ruff",
    )
    ts_mod = _build_hook_contributor(
        tmp_path / "bailiff-mod-ts",
        basename="bailiff-mod-ts",
        repo_url="https://github.com/biomejs/biome",
        rev="v1.9.4",
        hook_id="biome-check",
    )

    trust.add_trust(precommit.url)
    trust.add_trust(python_mod.url)
    trust.add_trust(ts_mod.url)

    dest = tmp_path / "proj"
    answers = {"project_name": "demo"}
    runner.init_many(
        [
            (_record("testcat/bailiff-mod-precommit", precommit, has_tasks=True), answers),
            (_record("testcat/bailiff-mod-python", python_mod, has_tasks=False), answers),
            (_record("testcat/bailiff-mod-ts", ts_mod, has_tasks=False), answers),
        ],
        str(dest),
        today="2026-07-16",
    )

    cfg_path = dest / ".pre-commit-config.yaml"
    assert cfg_path.exists(), ".pre-commit-config.yaml must exist after bundler runs"

    config = yaml.safe_load(cfg_path.read_text())
    urls = {r["repo"] for r in config["repos"]}
    assert "https://github.com/astral-sh/ruff-pre-commit" in urls, "ruff fragment missing"
    assert "https://github.com/biomejs/biome" in urls, "biome fragment missing"


def test_integration_bundler_inert_with_no_fragments(tmp_path: Path) -> None:
    """Bundler post-task runs but is inert when no .pre-commit.d/*.yaml fragments exist.

    Selects precommit alone (no contributor modules), then verifies the bundler
    produces .pre-commit-config.yaml (precommit itself writes its own fragment).
    This also confirms the bundler does not abort on an empty fragment dir.
    """
    precommit = _build_precommit_merge_fixture(tmp_path / "bailiff-mod-precommit")
    trust.add_trust(precommit.url)

    # Build a precommit fixture that does NOT write a fragment (empty template dir)
    no_frag_root = tmp_path / "bailiff-mod-precommit-nofrag"
    src = _MODULES_DIR / "bailiff-mod-precommit"
    import shutil as _shutil

    _shutil.copytree(src, no_frag_root, dirs_exist_ok=True)
    # Remove the fragment template so no .pre-commit.d file is rendered
    for p in (no_frag_root / "template" / ".pre-commit.d").glob("*"):
        p.unlink()
    (no_frag_root / "template" / ".pre-commit.d").rmdir()
    # Stub _tasks + remove depends_on
    import re as _re

    copier_yml = no_frag_root / "copier.yml"
    text = copier_yml.read_text()
    text = _re.sub(r"\n_tasks:.*\Z", "\n", text, flags=_re.DOTALL)
    text = text.rstrip() + "\n\n" + _PRECOMMIT_MERGE_STUB_TASKS
    _dep_pat = (
        r"\ndepends_on:\s*\n\s+type: yaml\s*\n\s+default:\s*\n"
        r"\s+- bailiff-mod-base\s*\n\s+when: false"
    )
    text = _re.sub(
        _dep_pat,
        "\ndepends_on:\n  type: yaml\n  default: []\n  when: false",
        text,
    )
    copier_yml.write_text(text)
    _git(no_frag_root, "init", "-q")
    _git(no_frag_root, "add", "-A")
    _git(no_frag_root, "commit", "-qm", "module")
    _git(no_frag_root, "tag", "v1.0.0")
    no_frag = TemplateRepo(path=no_frag_root, tag="v1.0.0")
    trust.add_trust(no_frag.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [
            (
                _record("testcat/bailiff-mod-precommit", no_frag, has_tasks=True),
                {"project_name": "demo"},
            ),
        ],
        str(dest),
        today="2026-07-16",
    )

    # Bundler ran but was inert (no fragments → no config written)
    assert not (dest / ".pre-commit-config.yaml").exists(), (
        ".pre-commit-config.yaml must not exist when no fragments were written"
    )


def test_integration_inert_when_precommit_absent(tmp_path: Path) -> None:
    """When precommit module is not in the stack, no bundler runs → no .pre-commit-config.yaml."""
    # A plain module with no precommit involvement
    plain_mod = build_template_repo(
        tmp_path / "mod-plain",
        files={
            "copier.yml": "project_name:\n  type: str\n_subdirectory: template\n",
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )
    trust.add_trust(plain_mod.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [(_record("testcat/mod-plain", plain_mod), {"project_name": "demo"})],
        str(dest),
        today="2026-07-16",
    )

    assert not (dest / ".pre-commit-config.yaml").exists(), (
        "bundler must not run when precommit module is absent"
    )
    assert not (dest / ".pre-commit.d").exists()


def test_integration_config_consistent_reproduce(tmp_path: Path) -> None:
    """Reproduce produces config-consistent .pre-commit-config.yaml (SC-004).

    Same hooks present after reproduce; no duplicate repos.
    """
    precommit = _build_precommit_merge_fixture(tmp_path / "bailiff-mod-precommit")
    python_mod = _build_hook_contributor(
        tmp_path / "bailiff-mod-python",
        basename="bailiff-mod-python",
        repo_url="https://github.com/astral-sh/ruff-pre-commit",
        rev="v0.6.9",
        hook_id="ruff",
    )

    trust.add_trust(precommit.url)
    trust.add_trust(python_mod.url)

    dest = tmp_path / "proj"
    answers = {"project_name": "demo"}
    runner.init_many(
        [
            (_record("testcat/bailiff-mod-precommit", precommit, has_tasks=True), answers),
            (_record("testcat/bailiff-mod-python", python_mod, has_tasks=False), answers),
        ],
        str(dest),
        today="2026-07-16",
    )

    after_init = yaml.safe_load((dest / ".pre-commit-config.yaml").read_text())
    init_urls = [r["repo"] for r in after_init["repos"]]

    # Reproduce
    runner.reproduce_many(str(dest))

    after_repro = yaml.safe_load((dest / ".pre-commit-config.yaml").read_text())
    repro_urls = [r["repo"] for r in after_repro["repos"]]

    # Config-consistent: same set of repo URLs
    assert set(init_urls) == set(repro_urls), (
        f"reproduce changed the hook set: init={init_urls} repro={repro_urls}"
    )

    # No duplication: each URL appears exactly once
    for url in repro_urls:
        count = repro_urls.count(url)
        assert count == 1, f"repo {url!r} duplicated {count} times after reproduce"


def test_integration_order_independent_same_config(tmp_path: Path) -> None:
    """Fragment set in any contribution order → config-consistent result.

    Two contributor modules; their fragment file names differ to exercise
    filesystem sort. The same URLs must appear in the output regardless of
    which contributor was ordered first.
    """
    precommit_a = _build_precommit_merge_fixture(tmp_path / "precommit-a" / "bailiff-mod-precommit")
    ruff_mod = _build_hook_contributor(
        tmp_path / "precommit-a" / "bailiff-mod-python",
        basename="bailiff-mod-python",
        repo_url="https://github.com/astral-sh/ruff-pre-commit",
        rev="v0.6.9",
        hook_id="ruff",
    )
    mypy_mod = _build_hook_contributor(
        tmp_path / "precommit-a" / "bailiff-mod-mypy",
        basename="bailiff-mod-mypy",
        repo_url="https://github.com/pre-commit/mirrors-mypy",
        rev="v1.11.2",
        hook_id="mypy",
    )

    trust.add_trust(precommit_a.url)
    trust.add_trust(ruff_mod.url)
    trust.add_trust(mypy_mod.url)

    dest_a = tmp_path / "proj-a"
    answers = {"project_name": "demo"}
    runner.init_many(
        [
            (_record("testcat/bailiff-mod-precommit", precommit_a, has_tasks=True), answers),
            (_record("testcat/bailiff-mod-python", ruff_mod, has_tasks=False), answers),
            (_record("testcat/bailiff-mod-mypy", mypy_mod, has_tasks=False), answers),
        ],
        str(dest_a),
        today="2026-07-16",
    )

    config_a = yaml.safe_load((dest_a / ".pre-commit-config.yaml").read_text())
    urls_a = {r["repo"] for r in config_a["repos"]}

    # Second run with reversed contributor order
    precommit_b = _build_precommit_merge_fixture(tmp_path / "precommit-b" / "bailiff-mod-precommit")
    ruff_mod_b = _build_hook_contributor(
        tmp_path / "precommit-b" / "bailiff-mod-python",
        basename="bailiff-mod-python",
        repo_url="https://github.com/astral-sh/ruff-pre-commit",
        rev="v0.6.9",
        hook_id="ruff",
    )
    mypy_mod_b = _build_hook_contributor(
        tmp_path / "precommit-b" / "bailiff-mod-mypy",
        basename="bailiff-mod-mypy",
        repo_url="https://github.com/pre-commit/mirrors-mypy",
        rev="v1.11.2",
        hook_id="mypy",
    )

    trust.add_trust(precommit_b.url)
    trust.add_trust(ruff_mod_b.url)
    trust.add_trust(mypy_mod_b.url)

    dest_b = tmp_path / "proj-b"
    # Reverse contributor order in selection
    answers_b = {"project_name": "demo"}
    runner.init_many(
        [
            (_record("testcat/bailiff-mod-precommit", precommit_b, has_tasks=True), answers_b),
            (_record("testcat/bailiff-mod-mypy", mypy_mod_b, has_tasks=False), answers_b),
            (_record("testcat/bailiff-mod-python", ruff_mod_b, has_tasks=False), answers_b),
        ],
        str(dest_b),
        today="2026-07-16",
    )

    config_b = yaml.safe_load((dest_b / ".pre-commit-config.yaml").read_text())
    urls_b = {r["repo"] for r in config_b["repos"]}

    assert urls_a == urls_b, f"order-dependent output: urls_a={urls_a} vs urls_b={urls_b}"
