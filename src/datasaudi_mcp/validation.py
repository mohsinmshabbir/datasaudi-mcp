"""Pure validation functions — zero I/O, so every fail-loud rule is unit-tested
offline. Implements R1 (measures), R2/R6 (drilldowns), R3 (normalize), R13 (fail-loud)."""

from __future__ import annotations

from .errors import ValidationError


def normalize(names: list[str]) -> list[str]:
    """R3: strip whitespace from each name; drop names empty after stripping."""
    return [s.strip() for s in names if s.strip()]


def validate_drilldowns(requested: list[str], valid_levels: list[str]) -> list[str]:
    """R2/R6: normalize, then require >=1 drilldown and every one a real level name.

    Raises ValidationError (R13) naming the first bad level and the valid options.
    Level names are case-sensitive (Probe H) — we do not fold case."""
    names = normalize(requested)
    if not names:
        raise ValidationError(
            "at least one drilldown (level name) is required; valid levels: "
            + ", ".join(valid_levels)
        )
    valid = set(valid_levels)
    for name in names:
        if name not in valid:
            raise ValidationError(
                f"no level {name!r} in this cube; valid levels: " + ", ".join(valid_levels)
            )
    return names


def validate_measures(requested: list[str], valid_measures: list[str]) -> list[str]:
    """R1 (THE trust-critical rule): the Tesseract API SILENTLY DROPS unknown measures
    (Probe D: measures='Price Index,Fake' -> HTTP 200 with only Price Index). The server
    will never catch this, so we must. Empty is allowed (a no-measures members query).

    Raises ValidationError (R13) naming the bad measure and the valid options."""
    names = normalize(requested)
    valid = set(valid_measures)
    for name in names:
        if name not in valid:
            raise ValidationError(
                f"no measure {name!r} in this cube; valid measures: " + ", ".join(valid_measures)
            )
    return names
