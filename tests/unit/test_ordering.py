"""Unit tests for bailiff.ordering — pure DAG/sort functions (spec 014 / T007).

Covers: build_dag normalization (depends_on is the ONLY edge; run_after/run_before
are inert/ignored), topo_sort determinism + stable tie-break (basename) +
order-independence, cycle → OrderingError, dangling depends_on → OrderingError,
basename collision → OrderingError, answers_file_name.
"""

from __future__ import annotations

import random

import pytest

from bailiff.catalog import TemplateRecord
from bailiff.errors import OrderingError
from bailiff.ordering import answers_file_name, build_dag, topo_sort

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rec(full_id: str) -> TemplateRecord:
    """Minimal TemplateRecord for a given full_id (no real git repo needed)."""
    return TemplateRecord(
        full_id=full_id,
        source=f"file:///tmp/{full_id}",
        ref="v1.0.0",
        versions=["v1.0.0"],
        reproducible=True,
        has_tasks=False,
        questions=["project_name"],
    )


def _basenames(records: list[TemplateRecord]) -> list[str]:
    return [r.full_id.rsplit("/", 1)[-1] for r in records]


# ---------------------------------------------------------------------------
# answers_file_name
# ---------------------------------------------------------------------------


def test_answers_file_name_uses_basename() -> None:
    rec = _rec("mycat/mymod")
    assert answers_file_name(rec) == ".copier-answers.mymod.yml"


def test_answers_file_name_nested_full_id() -> None:
    rec = _rec("org/namespace/tpl-foo")
    # basename = last component after final "/"
    assert answers_file_name(rec) == ".copier-answers.tpl-foo.yml"


# ---------------------------------------------------------------------------
# build_dag — edge normalization
# ---------------------------------------------------------------------------


def test_build_dag_no_edges() -> None:
    records = [_rec("cat/alpha"), _rec("cat/beta"), _rec("cat/gamma")]
    graph = build_dag(records, {})
    assert graph == {"alpha": set(), "beta": set(), "gamma": set()}


def test_build_dag_depends_on_single() -> None:
    # beta depends_on alpha → edge alpha → beta (beta has alpha as predecessor)
    records = [_rec("cat/alpha"), _rec("cat/beta")]
    edges = {"beta": {"depends_on": ["alpha"]}}
    graph = build_dag(records, edges)
    assert graph["beta"] == {"alpha"}
    assert graph["alpha"] == set()


def test_build_dag_run_after_is_inert() -> None:
    # spec 014 R7: run_after is dropped — it must NOT create any edge.
    records = [_rec("cat/alpha"), _rec("cat/beta")]
    edges = {"beta": {"run_after": ["alpha"]}}
    graph = build_dag(records, edges)
    assert graph["beta"] == set(), "run_after must not create an edge (inert in spec 014)"
    assert graph["alpha"] == set()


def test_build_dag_run_before_is_inert() -> None:
    # spec 014 R7: run_before is dropped — it must NOT create any inverted edge.
    records = [_rec("cat/alpha"), _rec("cat/beta")]
    edges = {"alpha": {"run_before": ["beta"]}}
    graph = build_dag(records, edges)
    assert graph["beta"] == set(), "run_before must not create an edge (inert in spec 014)"
    assert graph["alpha"] == set()


def test_build_dag_string_target_normalised() -> None:
    # a target given as a bare string (not a list) must be accepted
    records = [_rec("cat/alpha"), _rec("cat/beta")]
    edges = {"beta": {"depends_on": "alpha"}}
    graph = build_dag(records, edges)
    assert graph["beta"] == {"alpha"}


def test_build_dag_combined_edges() -> None:
    # gamma depends_on alpha AND beta depends_on alpha → only depends_on creates edges.
    # run_before would have added beta→gamma in old code; it must not here.
    records = [_rec("cat/alpha"), _rec("cat/beta"), _rec("cat/gamma")]
    edges = {
        "gamma": {"depends_on": ["alpha"]},
        "beta": {"depends_on": ["alpha"]},
    }
    graph = build_dag(records, edges)
    assert graph["gamma"] == {"alpha"}
    assert graph["beta"] == {"alpha"}
    assert graph["alpha"] == set()


# ---------------------------------------------------------------------------
# build_dag — validation errors
# ---------------------------------------------------------------------------


def test_build_dag_basename_collision_raises() -> None:
    # Two records with different full_ids but the same basename → refused
    records = [_rec("org1/mymod"), _rec("org2/mymod")]
    with pytest.raises(OrderingError, match="mymod"):
        build_dag(records, {})


def test_build_dag_dangling_depends_on_raises() -> None:
    records = [_rec("cat/beta")]  # alpha not in selection
    edges = {"beta": {"depends_on": ["alpha"]}}
    with pytest.raises(OrderingError, match="alpha"):
        build_dag(records, edges)


def test_build_dag_dangling_run_after_is_inert() -> None:
    # spec 014 R7: run_after is not an edge, so a missing target must NOT raise.
    records = [_rec("cat/beta")]
    edges = {"beta": {"run_after": ["missing-dep"]}}
    graph = build_dag(records, edges)  # must not raise
    assert graph["beta"] == set()


def test_build_dag_dangling_run_before_is_inert() -> None:
    # spec 014 R7: run_before is not an edge, so a missing target must NOT raise.
    records = [_rec("cat/alpha")]
    edges = {"alpha": {"run_before": ["nonexistent"]}}
    graph = build_dag(records, edges)  # must not raise
    assert graph["alpha"] == set()


# ---------------------------------------------------------------------------
# topo_sort — correctness and determinism
# ---------------------------------------------------------------------------


def test_topo_sort_respects_edge() -> None:
    # B depends_on A → A must appear before B
    rec_a = _rec("cat/tpl-a")
    rec_b = _rec("cat/tpl-b")
    records = [rec_b, rec_a]  # deliberately reversed
    graph = {"tpl-a": set(), "tpl-b": {"tpl-a"}}
    result = topo_sort(records, graph)
    basenames = _basenames(result)
    assert basenames.index("tpl-a") < basenames.index("tpl-b")


def test_topo_sort_stable_tiebreak_alphabetical() -> None:
    # C and D have no edges between them — stable tie-break is basename alphabetical
    rec_c = _rec("cat/tpl-c")
    rec_d = _rec("cat/tpl-d")
    graph = {"tpl-c": set(), "tpl-d": set()}
    result = topo_sort([rec_c, rec_d], graph)
    assert _basenames(result) == ["tpl-c", "tpl-d"]

    # also holds when input is reversed
    result2 = topo_sort([rec_d, rec_c], graph)
    assert _basenames(result2) == ["tpl-c", "tpl-d"]


def test_topo_sort_order_independence_for_independent_nodes() -> None:
    # Shuffling the input order of edge-independent records produces the same result.
    records = [_rec(f"cat/mod-{c}") for c in ["alpha", "beta", "gamma", "delta"]]
    graph = {f"mod-{c}": set() for c in ["alpha", "beta", "gamma", "delta"]}

    reference = _basenames(topo_sort(records, graph))
    rng = random.Random(42)
    for _ in range(10):
        shuffled = list(records)
        rng.shuffle(shuffled)
        assert _basenames(topo_sort(shuffled, graph)) == reference


def test_topo_sort_chain_ordering() -> None:
    # A → B → C chain: must be sorted A, B, C
    rec_a = _rec("cat/tpl-a")
    rec_b = _rec("cat/tpl-b")
    rec_c = _rec("cat/tpl-c")
    graph = {"tpl-a": set(), "tpl-b": {"tpl-a"}, "tpl-c": {"tpl-b"}}
    result = topo_sort([rec_c, rec_b, rec_a], graph)
    basenames = _basenames(result)
    assert basenames.index("tpl-a") < basenames.index("tpl-b")
    assert basenames.index("tpl-b") < basenames.index("tpl-c")


def test_topo_sort_cycle_raises_ordering_error() -> None:
    rec_e = _rec("cat/tpl-e")
    rec_f = _rec("cat/tpl-f")
    # E depends_on F, F depends_on E
    graph = {"tpl-e": {"tpl-f"}, "tpl-f": {"tpl-e"}}
    with pytest.raises(OrderingError, match="cycle"):
        topo_sort([rec_e, rec_f], graph)


def test_topo_sort_cycle_names_members() -> None:
    rec_e = _rec("cat/tpl-e")
    rec_f = _rec("cat/tpl-f")
    graph = {"tpl-e": {"tpl-f"}, "tpl-f": {"tpl-e"}}
    with pytest.raises(OrderingError) as exc_info:
        topo_sort([rec_e, rec_f], graph)
    msg = str(exc_info.value)
    # message must name at least one cycle member
    assert "tpl-e" in msg or "tpl-f" in msg


# ---------------------------------------------------------------------------
# Integration: build_dag + topo_sort round-trip
# ---------------------------------------------------------------------------


def test_dag_and_sort_roundtrip_b_depends_on_a() -> None:
    rec_a = _rec("testcat/tpl-a")
    rec_b = _rec("testcat/tpl-b")
    # Selection deliberately mis-ordered [B, A]
    edges = {"tpl-b": {"depends_on": ["tpl-a"]}}
    graph = build_dag([rec_b, rec_a], edges)
    result = topo_sort([rec_b, rec_a], graph)
    basenames = _basenames(result)
    assert basenames.index("tpl-a") < basenames.index("tpl-b")


def test_dag_and_sort_run_before_produces_no_edge() -> None:
    # spec 014 R7: run_before is inert — no edge is created, so topo sort is free
    # to use alphabetical tie-break (alpha before beta), not the old run_before order.
    rec_a = _rec("cat/alpha")
    rec_b = _rec("cat/beta")
    edges_run_before = {"alpha": {"run_before": ["beta"]}}
    graph_rb = build_dag([rec_a, rec_b], edges_run_before)
    # With run_before inert: no edges, tie-break = alphabetical → alpha, beta.
    result = _basenames(topo_sort([rec_a, rec_b], graph_rb))
    assert graph_rb == {"alpha": set(), "beta": set()}, "run_before must leave graph empty"
    assert result == ["alpha", "beta"]
