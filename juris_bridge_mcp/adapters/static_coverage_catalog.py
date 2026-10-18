"""Coverage declared in code, from the documented DataJud aliases."""

from juris_bridge_mcp.domain.coverage import CourtCoverage, SourceCoverage

_UFS = ("ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to").split()


def _datajud_aliases() -> tuple[str, ...]:
    superior = ("tst", "tse", "stj", "stm")
    federal = tuple(f"trf{n}" for n in range(1, 7))
    # The Federal District court is `tjdft`, not `tjdf`.
    state = tuple("tjdft" if uf == "df" else f"tj{uf}" for uf in _UFS)
    labor = tuple(f"trt{n}" for n in range(1, 25))
    # DataJud lists the electoral court of the Federal District as `tre-dft`.
    electoral = tuple("tre-dft" if uf == "df" else f"tre-{uf}" for uf in _UFS)
    military = ("tjmmg", "tjmrs", "tjmsp")
    return superior + federal + state + labor + electoral + military


class StaticCoverageCatalog:
    """The MVP Coverage: DataJud for Cases and the Senado API for Legislation."""

    def sources(self) -> tuple[SourceCoverage, ...]:
        courts = tuple(CourtCoverage(alias, supported=True) for alias in _datajud_aliases())
        # STF is not published by DataJud; listing it makes the gap explicit.
        courts += (CourtCoverage("stf", supported=False),)
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
