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

from copier import run_copy, run_recopy
from copier._types import VcsRef
from copier.errors import CopierError, UnsafeTemplateError

from clerk import discovery, trust
from clerk.errors import (
    ClerkError,
    InvalidRunSpecError,
    NotReproducibleError,
    UntrustedSourceError,
)


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
        raise UntrustedSourceError(_suggest_prefix(source), source=source)


def _suggest_prefix(source: str) -> str:
    """Suggest an org-level trailing-slash prefix to trust for this source."""
    # For https URLs, propose the owner path (…/<owner>/) so one entry covers a whole
    # org's clerk-mod-* repos; otherwise fall back to the exact source.
    if "://" in source:
        head, _, tail = source.rpartition("/")
        if head and tail:
            return head + "/"
    return source


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
        raise UntrustedSourceError(_suggest_prefix(spec.source), source=spec.source) from exc
    except ValueError as exc:
        # copier raises a bare ValueError for a missing required answer (verified).
        raise InvalidRunSpecError(f"invalid or incomplete answers: {exc}") from exc
    except CopierError as exc:
        raise _translate(exc) from exc
    return RunResult(dest=spec.dest, src=spec.source, ref=spec.ref, pretend=check)


def reproduce(dest: str) -> RunResult:
    """Faithfully reproduce an existing project at its recorded commit (FR-015).

    Agent-free: replays ``.copier-answers.yml`` via ``VcsRef.CURRENT`` (never the
    latest tag) with overwrite-in-place, non-interactive.
    """
    dst = Path(dest)
    if not (dst / ".copier-answers.yml").is_file():
        raise ClerkError(f"no .copier-answers.yml at {dest!r}; nothing to reproduce")
    try:
        run_recopy(
            dest,
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
