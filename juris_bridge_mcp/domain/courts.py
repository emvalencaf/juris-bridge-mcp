"""The Courts DataJud publishes, by alias, and how a CNJ number's `J.TR` segments name them."""

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure

# UFs in the CNJ's `TR` order (alphabetical by state name) for electoral and state courts.
UFS = ("ac al ap am ba ce df es go ma mt ms mg pa pb pr pe pi rj rn rs ro rr sc se sp to").split()

SOURCE = "datajud"
NOT_PUBLISHED = "stf"


def _court_by_segment() -> dict[tuple[int, int], str]:
    """Map `(J, TR)` to an alias for the Courts whose number identifies them (CNJ Res. 65/2008)."""
    table = {(7, 0): "stm"}
    table |= {(4, n): f"trf{n}" for n in range(1, 7)}
    table |= {(5, n): f"trt{n}" for n in range(1, 25)}
    for n, uf in enumerate(UFS, start=1):
        table[(6, n)] = f"tre-{uf}"
        table[(8, n)] = "tjdft" if uf == "df" else f"tj{uf}"
    table |= {(9, 13): "tjmmg", (9, 21): "tjmrs", (9, 26): "tjmsp"}
    return table


COURT_BY_SEGMENT = _court_by_segment()

# Superior courts whose numbers hold origin cases, so they are only reachable by alias.
_SUPERIOR_BY_ALIAS_ONLY = ("tst", "tse", "stj")

DATAJUD_COURTS = _SUPERIOR_BY_ALIAS_ONLY + tuple(COURT_BY_SEGMENT.values())

# DataJud's wiki lists the electoral court of the Federal District as `tre-dft`, but
# its index is `api_publica_tre-df` (the other name answers 404).
_ALIASES = {"tre-dft": "tre-df"}


def stf_not_covered() -> ToolFailure:
    """The failure for STF Cases, which DataJud does not publish."""
    return ToolFailure(
        ErrorCode.NOT_COVERED,
        "STF cases are not published by DataJud, the only Source for Cases.",
        source=SOURCE,
        retryable=False,
        hint="Use list_coverage to see which Courts are covered.",
    )


def resolve_court(alias: str) -> str:
    """Return the canonical alias for `alias`, or raise the matching failure."""
    key = _ALIASES.get(alias.strip().lower(), alias.strip().lower())
    if key == NOT_PUBLISHED:
        raise stf_not_covered()
    if key not in DATAJUD_COURTS:
        raise ToolFailure(
            ErrorCode.INVALID_ARGUMENT,
            f"Unknown court alias: {alias!r}",
            source=None,
            retryable=False,
            hint="Valid aliases: " + ", ".join(DATAJUD_COURTS),
        )
    return key
