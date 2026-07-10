"""The deterministic phase-2 executor: drive copier to init / check / reproduce.

This module contains ZERO agent involvement. It reads a frozen inputs document (the
run-spec the skill authored), then calls copier's **public** functions —
``run_copy`` / ``run_recopy`` — and translates copier's outcomes into clerk's small
error types (spec FR-005, FR-010, FR-011, FR-015). It uses no deprecated copier
surface.

Invariants (constitution III/V):

* init      → ``run_copy(data=…, defaults=True, overwrite=True, settings=…)``.
* reproduce → ``run_recopy(vcs_ref=VcsRef.CURRENT, defaults=True, overwrite=True)``
  — faithful replay at the recorded commit; NEVER bare recopy (which upgrades).
* check     → ``run_copy(pretend=True, …)`` — copier's own dry run validates without
  writing; clerk adds no bespoke validator.
* The current date is injected as the ``today`` answer so it freezes into the
  recorded answers and replays on reproduce (FR-007).
* Trust is never written here; an untrusted source raises ``UntrustedSourceError``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from copier import run_copy, run_recopy
from copier._types import VcsRef
from copier.errors import CopierError, UnsafeTemplateError

from clerk import discovery, trust
from clerk.catalog import TemplateRecord
from clerk.errors import (
    ClerkError,
    InvalidRunSpecError,
    NotReproducibleError,
    UntrustedSourceError,
)
from clerk.trust import suggest_prefix


@dataclass(frozen=True)
class RunSpec:
    """The frozen inputs the skill hands to the deterministic phase (FR-005).

    A documented plain mapping (the skill authors it as JSON/YAML): the fetchable
    source, an optional pinned ref, the answer values, and the destination. ``today``
    is injected by clerk if not already supplied.
    """

    source: str
    answers: dict[str, Any]
    dest: str
    ref: str | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> RunSpec:
        if not isinstance(data, dict):
            raise InvalidRunSpecError("run-spec must be a mapping")
        missing = [k for k in ("source", "dest") if not data.get(k)]
        if missing:
            raise InvalidRunSpecError(f"run-spec missing required field(s): {', '.join(missing)}")
        answers = data.get("answers", {})
        if not isinstance(answers, dict):
            raise InvalidRunSpecError("run-spec 'answers' must be a mapping")
        return cls(
            source=str(data["source"]),
            answers=dict(answers),
            dest=str(data["dest"]),
            ref=data.get("ref"),
        )


@dataclass(frozen=True)
class RunResult:
    """What the deterministic phase reports back (no copier objects leak out)."""

    dest: str
    src: str
    ref: str | None
    pretend: bool


def _with_today(answers: dict[str, Any], today: str | None) -> dict[str, Any]:
    """Inject the frozen generation date as the ``today`` answer (FR-007)."""
    merged = dict(answers)
    if today is not None and "today" not in merged:
        merged["today"] = today
    return merged


def _require_reproducible(source: str, ref: str | None) -> None:
    """Refuse a template that can't record its own answers (FR-016 / US5)."""
    desc = discovery.discover(source, ref)
    if not desc.reproducible:
        raise NotReproducibleError(
            f"template {source!r} ships no answers-file template "
            f"({{{{ _copier_conf.answers_file }}}}.jinja); the generated project could "
            f"never be reproduced, so clerk refuses to render it."
        )


def _require_trust_if_action_taking(source: str, ref: str | None) -> None:
    """If the template takes actions and the source is untrusted, refuse with the prefix.

    Advisory pre-check so clerk can name the exact prefix; copier re-checks
    authoritatively when it runs (FR-019, FR-020).
    """
    desc = discovery.discover(source, ref)
    if (desc.has_tasks or desc.jinja_extensions) and not trust.is_trusted(source):
        raise UntrustedSourceError(suggest_prefix(source), source=source)


def _translate(exc: CopierError) -> ClerkError:
    """Map a copier error to a legible clerk error (FR-010)."""
    if isinstance(exc, UnsafeTemplateError):
        return UntrustedSourceError("<source prefix>", source=None)
    return ClerkError(f"copier could not complete the operation: {exc}")


def init(spec: RunSpec, *, today: str | None = None, check: bool = False) -> RunResult:
    """Generate a project from ``spec`` (or dry-run validate when ``check``).

    ``check=True`` uses copier's own ``pretend`` dry run to validate inputs without
    writing anything (FR-006, FR-008).
    """
    _require_reproducible(spec.source, spec.ref)
    _require_trust_if_action_taking(spec.source, spec.ref)
    data = _with_today(spec.answers, today)
    try:
        run_copy(
            spec.source,
            spec.dest,
            data=data,
            vcs_ref=spec.ref,
            defaults=True,
            overwrite=True,
            quiet=True,
            pretend=check,
        )
    except UnsafeTemplateError as exc:
        raise UntrustedSourceError(suggest_prefix(spec.source), source=spec.source) from exc
    except ValueError as exc:
        # copier raises a bare ValueError for a missing required answer (verified).
        raise InvalidRunSpecError(f"invalid or incomplete answers: {exc}") from exc
    except CopierError as exc:
        raise _translate(exc) from exc
    return RunResult(dest=spec.dest, src=spec.source, ref=spec.ref, pretend=check)


def enumerate_answers_files(dest: str) -> list[Path]:
    """Return committed ``.copier-answers*.yml`` files in ``dest``, sorted by name.

    Finds ``<dest>/.copier-answers.yml`` (the default single-template name) plus any
    ``<dest>/.copier-answers.*.yml`` files written by multi-template layers. The
    stable name-sort gives a deterministic iteration order; spec 003 will slot its
    topo-sort into the caller's loop before this enumeration is consulted for order.
    """
    dst = Path(dest)
    files = sorted(dst.glob(".copier-answers*.yml"))
    return files


def reproduce(dest: str, *, answers_file: Path | None = None) -> RunResult:
    """Faithfully reproduce an existing project at its recorded commit (FR-015).

    Agent-free: replays the answers file via ``VcsRef.CURRENT`` (never the latest
    tag) with overwrite-in-place, non-interactive. When ``answers_file`` is given,
    that specific file drives the recopy (multi-layer loop); otherwise the default
    ``.copier-answers.yml`` is expected.
    """
    dst = Path(dest)
    target = answers_file if answers_file is not None else dst / ".copier-answers.yml"
    if not target.is_file():
        raise ClerkError(f"no answers file at {target!r}; nothing to reproduce")
    # copier requires answers_file to be relative to dst (validated by pydantic).
    rel_answers = target.relative_to(dst)
    try:
        run_recopy(
            dest,
            answers_file=rel_answers,
            vcs_ref=VcsRef.CURRENT,
            defaults=True,
            overwrite=True,
            quiet=True,
        )
    except UnsafeTemplateError as exc:
        # Reproduce/CI never prompts and must fail loudly when trust is absent.
        raise UntrustedSourceError("<recorded source prefix>", source=None) from exc
    except CopierError as exc:
        raise _translate(exc) from exc
    return RunResult(dest=dest, src="<recorded>", ref=":current:", pretend=False)


# ---------------------------------------------------------------------------
# Multi-template paths (spec 003)
# ---------------------------------------------------------------------------


def init_many(
    selection: list[tuple[TemplateRecord, dict[str, Any]]],
    dest: str,
    *,
    today: str | None = None,
    check: bool = False,
) -> list[RunResult]:
    """Apply (or preflight-check) a multi-template selection in dependency order.

    ``selection`` is a list of ``(record, answers)`` pairs where ``answers`` is the
    per-layer answer dict from the run-spec.  Earlier layers' answers are threaded
    into later layers via the accumulating ``data=`` dict (ADR-0003: ``data=``, not
    ``_external_data``).

    For each layer in topological order (stable full_id tie-break):
    1. Pre-checks trust + reproducibility (same guards as single-template ``init``).
    2. Runs ``run_copy`` with the accumulated answers merged with the layer's own
       answers, using a layer-specific ``answers_file`` name.
    3. Merges the written answers file back into the accumulator for later layers.

    ``check=True`` (all-gaps preflight, C-10): runs every layer with ``pretend=True``,
    collects errors across ALL layers, and raises a single aggregated
    ``InvalidRunSpecError`` naming every missing/invalid answer — never stops at the
    first failing layer.  Writes nothing.

    N=1 behaves identically to single-template ``init`` (uniform loop, spec 010).
    """
    from clerk import ordering  # local import avoids circular at module load

    records = [r for r, _ in selection]
    answers_map: dict[str, dict[str, Any]] = {r.full_id: a for r, a in selection}
    plan = ordering.layer_plan(records)
    accumulated: dict[str, Any] = _with_today({}, today)

    if not check:
        results: list[RunResult] = []
        for record, af_name in plan:
            _require_reproducible(record.source, record.ref)
            _require_trust_if_action_taking(record.source, record.ref)
            data = {**accumulated, **answers_map.get(record.full_id, {})}
            try:
                run_copy(
                    record.source,
                    dest,
                    data=data,
                    vcs_ref=record.ref or None,
                    answers_file=af_name,
                    defaults=True,
                    overwrite=True,
                    quiet=True,
                    pretend=False,
                )
            except UnsafeTemplateError as exc:
                raise UntrustedSourceError(
                    suggest_prefix(record.source), source=record.source
                ) from exc
            except ValueError as exc:
                raise InvalidRunSpecError(f"invalid or incomplete answers: {exc}") from exc
            except CopierError as exc:
                raise _translate(exc) from exc
            results.append(RunResult(dest=dest, src=record.source, ref=record.ref, pretend=False))
            _merge_layer_answers(accumulated, dest, af_name)
        return results

    # check=True: all-gaps preflight — run all layers, collect all errors.
    errors: list[str] = []
    for record, af_name in plan:
        _require_reproducible(record.source, record.ref)
        _require_trust_if_action_taking(record.source, record.ref)
        data = {**accumulated, **answers_map.get(record.full_id, {})}
        try:
            run_copy(
                record.source,
                dest,
                data=data,
                vcs_ref=record.ref or None,
                answers_file=af_name,
                defaults=True,
                overwrite=True,
                quiet=True,
                pretend=True,
            )
        except UnsafeTemplateError as exc:
            raise UntrustedSourceError(suggest_prefix(record.source), source=record.source) from exc
        except ValueError as exc:
            errors.append(f"{record.full_id}: {exc}")
        except CopierError as exc:
            errors.append(f"{record.full_id}: {exc}")
        # pretend=True writes nothing — thread what we have so later layers get the
        # best possible coverage even in preflight mode.
    if errors:
        raise InvalidRunSpecError(
            "preflight found missing or invalid answers:\n" + "\n".join(f"  - {e}" for e in errors)
        )
    return [RunResult(dest=dest, src=r.source, ref=r.ref, pretend=True) for r, _ in plan]


def _merge_layer_answers(accumulated: dict[str, Any], dest: str, af_name: str) -> None:
    """Read the just-written answers file and merge its user-visible answers into ``accumulated``.

    copier writes the answers file with ``_``-prefixed metadata keys (``_src_path``,
    ``_commit``, ``_answers_file``, ``_template``) plus the answered question values.
    We merge only the non-``_``-prefixed answers so that subsequent layers can
    reference earlier layers' answers via ``data=`` threading (ADR-0003).
    """
    af_path = Path(dest) / af_name
    if not af_path.is_file():
        return
    try:
        raw = yaml.safe_load(af_path.read_text()) or {}
    except Exception:  # noqa: BLE001 — best-effort; missing answers just don't thread
        return
    if not isinstance(raw, dict):
        return
    for k, v in raw.items():
        if not k.startswith("_"):
            accumulated[k] = v


def reproduce_many(dest: str) -> list[RunResult]:
    """Recompute the multi-layer order from committed state and reproduce each layer.

    Algorithm (spec 003 recompute-not-freeze contract):
    1. Enumerate committed ``.copier-answers*.yml`` files.
    2. For each file, read the recorded ``_src_path`` + ``_commit`` (the exact
       source and pinned commit copier wrote at init time).
    3. Re-discover each template at its pinned commit to re-read its edges.
    4. Rebuild the DAG + topo-sort (same stable full_id tie-break) → the
       recomputed order.
    5. Drive ``reproduce(dest, answers_file=<that file>)`` per layer in that order.

    Fails loudly per-layer if a source is unreachable (reproduce/CI never silently
    skips a layer).  N=1 behaves identically to single-template ``reproduce`` (uniform
    loop, spec 010 invariant).
    """
    from clerk import ordering  # local import avoids circular at module load

    answers_files = enumerate_answers_files(dest)
    if not answers_files:
        raise ClerkError(f"no .copier-answers*.yml at {dest!r}; nothing to reproduce")

    # Build minimal TemplateRecord-like objects from each answers file's metadata,
    # and simultaneously collect their edges by re-discovering at the pinned commit.
    records: list[TemplateRecord] = []
    edges_by_basename: dict[str, dict[str, Any]] = {}
    file_by_basename: dict[str, Path] = {}

    for af_path in answers_files:
        try:
            raw = yaml.safe_load(af_path.read_text()) or {}
        except Exception as exc:  # noqa: BLE001
            raise ClerkError(f"could not read answers file {af_path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ClerkError(f"answers file {af_path} did not parse to a mapping")

        src_path = raw.get("_src_path")
        commit = raw.get("_commit")
        if not src_path:
            raise ClerkError(
                f"answers file {af_path!r} has no _src_path; cannot reproduce this layer"
            )
        if not commit:
            raise ClerkError(
                f"answers file {af_path!r} has no _commit; cannot reproduce this layer"
            )

        # Re-discover at the pinned commit to re-read edges (recompute, not freeze).
        disc = discovery.discover(str(src_path), str(commit))

        # Reconstruct a minimal TemplateRecord: full_id derived from source basename
        # (matches the pattern catalog.py uses: catalog/basename — but here we use
        # a synthetic "_recorded/<basename>" so the full_id tie-break is consistent).
        basename = str(src_path).rstrip("/").rsplit("/", 1)[-1]
        if basename.endswith(".git"):
            basename = basename[:-4]
        full_id = f"_recorded/{basename}"

        record = TemplateRecord(
            full_id=full_id,
            source=str(src_path),
            ref=str(commit),
            versions=disc.versions,
            reproducible=disc.reproducible,
            has_tasks=disc.has_tasks,
            questions=[q.key for q in disc.questions],
        )
        records.append(record)
        edges_by_basename[basename] = disc.dependency_edges
        file_by_basename[basename] = af_path

    # Recompute order (same DAG build + topo-sort as init).
    plan = ordering.layer_plan_from_edges(records, edges_by_basename)

    results: list[RunResult] = []
    for record, _af_name in plan:
        basename = record.full_id.rsplit("/", 1)[-1]
        af_path = file_by_basename[basename]
        result = reproduce(dest, answers_file=af_path)
        results.append(result)
    return results
