"""The Courts DataJud publishes, by alias."""

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure

# UFs in the CNJ's `TR` order (alphabetical by state name) for electoral and state courts.
UFS = ("ac al ap am ba ce df es go ma mt ms mg pa pb pr pe pi rj rn rs ro rr sc se sp to").split()

SOURCE = "datajud"
NOT_PUBLISHED = "stf"


def _datajud_courts() -> tuple[str, ...]:
    superior = ("tst", "tse", "stj", "stm")
    federal = tuple(f"trf{n}" for n in range(1, 7))
    state = tuple("tjdft" if uf == "df" else f"tj{uf}" for uf in UFS)
    labor = tuple(f"trt{n}" for n in range(1, 25))
    electoral = tuple(f"tre-{uf}" for uf in UFS)
    military = ("tjmmg", "tjmrs", "tjmsp")
    return superior + federal + state + labor + electoral + military


DATAJUD_COURTS = _datajud_courts()

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
