"""Coverage declared in code, from the documented DataJud aliases."""

from juris_bridge_mcp.domain.courts import DATAJUD_COURTS, NOT_PUBLISHED
from juris_bridge_mcp.domain.coverage import CourtCoverage, SourceCoverage


class StaticCoverageCatalog:
    """The MVP Coverage: DataJud for Cases and the Senado API for Legislation."""

    def sources(self) -> tuple[SourceCoverage, ...]:
        courts = tuple(CourtCoverage(alias, supported=True) for alias in DATAJUD_COURTS)
        # STF is not published by DataJud; listing it makes the gap explicit.
        courts += (CourtCoverage(NOT_PUBLISHED, supported=False),)
        return (
            SourceCoverage(
                source="datajud",
                kind="cases",
                description="Case metadata and movements; no party names, no case text.",
                courts=courts,
            ),
            SourceCoverage(
                source="senado",
                kind="legislation",
                description="Federal legislation metadata by URN Lex; text from Planalto.",
            ),
        )
