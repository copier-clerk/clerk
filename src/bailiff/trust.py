"""Trust management — read copier's ``settings.yml`` ``trust:`` list; record consent.

Trust governs code execution: a template's ``_tasks`` / migrations / jinja
extensions only run from a source the user has trusted (copier gates this on
``settings.yml`` ``trust:``, never a blanket ``unsafe=True``). bailiff's rules
(constitution V):

* The deterministic core NEVER records trust on its own. It only *reads* trust and,
  when a source is untrusted, raises :class:`UntrustedSourceError` naming the exact
  prefix to add.
* ``trust add`` is the ONLY writer, invoked explicitly by the agent after human
  consent.
* Trust is stored in the fully-expanded ``https://`` form, because copier matches
  trust against the raw pre-expansion URL — a ``gh:`` shortcut and its expansion do
  not match (so bailiff always uses expanded URLs for both fetch and storage).

Reading uses copier's public ``load_settings``; writing round-trips the YAML file
ourselves (copier exposes no writer), preserving any ``defaults:`` block.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from platformdirs import user_config_path

_ENV_VAR = "COPIER_SETTINGS_PATH"


def settings_path() -> Path:
    """Resolve copier's settings.yml path (env override → platformdirs default).

    Mirrors copier's own resolution so bailiff reads and writes the SAME file copier
    consults at run time.
    """
    env = os.getenv(_ENV_VAR)
    if env:
        return Path(env)
    return user_config_path("copier", appauthor=False) / "settings.yml"


def list_trust() -> list[str]:
    """Return the currently trusted prefixes/URLs, in file order.

    Read from the raw YAML rather than copier's loader: copier models ``trust`` as
    an unordered ``set``, but bailiff shows/returns it in the order the user recorded
    it. Enforcement at run time is still copier's own; this is for display + the
    advisory :func:`is_trusted` check.
    """
    return list(_read_raw(settings_path()).get("trust", []) or [])


def is_trusted(source: str) -> bool:
    """True if ``source`` is covered by the user's trust settings.

    Implements copier's documented match rule directly (trailing-slash entry ⇒
    prefix match, otherwise exact) so bailiff stays on public surface and off copier's
    deprecated ``SettingsModel.is_trusted``. This is advisory (to decide whether to
    prompt for consent); copier re-checks authoritatively when it runs.
    """
    for entry in list_trust():
        if entry.endswith("/"):
            if source.startswith(entry):
                return True
        elif source == entry:
            return True
    return False


def add_trust(prefix: str) -> bool:
    """Record ``prefix`` as trusted. Returns True if added, False if already present.

    Idempotent: an existing prefix is a no-op and existing entries (and any
    ``defaults:`` block) are preserved. This is the ONLY function that writes trust,
    and it is invoked only on explicit human consent — never by init/reproduce.
    """
    path = settings_path()
    data = _read_raw(path)
    trust = list(data.get("trust", []) or [])
    if prefix in trust:
        return False
    trust.append(prefix)
    data["trust"] = trust
    _write_raw(path, data)
    return True


def _read_raw(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    loaded = yaml.safe_load(path.read_text()) or {}
    if not isinstance(loaded, dict):
        # A malformed settings file: don't silently clobber it.
        raise ValueError(f"copier settings file is not a mapping: {path}")
    return loaded


def suggest_prefix(source: str) -> str:
    """Suggest an org-level trailing-slash prefix to trust for ``source``.

    Proposes the owner path (``…/<owner>/``) so one entry covers a whole org's
    ``bailiff-mod-*`` repos. A bare ``owner/repo`` shorthand is resolved to its
    expanded ``https://`` URL FIRST (the form copier matches trust against — see the
    module docstring), so ``trust add --from-source owner/repo`` records the same
    org prefix as the full URL rather than a non-matching bare string.
    """
    from bailiff.discovery import resolve_locator  # local import: avoid import cycle

    resolved = resolve_locator(source)
    if "://" in resolved:
        head, _, tail = resolved.rpartition("/")
        if head and tail:
            return head + "/"
    return resolved


def _write_raw(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=True, default_flow_style=False))
