"""Where the Planalto keeps the page of a norm: no index by URN, so paths follow convention."""

from collections.abc import Callable

from juris_bridge_mcp.domain.legislation import Urn

# Planalto groups acts by presidential term from 2004 on; the first year of each range.
_ERA_STARTS = (2023, 2019, 2015, 2011, 2007, 2004)

# A rule lists the paths (under `ccivil_03`) a norm may live at, most likely first.
_PathRule = Callable[[int, int], list[str]]


def _by_term(folder: str, prefix: str, *, before: tuple[str, ...] = ()) -> _PathRule:
    """Build the rule for acts filed under their term, e.g. `_ato2019-2022/2021/lei/l14133.htm`.

    `before` lists the layouts of years ahead of 2004, with `{year}` and `{number}` slots.
    """

    def paths(number: int, year: int) -> list[str]:
        if year < _ERA_STARTS[-1]:
            return [layout.format(year=year, number=number) for layout in before]
        start = next(s for s in _ERA_STARTS if year >= s)
        end = 2006 if start == 2004 else start + 3
        return [f"_ato{start}-{end}/{year}/{folder}/{prefix}{number}.htm"]

    return paths


def _fixed(*layouts: str) -> _PathRule:
    """Build the rule for acts filed in one folder whatever the year."""
    return lambda number, year: [layout.format(number=number, year=year) for layout in layouts]


# The Planalto keeps the text as first published next to a consolidated page (with every later
# amendment applied) whose name suffix varies; the consolidated one is the law in force.
_CONSOLIDATED_SUFFIXES = ("compilado", "compilada", "cons")


def _consolidated_first(rule: _PathRule) -> _PathRule:
    """Wrap `rule` so each page is preceded by the names its consolidated version may have."""

    def paths(number: int, year: int) -> list[str]:
        return [
            variant
            for page in rule(number, year)
            for variant in [f"{page.removesuffix('.htm')}{s}.htm" for s in _CONSOLIDATED_SUFFIXES]
            + [page]
        ]

    return paths


# The folder names are case-insensitive and the server redirects a wrong file-name case.
_RULES: dict[str, _PathRule] = {
    "lei": _consolidated_first(
        _by_term("lei", "l", before=("leis/{year}/l{number}.htm", "leis/l{number}.htm"))
    ),
    "decreto": _consolidated_first(_by_term("decreto", "d", before=("decreto/d{number}.htm",))),
    "medida-provisoria": _by_term("mpv", "mpv"),
    "lei-complementar": _fixed("leis/lcp/lcp{number}.htm"),
    "decreto-lei": _consolidated_first(_fixed("decreto-lei/del{number:04d}.htm")),
    "emenda-constitucional": _fixed(
        "constituicao/emendas/emc/emc{number}.htm", "constituicao/emendas/emc/emc{number:02d}.htm"
    ),
}


def candidate_paths(urn: Urn) -> list[str]:
    """Return the page paths a norm may live at, most likely first; none for an unknown type."""
    rule = _RULES.get(urn.norm_type)
    if rule is None:
        return []
    return list(dict.fromkeys(rule(urn.number, urn.signed_on.year)))
