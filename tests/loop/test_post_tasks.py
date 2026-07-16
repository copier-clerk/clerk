"""spec 014 FR-021/R11: _post_tasks — deferred work after the render loop.

Tests:
- _post_tasks from a module run AFTER the whole render loop (not inline per-layer)
- _post_tasks run in depends_on order (module DAG + basename tie-break)
- _post_tasks run on BOTH init_many AND reproduce_many
- A failing _post_task (non-zero exit) raises BailiffError (FIX 2)
- Untrusted-source _post_tasks are blocked by the trust gate (FIX 4)
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from bailiff.errors import BailiffError, UntrustedSourceError
from tests.conftest import build_template_repo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _record(
    full_id: str, repo, *, has_tasks: bool = False, questions: list[str] | None = None
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


# ---------------------------------------------------------------------------
# _post_tasks run AFTER the render loop (not inline)
# ---------------------------------------------------------------------------


def test_post_task_runs_after_render_loop(tmp_path: Path) -> None:
    """_post_tasks run AFTER all layers have rendered.

    The post-task writes a marker file that DEPENDS ON another layer's output.
    If the post-task ran inline (at layer render time), the other layer's output
    would not yet exist and the task would fail or produce wrong output.

    Arrangement: layer A writes a_out.txt; layer B has a _post_task that reads
    a_out.txt and writes post_result.txt. If the task runs inline with B's render
    (before A runs), a_out.txt won't exist. After the full loop, it will.
    """
    tpl_a = build_template_repo(
        tmp_path / "mod-a",
        files={
            "copier.yml": "project_name:\n  type: str\n_subdirectory: template\n",
            "template/a_out.txt.jinja": "a={{ project_name }}\n",
        },
    )
    # B has a _post_task that writes a file proving it runs after A
    tpl_b = build_template_repo(
        tmp_path / "mod-b",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                depends_on:
                  type: yaml
                  default: ["mod-a"]
                  when: false
                _post_tasks:
                  - "test -f a_out.txt && echo post_task_ran > post_result.txt"
                _subdirectory: template
                """
            ),
            "template/b_out.txt.jinja": "b={{ project_name }}\n",
        },
    )
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [
            (_record("testcat/mod-a", tpl_a, has_tasks=False), {"project_name": "demo"}),
            (_record("testcat/mod-b", tpl_b, has_tasks=True), {"project_name": "demo"}),
        ],
        str(dest),
        today="2026-07-16",
    )

    # post_result.txt must exist — post_task ran and a_out.txt existed when it ran
    assert (dest / "post_result.txt").exists(), (
        "post_result.txt missing — _post_task either did not run or ran before a_out.txt existed"
    )
    assert "post_task_ran" in (dest / "post_result.txt").read_text()


def test_post_tasks_run_after_all_layers(tmp_path: Path) -> None:
    """_post_tasks from a module run after ALL layers have rendered.

    Two normal modules + one with a post_task that requires both outputs.
    The post_task checks for both outputs — proves it runs after the full loop.
    """
    tpl_a = build_template_repo(
        tmp_path / "mod-a",
        files={
            "copier.yml": "project_name:\n  type: str\n_subdirectory: template\n",
            "template/a_out.txt.jinja": "a={{ project_name }}\n",
        },
    )
    tpl_b = build_template_repo(
        tmp_path / "mod-b",
        files={
            "copier.yml": "project_name:\n  type: str\n_subdirectory: template\n",
            "template/b_out.txt.jinja": "b={{ project_name }}\n",
        },
    )
    # Merger module: has a post_task that requires both a_out.txt and b_out.txt
    tpl_merger = build_template_repo(
        tmp_path / "mod-merger",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                _post_tasks:
                  - "test -f a_out.txt && test -f b_out.txt && echo merged > merged.txt"
                _subdirectory: template
                """
            ),
            "template/merger_out.txt.jinja": "merger={{ project_name }}\n",
        },
    )
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)
    trust.add_trust(tpl_merger.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [
            (_record("testcat/mod-a", tpl_a), {"project_name": "demo"}),
            (_record("testcat/mod-b", tpl_b), {"project_name": "demo"}),
            (_record("testcat/mod-merger", tpl_merger, has_tasks=True), {"project_name": "demo"}),
        ],
        str(dest),
        today="2026-07-16",
    )

    assert (dest / "merged.txt").exists(), "merged.txt missing — post_task ran before all layers"
    assert "merged" in (dest / "merged.txt").read_text()


# ---------------------------------------------------------------------------
# _post_tasks run on reproduce_many too (FR-021)
# ---------------------------------------------------------------------------


def test_post_tasks_run_on_reproduce(tmp_path: Path) -> None:
    """_post_tasks run on reproduce_many, not just init_many (FR-021).

    copier _tasks run on reproduce, so post_tasks must too.
    """
    tpl_a = build_template_repo(
        tmp_path / "mod-a",
        files={
            "copier.yml": "project_name:\n  type: str\n_subdirectory: template\n",
            "template/a_out.txt.jinja": "a={{ project_name }}\n",
        },
    )
    tpl_b = build_template_repo(
        tmp_path / "mod-b",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                depends_on:
                  type: yaml
                  default: ["mod-a"]
                  when: false
                _post_tasks:
                  - "echo post_ran >> post_log.txt"
                _subdirectory: template
                """
            ),
            "template/b_out.txt.jinja": "b={{ project_name }}\n",
        },
    )
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [
            (_record("testcat/mod-a", tpl_a), {"project_name": "demo"}),
            (_record("testcat/mod-b", tpl_b, has_tasks=True), {"project_name": "demo"}),
        ],
        str(dest),
        today="2026-07-16",
    )
    assert (dest / "post_log.txt").exists(), "post_log.txt missing after init"
    init_count = (dest / "post_log.txt").read_text().count("post_ran")
    assert init_count >= 1, "post_task did not run at init"

    # Now reproduce — post_task must run again
    runner.reproduce_many(str(dest))
    after_count = (dest / "post_log.txt").read_text().count("post_ran")
    assert after_count > init_count, (
        f"post_task did not run on reproduce (count before={init_count}, after={after_count})"
    )


# ---------------------------------------------------------------------------
# _post_tasks in depends_on order
# ---------------------------------------------------------------------------


def test_post_tasks_ordered_by_depends_on(tmp_path: Path) -> None:
    """_post_tasks run in module depends_on order (DAG + basename tie-break).

    Module 'merger-b' depends_on 'merger-a'. The post_task of merger-b must run
    after the post_task of merger-a (which writes a prerequisite file).
    """
    tpl_ma = build_template_repo(
        tmp_path / "merger-a",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                _post_tasks:
                  - "echo step_a > order_log.txt"
                _subdirectory: template
                """
            ),
            "template/ma_out.txt.jinja": "ma={{ project_name }}\n",
        },
    )
    tpl_mb = build_template_repo(
        tmp_path / "merger-b",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                depends_on:
                  type: yaml
                  default: ["merger-a"]
                  when: false
                _post_tasks:
                  - "echo step_b >> order_log.txt"
                _subdirectory: template
                """
            ),
            "template/mb_out.txt.jinja": "mb={{ project_name }}\n",
        },
    )
    trust.add_trust(tpl_ma.url)
    trust.add_trust(tpl_mb.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [
            (_record("testcat/merger-a", tpl_ma, has_tasks=True), {"project_name": "demo"}),
            (_record("testcat/merger-b", tpl_mb, has_tasks=True), {"project_name": "demo"}),
        ],
        str(dest),
        today="2026-07-16",
    )

    assert (dest / "order_log.txt").exists()
    log = (dest / "order_log.txt").read_text()
    assert log.index("step_a") < log.index("step_b"), (
        f"step_a must precede step_b in order_log.txt, got:\n{log}"
    )


# ---------------------------------------------------------------------------
# FIX 2: failing _post_task raises BailiffError
# ---------------------------------------------------------------------------


def test_failing_post_task_raises(tmp_path: Path) -> None:
    """A _post_task that exits non-zero raises BailiffError (not silent failure).

    Previously check=False swallowed failures. After FIX 2 the runner raises.
    """
    tpl = build_template_repo(
        tmp_path / "mod-failing",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                _post_tasks:
                  - "exit 1"
                _subdirectory: template
                """
            ),
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )
    trust.add_trust(tpl.url)

    dest = tmp_path / "proj"
    with pytest.raises(BailiffError) as exc_info:
        runner.init_many(
            [(_record("testcat/mod-failing", tpl, has_tasks=True), {"project_name": "demo"})],
            str(dest),
            today="2026-07-16",
        )

    msg = str(exc_info.value)
    assert "post_task" in msg or "_post_task" in msg or "exit code" in msg, (
        f"BailiffError must mention post_task/exit code, got: {msg!r}"
    )


# ---------------------------------------------------------------------------
# FIX 4: untrusted source _post_tasks blocked by trust gate
# ---------------------------------------------------------------------------


def test_untrusted_source_post_task_blocked(tmp_path: Path) -> None:
    """_post_tasks from an untrusted source are blocked by the trust gate (Constitution V/FIX 4)."""
    tpl = build_template_repo(
        tmp_path / "mod-untrusted",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                _post_tasks:
                  - "echo should-not-run > post_ran.txt"
                _subdirectory: template
                """
            ),
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )
    # Deliberately do NOT add trust for tpl.url

    dest = tmp_path / "proj"
    with pytest.raises(UntrustedSourceError):
        runner.init_many(
            [(_record("testcat/mod-untrusted", tpl, has_tasks=True), {"project_name": "demo"})],
            str(dest),
            today="2026-07-16",
        )

    # post_ran.txt must NOT exist — trust gate fired before execution
    assert not (dest / "post_ran.txt").exists(), (
        "post_ran.txt exists — untrusted _post_task executed despite no trust"
    )
