"""clerk's small, legible error hierarchy.

clerk does not re-implement copier's validation; it surfaces copier's own results
(``copier.errors.*`` AND the bare ``builtins.ValueError`` copier raises for a
missing required question) as clear, actionable clerk errors with a non-zero exit
(spec FR-010, Constitution VII). These types exist so the CLI can present a
readable message instead of a bare stack trace — not to wrap every copier error.
"""

from __future__ import annotations


class ClerkError(Exception):
    """Base class for every error clerk surfaces to a person or the agent."""


class DiscoveryError(ClerkError):
    """A template could not be inspected (bad source, no usable version, bad config)."""


class UntrustedSourceError(ClerkError):
    """A run needs trust that is absent.

    Carries the exact source prefix the user must trust so the message can name it
    (spec FR-020). The deterministic core NEVER records trust itself.
    """

    def __init__(self, prefix: str, *, source: str | None = None) -> None:
        self.prefix = prefix
        self.source = source
        super().__init__(
            f"source is not trusted: {source or prefix!r}. It runs template tasks "
            f"(code execution), so it must be trusted first. To allow it, run:\n"
            f"    scripts/clerk.py trust add {prefix}\n"
            f"(this records the prefix in copier's settings.yml; reproduce/CI never "
            f"prompts and will fail here until trust is present)."
        )


class NotReproducibleError(ClerkError):
    """A template lacks the answers-file mechanism, so its output can't be reproduced.

    clerk refuses to generate from it rather than produce a project that can never
    be faithfully reproduced (spec FR-016 / US5).
    """


class InvalidRunSpecError(ClerkError):
    """The inputs document is malformed or incomplete (surfaced before any render)."""


class CatalogError(ClerkError):
    """A catalog operation failed.

    Raised for: missing or malformed catalog file; unknown or ambiguous full-id
    at ``validate``; any CRUD precondition that cannot be met. The CLI maps this
    to exit code 1 (same as other ``ClerkError`` subclasses).
    """


class OrderingError(ClerkError):
    """A dependency DAG for the selected templates is invalid.

    Raised for: a dependency cycle (names the cycle members), a dangling edge
    (names the missing dependency), or a basename collision among selected
    templates (names the colliding basename). Always raised before any write.
    """


class DefaultsError(ClerkError):
    """A defaults config operation failed.

    Raised for: malformed YAML in the defaults file; an explicit
    ``CLERK_DEFAULTS_PATH`` pointing at a nonexistent file. The message
    always includes the offending path and the reason.
    """


class SecretInAnswersError(ClerkError):
    """A run-spec supplies a value for a discovery-flagged secret key.

    Carries the offending KEY name(s) only — never the value. The agent must
    not collect secret values; they are supplied out-of-band via copier's masked
    prompt or an env mechanism (spec FR-003a / Constitution II).
    """

    def __init__(self, keys: list[str]) -> None:
        self.keys = keys
        key_list = ", ".join(repr(k) for k in keys)
        super().__init__(
            f"run-spec supplies values for secret question(s): {key_list}. "
            f"Secret values must never enter the run-spec or the agent context. "
            f"Supply them out-of-band via copier's masked interactive prompt or "
            f"an environment mechanism at the deterministic step."
        )
