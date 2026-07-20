"""The deterministic phase-2 executor: drive copier to init / check / reproduce / update.

This module contains ZERO agent involvement. It reads a frozen inputs document (the
run-spec the skill authored), then calls copier's **public** functions —
``run_copy`` / ``run_recopy`` / ``run_update`` — and translates copier's outcomes into
bailiff's small error types (spec FR-005, FR-010, FR-011, FR-015). It uses no deprecated
copier surface.

Invariants (constitution III/V):

* init      → ``run_copy(data=…, defaults=True, overwrite=True, settings=…)``.
* reproduce → ``run_recopy(vcs_ref=VcsRef.CURRENT, defaults=True, overwrite=True)``
  — faithful replay at the recorded commit; NEVER bare recopy (which upgrades).
* check     → ``run_copy(pretend=True, …)`` — copier's own dry run validates without
  writing; bailiff adds no bespoke validator.
* update    → ``run_update(data=…, defaults=True, overwrite=True, settings=…)``
  — the ONLY place bailiff advances a template version; announced, explicit (spec 006).
* The current date is injected as the ``today`` answer so it freezes into the
  recorded answers and replays on reproduce (FR-007).
* Trust is never written here; an untrusted source raises ``UntrustedSourceError``.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from copier import run_copy, run_recopy, run_update
from copier._types import VcsRef
from copier.errors import CopierError, UnsafeTemplateError

from bailiff import agent as _agent
from bailiff import defaults as _defaults
from bailiff import discovery, trust
from bailiff.catalog import TemplateRecord
from bailiff.errors import (
    BailiffError,
    CollisionError,
    DirtyWorktreeError,
    DowngradeError,
    InvalidRunSpecError,
    MergeConflictError,
    NotReproducibleError,
    OrderingError,
    SecretInAnswersError,
    UntrustedSourceError,
)
from bailiff.trust import suggest_prefix

# spec 014 FR-014/R10: schema marker written to each answers file post-render.
# reproduce_many refuses when this marker is absent or carries a different version.
_BAILIFF_SCHEMA_KEY = "_bailiff_schema"
_BAILIFF_SCHEMA_VERSION = "014"

# spec 015: reserved answers-file key holding frozen agent-task output, replayed
# (agent-free) on reproduce. Shape: {slot: {relative_path: content}} per producer
# module (contracts/agent-tasks.md §4).
_AGENT_FROZEN_KEY = "_agent_frozen"


@dataclass(frozen=True)
class RunSpec:
    """The frozen inputs the skill hands to the deterministic phase (FR-005).

    A documented plain mapping (the skill authors it as JSON/YAML): the fetchable
    source, an optional pinned ref, the answer values, and the destination. ``today``
    is injected by bailiff if not already supplied.
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
            f"never be reproduced, so bailiff refuses to render it."
        )


def _require_trust_if_action_taking(source: str, ref: str | None) -> None:
    """If the template takes actions and the source is untrusted, refuse with the prefix.

    Advisory pre-check so bailiff can name the exact prefix; copier re-checks
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

    copier would silently render the placeholder default — bailiff refuses instead
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


def _translate(exc: CopierError) -> BailiffError:
    """Map a copier error to a legible bailiff error (FR-010)."""
    if isinstance(exc, UnsafeTemplateError):
        return UntrustedSourceError("<source prefix>", source=None)
    return BailiffError(f"copier could not complete the operation: {exc}")


def init(spec: RunSpec, *, today: str | None = None, check: bool = False) -> RunResult:
    """Generate a project from ``spec`` (or dry-run validate when ``check``).

    ``check=True`` uses copier's own ``pretend`` dry run to validate inputs without
    writing anything (FR-006, FR-008).
    """
    # Expand a bare ``owner/repo`` GitHub shorthand to a clonable URL once, up
    # front, so trust, discovery, copier, and the recorded _src_path all agree
    # (copier treats bare owner/repo as a local path and would fail otherwise).
    source = discovery.resolve_locator(spec.source)
    _require_reproducible(source, spec.ref)
    _require_trust_if_action_taking(source, spec.ref)
    # Discover once; reuse for both secret checks and error redaction below.
    desc = discovery.discover(source, spec.ref)
    # Mechanical enforcement (FR-003a): reject secret keys in the run-spec before
    # any copier call, regardless of SKILL behavior.
    _check_no_secrets(spec.answers, desc)
    # Fail loud on required secrets with no value (FR-003c / Constitution V).
    _check_required_secrets_supplied(spec.answers, desc)
    # spec 016 FR-004/006: whole-plan (here N=1) tool preflight before any render —
    # runs under check=True too. Synthesize the one-layer plan/descs/answers shape.
    _basename = source.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    _fid = f"_/{_basename}"
    _rec = TemplateRecord(
        full_id=_fid,
        source=source,
        ref=spec.ref or "",
        versions=[],
        reproducible=True,
        has_tasks=desc.has_tasks,
        questions=[],
    )
    _check_required_tools([(_rec, ".copier-answers.yml")], {_fid: desc}, {_fid: spec.answers})
    data = _with_today(spec.answers, today)
    _secret_keys = desc.secret_questions
    # Load user defaults once; select keys relevant to this template (FR-001–003).
    # check=True (dry-run) receives the same user_defaults as the real run (FR-008).
    _raw_defaults = _defaults.load(_defaults.defaults_path())
    _merged_defaults = _defaults.fold_settings_defaults(_raw_defaults)
    user_defaults = _defaults.select_keys(_merged_defaults, desc.questions)
    # Canonicalize the destination: copier's _external_data loader compares a
    # resolve()-d answers-file path against the (unresolved) subproject root, so a
    # dest under a symlinked prefix (macOS /tmp → /private/tmp) raises
    # ForbiddenPathError. realpath the parent up front so the two agree. Single
    # init has no _external_data today, but this keeps init and init_many uniform.
    dest = _canonical_dest(spec.dest)
    try:
        run_copy(
            source,
            dest,
            data=data,
            vcs_ref=spec.ref,
            defaults=True,
            overwrite=True,
            quiet=True,
            pretend=check,
            user_defaults=user_defaults or None,
        )
    except UnsafeTemplateError as exc:
        raise UntrustedSourceError(suggest_prefix(source), source=source) from exc
    except ValueError as exc:
        # copier raises a bare ValueError for a missing required answer (verified).
        msg = _redact_secrets(str(exc), _secret_keys, data)
        raise InvalidRunSpecError(f"invalid or incomplete answers: {msg}") from exc
    except CopierError as exc:
        msg = _redact_secrets(str(exc), _secret_keys, data)
        raise BailiffError(f"copier could not complete the operation: {msg}") from exc
    # spec 014 FR-014/R10: write schema marker to the answers file so reproduce_many
    # can gate on it.  Single-template init writes `.copier-answers.yml` (the default
    # copier name when no custom answers_file is supplied).
    if not check:
        _write_schema_marker(dest, ".copier-answers.yml")
        # Whole-project initial commit as the last engine step (see
        # _finalize_initial_commit) so the tree is clean after init.
        _finalize_initial_commit(spec.answers, dest)
    return RunResult(dest=dest, src=source, ref=spec.ref, pretend=check)


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
    # Canonicalize (idempotent) so copier's _external_data path check agrees on a
    # symlinked prefix (macOS /tmp → /private/tmp). reproduce_many already passes a
    # canonical dest; a direct single-layer reproduce needs it too.
    dest = _canonical_dest(dest)
    dst = Path(dest)
    target = answers_file if answers_file is not None else dst / ".copier-answers.yml"
    if not target.is_file():
        raise BailiffError(f"no answers file at {target!r}; nothing to reproduce")
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


def _check_capability_conflicts(
    records: list[TemplateRecord],
    dest: str,
    exclusive_capabilities: frozenset[str],
) -> None:
    """Warn (never raise) when >1 provider of an exclusive capability is present.

    ``exclusive_capabilities`` is the catalog-wide set of capability names where ANY
    listed module declares ``exclusive: true`` (group-infection semantics, spec 013
    FR-008) — pre-computed by the CLI so this function needs no catalog awareness.
    Providers are collected from the current selection plus any already-installed
    modules recorded in ``dest``'s ``.copier-answers.*.yml`` files (incremental-add
    path, FR-011). Capabilities are informational: this NEVER blocks the run.
    """
    if not exclusive_capabilities:
        return

    providers: dict[str, list[str]] = {}
    for rec in records:
        base = rec.full_id.rsplit("/", 1)[-1]
        for cap in rec.provides:
            providers.setdefault(cap, []).append(base)

    # Incremental add: read installed modules' capabilities at their pinned commit.
    for af_path in enumerate_answers_files(dest):
        raw = _read_answers_metadata(af_path)
        src = raw.get("_src_path")
        commit = raw.get("_commit")
        if not src or not commit:
            continue
        try:
            disc = discovery.discover(str(src), str(commit))
        except BailiffError:
            continue  # warn-only check is best-effort; never fail the init here
        base = str(src).rstrip("/").rsplit("/", 1)[-1]
        base = base.removesuffix(".git")
        for cap in disc.provides:
            providers.setdefault(cap, []).append(base)

    for cap, mods in sorted(providers.items()):
        uniq = list(dict.fromkeys(mods))  # a re-selected installed module counts once
        if len(uniq) > 1 and cap in exclusive_capabilities:
            warnings.warn(
                f"CAPABILITY CONFLICT: {cap!r} is declared exclusive in the catalog, "
                f"but multiple selected/installed modules provide it: {', '.join(uniq)}. "
                f"These modules are alternatives — proceeding anyway (capability tags "
                f"are informational and never block).",
                stacklevel=2,
            )


def _scan_init_collisions(
    plan: list[tuple[TemplateRecord, str]],
    dest: str,
    accumulated: dict[str, Any],
    answers_map: dict[str, dict[str, Any]],
) -> None:
    """Pre-render overlap scan: hard-stop before any real write (spec 013 FR-013).

    Renders each layer into an isolated temp dir and compares the written file
    sets (answers files excluded). A static glob of the template tree would miss
    Jinja conditionals in filenames; the render is the only correct observable
    output. ``skip_tasks=True`` is a SAFETY REQUIREMENT: without it, task-bearing
    modules would execute their ``_tasks`` (``gh repo create``, git init, network
    calls) during what must be a side-effect-free scan. Raises ``CollisionError``
    on the first overlapping path; temp dirs are always cleaned up. Every layer
    has already passed the trust/reproducibility/secret pre-checks.

    The scan renders each layer ALONE, so an ``_external_data`` consumer sees no
    producer answers file and copier resolves the alias to an empty dict. That is
    correct for overlap detection: no template FILENAME branches on
    ``_external_data`` (only file bodies do), so the degraded solo render yields
    the same path set as the real run. The temp dir MUST be canonicalized with
    ``realpath`` — on macOS ``$TMPDIR`` is a ``/var → /private/var`` symlink, and
    copier's ``_external_data`` loader compares a ``resolve()``-d answers-file path
    against the unresolved subproject root, raising ``ForbiddenPathError`` for
    every consumer otherwise (which silently skipped the overlap check).
    """
    seen: dict[str, str] = {}  # relative path → full_id of the layer that wrote it
    for record, af_name in plan:
        layer_answers = answers_map.get(record.full_id, {})
        data = {**accumulated, **layer_answers}
        tmp = os.path.realpath(tempfile.mkdtemp(prefix="bailiff-collision-"))
        try:
            try:
                run_copy(
                    record.source,
                    tmp,
                    data=data,
                    vcs_ref=record.ref or None,
                    answers_file=af_name,
                    defaults=True,
                    overwrite=True,
                    quiet=True,
                    pretend=False,
                    skip_tasks=True,
                )
            except UnsafeTemplateError as exc:
                raise UntrustedSourceError(
                    suggest_prefix(record.source), source=record.source
                ) from exc
            except (ValueError, CopierError) as exc:
                # The real render (or preflight) owns answer-error reporting with
                # secret redaction; a layer that cannot render cannot collide.
                warnings.warn(
                    f"collision scan could not render {record.full_id!r} "
                    f"({type(exc).__name__}); overlap check skipped for this layer",
                    stacklevel=2,
                )
                continue
            tmp_root = Path(tmp)
            for path in sorted(tmp_root.rglob("*")):
                if not path.is_file():
                    continue
                rel = str(path.relative_to(tmp_root))
                name = path.name
                if name.startswith(".copier-answers") and name.endswith(".yml"):
                    continue
                if rel in seen:
                    raise CollisionError(rel, [seen[rel], record.full_id])
                seen[rel] = record.full_id
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def _check_external_data_deps(
    plan: list[tuple[TemplateRecord, str]],
    descs: dict[str, discovery.Discovery],
) -> None:
    """Enforce _external_data hard data-dependencies (spec 014 FR-006/R6).

    For each module in the plan, inspect its ``external_data_aliases`` mapping.
    Each alias points to a producer basename.  If that basename is absent from
    the selection, raise a loud ``OrderingError`` naming the alias and the
    missing producer — never a silent empty render (FR-006 inverted).

    Producer presence is enough; ordering (producer before consumer) is already
    guaranteed by the layer plan because discovery now exposes the mapping and
    callers add a depends_on edge for the producer.  This function is the
    preflight that CATCHES the missing-producer case before any render.
    """
    basename_set = {record.full_id.rsplit("/", 1)[-1] for record, _ in plan}

    for record, _ in plan:
        basename = record.full_id.rsplit("/", 1)[-1]
        desc = descs.get(record.full_id)
        if not desc:
            continue
        for alias, producer_basename in desc.external_data_aliases.items():
            if producer_basename not in basename_set:
                raise OrderingError(
                    f"missing _external_data producer: {basename!r} declares "
                    f"_external_data alias {alias!r} pointing at producer "
                    f"{producer_basename!r}, but {producer_basename!r} is not in "
                    f"the selection. Add {producer_basename!r} to the selection or "
                    f"remove the alias. (spec 014 FR-006/R6 — a fact read is a hard "
                    f"data-dependency; copier would silently return {{}} → empty render.)"
                )


def _check_required_tools(
    plan: list[tuple[TemplateRecord, str]],
    descs: dict[str, discovery.Discovery],
    answers_map: dict[str, dict[str, Any]],
) -> None:
    """Whole-plan tool preflight — fail BEFORE any render if a required tool is missing.

    spec 016 FR-004: for each module, for each ``_bailiff_requires`` entry whose ``when``
    answer-key (if set) is truthy in that layer's answers, ``shutil.which(tool)``. Collect
    ALL misses across the plan and raise ONE ``BailiffError`` naming every
    ``tool — needed by <module>``. Runs after trust/reproducibility/external-data/collision
    (which already ran discovery), before the first ``run_copy`` — so a missing tool never
    leaves a partial tree. copier renders THEN runs ``_tasks``, so the per-module
    ``command -v`` guard is only a backstop; this is the true pre-write gate.

    A tool is checked only under a truthy ``when`` (opt-in), so ``install_hooks: false``
    needs no hook-manager binary (FR-005/D2: modules provisioning via mise declare mise).
    """
    misses: list[str] = []
    seen: set[str] = set()  # dedupe (tool, module) across layers
    for record, _ in plan:
        basename = record.full_id.rsplit("/", 1)[-1]
        desc = descs.get(record.full_id)
        if not desc or not desc.requires:
            continue
        answers = answers_map.get(record.full_id, {})
        for entry in desc.requires:
            tool = entry["tool"]
            when = entry.get("when", "")
            if when and not _answer_truthy(answers.get(when)):
                continue
            key = f"{tool}\0{basename}"
            if key in seen:
                continue
            seen.add(key)
            if shutil.which(tool) is None:
                misses.append(f"  {tool} — needed by {basename}")
    if misses:
        raise BailiffError(
            "required tool(s) not found on PATH (install them, then re-run):\n" + "\n".join(misses)
        )


def _write_schema_marker(dest: str, af_name: str) -> None:
    """Append ``_bailiff_schema: '014'`` to the answers file post-render (spec 014 R10).

    Uses an APPEND-ONLY write: if the marker is already present (idempotent re-run),
    do nothing.  Otherwise append a single YAML line to the end of the file.
    This preserves copier's exact serialization of the answers content rather than
    re-emitting through PyYAML (which can reorder keys / change quote style and would
    perturb the committed reproduce state).

    The marker line is ``_bailiff_schema: '014'`` — single-quoted to match the YAML
    string literal form copier uses for its own metadata keys.
    """
    af_path = Path(dest) / af_name
    if not af_path.is_file():
        return
    existing = af_path.read_text()
    # Idempotent: skip if marker already present anywhere in the file.
    if f"{_BAILIFF_SCHEMA_KEY}:" in existing:
        return
    # Append marker as a single YAML line.  Ensure file ends with newline first.
    if existing and not existing.endswith("\n"):
        existing += "\n"
    af_path.write_text(existing + f"{_BAILIFF_SCHEMA_KEY}: '{_BAILIFF_SCHEMA_VERSION}'\n")


def _run_agent_slot(
    desc: discovery.Discovery,
    field_name: str,
    slot: str,
    *,
    basename: str,
    dest: str,
    selection: list[str],
    answers_files: dict[str, str],
    agent: _agent.AgentTask,
    written: dict[str, str],
) -> None:
    """Invoke one agent-task slot at INIT, write its files, and freeze them (FR-006/009).

    ``field_name`` is ``agent_tasks`` or ``post_agent_tasks``; ``slot`` is ``pre`` or
    ``post``. No-op when the module did not declare that slot. Records every written
    path in ``written`` (path → producing module basename) so the reproduce-safety
    lint can check managed-owned overlaps (FR-012).
    """
    block = getattr(desc, field_name)
    instruction = block.get(slot)
    if not instruction:
        return
    slot_id = f"{field_name}.{slot}"
    context = _agent.AgentContext(
        dest=dest,
        module=basename,
        slot=slot_id,
        selection=selection,
        answers_files=answers_files,
    )
    result = agent(instruction, context) or {}
    if not isinstance(result, dict):
        raise BailiffError(
            f"agent task {slot_id!r} from {basename!r} returned "
            f"{type(result).__name__}, expected a {{path: content}} mapping"
        )
    dest_path = Path(dest)
    for rel, content in result.items():
        target = dest_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        written[str(rel)] = basename
    _freeze_agent_output(dest, _answers_file_for(basename), slot_id, result)


def _answers_file_for(basename: str) -> str:
    """The per-layer answers-file name for a module basename (spec 014 convention)."""
    return f".copier-answers.{basename}.yml"


def _freeze_agent_output(dest: str, af_name: str, slot_id: str, result: dict[str, str]) -> None:
    """Append the agent slot's output to the producer's answers file (FR-009).

    Frozen shape (opaque to bailiff, replayed verbatim on reproduce):

        _agent_frozen:
          <slot_id>:
            <relative_path>: <content>

    Merges into any existing ``_agent_frozen`` block (multiple slots per module).
    Uses PyYAML only for THIS block appended after copier's own serialization, so
    copier's answer lines stay byte-stable (like ``_write_schema_marker``).
    """
    af_path = Path(dest) / af_name
    if not af_path.is_file() or not result:
        return
    existing = af_path.read_text()
    parsed = yaml.safe_load(existing) or {}
    frozen = parsed.get(_AGENT_FROZEN_KEY) or {}
    frozen[slot_id] = dict(result)
    # Rewrite the file: copier answers first (dropping any prior _agent_frozen
    # block, always appended last), then the merged block as a single YAML tail.
    body = _strip_frozen_block(existing)
    if body and not body.endswith("\n"):
        body += "\n"
    tail = yaml.safe_dump({_AGENT_FROZEN_KEY: frozen}, sort_keys=True, default_flow_style=False)
    af_path.write_text(body + tail)


def _strip_frozen_block(text: str) -> str:
    """Return ``text`` without a trailing top-level ``_agent_frozen:`` block.

    The block is always appended last (this function is its only writer), so we cut
    from the ``_agent_frozen:`` line to EOF. Absent → returned unchanged.
    """
    marker = f"{_AGENT_FROZEN_KEY}:"
    idx = text.find(f"\n{marker}")
    if text.startswith(marker):
        return ""
    if idx == -1:
        return text
    return text[: idx + 1]


def _replay_frozen_block(dest: str, block: dict[str, Any]) -> None:
    """Replay a producer's frozen agent output at REPRODUCE — no agent (FR-010/011).

    ``block`` is the module's ``_agent_frozen`` mapping ({slot: {path: content}}),
    captured before the reproduce loop. Re-writes every recorded ``{path: content}``.
    Deterministic; the phase-1 agent is never invoked.
    """
    dest_path = Path(dest)
    for _slot_id, files in block.items():
        if not isinstance(files, dict):
            continue
        for rel, content in files.items():
            target = dest_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content if isinstance(content, str) else str(content))


def _rewrite_frozen_block(dest: str, af_name: str, block: dict[str, Any]) -> None:
    """Re-append an ``_agent_frozen`` block to an answers file after reproduce.

    copier's run_recopy re-renders the answers file without the appended block, so
    reproduce must restore it (keeping the reproduced tree reproducible again). Same
    append-after-copier-serialization discipline as ``_freeze_agent_output``.
    """
    af_path = Path(dest) / af_name
    if not af_path.is_file() or not block:
        return
    body = _strip_frozen_block(af_path.read_text())
    if body and not body.endswith("\n"):
        body += "\n"
    tail = yaml.safe_dump({_AGENT_FROZEN_KEY: block}, sort_keys=True, default_flow_style=False)
    af_path.write_text(body + tail)


def _lint_agent_managed_overlap(
    plan: list[tuple[TemplateRecord, str]],
    descs: dict[str, discovery.Discovery],
    dest: str,
    agent_written: dict[str, str],
) -> None:
    """Fail loud if an agent task wrote a MANAGED-render path without freezing it (FR-012).

    A managed path re-renders byte-identically on reproduce and would clobber the
    agent output. Since every agent write is frozen by ``_run_agent_slot``, the only
    way to violate this is an agent that writes a path also emitted by a template's
    managed render AND that we could not freeze (no producer answers file). We detect
    the overlap: agent-written paths that also exist as committed managed renders must
    be present in some ``_agent_frozen`` block.
    """
    frozen_paths: set[str] = set()
    for _record, af_name in plan:
        af_path = Path(dest) / af_name
        if not af_path.is_file():
            continue
        parsed = yaml.safe_load(af_path.read_text()) or {}
        frozen = parsed.get(_AGENT_FROZEN_KEY) or {}
        for files in frozen.values():
            if isinstance(files, dict):
                frozen_paths.update(str(p) for p in files)
    unfrozen = sorted(p for p in agent_written if p not in frozen_paths)
    if unfrozen:
        raise BailiffError(
            "reproduce-safety: agent task wrote path(s) not captured in _agent_frozen, "
            f"so a managed re-render would clobber them on reproduce: {unfrozen}"
        )


def _canonical_dest(dest: str) -> str:
    """Resolve symlinks in the destination path so copier's path checks agree.

    copier's ``_external_data`` loader compares a ``resolve()``-d answers-file path
    against the subproject root it holds unresolved; when the dest sits under a
    symlinked prefix (macOS ``/tmp`` → ``/private/tmp``) the two never match and
    it raises ``ForbiddenPathError`` for every cross-module read. ``realpath``
    resolves symlinks in the existing ancestors and leaves the not-yet-created
    leaf literal, so it is safe before the dir exists. Idempotent.
    """
    return os.path.realpath(dest)


def _answer_truthy(value: Any) -> bool:
    """Truthiness for an answer value. copier serializes bools as real booleans, but
    a run-spec may carry strings — accept the common truthy string forms too."""
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "on"}
    return bool(value)


def _initial_commit_requested(all_answers: dict[str, Any]) -> bool:
    """True when the scaffold should be committed by the engine after the full run.

    Reads the ``initial_commit`` and ``run_git_init`` answers (produced by
    ``bailiff-mod-base``). Both must be truthy: a commit needs a repo, and it is
    opt-in.
    """
    return _answer_truthy(all_answers.get("initial_commit")) and _answer_truthy(
        all_answers.get("run_git_init", True)
    )


def _finalize_initial_commit(all_answers: dict[str, Any], dest: str) -> None:
    """Commit the whole scaffold once, AFTER the full render loop + post-tasks + markers.

    The initial commit is a whole-project concern, not a per-module task: a base
    ``_task`` fires at base's position in the render loop (base is ``pre`` phase),
    so it would commit only base's own files and leave every later layer's output —
    plus post-task outputs (``.gitignore`` concat, the pre-commit bundler) and the
    appended ``_bailiff_schema`` markers — uncommitted. Running the commit here, as
    the last engine step, leaves a clean tree after init. Gated on
    ``initial_commit and run_git_init``; a no-op when the tree is already clean.
    """
    if not _initial_commit_requested(all_answers):
        return
    discovery.git_commit_if_dirty(dest, "Initial project scaffold")


def _run_post_tasks(
    plan: list[tuple[TemplateRecord, str]],
    descs: dict[str, discovery.Discovery],
    dest: str,
) -> None:
    """Run _post_tasks for all modules in plan order, after the render loop (spec 014 FR-021/R11).

    Collects _post_tasks across all selected modules in depends_on order and
    executes them in the destination directory.

    Trust gate: ``_require_trust_if_action_taking`` is called here for each module
    that has post-tasks (Constitution V — post-tasks run arbitrary shell).
    ``has_tasks=True`` is already set by discovery when ``_post_tasks`` is present,
    so the pre-render loop's trust check would also catch untrusted sources, but we
    re-check here as the authoritative guard for the post-task execution path.

    Failure handling: a non-zero exit code raises ``BailiffError``, mirroring how
    copier surfaces inline ``_tasks`` failures — a failing post-task must not pass
    silently.

    Execution is delegated to ``discovery.run_post_task`` so that runner.py stays
    process-invocation-free (FR-004: secrets must never appear in argv).
    """
    for record, _ in plan:
        desc = descs.get(record.full_id)
        if not desc or not desc.post_tasks:
            continue
        # Trust gate: refuse to run post-tasks from an untrusted source (Constitution V).
        _require_trust_if_action_taking(record.source, record.ref)
        basename = record.full_id.rsplit("/", 1)[-1]
        for i, task in enumerate(desc.post_tasks):
            # task may be a string or a dict with 'command' + optional 'when'
            cmd = task.get("command", "") if isinstance(task, dict) else str(task)
            if not cmd:
                continue
            rc = discovery.run_post_task(cmd, dest)
            if rc != 0:
                raise BailiffError(
                    f"_post_task #{i} from {basename!r} failed with exit code {rc}: {cmd!r}"
                )


def init_many(
    selection: list[tuple[TemplateRecord, dict[str, Any]]],
    dest: str,
    *,
    today: str | None = None,
    check: bool = False,
    exclusive_capabilities: frozenset[str] = frozenset(),
    agent: _agent.AgentTask = _agent.noop_agent,
) -> list[RunResult]:
    """Apply (or preflight-check) a multi-template selection in dependency order.

    ``selection`` is a list of ``(record, answers)`` pairs where ``answers`` is the
    per-layer answer dict from the run-spec.

    spec 014 FR-001/002: accumulated stays ``{today}`` — no private answers bleed
    across layers.  Cross-module facts flow exclusively via copier's ``_external_data``
    mechanism; bailiff enforces that each declared alias has its producer present in
    the selection (FR-006/R6).

    For each layer in topological order (phase → DAG → basename tie-break):
    1. Pre-checks trust + reproducibility (same guards as single-template ``init``).
    2. Runs ``run_copy`` with ``{today, ...per-layer answers}`` — no cross-layer bleed.
    3. Writes ``_bailiff_schema: '014'`` to the answers file (FR-014/R10).
    4. After the full render loop, runs ``_post_tasks`` in module order (FR-021/R11).

    ``check=True`` (all-gaps preflight, C-10): runs every layer with ``pretend=True``,
    collects errors across ALL layers, and raises a single aggregated
    ``InvalidRunSpecError`` naming every missing/invalid answer — never stops at the
    first failing layer.  Writes nothing.

    N=1 behaves identically to single-template ``init`` (uniform loop, spec 010).
    """
    from bailiff import ordering  # local import avoids circular at module load

    # Expand any bare ``owner/repo`` shorthand to a clonable URL up front, so
    # trust/discovery/copier/recorded _src_path all agree (copier treats bare
    # owner/repo as a local path and would fail). TemplateRecord.source is the
    # "normalized/expanded source used for discovery" — normalize it here.
    for record, _a in selection:
        record.source = discovery.resolve_locator(record.source)
    # Canonicalize the destination so copier's _external_data path check (a
    # resolve()-d answers-file path vs the unresolved subproject root) agrees —
    # a symlinked prefix (macOS /tmp → /private/tmp) otherwise raises
    # ForbiddenPathError for every cross-module read.
    dest = _canonical_dest(dest)

    records = [r for r, _ in selection]
    answers_map: dict[str, dict[str, Any]] = {r.full_id: a for r, a in selection}
    plan = ordering.layer_plan(records)
    # Capability conflicts warn on BOTH the real run and the preflight (FR-008);
    # reproduce/update paths never consult capabilities (FR-012 / SC-008).
    _check_capability_conflicts(records, dest, exclusive_capabilities)
    # accumulated is seeded ONLY with today — it NEVER accretes private answers
    # from rendered layers (spec 014 FR-001/002/003).
    accumulated: dict[str, Any] = _with_today({}, today)

    # Load and fold defaults once per init_many call; select per-layer below (FR-007).
    _raw_defaults = _defaults.load(_defaults.defaults_path())
    _merged_defaults = _defaults.fold_settings_defaults(_raw_defaults)

    if not check:
        # ALL pre-render guards run for every layer BEFORE the collision scan, so
        # the scan never renders an untrusted/unreproducible source and never sees
        # a run-spec that violates the secret rules (FR-003a/c). Discover once per
        # layer here and reuse below (one clone per layer, same as before).
        descs: dict[str, discovery.Discovery] = {}
        for record, _af in plan:
            _require_reproducible(record.source, record.ref)
            _require_trust_if_action_taking(record.source, record.ref)
            layer_answers = answers_map.get(record.full_id, {})
            desc = discovery.discover(record.source, record.ref)
            _check_no_secrets(layer_answers, desc)
            _check_required_secrets_supplied(layer_answers, desc)
            descs[record.full_id] = desc
        # spec 014 FR-006/R6: enforce _external_data hard data-dependencies.
        # Producer absent → loud OrderingError before any render.
        _check_external_data_deps(plan, descs)
        # spec 016 FR-004: whole-plan tool preflight — fail before any render if a
        # required tool is missing (copier renders then runs _tasks, so a _task
        # guard is only a backstop).
        _check_required_tools(plan, descs, answers_map)
        # Init-only collision hard-stop (FR-013): renders to isolated temp dirs,
        # raises CollisionError before any write into dest.
        _scan_init_collisions(plan, dest, accumulated, answers_map)
        # spec 015 agent-task context: basenames in render (sort) order + each
        # layer's answers-file path. The agent projects from the actual selection.
        _basenames = [record.full_id.rsplit("/", 1)[-1] for record, _ in plan]
        _answers_files = {b: _answers_file_for(b) for b in _basenames}
        _agent_written: dict[str, str] = {}
        results: list[RunResult] = []
        for record, af_name in plan:
            basename = record.full_id.rsplit("/", 1)[-1]
            layer_answers = answers_map.get(record.full_id, {})
            desc = descs[record.full_id]
            # spec 014 FR-001/002: data= is {today} + per-layer answers only.
            # No accumulated cross-layer bleed.
            data = {**accumulated, **layer_answers}
            _secret_keys = desc.secret_questions
            user_defaults = _defaults.select_keys(_merged_defaults, desc.questions)

            def _agent_slot(
                field_name: str,
                slot: str,
                _desc: discovery.Discovery = desc,
                _bn: str = basename,
            ) -> None:
                _run_agent_slot(
                    _desc,
                    field_name,
                    slot,
                    basename=_bn,
                    dest=dest,
                    selection=_basenames,
                    answers_files=_answers_files,
                    agent=agent,
                    written=_agent_written,
                )

            # spec 015 FR-006: render → _agent_tasks.pre → _tasks → _agent_tasks.post.
            # copier runs render + inline _tasks atomically, so pre wraps the copier
            # call and post follows it.
            _agent_slot("agent_tasks", "pre")
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
                raise BailiffError(f"copier could not complete the operation: {msg}") from exc
            results.append(RunResult(dest=dest, src=record.source, ref=record.ref, pretend=False))
            # spec 014 FR-014/R10: write schema marker post-render (not a copier answer).
            _write_schema_marker(dest, af_name)
            _agent_slot("agent_tasks", "post")
        # spec 015 FR-007: post-loop — every _post_agent_tasks.pre → _post_tasks →
        # every _post_agent_tasks.post, in module sort order within each stage.
        for record, _af in plan:
            _run_agent_slot(
                descs[record.full_id],
                "post_agent_tasks",
                "pre",
                basename=record.full_id.rsplit("/", 1)[-1],
                dest=dest,
                selection=_basenames,
                answers_files=_answers_files,
                agent=agent,
                written=_agent_written,
            )
        # spec 014 FR-021/R11: run _post_tasks after the full render loop.
        _run_post_tasks(plan, descs, dest)
        for record, _af in plan:
            _run_agent_slot(
                descs[record.full_id],
                "post_agent_tasks",
                "post",
                basename=record.full_id.rsplit("/", 1)[-1],
                dest=dest,
                selection=_basenames,
                answers_files=_answers_files,
                agent=agent,
                written=_agent_written,
            )
        # spec 015 FR-012: reproduce-safety lint — every agent-written path must be
        # frozen so a managed re-render can't clobber it on reproduce.
        _lint_agent_managed_overlap(plan, descs, dest, _agent_written)
        # Whole-project initial commit AFTER post-tasks + schema markers, so the
        # tree is clean after init (not a per-module task — see
        # _finalize_initial_commit). Reads base's initial_commit/run_git_init.
        _finalize_initial_commit(
            {k: v for layer in answers_map.values() for k, v in layer.items()}, dest
        )
        return results

    # check=True: all-gaps preflight — run all layers, collect all errors.
    errors: list[str] = []
    check_descs: dict[str, discovery.Discovery] = {}
    for record, af_name in plan:
        _require_reproducible(record.source, record.ref)
        _require_trust_if_action_taking(record.source, record.ref)
        layer_answers = answers_map.get(record.full_id, {})
        # Discover once per layer; reuse for both secret checks and redaction.
        desc = discovery.discover(record.source, record.ref)
        check_descs[record.full_id] = desc
        # FR-003a: reject secrets in per-layer answers even in preflight mode.
        _check_no_secrets(layer_answers, desc)
        # FR-003c: fail loud on required secrets with no value.
        _check_required_secrets_supplied(layer_answers, desc)
        # spec 014 FR-001/002: no cross-layer bleed in preflight either.
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
    if errors:
        raise InvalidRunSpecError(
            "preflight found missing or invalid answers:\n" + "\n".join(f"  - {e}" for e in errors)
        )
    # spec 016 FR-006: the tool preflight runs under --check too, so a dry run
    # surfaces missing tools without writing.
    _check_required_tools(plan, check_descs, answers_map)
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


def _check_schema_gate(af_path: Path) -> None:
    """Refuse reproduce when answers file lacks or mismatches ``_bailiff_schema`` (spec 014 R10).

    A pre-014 tree cannot have the marker.  copier silently ignores unknown recorded
    answer keys, so a stale tree would silently mis-render.  This gate makes the
    break explicit with a loud error and re-init guidance (FR-014/SC-006).
    """
    try:
        raw = yaml.safe_load(af_path.read_text()) or {}
    except Exception:  # noqa: BLE001
        raw = {}
    schema = raw.get(_BAILIFF_SCHEMA_KEY)
    if schema is None:
        raise BailiffError(
            f"answers file {af_path!r} is missing the {_BAILIFF_SCHEMA_KEY!r} marker. "
            f"This tree was scaffolded before spec 014 (or by a version of bailiff that "
            f"did not write the schema marker). Reproduce is refused to prevent a silent "
            f"mis-render from stale recorded answers. "
            f"Re-init the project with the current module versions to generate a fresh "
            f"014-schema tree: delete the project directory and run `bailiff init` again. "
            f"(spec 014 FR-014/R10)"
        )
    if str(schema) != _BAILIFF_SCHEMA_VERSION:
        raise BailiffError(
            f"answers file {af_path!r} has {_BAILIFF_SCHEMA_KEY}={schema!r} "
            f"but this bailiff requires schema {_BAILIFF_SCHEMA_VERSION!r}. "
            f"Re-init the project to upgrade to the current schema version. "
            f"(spec 014 FR-014/R10)"
        )


def reproduce_many(dest: str) -> list[RunResult]:
    """Recompute the multi-layer order from committed state and reproduce each layer.

    Algorithm (spec 003 recompute-not-freeze contract):
    1. Enumerate committed ``.copier-answers*.yml`` files.
    2. For each file, check the ``_bailiff_schema`` gate (spec 014 FR-014/R10).
    3. Read the recorded ``_src_path`` + ``_commit`` (the exact source and pinned
       commit copier wrote at init time).
    4. Re-discover each template at its pinned commit to re-read its edges + phase.
    5. Rebuild the DAG + topo-sort (phase → DAG → basename tie-break) → the
       recomputed order.
    6. Drive ``reproduce(dest, answers_file=<that file>)`` per layer in that order.
    7. Run ``_post_tasks`` after the full loop (spec 014 FR-021/R11).

    Fails loudly per-layer if a source is unreachable (reproduce/CI never silently
    skips a layer).  N=1 behaves identically to single-template ``reproduce`` (uniform
    loop, spec 010 invariant).
    """
    from bailiff import ordering  # local import avoids circular at module load

    # Canonicalize so copier's _external_data path check agrees on a symlinked
    # prefix (macOS /tmp → /private/tmp), same as init_many (else a cross-module
    # consumer raises ForbiddenPathError on reproduce).
    dest = _canonical_dest(dest)
    answers_files = enumerate_answers_files(dest)
    if not answers_files:
        raise BailiffError(f"no .copier-answers*.yml at {dest!r}; nothing to reproduce")

    # Build minimal TemplateRecord-like objects from each answers file's metadata,
    # and simultaneously collect their edges by re-discovering at the pinned commit.
    records: list[TemplateRecord] = []
    edges_by_basename: dict[str, dict[str, Any]] = {}
    phases_by_basename: dict[str, str] = {}
    ext_data_by_basename: dict[str, dict[str, str]] = {}
    file_by_basename: dict[str, Path] = {}
    descs_by_basename: dict[str, discovery.Discovery] = {}

    for af_path in answers_files:
        # spec 014 FR-014/R10: refuse pre-014 or wrong-schema trees before any render.
        _check_schema_gate(af_path)

        try:
            raw = yaml.safe_load(af_path.read_text()) or {}
        except Exception as exc:  # noqa: BLE001
            raise BailiffError(f"could not read answers file {af_path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise BailiffError(f"answers file {af_path} did not parse to a mapping")

        src_path = raw.get("_src_path")
        commit = raw.get("_commit")
        if not src_path:
            raise BailiffError(
                f"answers file {af_path!r} has no _src_path; cannot reproduce this layer"
            )
        if not commit:
            raise BailiffError(
                f"answers file {af_path!r} has no _commit; cannot reproduce this layer"
            )

        # Re-discover at the pinned commit to re-read edges + phase (recompute, not freeze).
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
        phases_by_basename[basename] = disc.phase
        ext_data_by_basename[basename] = disc.external_data_aliases
        file_by_basename[basename] = af_path
        descs_by_basename[basename] = disc

    # Recompute order (same DAG build + topo-sort as init, now phase- and alias-aware).
    plan = ordering.layer_plan_from_edges(
        records, edges_by_basename, phases_by_basename, ext_data_by_basename
    )

    # Map full_id → disc for _run_post_tasks
    descs_by_full_id: dict[str, discovery.Discovery] = {}
    for record in records:
        basename = record.full_id.rsplit("/", 1)[-1]
        if basename in descs_by_basename:
            descs_by_full_id[record.full_id] = descs_by_basename[basename]

    # spec 015: capture each layer's frozen agent block BEFORE the reproduce loop —
    # copier's run_recopy re-renders the answers file from `_copier_answers` (which
    # does NOT carry the appended `_agent_frozen`), so it would be lost otherwise.
    frozen_by_basename: dict[str, dict[str, Any]] = {}
    for record, _af_name in plan:
        basename = record.full_id.rsplit("/", 1)[-1]
        parsed = yaml.safe_load(file_by_basename[basename].read_text()) or {}
        block = parsed.get(_AGENT_FROZEN_KEY)
        if isinstance(block, dict):
            frozen_by_basename[basename] = block

    results: list[RunResult] = []
    for record, _af_name in plan:
        basename = record.full_id.rsplit("/", 1)[-1]
        af_path = file_by_basename[basename]
        result = reproduce(dest, answers_file=af_path)
        results.append(result)
        # Re-write schema marker after reproduce (copier recopy may overwrite the file).
        _write_schema_marker(dest, _af_name)
        # Re-append the frozen block so the reproduced tree stays reproducible again.
        if basename in frozen_by_basename:
            _rewrite_frozen_block(dest, _af_name, frozen_by_basename[basename])
    # spec 015 FR-010/011: replay each layer's frozen agent output (agent-free)
    # BEFORE _post_tasks, so mechanical post-tasks (e.g. the pre-commit bundler)
    # consume the projected files. The phase-1 agent is NEVER invoked on reproduce.
    for block in frozen_by_basename.values():
        _replay_frozen_block(dest, block)
    # spec 014 FR-021/R11: run _post_tasks after the full reproduce loop.
    _run_post_tasks(plan, descs_by_full_id, dest)
    return results


# ---------------------------------------------------------------------------
# Update path (spec 006) — the ONLY place bailiff advances a template version
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
    # Canonicalize (idempotent) so copier's _external_data path check agrees on a
    # symlinked prefix (macOS /tmp → /private/tmp), same as init/reproduce.
    dest = _canonical_dest(dest)
    dst = Path(dest)
    if not answers_file.is_file():
        raise BailiffError(f"no answers file at {answers_file!r}; nothing to update")

    raw = _read_answers_metadata(answers_file)
    src_path = raw.get("_src_path")
    current_commit = raw.get("_commit")
    if not src_path:
        raise BailiffError(
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
    from bailiff import ordering  # local import avoids circular at module load

    # Canonicalize so copier's _external_data path check agrees on a symlinked
    # prefix (macOS /tmp → /private/tmp), same as init_many/reproduce_many.
    dest = _canonical_dest(dest)

    # Prerequisite: the tree must be clean before an upgrade. Two reasons, both point
    # to "commit or stash first": (1) a real upgrade commits each layer between layers
    # (git add -A), which would sweep the user's unrelated uncommitted work into a bailiff
    # commit; (2) copier's own run_update refuses a dirty tree even in pretend mode.
    # Checked up front, before any network clone, so bailiff surfaces one clear error
    # instead of copier's cryptic "repository is dirty" mid-run.
    if discovery.worktree_is_dirty(dest):
        raise DirtyWorktreeError(
            f"{dest!r} has uncommitted changes. Upgrade requires a clean working tree "
            f"(it commits each template layer between layers, and copier refuses a dirty "
            f"tree). Commit or stash your changes first, then re-run the upgrade."
        )

    answers_files = enumerate_answers_files(dest)
    if not answers_files:
        raise BailiffError(f"no .copier-answers*.yml at {dest!r}; nothing to update")

    records: list[TemplateRecord] = []
    edges_by_basename: dict[str, dict[str, Any]] = {}
    file_by_basename: dict[str, Path] = {}

    for af_path in answers_files:
        raw = _read_answers_metadata(af_path)
        if not isinstance(raw, dict):
            raise BailiffError(f"answers file {af_path} did not parse to a mapping")

        src_path = raw.get("_src_path")
        commit = raw.get("_commit")
        if not src_path:
            raise BailiffError(
                f"answers file {af_path!r} has no _src_path; cannot update this layer"
            )
        if not commit:
            raise BailiffError(f"answers file {af_path!r} has no _commit; cannot update this layer")

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
            discovery.git_commit_if_dirty(dest, f"bailiff: upgrade {basename}")
    return results
