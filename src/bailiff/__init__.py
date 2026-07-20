"""bailiff — an agentic conductor for copier.

The bailiff fills in the paperwork (per-module answer files); copier makes the
copies. See docs/decisions/ for the architecture.
"""

try:
    from importlib.metadata import version as _version

    __version__: str = _version("bailiff")
except Exception:
    __version__ = "0.4.2"
