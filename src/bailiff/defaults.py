"""User-owned defaults store — flat YAML mapping of question key → value.

Provides soft per-template defaults by selecting the keys relevant to the
current template's questions and passing them as ``user_defaults=`` to
``run_copy``. Mirrors ``catalog.py``'s path-resolution pattern (platformdirs
+ env override). Pure load/filter helpers; no copier import in this module.

Default path: ``user_config_path("bailiff", appauthor=False)/defaults.yml``,
overridable via the ``BAILIFF_DEFAULTS_PATH`` environment variable.

YAML shape::

    # bailiff user defaults — ~/.config/bailiff/defaults.yml
    author_name: Ada Lovelace
    author_email: ada@example.com
    github_org: acme
    license: MIT
    python_version: "3.12"

Keys absent from the current template's questions are silently ignored
(portability invariant — one file across many templates).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from platformdirs import user_config_path

from bailiff.errors import DefaultsError

if TYPE_CHECKING:
    from bailiff.discovery import Question

_ENV_VAR = "BAILIFF_DEFAULTS_PATH"
_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def defaults_path() -> Path:
    """Resolve the defaults YAML path (env override → platformdirs default).

    When ``BAILIFF_DEFAULTS_PATH`` is set and the path does not exist, raises
    ``DefaultsError`` — an explicit override that silently no-ops is
    surprising (Q-004c resolved). The default platformdirs path being absent
    is a silent no-op handled by ``load()``.
    """
    env = os.getenv(_ENV_VAR)
    if env:
        p = Path(env)
        if not p.is_file():
            raise DefaultsError(
                f"defaults file not found: {p}\n  ({_ENV_VAR} is set but the path does not exist)"
            )
        return p
    return user_config_path("bailiff", appauthor=False) / "defaults.yml"


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def load(path: Path) -> dict[str, Any]:
    """Load the defaults YAML file at ``path``.

    - Missing file → returns ``{}`` (no error; the platformdirs default
      path being absent is a normal first-run state).
    - Malformed YAML → raises ``DefaultsError`` with path + reason.
    - Non-mapping top-level → raises ``DefaultsError``.
    """
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise DefaultsError(f"defaults file is not valid YAML: {path}\n  {exc}") from exc
    if data is None:
        # Empty file is treated as an empty mapping (valid; user created the file but
        # left it blank).
        return {}
    if not isinstance(data, dict):
        raise DefaultsError(
            f"defaults file did not parse to a mapping: {path}\n"
            f"  top-level value is {type(data).__name__!r}, expected a YAML mapping"
        )
    return dict(data)


# ---------------------------------------------------------------------------
# Key selection
# ---------------------------------------------------------------------------


def select_keys(defaults: dict[str, Any], questions: list[Question]) -> dict[str, Any]:
    """Filter ``defaults`` to keys valid for this template invocation.

    Excludes:
    - Keys not present in ``questions`` (portability invariant).
    - Questions with ``secret: true`` (FR-004, SC-003 — spec 005 handles those).
    - Questions whose ``when`` is statically ``False`` (SHOULD, FR-004 — hidden
      dependency-edge sentinels; copier silently ignores them in user_defaults
      but filtering avoids confusion).
    """
    question_map = {q.key: q for q in questions}
    selected: dict[str, Any] = {}
    for key, value in defaults.items():
        q = question_map.get(key)
        if q is None:
            continue
        if q.secret:
            continue
        # Statically-false `when` marks dependency-edge sentinels (e.g. depends_on).
        if q.when is False:
            continue
        selected[key] = value
    return selected


# ---------------------------------------------------------------------------
# settings.yml defaults fold (best-effort)
# ---------------------------------------------------------------------------


def fold_settings_defaults(bailiff_defaults: dict[str, Any]) -> dict[str, Any]:
    """Merge copier's ``settings.yml defaults:`` as a lower-priority fallback.

    Result: ``{**copier_settings_defaults, **bailiff_defaults}`` so the bailiff
    defaults file always wins on collision. Best-effort: any exception from
    ``load_settings()`` is swallowed and only the bailiff defaults are returned
    (Q-004b resolved — graceful degradation, FR-005).
    """
    try:
        from copier import load_settings  # local import: copier not required at module load

        settings = load_settings()
        settings_defaults = dict(settings.defaults) if settings.defaults else {}
    except Exception as exc:  # noqa: BLE001 — best-effort; degrades gracefully
        _logger.debug("could not load copier settings.yml defaults (ignored): %s", exc)
        return bailiff_defaults
    return {**settings_defaults, **bailiff_defaults}
