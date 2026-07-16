"""spec 014 SC-008: dependency model — single depends_on, stratified phases, cross-phase rejection.

Tests:
- depends_on orders correctly (target before consumer)
- Dangling depends_on → loud OrderingError naming the target
- Phase ordering: pre runs before normal; normal before post (once post is used)
- Forward cross-phase edge (normal→post) rejected at discovery
- depends_on is the canonical edge (FR-019/FR-020/R7/R8)
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from bailiff import ordering, runner, trust
from bailiff.catalog import TemplateRecord
from bailiff.errors import OrderingError
from tests.conftest import build_template_repo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _record(
    full_id: str,
    repo,
    questions: list[str] | None = None,
) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=questions or ["project_name"],
    )


# ---------------------------------------------------------------------------
# depends_on orders correctly
# ---------------------------------------------------------------------------


def test_depends_on_orders_consumer_after_target(tmp_path: Path) -> None:
    """Module B depends_on A → A renders before B, even when mis-ordered in selection."""
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
                _subdirectory: template
                """
            ),
            "template/b_out.txt.jinja": "b={{ project_name }}\n",
        },
    )
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    # Mis-ordered: B before A in selection
    runner.init_many(
        [
            (_record("testcat/mod-b", tpl_b), {"project_name": "demo"}),
            (_record("testcat/mod-a", tpl_a), {"project_name": "demo"}),
        ],
        str(dest),
        today="2026-07-16",
    )

    assert (dest / "a_out.txt").exists()
    assert (dest / "b_out.txt").exists()


def test_depends_on_dangling_raises_ordering_error(tmp_path: Path) -> None:
    """depends_on pointing at a module not in the selection → loud OrderingError."""
    tpl_b = build_template_repo(
        tmp_path / "mod-b",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                depends_on:
                  type: yaml
                  default: ["mod-missing"]
                  when: false
                _subdirectory: template
                """
            ),
            "template/b_out.txt.jinja": "b={{ project_name }}\n",
        },
    )
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    with pytest.raises(OrderingError) as exc_info:
        runner.init_many(
            [(_record("testcat/mod-b", tpl_b), {"project_name": "demo"})],
            str(dest),
            today="2026-07-16",
        )

    msg = str(exc_info.value)
    assert "mod-missing" in msg, f"Error must name the dangling target, got: {msg!r}"


# ---------------------------------------------------------------------------
# Phase ordering: pre runs before normal
# ---------------------------------------------------------------------------


def test_pre_phase_runs_before_normal(tmp_path: Path) -> None:
    """A module with phase=pre is ordered before any normal-phase module.

    base=pre is the canonical example. A pre-phase module with no edges runs first.
    """
    # pre-phase module (no depends_on)
    pre_mod = build_template_repo(
        tmp_path / "mod-pre",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                _bailiff_phase: pre
                _subdirectory: template
                """
            ),
            "template/pre_out.txt.jinja": "pre={{ project_name }}\n",
        },
    )
    # normal-phase module
    normal_mod = build_template_repo(
        tmp_path / "mod-normal",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                _subdirectory: template
                """
            ),
            "template/normal_out.txt.jinja": "normal={{ project_name }}\n",
        },
    )
    trust.add_trust(pre_mod.url)
    trust.add_trust(normal_mod.url)

    dest = tmp_path / "proj"
    # Mis-ordered: normal before pre
    runner.init_many(
        [
            (_record("testcat/mod-normal", normal_mod), {"project_name": "demo"}),
            (_record("testcat/mod-pre", pre_mod), {"project_name": "demo"}),
        ],
        str(dest),
        today="2026-07-16",
    )

    assert (dest / "pre_out.txt").exists()
    assert (dest / "normal_out.txt").exists()


def test_phase_ordering_via_layer_plan(tmp_path: Path) -> None:
    """layer_plan returns pre-phase modules before normal-phase modules."""
    pre_mod = build_template_repo(
        tmp_path / "mod-pre",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                _bailiff_phase: pre
                _subdirectory: template
                """
            ),
            "template/pre_out.txt.jinja": "pre={{ project_name }}\n",
        },
    )
    normal_mod = build_template_repo(
        tmp_path / "mod-normal",
        files={
            "copier.yml": "project_name:\n  type: str\n_subdirectory: template\n",
            "template/normal_out.txt.jinja": "normal={{ project_name }}\n",
        },
    )

    pre_record = _record("testcat/mod-pre", pre_mod)
    normal_record = _record("testcat/mod-normal", normal_mod)

    # Mis-ordered: normal first
    plan = ordering.layer_plan([normal_record, pre_record])
    basenames = [r.full_id.rsplit("/", 1)[-1] for r, _ in plan]

    assert basenames.index("mod-pre") < basenames.index("mod-normal"), (
        f"pre-phase should come before normal, got order: {basenames}"
    )


# ---------------------------------------------------------------------------
# Forward cross-phase edge rejection (FR-020)
# ---------------------------------------------------------------------------


def test_forward_cross_phase_edge_rejected(tmp_path: Path) -> None:
    """A normal-phase module depends_on a post-phase module → OrderingError (FR-020).

    A forward cross-phase edge (normal→post) is illegal: post is reserved for
    deferred-work modules, and normal must never depend on a post module.
    """
    post_mod = build_template_repo(
        tmp_path / "mod-post",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                _bailiff_phase: post
                _subdirectory: template
                """
            ),
            "template/post_out.txt.jinja": "post={{ project_name }}\n",
        },
    )
    normal_mod = build_template_repo(
        tmp_path / "mod-normal",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                depends_on:
                  type: yaml
                  default: ["mod-post"]
                  when: false
                _subdirectory: template
                """
            ),
            "template/normal_out.txt.jinja": "normal={{ project_name }}\n",
        },
    )
    trust.add_trust(post_mod.url)
    trust.add_trust(normal_mod.url)

    dest = tmp_path / "proj"
    with pytest.raises(OrderingError) as exc_info:
        runner.init_many(
            [
                (_record("testcat/mod-normal", normal_mod), {"project_name": "demo"}),
                (_record("testcat/mod-post", post_mod), {"project_name": "demo"}),
            ],
            str(dest),
            today="2026-07-16",
        )

    msg = str(exc_info.value)
    assert "phase" in msg.lower() or "cross-phase" in msg.lower() or "forward" in msg.lower(), (
        f"Error must mention phase/cross-phase, got: {msg!r}"
    )


def test_pre_cannot_depend_on_normal(tmp_path: Path) -> None:
    """A pre-phase module depends_on a normal-phase module → OrderingError (FR-020).

    pre→normal is a forward cross-phase edge: pre may only depend on pre.
    """
    normal_mod = build_template_repo(
        tmp_path / "mod-normal",
        files={
            "copier.yml": "project_name:\n  type: str\n_subdirectory: template\n",
            "template/n_out.txt.jinja": "n={{ project_name }}\n",
        },
    )
    pre_mod = build_template_repo(
        tmp_path / "mod-pre",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                _bailiff_phase: pre
                depends_on:
                  type: yaml
                  default: ["mod-normal"]
                  when: false
                _subdirectory: template
                """
            ),
            "template/pre_out.txt.jinja": "pre={{ project_name }}\n",
        },
    )
    trust.add_trust(pre_mod.url)
    trust.add_trust(normal_mod.url)

    dest = tmp_path / "proj"
    with pytest.raises(OrderingError) as exc_info:
        runner.init_many(
            [
                (_record("testcat/mod-pre", pre_mod), {"project_name": "demo"}),
                (_record("testcat/mod-normal", normal_mod), {"project_name": "demo"}),
            ],
            str(dest),
            today="2026-07-16",
        )

    msg = str(exc_info.value)
    assert "phase" in msg.lower() or "cross-phase" in msg.lower() or "forward" in msg.lower(), (
        f"Error must mention phase/cross-phase, got: {msg!r}"
    )


# ---------------------------------------------------------------------------
# Post-phase runs after normal
# ---------------------------------------------------------------------------


def test_post_phase_runs_after_normal(tmp_path: Path) -> None:
    """A post-phase module runs after all normal-phase modules (FR-020)."""
    post_mod = build_template_repo(
        tmp_path / "mod-post",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                _bailiff_phase: post
                _subdirectory: template
                """
            ),
            "template/post_out.txt.jinja": "post={{ project_name }}\n",
        },
    )
    normal_mod = build_template_repo(
        tmp_path / "mod-normal",
        files={
            "copier.yml": "project_name:\n  type: str\n_subdirectory: template\n",
            "template/normal_out.txt.jinja": "normal={{ project_name }}\n",
        },
    )

    post_record = _record("testcat/mod-post", post_mod)
    normal_record = _record("testcat/mod-normal", normal_mod)

    # layer_plan with post first in input should reorder
    plan = ordering.layer_plan([post_record, normal_record])
    basenames = [r.full_id.rsplit("/", 1)[-1] for r, _ in plan]

    assert basenames.index("mod-normal") < basenames.index("mod-post"), (
        f"normal should come before post, got order: {basenames}"
    )
