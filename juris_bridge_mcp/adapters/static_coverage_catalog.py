"""Coverage declared in code, from the documented DataJud aliases."""

from juris_bridge_mcp.domain.courts import DATAJUD_COURTS, NOT_PUBLISHED
from juris_bridge_mcp.domain.coverage import CourtCoverage, SourceCoverage
from juris_bridge_mcp.domain.publication_courts import (
    DJEN_COURTS,
    DJEN_START_DATES,
    NON_DJEN_COURTS,
)


class StaticCoverageCatalog:
    """The Coverage: DataJud (Cases), the DJEN (Publications) and the Senado API (Legislation)."""

    def sources(self) -> tuple[SourceCoverage, ...]:
        courts = tuple(CourtCoverage(alias, supported=True) for alias in DATAJUD_COURTS)
        # STF is not published by DataJud; listing it makes the gap explicit.
        courts += (
            CourtCoverage(NOT_PUBLISHED, supported=False, reason="Not published by DataJud."),
        )
        djen_courts = tuple(
            CourtCoverage(alias, supported=True, available_from=DJEN_START_DATES.get(alias))
            for alias in DJEN_COURTS
        ) + tuple(
            CourtCoverage(alias, supported=False, reason=reason)
            for alias, reason in NON_DJEN_COURTS.items()
        )
        return (
            SourceCoverage(
                source="datajud",
                kind="cases",
                description="Case metadata and movements; no party names, no case text.",
                courts=courts,
            ),
            SourceCoverage(
                source="djen",
                kind="publications",
                description=(
                    "Publications of the Diário de Justiça Eletrônico Nacional: the DJEN is no "
                    "archive (about 2021 onward, later for many Courts), so results can be "
                    "non-exhaustive. `available_from` is the first day with data seen in "
                    "sampled weeks; it is absent when no start is known."
                ),
                courts=djen_courts,
            ),
            SourceCoverage(
                source="senado",
                kind="legislation",
                description="Federal legislation metadata by URN Lex; text from Planalto.",
            ),
        )
