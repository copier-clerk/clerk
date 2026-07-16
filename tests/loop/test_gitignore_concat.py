"""spec 014 T047 / SC-005 / FR-013: gitignore idempotent ordered-concat.

base's _post_task folds .gitignore.d/* fragments into .gitignore using delimited
blocks (# >>> <module> >>> … # <<< <module> <<<). Reproduce must not duplicate
entries (config-consistent, not byte-identical).

Tests:
- base + two contributors → fragments folded into .gitignore via delimited blocks
- Reproduce twice → no duplicates (idempotent replace, not append)
- Fragment order is deterministic (sorted by filename)
- Module with no .gitignore.d contribution → concat is a no-op on .gitignore
- Empty fragment skipped (no empty block written)
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from tests.conftest import build_template_repo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _record(full_id: str, repo) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=["project_name"],
    )


# Minimal base module with the gitignore concat _post_task (mirrors real base).
_BASE_POST_TASK = dedent(
    """\
    _post_tasks:
      - |-
        python3 -c "
        import pathlib, re, sys
        gi = pathlib.Path('.gitignore')
        d = pathlib.Path('.gitignore.d')
        if not d.is_dir():
            sys.exit(0)
        fragments = sorted(d.iterdir())
        if not fragments:
            sys.exit(0)
        base = gi.read_text() if gi.exists() else ''
        for frag in fragments:
            module = frag.name
            content = frag.read_text().rstrip()
            if not content:
                continue
            block = '# >>> ' + module + ' >>>\\n' + content + '\\n# <<< ' + module + ' <<<'
            pattern = re.compile(
                r'# >>> ' + re.escape(module) + r' >>>.*?# <<< ' + re.escape(module) + r' <<<',
                re.DOTALL,
            )
            if pattern.search(base):
                base = pattern.sub(block, base)
            else:
                ends2 = base.endswith('\\n\\n')
                ends1 = base.endswith('\\n')
                sep = '' if ends2 else ('\\n' if ends1 else '\\n\\n')
                base = base + sep + block + '\\n'
        gi.write_text(base)
        "
    """
)


def _make_base_module(root: Path) -> object:
    """Minimal base with .gitignore seed task + gitignore concat _post_task."""
    copier_yml = (
        dedent(
            """\
        project_name:
          type: str
        _subdirectory: template
        _bailiff_phase: pre
        _tasks:
          - "test -f .gitignore || printf '# base gitignore\\n' > .gitignore"
        """
        )
        + _BASE_POST_TASK
    )
    return build_template_repo(
        root / "bailiff-mod-base",
        files={"copier.yml": copier_yml},
    )


def _make_contributor(
    root: Path,
    name: str,
    fragment_lines: str,
    *,
    depends_on: str = "bailiff-mod-base",
) -> object:
    """Module that contributes a .gitignore.d/<name> fragment."""
    copier_yml = dedent(
        f"""\
        project_name:
          type: str
        depends_on:
          type: yaml
          default: ["{depends_on}"]
          when: false
        _subdirectory: template
        """
    )
    return build_template_repo(
        root / name,
        files={
            "copier.yml": copier_yml,
            f"template/.gitignore.d/{name}": fragment_lines,
        },
    )


# ---------------------------------------------------------------------------
# AS1: fragments folded into .gitignore via delimited blocks
# ---------------------------------------------------------------------------


def test_fragments_folded_into_gitignore(tmp_path: Path) -> None:
    """base + two contributors → .gitignore contains delimited blocks for each fragment."""
    dest = tmp_path / "proj"
    base = _make_base_module(tmp_path / "repos")
    python = _make_contributor(tmp_path / "repos", "bailiff-mod-python", "__pycache__/\n*.pyc\n")
    rust = _make_contributor(tmp_path / "repos", "bailiff-mod-rust", "target/\n")

    for repo in (base, python, rust):
        trust.add_trust(repo.url)

    selection = [
        (_record(f"myorg/{r.path.name}", r), {"project_name": "myproj"})
        for r in (base, python, rust)
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")

    gi = (dest / ".gitignore").read_text()

    assert "# >>> bailiff-mod-python >>>" in gi, "python block opener missing"
    assert "__pycache__/" in gi, "python fragment content missing"
    assert "# <<< bailiff-mod-python <<<" in gi, "python block closer missing"

    assert "# >>> bailiff-mod-rust >>>" in gi, "rust block opener missing"
    assert "target/" in gi, "rust fragment content missing"
    assert "# <<< bailiff-mod-rust <<<" in gi, "rust block closer missing"


# ---------------------------------------------------------------------------
# AS2: reproduce twice → no duplicates (idempotent)
# ---------------------------------------------------------------------------


def test_reproduce_twice_no_duplicates(tmp_path: Path) -> None:
    """Reproduce twice: delimited blocks are replaced, not appended — no duplicates."""
    dest = tmp_path / "proj"
    base = _make_base_module(tmp_path / "repos")
    python = _make_contributor(tmp_path / "repos", "bailiff-mod-python", "__pycache__/\n*.pyc\n")

    for repo in (base, python):
        trust.add_trust(repo.url)

    selection = [
        (_record(f"myorg/{r.path.name}", r), {"project_name": "myproj"}) for r in (base, python)
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")
    runner.reproduce_many(str(dest))
    runner.reproduce_many(str(dest))

    gi = (dest / ".gitignore").read_text()

    # Each block opener must appear exactly once.
    assert gi.count("# >>> bailiff-mod-python >>>") == 1, "python block duplicated after reproduce"
    assert gi.count("__pycache__/") == 1, "__pycache__/ entry duplicated after reproduce"


# ---------------------------------------------------------------------------
# AS3: fragment order is deterministic (sorted by filename)
# ---------------------------------------------------------------------------


def test_fragment_order_deterministic(tmp_path: Path) -> None:
    """Fragments are folded in sorted filename order regardless of module render order."""
    dest = tmp_path / "proj"
    base = _make_base_module(tmp_path / "repos")
    # "zzz" sorts after "aaa" — force reverse registration order via depends_on.
    aaa = _make_contributor(tmp_path / "repos", "bailiff-mod-aaa", "# aaa ignore\n")
    zzz = _make_contributor(tmp_path / "repos", "bailiff-mod-zzz", "# zzz ignore\n")

    for repo in (base, aaa, zzz):
        trust.add_trust(repo.url)

    # Deliberately register zzz before aaa in selection order.
    selection = [
        (_record(f"myorg/{r.path.name}", r), {"project_name": "myproj"}) for r in (base, zzz, aaa)
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")

    gi = (dest / ".gitignore").read_text()
    pos_aaa = gi.index("# >>> bailiff-mod-aaa >>>")
    pos_zzz = gi.index("# >>> bailiff-mod-zzz >>>")
    assert pos_aaa < pos_zzz, "fragments must be folded in sorted filename order"


# ---------------------------------------------------------------------------
# AS4: no .gitignore.d/ → concat is a no-op
# ---------------------------------------------------------------------------


def test_no_fragments_noop(tmp_path: Path) -> None:
    """base alone with no .gitignore.d/ contributors → .gitignore unchanged by post-task."""
    dest = tmp_path / "proj"
    base = _make_base_module(tmp_path / "repos")
    trust.add_trust(base.url)

    selection = [(_record("myorg/bailiff-mod-base", base), {"project_name": "myproj"})]
    runner.init_many(selection, str(dest), today="2026-07-14")

    gi = (dest / ".gitignore").read_text()
    assert "# >>> " not in gi, "no fragment blocks expected when .gitignore.d/ is absent"


# ---------------------------------------------------------------------------
# AS5: empty fragment skipped
# ---------------------------------------------------------------------------


def test_empty_fragment_skipped(tmp_path: Path) -> None:
    """A contributor with an empty .gitignore.d file produces no block in .gitignore."""
    dest = tmp_path / "proj"
    base = _make_base_module(tmp_path / "repos")
    empty = _make_contributor(tmp_path / "repos", "bailiff-mod-empty", "")

    for repo in (base, empty):
        trust.add_trust(repo.url)

    selection = [
        (_record(f"myorg/{r.path.name}", r), {"project_name": "myproj"}) for r in (base, empty)
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")

    gi = (dest / ".gitignore").read_text()
    assert "# >>> bailiff-mod-empty >>>" not in gi, (
        "empty fragment must not produce a delimited block"
    )
