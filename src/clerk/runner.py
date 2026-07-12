"""The deterministic phase-2 executor: drive copier to init / check / reproduce / update.

This module contains ZERO agent involvement. It reads a frozen inputs document (the
run-spec the skill authored), then calls copier's **public** functions —
``run_copy`` / ``run_recopy`` / ``run_update`` — and translates copier's outcomes into
clerk's small error types (spec FR-005, FR-010, FR-011, FR-015). It uses no deprecated
copier surface.

Invariants (constitution III/V):

* init      → ``run_copy(data=…, defaults=True, overwrite=True, settings=…)``.
* reproduce → ``run_recopy(vcs_ref=VcsRef.CURRENT, defaults=True, overwrite=True)``
  — faithful replay at the recorded commit; NEVER bare recopy (which upgrades).
* check     → ``run_copy(pretend=True, …)`` — copier's own dry run validates without
  writing; clerk adds no bespoke validator.
* update    → ``run_update(data=…, defaults=True, overwrite=True, settings=…)``
  — the ONLY place clerk advances a template version; announced, explicit (spec 006).
* The current date is injected as the ``today`` answer so it freezes into the
  recorded answers and replays on reproduce (FR-007).
* Trust is never written here; an untrusted source raises ``UntrustedSourceError``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from copier import run_copy, run_recopy, run_update
from copier._types import VcsRef
from copier.errors import CopierError, UnsafeTemplateError

from clerk import defaults as _defaults
from clerk import discovery, trust
from clerk.catalog import TemplateRecord
from clerk.errors import (
    ClerkError,
    DirtyWorktreeError,
    DowngradeError,
    InvalidRunSpecError,
    MergeConflictError,
    NotReproducibleError,
    SecretInAnswersError,
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


def _check_no_secrets(answers: dict[str, Any], desc: discovery.Discovery) -> None:
    """Fail loud if the run-spec supplies a value for any discovery-flagged secret key.

    Named key, never the value — that is the invariant (FR-003a / SC-003a).  This
    runs before any copier call so a secret never flows through even if the SKILL
    rule is violated.  Takes a pre-fetched ``Discovery`` so the caller pays for one
    clone per layer, not one per check.
    """
    secret_set = set(desc.secret_questions)
    offenders = [k for k in answers if k in secret_set]
    if offenders:
        raise SecretInAnswersError(offenders)


def _check_required_secrets_supplied(answers: dict[str, Any], desc: discovery.Discovery) -> None:
    """Fail loud if a required secret question has no value in non-interactive mode.

    copier would silently render the placeholder default — clerk refuses instead
    (FR-003c / SC-003c / Constitution V).  A question is "required" in our context
    when it has a falsy default (empty string or None), matching copier's own
    check for secret questions.
    """
    for q in desc.questions:
        if not q.secret:
            continue
        if q.key in answers:
            continue
        # default_raw is reported un-rendered; treat falsy as "no real default"
        if not q.default_raw:
            raise InvalidRunSpecError(
                f"secret question {q.key!r} has no value and no usable default. "
                f"Supply it out-of-band via copier's masked interactive prompt or "
                f"an environment mechanism — not through the run-spec. "
                f"(Constitution V: non-interactive run must not silently default a credential.)"
            )


def _redact_secrets(message: str, secret_keys: list[str], answers: dict[str, Any]) -> str:
    """Scrub secret answer values from an error message before surfacing it.

    copier validator errors can embed the answer value; we replace each secret
    value found in the message with a redaction marker (FR-004 / SC-003).
    Only replaces non-empty values to avoid over-redacting on empty defaults.
    """
    for key in secret_keys:
        val = answers.get(key)
        if val and str(val) in message:
            message = message.replace(str(val), "<redacted>")
    return message


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
    # Discover once; reuse for both secret checks and error redaction below.
    desc = discovery.discover(spec.source, spec.ref)
    # Mechanical enforcement (FR-003a): reject secret keys in the run-spec before
    # any copier call, regardless of SKILL behavior.
    _check_no_secrets(spec.answers, desc)
    # Fail loud on required secrets with no value (FR-003c / Constitution V).
    _check_required_secrets_supplied(spec.answers, desc)
    data = _with_today(spec.answers, today)
    _secret_keys = desc.secret_questions
    # Load user defaults once; select keys relevant to this template (FR-001–003).
    # check=True (dry-run) receives the same user_defaults as the real run (FR-008).
    _raw_defaults = _defaults.load(_defaults.defaults_path())
    _merged_defaults = _defaults.fold_settings_defaults(_raw_defaults)
    user_defaults = _defaults.select_keys(_merged_defaults, desc.questions)
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
            user_defaults=user_defaults or None,
        )
    except UnsafeTemplateError as exc:
        raise UntrustedSourceError(suggest_prefix(spec.source), source=spec.source) from exc
    except ValueError as exc:
        # copier raises a bare ValueError for a missing required answer (verified).
        msg = _redact_secrets(str(exc), _secret_keys, data)
        raise InvalidRunSpecError(f"invalid or incomplete answers: {msg}") from exc
    except CopierError as exc:
        msg = _redact_secrets(str(exc), _secret_keys, data)
        raise ClerkError(f"copier could not complete the operation: {msg}") from exc
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

    For each layer in topological order (stable basename tie-break):
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

    # Load and fold defaults once per init_many call; select per-layer below (FR-007).
    _raw_defaults = _defaults.load(_defaults.defaults_path())
    _merged_defaults = _defaults.fold_settings_defaults(_raw_defaults)

    if not check:
        results: list[RunResult] = []
        for record, af_name in plan:
            _require_reproducible(record.source, record.ref)
            _require_trust_if_action_taking(record.source, record.ref)
            layer_answers = answers_map.get(record.full_id, {})
            # Discover once per layer; reuse for both secret checks and redaction.
            desc = discovery.discover(record.source, record.ref)
            # FR-003a: reject secrets in per-layer answers before any copier call.
            _check_no_secrets(layer_answers, desc)
            # FR-003c: fail loud on required secrets with no value.
            _check_required_secrets_supplied(layer_answers, desc)
            data = {**accumulated, **layer_answers}
            _secret_keys = desc.secret_questions
            user_defaults = _defaults.select_keys(_merged_defaults, desc.questions)
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
                    user_defaults=user_defaults or None,
                )
            except UnsafeTemplateError as exc:
                raise UntrustedSourceError(
                    suggest_prefix(record.source), source=record.source
                ) from exc
            except ValueError as exc:
                msg = _redact_secrets(str(exc), _secret_keys, data)
                raise InvalidRunSpecError(f"invalid or incomplete answers: {msg}") from exc
            except CopierError as exc:
                msg = _redact_secrets(str(exc), _secret_keys, data)
                raise ClerkError(f"copier could not complete the operation: {msg}") from exc
            results.append(RunResult(dest=dest, src=record.source, ref=record.ref, pretend=False))
            _merge_layer_answers(accumulated, dest, af_name)
        return results

    # check=True: all-gaps preflight — run all layers, collect all errors.
    errors: list[str] = []
    for record, af_name in plan:
        _require_reproducible(record.source, record.ref)
        _require_trust_if_action_taking(record.source, record.ref)
        layer_answers = answers_map.get(record.full_id, {})
        # Discover once per layer; reuse for both secret checks and redaction.
        desc = discovery.discover(record.source, record.ref)
        # FR-003a: reject secrets in per-layer answers even in preflight mode.
        _check_no_secrets(layer_answers, desc)
        # FR-003c: fail loud on required secrets with no value.
        _check_required_secrets_supplied(layer_answers, desc)
        data = {**accumulated, **layer_answers}
        _secret_keys = desc.secret_questions
        user_defaults = _defaults.select_keys(_merged_defaults, desc.questions)
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
                user_defaults=user_defaults or None,
            )
        except UnsafeTemplateError as exc:
            raise UntrustedSourceError(suggest_prefix(record.source), source=record.source) from exc
        except ValueError as exc:
            msg = _redact_secrets(str(exc), _secret_keys, data)
            errors.append(f"{record.full_id}: {msg}")
        except CopierError as exc:
            msg = _redact_secrets(str(exc), _secret_keys, data)
            errors.append(f"{record.full_id}: {msg}")
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
    4. Rebuild the DAG + topo-sort (same stable basename tie-break) → the
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
        # a synthetic "_recorded/<basename>" so the basename tie-break resolves to the
        # same key init used, keeping init order == reproduce order).
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


# ---------------------------------------------------------------------------
# Update path (spec 006) — the ONLY place clerk advances a template version
# ---------------------------------------------------------------------------


def _read_answers_metadata(af_path: Path) -> dict[str, Any]:
    """Read the copier-written metadata from an answers file (best-effort)."""
    try:
        raw = yaml.safe_load(af_path.read_text()) or {}
    except Exception:  # noqa: BLE001
        return {}
    return raw if isinstance(raw, dict) else {}


def _scan_conflicts(dest: str, conflict: str) -> list[str]:
    """Post-update scan for conflict markers or .rej files in the destination tree.

    Phase 0 / T002 finding: copier's run_update does NOT raise on conflict — it
    writes inline markers (``<<<<<<< before updating`` / ``>>>>>>> after updating``)
    or .rej files and returns the Worker normally.  We must detect them ourselves.
    The ``<<<<<<< `` prefix catches both copier's own markers and the standard git
    ``<<<<<<< HEAD`` form (future-proofing at no cost).
    """
    dst = Path(dest)
    conflicted: list[str] = []
    if conflict == "rej":
        for path in dst.rglob("*.rej"):
            if ".git" not in path.parts:
                conflicted.append(str(path.relative_to(dst)))
    else:
        # inline mode: scan all text-like files for the conflict-marker prefix
        for path in dst.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts:
                continue
            try:
                text = path.read_bytes()
                if b"<<<<<<< " in text:
                    conflicted.append(str(path.relative_to(dst)))
            except OSError:
                continue
    return conflicted


def _require_trust_if_update_action_taking(source: str, desc: discovery.Discovery) -> None:
    """Trust pre-check for update: refuse if source has migrations OR tasks and is untrusted.

    Migrations run code → same trust surface as _tasks (spec 006 FR-004,
    Constitution V).  Discovery is safe to call on untrusted sources (no code runs).

    Takes an already-computed ``Discovery`` (the caller has discovered the source at
    the target ref) so this pre-check does not re-clone the template.
    """
    if (desc.has_tasks or desc.has_migrations or desc.jinja_extensions) and not trust.is_trusted(
        source
    ):
        raise UntrustedSourceError(suggest_prefix(source), source=source)


def update(
    dest: str,
    *,
    answers_file: Path,
    vcs_ref: str | None = None,
    pretend: bool = False,
    conflict: str = "inline",
    skip_tasks: bool = False,
) -> RunResult:
    """Upgrade one layer of ``dest`` to a newer template version (spec 006 FR-009).

    Mirrors ``reproduce`` in structure: reads the committed answers file, pre-checks
    trust and format, calls ``run_update``, then scans for conflicts.

    Phase 0 / T001 finding: ``skip_tasks=True`` suppresses ``_tasks`` but NOT
    ``_migrations`` — copier calls migration_tasks() unconditionally in _apply_update().
    A separate ``--skip-migrations`` flag would require copier API support that does
    not exist; we document this constraint rather than silently misrepresent it.
    """
    dst = Path(dest)
    if not answers_file.is_file():
        raise ClerkError(f"no answers file at {answers_file!r}; nothing to update")

    raw = _read_answers_metadata(answers_file)
    src_path = raw.get("_src_path")
    current_commit = raw.get("_commit")
    if not src_path:
        raise ClerkError(
            f"answers file {answers_file!r} has no _src_path; cannot update this layer"
        )

    # Discovery at target version (None = latest PEP 440 tag).
    # We also need the raw copier.yml to format-check _migrations (Constitution VI).
    # _check_migrations_format_at_source re-clones shallowly — acceptable because
    # discover() already clones once; the extra clone is needed to get the raw YAML.
    desc = discovery.discover(str(src_path), vcs_ref)

    # Format pre-check: refuse deprecated _migrations form before any run_update call.
    discovery.check_migrations_format_at_source(str(src_path), vcs_ref)

    # Trust pre-check: untrusted source with migrations or tasks → refuse (FR-004).
    # Reuses the `desc` discovered above — no extra clone.
    _require_trust_if_update_action_taking(str(src_path), desc)

    # Already-at-target: if the target version matches current commit, nothing to do.
    target_version = vcs_ref or (desc.versions[-1] if desc.versions else None)
    if target_version and current_commit == target_version:
        return RunResult(dest=dest, src=str(src_path), ref=target_version, pretend=pretend)

    # Downgrade check: copier's run_update also checks this (raises UserMessageError),
    # but we check here to surface a typed DowngradeError before calling copier.
    if target_version and current_commit and desc.versions:
        from packaging.version import InvalidVersion, Version

        try:
            current_v = Version(str(current_commit).lstrip("v"))
            target_v = Version(str(target_version).lstrip("v"))
            if target_v < current_v:
                raise DowngradeError(
                    f"cannot downgrade {str(src_path)!r}: "
                    f"current version {current_commit!r} is newer than "
                    f"target {target_version!r}. Downgrades are not supported; "
                    f"use copier CLI directly if you need to downgrade."
                )
        except InvalidVersion:
            pass  # non-PEP-440 commits (SHA) — let copier handle it

    # Announce the upgrade
    src_basename = str(src_path).rstrip("/").rsplit("/", 1)[-1]
    if src_basename.endswith(".git"):
        src_basename = src_basename[:-4]
    from_label = current_commit or "unknown"
    to_label = target_version or "latest"
    print(f"Upgrading {src_basename}: {from_label} → {to_label}")

    # Build the accumulated answers from the committed file (non-_ keys only)
    data: dict[str, Any] = {k: v for k, v in raw.items() if not k.startswith("_")}

    rel_answers = answers_file.relative_to(dst)

    try:
        run_update(
            dest,
            data=data,
            answers_file=rel_answers,
            vcs_ref=vcs_ref or None,
            defaults=True,
            overwrite=True,
            quiet=True,
            conflict=conflict,  # type: ignore[arg-type]
            pretend=pretend,
            skip_tasks=skip_tasks,
        )
    except UnsafeTemplateError as exc:
        raise UntrustedSourceError(suggest_prefix(str(src_path)), source=str(src_path)) from exc
    except CopierError as exc:
        raise _translate(exc) from exc

    if not pretend:
        conflicted = _scan_conflicts(dest, conflict)
        if conflicted:
            conflict_list = ", ".join(conflicted)
            print(
                f"  ✗ {src_basename}: merge conflict in "
                f"{conflict_list} — resolve and re-run upgrade"
            )
            raise MergeConflictError(conflicted)

    print(f"  ✓ {src_basename} upgraded to {to_label}")
    return RunResult(dest=dest, src=str(src_path), ref=target_version, pretend=pretend)


def update_many(
    dest: str,
    *,
    vcs_ref: str | None = None,
    today: str | None = None,
    pretend: bool = False,
    conflict: str = "inline",
    skip_tasks: bool = False,
) -> list[RunResult]:
    """Upgrade all layers of ``dest`` in dependency order (spec 006 FR-009, FR-010).

    Algorithm (mirrors reproduce_many, but resolves DAG at TARGET versions):
    1. Enumerate committed .copier-answers*.yml files.
    2. For each, read _src_path + _commit.
    3. Discover each template at the TARGET version (vcs_ref or latest).
    4. Format-check migrations + trust pre-check per layer.
    5. Rebuild DAG at target versions (may add new deps from upgraded templates).
       Refuse if any new dep is not in the project (Q-006b → dangling edge → OrderingError).
    6. Emit per-layer upgrade announcements.
    7. Loop update() per layer in order.

    N=1 behaves identically to single-layer update (uniform loop, spec 010).
    """
    from clerk import ordering  # local import avoids circular at module load

    # Prerequisite: the tree must be clean before an upgrade. Two reasons, both point
    # to "commit or stash first": (1) a real upgrade commits each layer between layers
    # (git add -A), which would sweep the user's unrelated uncommitted work into a clerk
    # commit; (2) copier's own run_update refuses a dirty tree even in pretend mode.
    # Checked up front, before any network clone, so clerk surfaces one clear error
    # instead of copier's cryptic "repository is dirty" mid-run.
    if discovery.worktree_is_dirty(dest):
        raise DirtyWorktreeError(
            f"{dest!r} has uncommitted changes. Upgrade requires a clean working tree "
            f"(it commits each template layer between layers, and copier refuses a dirty "
            f"tree). Commit or stash your changes first, then re-run the upgrade."
        )

    answers_files = enumerate_answers_files(dest)
    if not answers_files:
        raise ClerkError(f"no .copier-answers*.yml at {dest!r}; nothing to update")

    records: list[TemplateRecord] = []
    edges_by_basename: dict[str, dict[str, Any]] = {}
    file_by_basename: dict[str, Path] = {}

    for af_path in answers_files:
        raw = _read_answers_metadata(af_path)
        if not isinstance(raw, dict):
            raise ClerkError(f"answers file {af_path} did not parse to a mapping")

        src_path = raw.get("_src_path")
        commit = raw.get("_commit")
        if not src_path:
            raise ClerkError(f"answers file {af_path!r} has no _src_path; cannot update this layer")
        if not commit:
            raise ClerkError(f"answers file {af_path!r} has no _commit; cannot update this layer")

        # Discover at TARGET version (not pinned commit) — this is what makes upgrade
        # different from reproduce: we re-solve edges at the version we're upgrading TO.
        disc = discovery.discover(str(src_path), vcs_ref)

        # Format pre-check and trust pre-check before any run_update call.
        # Trust check reuses `disc` (discovered just above) — no extra clone.
        discovery.check_migrations_format_at_source(str(src_path), vcs_ref)
        _require_trust_if_update_action_taking(str(src_path), disc)

        basename = str(src_path).rstrip("/").rsplit("/", 1)[-1]
        if basename.endswith(".git"):
            basename = basename[:-4]
        full_id = f"_recorded/{basename}"

        record = TemplateRecord(
            full_id=full_id,
            source=str(src_path),
            ref=vcs_ref or (disc.versions[-1] if disc.versions else str(commit)),
            versions=disc.versions,
            reproducible=disc.reproducible,
            has_tasks=disc.has_tasks,
            questions=[q.key for q in disc.questions],
        )
        records.append(record)
        edges_by_basename[basename] = disc.dependency_edges
        file_by_basename[basename] = af_path

    # Recompute DAG at target versions.  build_dag raises OrderingError on dangling
    # edges — this is the Q-006b enforcement point: a new dep in the upgraded template
    # that is not in the project appears as a dangling edge and is refused here.
    plan = ordering.layer_plan_from_edges(records, edges_by_basename)

    results: list[RunResult] = []
    for record, _af_name in plan:
        basename = record.full_id.rsplit("/", 1)[-1]
        af_path = file_by_basename[basename]
        result = update(
            dest,
            answers_file=af_path,
            vcs_ref=vcs_ref,
            pretend=pretend,
            conflict=conflict,
            skip_tasks=skip_tasks,
        )
        results.append(result)
        # copier's run_update requires a clean git working tree before each layer.
        # After upgrading a layer, commit the changes so the next layer's run_update
        # sees a clean state. pretend=True writes nothing so no commit is needed.
        if not pretend:
            # copier's run_update requires a clean git tree before each layer.
            # Commit after each layer so the next layer's run_update sees clean state.
            # This is multi-layer coordination copier cannot do cross-template (C-11).
            discovery.git_commit_if_dirty(dest, f"clerk: upgrade {basename}")
    return results
