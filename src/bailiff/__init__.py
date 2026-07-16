"""bailiff — an agentic conductor for copier.

The bailiff fills in the paperwork (per-module answer files); copier makes the
copies. See docs/decisions/ for the architecture.
"""

from importlib.metadata import version as _version

# Single-sourced from the installed distribution metadata (spec 013 FR-003).
# No bare-checkout fallback: scripts/bailiff.py is deleted, so __version__ is
# only read from an installed context (editable or wheel); a broken install
# surfaces as a clean PackageNotFoundError rather than a silently stale string.
__version__: str = _version("bailiff")
