"""Shared exception types. Kept in their own module to avoid circular imports
between client / catalog / validation / server."""

from __future__ import annotations


class DataSaudiError(RuntimeError):
    """The Tesseract API returned an error payload or a non-2xx status."""


class DataSaudiServerError(DataSaudiError):
    """A deterministic HTTP 500 from Tesseract (R20 combinatorial collapse).

    Distinct from transient 5xx: this recurs identically on retry, so callers
    must NOT retry it — they steer the model to drop a drilldown instead.
    """


class ValidationError(ValueError):
    """A fail-loud client-side validation failure (R13). Its message names what
    was wrong AND the valid options, so the model can self-correct in one turn."""
