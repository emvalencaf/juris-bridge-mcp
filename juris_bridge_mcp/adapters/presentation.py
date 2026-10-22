"""Formatting shared by the presenters."""

from datetime import UTC, datetime


def iso_utc(moment: datetime | None) -> str | None:
    """Return the moment as ISO 8601 in UTC with a `Z` suffix, or `None`."""
    if moment is None:
        return None
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")
