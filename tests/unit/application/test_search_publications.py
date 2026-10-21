from datetime import date

import pytest

from juris_bridge_mcp.application.use_cases.search_publications import (
    MAX_DJEN_PAGE,
    MAX_PAGES_PER_CALL,
    search_publications,
)
from juris_bridge_mcp.domain.cnj_number import CnjNumber
from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.publication import Publication, PublicationPage
from juris_bridge_mcp.domain.publication_kind import PublicationKind

DAY = date(2026, 10, 15)


def _publication(index: int, kind: PublicationKind = PublicationKind.SENTENCA) -> Publication:
    return Publication(
        court="tjsp",
        day=DAY,
        number=CnjNumber("12345677620258260100"),
        document_type="Intimação",
        excerpt="texto",
        text_length=5,
        item_hash=f"hash{index}",
        kind=kind,
    )


def _page(*kinds: PublicationKind, **fields) -> PublicationPage:
    publications = tuple(_publication(i, kind) for i, kind in enumerate(kinds))
    return PublicationPage(publications=publications, **{"total": len(kinds), **fields})


class _Repository:
    """Answers `pages` in order, the last one again if asked past the end."""

    def __init__(self, *pages):
        self.pages = pages or (PublicationPage(publications=(), total=0),)
        self.asked: list[tuple] = []

    async def search(self, court, query, date_from, date_to, *, page=1):
        self.asked.append((court, query, date_from, date_to, page))
        return self.pages[min(page, len(self.pages)) - 1]


async def _search(repository, **overrides):
    arguments = {"court": "tjsp", "date_from": DAY, "date_to": DAY, "query": "recurso especial"}
    return await search_publications(repository, **{**arguments, **overrides})


async def _code(repository, **overrides) -> ErrorCode:
    with pytest.raises(ToolFailure) as caught:
        await _search(repository, **overrides)
    assert repository.asked == []
    return caught.value.code


async def test_asks_the_resolved_court_with_the_trimmed_query_as_is():
    repository = _Repository()

    result = await _search(repository, court=" TJSP ", query="  recurso especial ", limit=5)

    assert repository.asked == [("tjsp", "recurso especial", DAY, DAY, 1)]
    assert result.court == "tjsp" and result.hint is None


async def test_limit_defaults_to_10():
    repository = _Repository(_page(*(PublicationKind.SENTENCA,) * 12))

    result = await _search(repository)

    assert len(result.publications) == 10 and result.next_cursor


@pytest.mark.parametrize("limit", [0, 26])
async def test_a_limit_outside_1_to_25_is_invalid(limit):
    assert await _code(_Repository(), limit=limit) is ErrorCode.INVALID_ARGUMENT


async def test_a_window_of_32_days_is_invalid_and_31_is_allowed():
    assert (
        await _code(_Repository(), date_from=date(2026, 9, 1), date_to=date(2026, 10, 2))
        is ErrorCode.INVALID_ARGUMENT
    )
    repository = _Repository()
    await _search(repository, date_from=date(2026, 9, 1), date_to=date(2026, 10, 1))
    assert len(repository.asked) == 1


async def test_a_window_that_ends_before_it_starts_is_invalid():
    assert (
        await _code(_Repository(), date_from=date(2026, 10, 16), date_to=DAY)
        is ErrorCode.INVALID_ARGUMENT
    )


@pytest.mark.parametrize("query", ["", "    ", " abc ", "abcd"])
async def test_a_trimmed_query_under_5_characters_never_reaches_the_source(query):
    assert await _code(_Repository(), query=query) is ErrorCode.INVALID_ARGUMENT


async def test_a_court_the_djen_does_not_reach_is_not_covered():
    assert await _code(_Repository(), court="stf") is ErrorCode.NOT_COVERED


async def test_despachos_and_notices_are_dropped_and_counted():
    kinds = (
        PublicationKind.NOT_A_DECISION,
        PublicationKind.ACORDAO,
        PublicationKind.NOT_A_DECISION,
    )
    repository = _Repository(_page(*kinds))

    result = await _search(repository)

    assert [p.kind for p in result.publications] == [PublicationKind.ACORDAO]
    assert result.not_decisions_dropped == 2


async def test_by_default_every_decision_stays_ambiguous_included():
    kinds = tuple(k for k in PublicationKind if k is not PublicationKind.NOT_A_DECISION)

    result = await _search(_Repository(_page(*kinds)))

    assert [p.kind for p in result.publications] == list(kinds)


@pytest.mark.parametrize(
    "kind",
    ["acordao", "sentenca", "decisao_monocratica", "decisao_interlocutoria", "ambiguous"],
)
async def test_the_kind_filter_keeps_only_that_kind(kind):
    kinds = tuple(k for k in PublicationKind if k is not PublicationKind.NOT_A_DECISION)

    result = await _search(
        _Repository(_page(*kinds, PublicationKind.ACORDAO)), kind=f" {kind.upper()} "
    )

    assert {p.kind.value for p in result.publications} == {kind}


@pytest.mark.parametrize("kind", ["despacho", "not_a_decision", "", "decisao"])
async def test_an_unknown_kind_is_invalid_and_never_reaches_the_source(kind):
    assert await _code(_Repository(), kind=kind) is ErrorCode.INVALID_ARGUMENT


async def test_the_limit_applies_after_the_filter():
    kinds = (PublicationKind.NOT_A_DECISION,) * 8 + (PublicationKind.SENTENCA,) * 3

    result = await _search(_Repository(_page(*kinds)), limit=2)

    assert len(result.publications) == 2 and result.next_cursor


SENTENCA = PublicationKind.SENTENCA
DESPACHO = PublicationKind.NOT_A_DECISION


async def test_the_last_page_has_no_next_cursor():
    result = await _search(_Repository(_page(SENTENCA, SENTENCA)))

    assert result.next_cursor is None and result.hint is None


async def test_a_cursor_resumes_after_the_last_publication_returned():
    repository = _Repository(_page(*(SENTENCA,) * 5))
    first = await _search(repository, limit=2)
    second = await _search(repository, limit=2, cursor=first.next_cursor)

    assert [p.item_hash for p in first.publications] == ["hash0", "hash1"]
    assert [p.item_hash for p in second.publications] == ["hash2", "hash3"]
    assert repository.asked[-1][4] == 1


async def test_reading_on_to_the_next_source_page_when_the_first_runs_out():
    repository = _Repository(_page(SENTENCA, more=True), _page(SENTENCA, SENTENCA))

    result = await _search(repository, limit=3)

    assert len(result.publications) == 3 and result.next_cursor is None
    assert [asked[4] for asked in repository.asked] == [1, 2]


async def test_a_page_that_ends_exactly_on_the_limit_resumes_on_the_next_source_page():
    repository = _Repository(_page(SENTENCA, SENTENCA, more=True), _page(SENTENCA))

    first = await _search(repository, limit=2)
    second = await _search(repository, limit=2, cursor=first.next_cursor)

    assert len(first.publications) == 2 and first.next_cursor
    assert len(second.publications) == 1 and second.next_cursor is None


async def test_a_call_reads_a_bounded_number_of_source_pages():
    repository = _Repository(_page(DESPACHO, more=True))

    result = await _search(repository)

    assert len(repository.asked) == MAX_PAGES_PER_CALL
    assert result.publications == () and result.next_cursor


async def test_the_source_depth_ceiling_ends_the_paging_with_a_hint():
    repository = _Repository(_page(SENTENCA, more=True))
    first = await _search(repository, limit=1)
    key = Cursor.decode(first.next_cursor, scopes=("tjsp",)).filters_key
    cursor = Cursor("tjsp", (MAX_DJEN_PAGE, 1), key).encode()

    result = await _search(repository, limit=1, cursor=cursor)

    assert result.next_cursor is None and "narrow" in result.hint


async def test_the_kind_filter_pages_over_the_kept_items_only():
    repository = _Repository(
        _page(SENTENCA, PublicationKind.ACORDAO, SENTENCA, PublicationKind.ACORDAO)
    )

    first = await _search(repository, kind="acordao", limit=1)
    second = await _search(repository, kind="acordao", limit=1, cursor=first.next_cursor)

    assert [p.item_hash for p in first.publications] == ["hash1"]
    assert [p.item_hash for p in second.publications] == ["hash3"]


async def test_a_cursor_from_another_search_is_invalid():
    repository = _Repository(_page(*(SENTENCA,) * 5))
    first = await _search(repository, limit=2)
    asked = len(repository.asked)

    for change in (
        {"query": "outra consulta"},
        {"kind": "sentenca"},
        {"date_to": date(2026, 10, 16)},
    ):
        with pytest.raises(ToolFailure) as caught:
            await _search(repository, limit=2, cursor=first.next_cursor, **change)
        assert caught.value.code is ErrorCode.INVALID_ARGUMENT
    assert len(repository.asked) == asked


@pytest.mark.parametrize("position", [(0, 0), (MAX_DJEN_PAGE + 1, 0), (1, -1), (1,), ("a", 0)])
async def test_a_cursor_with_a_malformed_position_is_invalid(position):
    repository = _Repository()
    first = await _search(_Repository(_page(*(SENTENCA,) * 3)), limit=1)
    key = Cursor.decode(first.next_cursor, scopes=("tjsp",)).filters_key

    with pytest.raises(ToolFailure) as caught:
        await _search(repository, cursor=Cursor("tjsp", position, key).encode())

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT and repository.asked == []
