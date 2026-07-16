"""spec 014 SC-002: _external_data enforcement — hard data-dependency (FR-006/R6/R9).

Tests:
- Producer present in selection → resolves; producer ordered before consumer
- Producer ABSENT → loud OrderingError naming the alias
- Non-base producer (e.g. moon) resolves via the same mechanism
- Non-convention path lint: _external_data value not matching .copier-answers.<basename>.yml → error
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from bailiff.errors import OrderingError
from tests.conftest import (
    build_template_repo,
)


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _record(full_id: str, repo, questions: list[str] | None = None) -> TemplateRecord:
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
# SC-002 AS1: producer present → consumer reads fact, ordered after producer
# ---------------------------------------------------------------------------


def test_external_data_producer_present_resolves(tmp_path: Path) -> None:
    """Consumer with _external_data alias resolves producer's fact when producer is in stack.

    copier handles the actual data-passing via _external_data at render time.
    bailiff's role: detect the alias→basename mapping and enforce ordering.
    """
    # Producer writes project_name to its answers file
    producer = build_template_repo(
        tmp_path / "mod-base",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                  default: proj
                _subdirectory: template
                """
            ),
            "template/base_out.txt.jinja": "base={{ project_name }}\n",
        },
    )
    # Consumer declares _external_data alias at producer's answers file
    consumer = build_template_repo(
        tmp_path / "mod-consumer",
        files={
            "copier.yml": dedent(
                """\
                _external_data:
                  base: .copier-answers.mod-base.yml
                own_key:
                  type: str
                  default: own
                _subdirectory: template
                """
            ),
            "template/consumer_out.txt.jinja": "own={{ own_key }}\n",
        },
    )
    trust.add_trust(producer.url)
    trust.add_trust(consumer.url)

    dest = tmp_path / "proj"
    selection = [
        (_record("testcat/mod-consumer", consumer, questions=["own_key"]), {}),
        (
            _record("testcat/mod-base", producer, questions=["project_name"]),
            {"project_name": "myproj"},
        ),
    ]
    # Must NOT raise OrderingError — producer is present
    results = runner.init_many(selection, str(dest), today="2026-07-16")
    assert len(results) == 2

    # Producer answers file must exist
    assert (dest / ".copier-answers.mod-base.yml").exists()
    assert (dest / ".copier-answers.mod-consumer.yml").exists()


def test_external_data_producer_absent_raises_ordering_error(tmp_path: Path) -> None:
    """Consumer with _external_data alias for absent producer → loud OrderingError.

    copier's own behavior would silently return {} → empty render. bailiff must produce
    the error copier will not (FR-006 inverted, SC-002 AS2).
    """
    # Consumer declares alias at mod-base, but mod-base is NOT in the selection
    consumer = build_template_repo(
        tmp_path / "mod-consumer",
        files={
            "copier.yml": dedent(
                """\
                _external_data:
                  base: .copier-answers.mod-base.yml
                own_key:
                  type: str
                  default: own
                _subdirectory: template
                """
            ),
            "template/consumer_out.txt.jinja": "own={{ own_key }}\n",
        },
    )
    trust.add_trust(consumer.url)

    dest = tmp_path / "proj"
    selection = [
        # Only consumer; no producer (mod-base absent)
        (_record("testcat/mod-consumer", consumer, questions=["own_key"]), {}),
    ]
    with pytest.raises(OrderingError) as exc_info:
        runner.init_many(selection, str(dest), today="2026-07-16")

    # Error must name the alias / missing producer
    msg = str(exc_info.value)
    assert "mod-base" in msg or "base" in msg, (
        f"OrderingError must name the missing producer alias, got: {msg!r}"
    )


def test_external_data_ordering_error_names_alias(tmp_path: Path) -> None:
    """The OrderingError for a missing _external_data producer names the alias key."""
    consumer = build_template_repo(
        tmp_path / "mod-ts",
        files={
            "copier.yml": dedent(
                """\
                _external_data:
                  precommit: .copier-answers.mod-precommit.yml
                own:
                  type: str
                  default: own
                _subdirectory: template
                """
            ),
            "template/out.txt.jinja": "x={{ own }}\n",
        },
    )
    trust.add_trust(consumer.url)

    dest = tmp_path / "proj"
    with pytest.raises(OrderingError) as exc_info:
        runner.init_many(
            [(_record("testcat/mod-ts", consumer, questions=["own"]), {})],
            str(dest),
            today="2026-07-16",
        )

    msg = str(exc_info.value)
    # Must reference either the alias name or the missing producer basename
    assert "precommit" in msg or "mod-precommit" in msg, (
        f"Error must name the alias/producer, got: {msg!r}"
    )


# ---------------------------------------------------------------------------
# SC-002 AS3: non-base producer (moon) resolves via same mechanism
# ---------------------------------------------------------------------------


def test_external_data_non_base_producer_resolves(tmp_path: Path) -> None:
    """Non-base producer (moon) resolves when present; mechanism is not base-specific."""
    # Moon-like producer
    moon_producer = build_template_repo(
        tmp_path / "mod-moon",
        files={
            "copier.yml": dedent(
                """\
                monorepo_tool:
                  type: str
                  default: moon
                _subdirectory: template
                """
            ),
            "template/moon_out.txt.jinja": "tool={{ monorepo_tool }}\n",
        },
    )
    # Consumer reads from moon
    ci_consumer = build_template_repo(
        tmp_path / "mod-ci",
        files={
            "copier.yml": dedent(
                """\
                _external_data:
                  moon: .copier-answers.mod-moon.yml
                own:
                  type: str
                  default: ci
                _subdirectory: template
                """
            ),
            "template/ci_out.txt.jinja": "ci={{ own }}\n",
        },
    )
    trust.add_trust(moon_producer.url)
    trust.add_trust(ci_consumer.url)

    dest = tmp_path / "proj"
    selection = [
        (_record("testcat/mod-ci", ci_consumer, questions=["own"]), {}),
        (_record("testcat/mod-moon", moon_producer, questions=["monorepo_tool"]), {}),
    ]
    # Must succeed — moon is in the selection
    results = runner.init_many(selection, str(dest), today="2026-07-16")
    assert len(results) == 2


def test_external_data_non_base_producer_absent_raises(tmp_path: Path) -> None:
    """Non-base producer absent → same loud OrderingError (mechanism is general)."""
    ci_consumer = build_template_repo(
        tmp_path / "mod-ci",
        files={
            "copier.yml": dedent(
                """\
                _external_data:
                  moon: .copier-answers.mod-moon.yml
                own:
                  type: str
                  default: ci
                _subdirectory: template
                """
            ),
            "template/ci_out.txt.jinja": "ci={{ own }}\n",
        },
    )
    trust.add_trust(ci_consumer.url)

    dest = tmp_path / "proj"
    with pytest.raises(OrderingError) as exc_info:
        runner.init_many(
            [(_record("testcat/mod-ci", ci_consumer, questions=["own"]), {})],
            str(dest),
            today="2026-07-16",
        )

    msg = str(exc_info.value)
    assert "moon" in msg or "mod-moon" in msg, (
        f"Error must name the missing moon producer/alias, got: {msg!r}"
    )


# ---------------------------------------------------------------------------
# FR-006a: path lint — non-convention _external_data value rejected at discovery
# ---------------------------------------------------------------------------


def test_external_data_non_literal_path_rejected(tmp_path: Path) -> None:
    """_external_data value with Jinja expression is rejected by discovery path lint (FR-006a/R9)."""  # noqa: E501
    bad_consumer = build_template_repo(
        tmp_path / "mod-bad",
        files={
            "copier.yml": dedent(
                """\
                _external_data:
                  base: "{{ some_var }}.copier-answers.yml"
                own:
                  type: str
                  default: own
                _subdirectory: template
                """
            ),
            "template/out.txt.jinja": "x={{ own }}\n",
        },
    )
    trust.add_trust(bad_consumer.url)

    dest = tmp_path / "proj"
    from bailiff.errors import BailiffError

    with pytest.raises(BailiffError) as exc_info:
        runner.init_many(
            [(_record("testcat/mod-bad", bad_consumer, questions=["own"]), {})],
            str(dest),
            today="2026-07-16",
        )

    msg = str(exc_info.value)
    assert "external_data" in msg.lower() or "path" in msg.lower() or "lint" in msg.lower(), (
        f"Error must mention external_data path lint, got: {msg!r}"
    )


def test_external_data_traversal_path_rejected(tmp_path: Path) -> None:
    """_external_data value with path traversal is rejected (FR-006a/R9)."""
    bad_consumer = build_template_repo(
        tmp_path / "mod-bad2",
        files={
            "copier.yml": dedent(
                """\
                _external_data:
                  base: "../other/.copier-answers.yml"
                own:
                  type: str
                  default: own
                _subdirectory: template
                """
            ),
            "template/out.txt.jinja": "x={{ own }}\n",
        },
    )
    trust.add_trust(bad_consumer.url)

    dest = tmp_path / "proj"
    from bailiff.errors import BailiffError

    with pytest.raises(BailiffError):
        runner.init_many(
            [(_record("testcat/mod-bad2", bad_consumer, questions=["own"]), {})],
            str(dest),
            today="2026-07-16",
        )
