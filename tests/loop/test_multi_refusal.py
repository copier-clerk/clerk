"""US4: ordering refusals — cycle, dangling edge, basename collision, pre-write (spec 003 / T014).

Tests:
- cycle → refused pre-write, message names cycle (SC-004)
- dangling edge → refused naming missing dependency (SC-004)
- basename collision → refused naming colliding basename (SC-004)
- nothing written in every refusal case (SC-004)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bailiff import runner, trust
from bailiff.errors import OrderingError
from tests.conftest import MultiTemplateSet

_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "bailiff.py"


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _make_record(full_id: str, repo):
    from bailiff.catalog import TemplateRecord

    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=["project_name"],
    )


# ---------------------------------------------------------------------------
# T014-a: cycle → refused before any write, message names cycle
# ---------------------------------------------------------------------------


def test_cycle_raises_ordering_error(multi_template_set: MultiTemplateSet, tmp_path: Path) -> None:
    """E depends_on F, F depends_on E → OrderingError before any write."""
    tpl_e = multi_template_set.tpl_e
    tpl_f = multi_template_set.tpl_f
    trust.add_trust(tpl_e.url)
    trust.add_trust(tpl_f.url)

    dest = tmp_path / "proj"
    with pytest.raises(OrderingError) as exc_info:
        runner.init_many(
            [
                (_make_record("testcat/tpl-e", tpl_e), {"project_name": "demo"}),
                (_make_record("testcat/tpl-f", tpl_f), {"project_name": "demo"}),
            ],
            str(dest),
            today="2026-07-09",
        )

    msg = str(exc_info.value)
    # Message must name the cycle (mentions "cycle" and at least one member)
    assert "cycle" in msg.lower(), f"Expected 'cycle' in error: {msg}"
    assert "tpl-e" in msg or "tpl-f" in msg, f"Expected cycle members named: {msg}"


def test_cycle_writes_nothing(multi_template_set: MultiTemplateSet, tmp_path: Path) -> None:
    """Cycle refusal must leave dest untouched."""
    tpl_e = multi_template_set.tpl_e
    tpl_f = multi_template_set.tpl_f
    trust.add_trust(tpl_e.url)
    trust.add_trust(tpl_f.url)

    dest = tmp_path / "proj"
    with pytest.raises(OrderingError):
        runner.init_many(
            [
                (_make_record("testcat/tpl-e", tpl_e), {"project_name": "demo"}),
                (_make_record("testcat/tpl-f", tpl_f), {"project_name": "demo"}),
            ],
            str(dest),
            today="2026-07-09",
        )

    assert not dest.exists() or not list(dest.iterdir()), (
        f"Cycle refusal wrote files: {list(dest.iterdir()) if dest.exists() else '(dest created)'}"
    )


def test_cycle_via_cli_exits_1(multi_template_set: MultiTemplateSet, tmp_path: Path) -> None:
    """scripts/bailiff.py init with a cycle exits 1 (OrderingError → BailiffError → exit 1)."""
    tpl_e = multi_template_set.tpl_e
    tpl_f = multi_template_set.tpl_f
    trust.add_trust(tpl_e.url)
    trust.add_trust(tpl_f.url)

    dest = tmp_path / "proj"
    spec = {
        "dest": str(dest),
        "selection": [
            {
                "full_id": "testcat/tpl-e",
                "source": tpl_e.url,
                "ref": tpl_e.tag,
                "answers": {"project_name": "demo"},
            },
            {
                "full_id": "testcat/tpl-f",
                "source": tpl_f.url,
                "ref": tpl_f.tag,
                "answers": {"project_name": "demo"},
            },
        ],
    }
    spec_path = tmp_path / "run_spec.json"
    spec_path.write_text(json.dumps(spec))

    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "init", "--run-spec", str(spec_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "COPIER_SETTINGS_PATH": str(tmp_path / "settings.yml")},
    )

    assert result.returncode == 1, (
        f"Expected exit 1 for cycle;\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert not dest.exists() or not list(dest.iterdir())


# ---------------------------------------------------------------------------
# T014-b: dangling edge → refused naming missing dep
# ---------------------------------------------------------------------------


def test_dangling_edge_raises_ordering_error(
    multi_template_set: MultiTemplateSet, tmp_path: Path
) -> None:
    """B depends_on A, but A is not in the selection → OrderingError naming A."""
    tpl_b = multi_template_set.tpl_b  # depends_on tpl-a
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    # Only include B, not A → dangling edge
    with pytest.raises(OrderingError) as exc_info:
        runner.init_many(
            [(_make_record("testcat/tpl-b", tpl_b), {"project_name": "demo"})],
            str(dest),
            today="2026-07-09",
        )

    msg = str(exc_info.value)
    assert "tpl-a" in msg, f"Expected missing dep 'tpl-a' named in error: {msg}"


def test_dangling_edge_writes_nothing(multi_template_set: MultiTemplateSet, tmp_path: Path) -> None:
    """Dangling edge refusal must leave dest untouched."""
    tpl_b = multi_template_set.tpl_b
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    with pytest.raises(OrderingError):
        runner.init_many(
            [(_make_record("testcat/tpl-b", tpl_b), {"project_name": "demo"})],
            str(dest),
            today="2026-07-09",
        )

    assert not dest.exists() or not list(dest.iterdir()), "Dangling edge refusal wrote files"


def test_dangling_edge_via_cli_exits_1(
    multi_template_set: MultiTemplateSet, tmp_path: Path
) -> None:
    """scripts/bailiff.py init with dangling edge exits 1."""
    tpl_b = multi_template_set.tpl_b
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    spec = {
        "dest": str(dest),
        "selection": [
            {
                "full_id": "testcat/tpl-b",
                "source": tpl_b.url,
                "ref": tpl_b.tag,
                "answers": {"project_name": "demo"},
            },
        ],
    }
    spec_path = tmp_path / "run_spec.json"
    spec_path.write_text(json.dumps(spec))

    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "init", "--run-spec", str(spec_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "COPIER_SETTINGS_PATH": str(tmp_path / "settings.yml")},
    )

    assert result.returncode == 1, (
        f"Expected exit 1 for dangling edge;\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert not dest.exists() or not list(dest.iterdir())


# ---------------------------------------------------------------------------
# T014-c: basename collision → refused naming colliding basename
# ---------------------------------------------------------------------------


def test_basename_collision_raises_ordering_error(
    multi_template_set: MultiTemplateSet, tmp_path: Path
) -> None:
    """Two templates sharing basename 'mymod' → OrderingError naming 'mymod'."""
    col1 = multi_template_set.collision_1
    col2 = multi_template_set.collision_2
    trust.add_trust(col1.url)
    trust.add_trust(col2.url)

    dest = tmp_path / "proj"
    with pytest.raises(OrderingError) as exc_info:
        runner.init_many(
            [
                (_make_record("org1/mymod", col1), {"project_name": "demo"}),
                (_make_record("org2/mymod", col2), {"project_name": "demo"}),
            ],
            str(dest),
            today="2026-07-09",
        )

    msg = str(exc_info.value)
    assert "mymod" in msg, f"Expected colliding basename 'mymod' in error: {msg}"


def test_basename_collision_writes_nothing(
    multi_template_set: MultiTemplateSet, tmp_path: Path
) -> None:
    """Basename collision refusal must leave dest untouched."""
    col1 = multi_template_set.collision_1
    col2 = multi_template_set.collision_2
    trust.add_trust(col1.url)
    trust.add_trust(col2.url)

    dest = tmp_path / "proj"
    with pytest.raises(OrderingError):
        runner.init_many(
            [
                (_make_record("org1/mymod", col1), {"project_name": "demo"}),
                (_make_record("org2/mymod", col2), {"project_name": "demo"}),
            ],
            str(dest),
            today="2026-07-09",
        )

    assert not dest.exists() or not list(dest.iterdir()), "Basename collision refusal wrote files"


def test_basename_collision_via_cli_exits_1(
    multi_template_set: MultiTemplateSet, tmp_path: Path
) -> None:
    """scripts/bailiff.py init with basename collision exits 1."""
    col1 = multi_template_set.collision_1
    col2 = multi_template_set.collision_2
    trust.add_trust(col1.url)
    trust.add_trust(col2.url)

    dest = tmp_path / "proj"
    spec = {
        "dest": str(dest),
        "selection": [
            {
                "full_id": "org1/mymod",
                "source": col1.url,
                "ref": col1.tag,
                "answers": {"project_name": "demo"},
            },
            {
                "full_id": "org2/mymod",
                "source": col2.url,
                "ref": col2.tag,
                "answers": {"project_name": "demo"},
            },
        ],
    }
    spec_path = tmp_path / "run_spec.json"
    spec_path.write_text(json.dumps(spec))

    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "init", "--run-spec", str(spec_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "COPIER_SETTINGS_PATH": str(tmp_path / "settings.yml")},
    )

    assert result.returncode == 1, (
        f"Expected exit 1 for collision;\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert not dest.exists() or not list(dest.iterdir())
