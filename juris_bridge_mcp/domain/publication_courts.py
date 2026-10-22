"""The Courts that publish in the DJEN, and since when."""

from datetime import date

from juris_bridge_mcp.domain.courts import DATAJUD_COURTS
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure, not_covered
from juris_bridge_mcp.domain.publication import SOURCE

ELECTORAL_PREFIX = "tre-"

# Courts decided as not covered (ADR 0006), each with the reason a client is told.
NON_DJEN_COURTS = {
    "stf": "Not a DJEN sender: its queries fail, and it keeps its own portal.",
    **{
        c: "Sends to the DJEN only now and then (sampled weeks held no items); not covered."
        for c in DATAJUD_COURTS
        if c.startswith(ELECTORAL_PREFIX)
    },
}

DJEN_COURTS = tuple(c for c in DATAJUD_COURTS if c not in NON_DJEN_COURTS)

# First day with data seen in sampled weeks (docs/research on the DJEN coverage): the DJEN
# is no historical archive. A Court missing here has no known start.
DJEN_START_DATES = {
    "tst": date(2024, 9, 1),
    "trt2": date(2024, 9, 1),
    "stj": date(2024, 12, 1),
    "tjrj": date(2024, 12, 1),
    "tjsp": date(2025, 3, 1),
    "stm": date(2025, 4, 1),
    "tjmg": date(2023, 3, 1),
    "tjrs": date(2023, 3, 1),
    "trf6": date(2023, 3, 1),
    "trf1": date(2021, 3, 1),
    "trf3": date(2021, 3, 1),
    "tjpr": date(2021, 3, 1),
}


def _not_covered(message: str) -> ToolFailure:
    return not_covered(SOURCE, message, "Use list_coverage to see which Courts are covered.")


def resolve_djen_court(alias: str, date_to: date) -> str:
    """Return the canonical alias of a Court publishing in the DJEN on or before `date_to`."""
    key = alias.strip().lower()
    if key in NON_DJEN_COURTS:
        raise _not_covered(f"{key.upper()} is not covered by the DJEN: {NON_DJEN_COURTS[key]}")
    if key not in DJEN_COURTS:
        raise ToolFailure(
            ErrorCode.INVALID_ARGUMENT,
            f"Unknown court alias: {alias!r}",
            source=None,
            retryable=False,
            hint="Valid aliases: " + ", ".join(DJEN_COURTS),
        )
    start = DJEN_START_DATES.get(key)
    if start is not None and date_to < start:
        raise _not_covered(
            f"{key.upper()} has no Publications in the DJEN before {start.isoformat()}."
        )
    return key
