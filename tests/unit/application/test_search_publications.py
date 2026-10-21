from datetime import date, timedelta

import pytest

from juris_bridge_mcp.application.use_cases.search_publications import (
    MAX_DJEN_PAGE,
    MAX_REQUESTS_PER_CALL,
    search_publications,
)
from juris_bridge_mcp.domain.cnj_number import CnjNumber
from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.publication import COUNT_CAP, Publication, PublicationPage
from juris_bridge_mcp.domain.publication_kind import PublicationKind

DAY = date(2026, 10, 15)


def _publication(
    index: int,
    kind: PublicationKind = PublicationKind.SENTENCA,
    organ_id: int | None = None,
    text: str = "recurso especial",
) -> Publication:
    return Publication(
        court="tjsp",
        day=DAY,
        number=CnjNumber("12345677620258260100"),
        document_type="Intimação",
        excerpt="texto",
        text_length=len(text),
        text=text,
        item_hash=f"hash{index}",
        kind=kind,
        organ_id=organ_id,
    )


def _page(*kinds: PublicationKind, **fields) -> PublicationPage:
    publications = tuple(_publication(i, kind) for i, kind in enumerate(kinds))
    return PublicationPage(publications=publications, **{"total": len(kinds), **fields})


class _Repository:
    """Answers `pages` in order, the last one again if asked past the end."""

    def __init__(self, *pages):
        self.pages = pages or (PublicationPage(publications=(), total=0),)
        self.asked: list[tuple] = []
        self.organs: list[int | None] = []
        self.numbers: list[CnjNumber | None] = []

    async def search(self, request):
        self.asked.append(
            (request.court, request.query, request.date_from, request.date_to, request.page)
        )
        self.organs.append(request.organ_id)
        self.numbers.append(request.cnj_number)
        return self.pages[min(request.page, len(self.pages)) - 1]


class _Days:
    """Answers per (day, organ, page) from `script`; anything else is an empty page."""

    def __init__(self, script=None):
        self.script = script or {}
        self.asked: list[tuple] = []

    async def search(self, request):
        assert request.date_from == request.date_to
        key = (request.date_from, request.organ_id, request.page)
        self.asked.append(key)
        return self.script.get(key, PublicationPage(publications=(), total=0))


async def _search(repository, **overrides):
    arguments = {"court": "tjsp", "date_from": DAY, "date_to": DAY, "query": "recurso especial"}
    return await search_publications(repository, **{**arguments, **overrides})


async def _code(repository, **overrides) -> ErrorCode:
    with pytest.raises(ToolFailure) as caught:
        await _search(repository, **overrides)
    assert repository.asked == []
    return caught.value.code


async def test_asks_the_resolved_court_with_the_longest_word_of_the_query():
    repository = _Repository()

    result = await _search(repository, court=" TJSP ", query="  recurso especial ", limit=5)

    assert repository.asked == [("tjsp", "especial", DAY, DAY, 1)]
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
    assert len(repository.asked) == MAX_REQUESTS_PER_CALL


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

    assert len(repository.asked) == MAX_REQUESTS_PER_CALL
    assert result.publications == () and result.next_cursor


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


def _cursor(position, key=None):
    key = key or "|".join(("2026-10-15", "2026-10-15", "recurso especial", "", ""))
    return Cursor("tjsp", position, key).encode()


@pytest.mark.parametrize(
    "position",
    [
        ("2026-10-15", 0, "", 0, 0, ""),
        ("2026-10-15", 0, "", MAX_DJEN_PAGE + 1, 0, ""),
        ("2026-10-15", 0, "", 1, -1, ""),
        ("2026-10-15", 0, "", 1, 0, "other"),
        ("2026-10-15", 0, "x", 1, 0, ""),
        ("2026-10-14", 0, "", 1, 0, ""),
        ("2026-10-16", 0, "", 1, 0, ""),
        ("yesterday", 0, "", 1, 0, ""),
        ("2026-10-15", 0, "", 1, 0),
        (1, 0, "", 1, 0, ""),
        ("2026-10-15", 0, "", "a", 0, ""),
        ("2026-10-15", 1, "", 1, 0, ""),
        ("2026-10-15", -1, "", 1, 0, ""),
    ],
)
async def test_a_cursor_with_a_malformed_position_is_invalid(position):
    repository = _Repository()

    with pytest.raises(ToolFailure) as caught:
        await _search(repository, cursor=_cursor(position))

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT and repository.asked == []


@pytest.mark.parametrize("token", ["not a cursor", "e30", ""])
async def test_a_garbage_cursor_is_invalid(token):
    with pytest.raises(ToolFailure) as caught:
        await _search(_Repository(), cursor=token)

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


FIRST, LAST = date(2026, 10, 1), date(2026, 10, 3)


async def test_the_window_is_walked_newest_day_first():
    days = _Days()

    result = await _search(days, date_from=FIRST, date_to=LAST)

    assert [asked[0] for asked in days.asked] == [LAST, LAST - timedelta(1), FIRST]
    assert result.complete is True and result.incomplete_reason is None
    assert result.next_cursor is None


async def test_the_search_goes_on_to_older_days_until_the_limit_is_filled():
    days = _Days({(LAST, None, 1): _page(SENTENCA), (FIRST, None, 1): _page(SENTENCA, SENTENCA)})

    result = await _search(days, date_from=FIRST, date_to=LAST, limit=2)

    assert len(result.publications) == 2 and result.next_cursor
    assert [asked[0] for asked in days.asked] == [LAST, LAST - timedelta(1), FIRST]


async def test_a_call_stops_at_its_request_budget_with_a_cursor_that_carries_on():
    window = {"date_from": date(2026, 9, 1), "date_to": date(2026, 9, 30)}
    days = _Days()

    first = await _search(days, **window)
    second = await _search(days, **window, cursor=first.next_cursor)
    third = await _search(days, **window, cursor=second.next_cursor)

    assert len(days.asked) == 30
    assert (first.complete, first.incomplete_reason) == (False, "budget")
    assert (second.complete, second.incomplete_reason) == (False, "budget")
    assert (third.complete, third.incomplete_reason) == (True, None)
    assert third.next_cursor is None
    visited = [asked[0] for asked in days.asked]
    assert visited == [date(2026, 9, 30) - timedelta(i) for i in range(30)]


async def test_a_full_page_ends_the_call_before_the_budget_is_spent():
    days = _Days({(LAST, None, 1): _page(SENTENCA, SENTENCA)})

    result = await _search(days, date_from=FIRST, date_to=LAST, limit=2)

    assert len(days.asked) == 1 and result.next_cursor
    assert result.complete is False and result.incomplete_reason == "budget"


def _capped(day, *organs, **fields):
    publications = tuple(_publication(i, organ_id=organ) for i, organ in enumerate(organs))
    return PublicationPage(publications=publications, total=COUNT_CAP, **fields)


async def test_a_day_that_hits_the_count_cap_is_split_by_orgao_and_reported_as_slice_cap():
    days = _Days(
        {
            (DAY, None, 1): _capped(DAY, 1001, 1002),
            (DAY, 1001, 1): _page(SENTENCA),
            (DAY, 1002, 1): _page(SENTENCA, SENTENCA),
        }
    )

    result = await _search(days)

    assert days.asked == [(DAY, None, 1), (DAY, 1001, 1), (DAY, 1002, 1)]
    assert len(result.publications) == 3
    assert result.complete is False and result.incomplete_reason == "slice_cap"
    assert result.next_cursor is None


async def test_a_cursor_resumes_inside_an_orgao_slice():
    days = _Days(
        {
            (DAY, None, 1): _capped(DAY, 1001, 1002),
            (DAY, 1001, 1): _page(SENTENCA, SENTENCA),
            (DAY, 1002, 1): _page(SENTENCA),
        }
    )

    first = await _search(days, limit=1)
    second = await _search(days, limit=1, cursor=first.next_cursor)
    third = await _search(days, limit=1, cursor=second.next_cursor)

    assert [len(r.publications) for r in (first, second, third)] == [1, 1, 1]
    assert days.asked[-1] == (DAY, 1002, 1)
    assert third.next_cursor is None
    assert (third.complete, third.incomplete_reason) == (False, "slice_cap")


async def test_an_orgao_slice_that_still_hits_the_cap_is_slice_cap():
    days = _Days(
        {
            (DAY, None, 1): _capped(DAY, 1001),
            (DAY, 1001, 1): _capped(DAY, 1001),
        }
    )

    result = await _search(days)

    assert result.incomplete_reason == "slice_cap" and result.complete is False


async def test_a_capped_day_with_no_orgao_to_split_by_is_read_as_it_is_and_slice_cap():
    days = _Days({(DAY, None, 1): _capped(DAY, None, None)})

    result = await _search(days)

    assert days.asked == [(DAY, None, 1)]
    assert result.incomplete_reason == "slice_cap" and len(result.publications) == 2


async def test_the_depth_ceiling_is_truncation_not_an_error():
    days = _Days(
        {
            (DAY, None, 1): _page(SENTENCA, more=True),
            (DAY, None, 2): PublicationPage(publications=(), total=0, truncated=True),
        }
    )

    result = await _search(days)

    assert len(result.publications) == 1 and result.next_cursor is None
    assert (result.complete, result.incomplete_reason) == (False, "depth_ceiling")


async def test_the_last_page_the_source_serves_is_the_depth_ceiling():
    days = _Days({(DAY, None, MAX_DJEN_PAGE): _page(SENTENCA, more=True)})
    cursor = _cursor((DAY.isoformat(), 0, "", MAX_DJEN_PAGE, 0, ""))

    result = await _search(days, cursor=cursor)

    assert result.next_cursor is None and result.incomplete_reason == "depth_ceiling"


async def test_a_truncation_met_earlier_is_still_reported_by_the_last_call():
    days = _Days(
        {
            (LAST, None, 1): _page(SENTENCA, more=True),
            (LAST, None, 2): PublicationPage(publications=(), total=0, truncated=True),
        }
    )

    first = await _search(days, date_from=FIRST, date_to=LAST, limit=1)
    second = await _search(days, date_from=FIRST, date_to=LAST, cursor=first.next_cursor)

    assert first.next_cursor and first.incomplete_reason == "budget"
    assert second.next_cursor is None and second.incomplete_reason == "depth_ceiling"


async def test_a_cursor_never_shows_a_page_number_or_offset_in_the_clear():
    days = _Days({(DAY, None, 1): _page(SENTENCA, SENTENCA)})

    first = await _search(days, limit=1)

    assert first.next_cursor and "page" not in first.next_cursor.lower()


async def test_a_request_repeated_after_a_429_counts_against_the_budget():
    costly = PublicationPage(publications=(), total=0, requests=2)
    days = _Days({(date(2026, 9, 30) - timedelta(i), None, 1): costly for i in range(30)})

    result = await _search(days, date_from=date(2026, 9, 1), date_to=date(2026, 9, 30))

    assert len(days.asked) == MAX_REQUESTS_PER_CALL // 2
    assert result.incomplete_reason == "budget"


def _with_text(index: int, text: str, kind: PublicationKind = SENTENCA) -> Publication:
    return _publication(index, kind, text=text)


class _ByTerm:
    """Answers each dispatched term with its own page."""

    def __init__(self, **pages):
        self.pages = pages
        self.asked: list[str] = []

    async def search(self, request):
        self.asked.append(request.query)
        return self.pages.get(request.query, PublicationPage(publications=(), total=0))


def _of(*publications: Publication) -> PublicationPage:
    return PublicationPage(publications=publications, total=len(publications))


async def test_the_other_words_and_the_exclusions_filter_the_fetched_text():
    repository = _Repository(
        _of(
            _with_text(1, "Recursos especiais sobre custas"),
            _with_text(2, "Especial, sem a outra palavra"),
            _with_text(3, "recurso especial e honorários"),
        )
    )

    result = await _search(repository, query="recurso especial -honorarios")

    assert [p.item_hash for p in result.publications] == ["hash1"]


async def test_each_or_group_asks_the_source_for_its_own_term():
    repository = _ByTerm(
        especial=_of(_with_text(1, "recurso especial")),
        indenizacao=_of(_with_text(2, "dano indenizacao")),
    )

    result = await _search(repository, query="recurso especial OR dano indenizacao")

    assert repository.asked == ["especial", "indenizacao"]
    assert sorted(p.item_hash for p in result.publications) == ["hash1", "hash2"]


async def test_the_union_has_no_duplicates_by_id():
    both = _with_text(1, "recurso especial dano")
    repository = _ByTerm(especial=_of(both), recurso=_of(both))

    result = await _search(repository, query="especial OR recurso dano")

    assert [p.id for p in result.publications] == [both.id]


async def test_a_group_does_not_claim_what_its_source_term_would_not_return():
    plural = _with_text(1, "recursos especial")
    repository = _ByTerm(especial=_of(plural), recursos=_of(plural))

    result = await _search(repository, query="recurso especial OR recursos")

    assert len(result.publications) == 1


async def test_the_groups_are_read_in_turn_and_a_cursor_resumes_in_the_right_group():
    repository = _ByTerm(
        especial=_of(_with_text(1, "recurso especial")),
        indenizacao=_of(_with_text(2, "dano indenizacao"), _with_text(3, "dano indenizacao")),
    )
    query = "recurso especial OR dano indenizacao"

    first = await _search(repository, query=query, limit=2)
    second = await _search(repository, query=query, limit=2, cursor=first.next_cursor)

    assert [p.item_hash for p in first.publications] == ["hash1", "hash2"]
    assert [p.item_hash for p in second.publications] == ["hash3"] and second.complete


async def test_the_result_does_not_carry_the_text_it_was_filtered_on():
    result = await _search(_Repository(_of(_with_text(1, "recurso especial"))))

    assert result.publications[0].text == ""


async def test_a_group_without_a_term_the_source_accepts_never_reaches_it():
    repository = _Repository()

    assert await _code(repository, query="recurso OR de ao") is ErrorCode.INVALID_ARGUMENT
    assert await _code(repository, query='recurso "especial') is ErrorCode.INVALID_ARGUMENT
    assert await _code(repository, query="a OR b OR c OR d recurso") is ErrorCode.INVALID_ARGUMENT


async def test_scores_the_items_of_the_page_but_keeps_them_in_date_order():
    weak = _publication(0, text="recurso especial " + "x " * 50)
    strong = _publication(1, text="recurso especial recurso especial")
    repository = _Repository(PublicationPage(publications=(weak, strong), total=2))

    result = await _search(repository, query="recurso especial")

    assert [p.item_hash for p in result.publications] == ["hash0", "hash1"]
    assert result.publications[1].relevance.score > result.publications[0].relevance.score > 0
    assert result.publications[0].relevance.matched_terms == ("recurso", "especial")
    assert all(p.text == "" for p in result.publications)


NUMBER = CnjNumber("12345677620258260100")
OTHER = CnjNumber("00000011520258260100")


async def _by_number(repository, cnj_number=NUMBER.digits, **overrides):
    """Search by CNJ number alone: no court and no query unless `overrides` give them."""
    arguments = {"court": None, "query": None, "cnj_number": cnj_number, **overrides}
    return await _search(repository, **arguments)


async def test_a_cnj_number_asks_the_source_for_it_with_no_text_and_derives_the_court():
    repository = _Repository(_of(_with_text(1, "qualquer coisa")))

    result = await _by_number(repository, "1234567-76.2025.8.26.0100")

    assert repository.asked == [("tjsp", "", DAY, DAY, 1)]
    assert repository.numbers == [NUMBER]
    assert result.court == "tjsp" and [p.item_hash for p in result.publications] == ["hash1"]
    assert result.publications[0].relevance.score == 0.0
    assert result.complete


async def test_the_20_digit_form_of_the_number_is_accepted():
    repository = _Repository()

    await _by_number(repository, court="tjsp")

    assert repository.numbers == [NUMBER]


async def test_with_a_number_the_query_filters_locally_and_needs_no_long_term():
    repository = _Repository(
        _of(_with_text(1, "Dano moral na sentença"), _with_text(2, "outro assunto"))
    )

    result = await _by_number(repository, query="dano -outro")

    assert repository.asked[0][1] == ""
    assert [p.item_hash for p in result.publications] == ["hash1"]
    assert result.publications[0].relevance.matched_terms == ("dano",)


async def test_the_court_given_with_a_number_must_be_the_one_it_derives():
    repository = _Repository()

    with pytest.raises(ToolFailure) as caught:
        await _by_number(repository, court="trf1")

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT and repository.asked == []


@pytest.mark.parametrize("raw", ["", "123", "1234567-76.2025.8.26.0101", "x" * 20])
async def test_an_invalid_cnj_number_is_invalid_argument(raw):
    repository = _Repository()

    with pytest.raises(ToolFailure) as caught:
        await _by_number(repository, raw, court="tjsp")

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT and repository.asked == []


async def test_without_a_number_a_court_and_a_query_are_required():
    assert await _code(_Repository(), court=None) is ErrorCode.INVALID_ARGUMENT
    assert await _code(_Repository(), query=None) is ErrorCode.INVALID_ARGUMENT
    assert await _code(_Repository(), query="  ") is ErrorCode.INVALID_ARGUMENT


async def test_a_number_with_no_publications_is_an_empty_complete_result():
    result = await _by_number(_Repository())

    assert result.publications == () and result.complete and result.next_cursor is None


async def test_a_cursor_resumes_the_search_by_number_that_issued_it():
    repository = _Repository(_of(*(_with_text(i, "x") for i in range(3))))
    first = await _by_number(repository, limit=1)

    rest = await _by_number(repository, cursor=first.next_cursor)

    assert first.next_cursor
    assert [p.item_hash for p in rest.publications] == ["hash1", "hash2"]


async def test_a_cursor_is_refused_for_another_number():
    repository = _Repository(_of(*(_with_text(i, "x") for i in range(3))))
    first = await _by_number(repository, limit=1)

    with pytest.raises(ToolFailure) as caught:
        await _by_number(repository, OTHER.digits, cursor=first.next_cursor)

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
