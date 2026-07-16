"""bailiff's dependency-ordering brain — the C-11-sanctioned coordination glue.

Computes the topological application order for a selection of templates from
their statically-declared ``when:false`` edges (``depends_on``, ``run_after``,
``run_before``) and their ``_bailiff_phase`` setting (spec 014 FR-019/FR-020).

Phase model (spec 014 FR-020/R8): modules carry a phase — ``pre`` | ``normal``
(default) | ``post``.  Sort = (phase) → (``depends_on`` DAG) → (basename).
Edge legality: ``pre`` may depend only on ``pre``; ``normal`` may depend on
``pre`` + ``normal``; ``post`` may depend on anything.  A forward cross-phase
edge (e.g. ``normal`` → ``post``) is rejected with an ``OrderingError``.

Identity: nodes are keyed by **basename** (the repo name, i.e. the last
component of the full_id) within a valid selection — the portable name a
template author uses inside their ``copier.yml`` when naming a sibling template.
The tie-break for the stable topological sort is lexicographic by **basename**
(unique within a valid selection after the collision check; identical across the
init and reproduce paths, which reconstruct full_ids differently).

Validation (raised before any sort or return):

* **Basename collision** — two selected templates with the same basename →
  ``OrderingError`` naming the colliding basename.
* **Dangling edge** — an edge target that is not among the selected basenames →
  ``OrderingError`` naming the missing dependency.
* **Forward cross-phase edge** — a dependency that jumps to a later phase →
  ``OrderingError`` naming the offending pair (spec 014 FR-020).
* **Cycle** — a cycle in the dependency graph → ``OrderingError`` naming the
  cycle members (via ``graphlib.CycleError``).
"""

from __future__ import annotations

from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bailiff import discovery
from bailiff.errors import OrderingError

if TYPE_CHECKING:
    from bailiff.catalog import TemplateRecord


def _basename(record: TemplateRecord) -> str:
    """Extract the repo basename from a ``full_id`` (``catalog/basename`` → ``basename``)."""
    return record.full_id.rsplit("/", 1)[-1]


def answers_file_name(record: TemplateRecord) -> str:
    """Return the answers-file name for ``record``: ``.copier-answers.<basename>.yml``."""
    return f".copier-answers.{_basename(record)}.yml"


# Phase ordering: lower index = earlier in execution.
_PHASE_ORDER = {"pre": 0, "normal": 1, "post": 2}


def build_dag(
    records: list[TemplateRecord],
    edges_by_basename: dict[str, dict[str, Any]],
    phases_by_basename: dict[str, str] | None = None,
) -> dict[str, set[str]]:
    """Build a dependency graph from the selected records and their declared edges.

    ``edges_by_basename`` maps each selected template's basename to its
    ``dependency_edges`` dict (from ``discovery.Discovery.dependency_edges``),
    which has keys ``depends_on``, ``run_after``, ``run_before`` with list values.

    ``phases_by_basename`` maps each basename to its ``_bailiff_phase`` value
    (spec 014 FR-020).  When provided, forward cross-phase edges are rejected.

    Returns a graph ``{basename: {predecessors}}`` suitable for
    ``graphlib.TopologicalSorter`` — a node with no predecessors maps to an empty set.

    Raises ``OrderingError`` for:
    - basename collision among selected templates (two records share a basename)
    - dangling edge (an edge target not present in the selection)
    - forward cross-phase edge (spec 014 FR-020)
    """
    phases = phases_by_basename or {}

    # 1. Check basename collision.
    basenames: list[str] = [_basename(r) for r in records]
    seen: dict[str, int] = {}
    for b in basenames:
        seen[b] = seen.get(b, 0) + 1
    collisions = [b for b, count in seen.items() if count > 1]
    if collisions:
        raise OrderingError(
            f"basename collision among selected templates: "
            f"{', '.join(sorted(collisions))}. "
            f"Two selected templates share the same repo basename, which would "
            f"overwrite each other's answers file. Use templates with distinct basenames."
        )

    basename_set = set(basenames)

    # 2. Initialize graph — every node present, even with no edges.
    graph: dict[str, set[str]] = {b: set() for b in basenames}

    # 3. Normalize edges: depends_on/run_after → (dep → self); run_before → (self → dep).
    for record in records:
        self_b = _basename(record)
        self_phase = phases.get(self_b, "normal")
        self_phase_idx = _PHASE_ORDER.get(self_phase, 1)
        edges = edges_by_basename.get(self_b, {})

        # depends_on and run_after: X → self (self depends on X)
        for key in ("depends_on", "run_after"):
            targets = edges.get(key)
            if not targets:
                continue
            if isinstance(targets, str):
                targets = [targets]
            for target in targets:
                target = str(target)
                if target not in basename_set:
                    raise OrderingError(
                        f"dangling edge: {self_b!r} declares {key}={target!r}, "
                        f"but {target!r} is not in the selection. "
                        f"Add {target!r} to the selection or remove the edge."
                    )
                # Validate phase legality: self may not depend on a LATER phase (FR-020).
                target_phase = phases.get(target, "normal")
                target_phase_idx = _PHASE_ORDER.get(target_phase, 1)
                if target_phase_idx > self_phase_idx:
                    raise OrderingError(
                        f"forward cross-phase edge: {self_b!r} (phase={self_phase!r}) "
                        f"declares {key}={target!r} (phase={target_phase!r}). "
                        f"A {self_phase!r}-phase module may not depend on a later "
                        f"{target_phase!r}-phase module. "
                        f"Edge legality: pre→pre only; normal→pre+normal; post→anything. "
                        f"(spec 014 FR-020/R8)"
                    )
                graph[self_b].add(target)

        # run_before: self → Y (self must come before Y)
        run_before = edges.get("run_before")
        if run_before:
            if isinstance(run_before, str):
                run_before = [run_before]
            for target in run_before:
                target = str(target)
                if target not in basename_set:
                    raise OrderingError(
                        f"dangling edge: {self_b!r} declares run_before={target!r}, "
                        f"but {target!r} is not in the selection. "
                        f"Add {target!r} to the selection or remove the edge."
                    )
                # self → Y means Y must come after self → Y has self as a predecessor
                graph[target].add(self_b)

    return graph


def topo_sort(
    records: list[TemplateRecord],
    graph: dict[str, set[str]],
    phases_by_basename: dict[str, str] | None = None,
) -> list[TemplateRecord]:
    """Topologically sort ``records`` given the dependency graph.

    Sort key: (phase_index, DAG constraints, basename).  Phase ordering ensures
    ``pre`` modules come before ``normal`` and ``normal`` before ``post``
    (spec 014 FR-020/R8), even among constraint-free nodes.  Within the same
    phase, the tie-break is lexicographic by basename.

    Raises ``OrderingError`` if a cycle is detected (names the cycle members).
    """
    phases = phases_by_basename or {}

    # Build basename → record for lookup.
    by_basename: dict[str, TemplateRecord] = {_basename(r): r for r in records}

    ts = TopologicalSorter(graph)
    try:
        ts.prepare()
    except CycleError as exc:
        # CycleError args[1] is the cycle node list.
        cycle_nodes = list(exc.args[1]) if len(exc.args) > 1 else []
        cycle_str = " → ".join(str(n) for n in cycle_nodes)
        raise OrderingError(
            f"dependency cycle detected: {cycle_str}. Remove one of these edges to break the cycle."
        ) from exc

    result: list[TemplateRecord] = []
    while ts.is_active():
        ready_basenames = ts.get_ready()
        # Sort by (phase_index, basename) for deterministic, phase-respecting order.
        sorted_ready = sorted(
            ready_basenames,
            key=lambda b: (_PHASE_ORDER.get(phases.get(b, "normal"), 1), b),
        )
        for b in sorted_ready:
            result.append(by_basename[b])
            ts.done(b)

    return result


def layer_plan(records: list[TemplateRecord]) -> list[tuple[TemplateRecord, str]]:
    """Compute the ordered layer plan for ``records``.

    For each record, calls ``discovery.discover`` to fetch its declared edges and
    phase, builds the DAG, validates it (raises ``OrderingError`` on cycle, dangling
    edge, basename collision, or forward cross-phase edge), topo-sorts with the
    stable phase→basename tie-break, and returns ``[(record, answers_file_name)]``
    in application order.

    This is the entry point for both ``init_many`` and ``reproduce_many`` — the
    same algorithm, same tie-break, same deterministic result.
    """
    edges_by_basename: dict[str, dict[str, Any]] = {}
    phases_by_basename: dict[str, str] = {}
    for record in records:
        b = _basename(record)
        disc = discovery.discover(record.source, record.ref or None)
        edges_by_basename[b] = disc.dependency_edges
        phases_by_basename[b] = disc.phase

    graph = build_dag(records, edges_by_basename, phases_by_basename)
    ordered = topo_sort(records, graph, phases_by_basename)
    return [(r, answers_file_name(r)) for r in ordered]


def layer_plan_from_edges(
    records: list[TemplateRecord],
    edges_by_basename: dict[str, dict[str, Any]],
    phases_by_basename: dict[str, str] | None = None,
) -> list[tuple[TemplateRecord, str]]:
    """Like ``layer_plan`` but accepts pre-fetched edges (avoids duplicate discovers).

    Used by ``reproduce_many`` which has already fetched edges while reading the
    committed answers files.  ``phases_by_basename`` carries the ``_bailiff_phase``
    values discovered at the same time as the edges.
    """
    graph = build_dag(records, edges_by_basename, phases_by_basename)
    ordered = topo_sort(records, graph, phases_by_basename)
    return [(r, answers_file_name(r)) for r in ordered]


def answers_file_path(dest: str, record: TemplateRecord) -> Path:
    """Full path to the answers file for ``record`` inside ``dest``."""
    return Path(dest) / answers_file_name(record)
