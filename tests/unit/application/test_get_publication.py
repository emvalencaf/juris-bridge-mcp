import base64
from datetime import date

import pytest

from juris_bridge_mcp.application.use_cases.get_publication import SLICE_CHARS, get_publication
from juris_bridge_mcp.domain.cnj_number import CnjNumber
from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.publication import Publication, PublicationPage
from juris_bridge_mcp.domain.publication_kind import PublicationKind

DAY = date(2026, 10, 15)


def _publication(item_hash: str = "h1", text: str = "texto curto") -> Publication:
    return Publication(
        court="tjsp",
        day=DAY,
        number=CnjNumber("12345677620258260100"),
        document_type="Acórdão",
        excerpt=text[:50],
        text_length=len(text),
        text=text,
        item_hash=item_hash,
        kind=PublicationKind.ACORDAO,
    )


class _Repository:
    def __init__(self, *pages: PublicationPage) -> None:
        self.pages = pages
        self.asked: list = []

    async def search(self, request):
        self.asked.append(request)
        return self.pages[min(request.page, len(self.pages)) - 1]


def _page(*publications: Publication, more: bool = False) -> PublicationPage:
    return PublicationPage(publications=publications, total=len(publications), more=more)


def _encode(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


async def _failure(**kwargs) -> ToolFailure:
    with pytest.raises(ToolFailure) as caught:
        await get_publication(_Repository(_page(_publication())), **kwargs)
    return caught.value


async def test_returns_the_whole_short_text_in_one_slice():
    wanted = _publication()
    result = await get_publication(_Repository(_page(wanted)), publication_id=wanted.id)

    assert result.text == "texto curto" and not result.truncated and result.next_cursor is None
    assert result.publication == wanted


async def test_repeats_the_narrow_query_the_id_carries():
    wanted = _publication()
    repository = _Repository(_page(wanted))

    await get_publication(repository, publication_id=wanted.id)

    request = repository.asked[0]
    assert (request.court, request.date_from, request.date_to) == ("tjsp", DAY, DAY)
    assert request.cnj_number == wanted.number and request.query == ""


async def test_picks_the_item_by_its_hash_among_those_of_the_case():
    wanted = _publication("h2", "o segundo")
    repository = _Repository(_page(_publication("h1", "o primeiro"), wanted))

    result = await get_publication(repository, publication_id=wanted.id)

    assert result.text == "o segundo"


async def test_looks_on_the_next_page_when_the_item_is_not_on_the_first():
    wanted = _publication("h2", "na segunda")
    repository = _Repository(_page(_publication("h1"), more=True), _page(wanted))

    result = await get_publication(repository, publication_id=wanted.id)

    assert result.text == "na segunda" and len(repository.asked) == 2


async def test_an_item_gone_is_not_found():
    gone = _publication("gone")
    with pytest.raises(ToolFailure) as caught:
        await get_publication(_Repository(_page(_publication("h1"))), publication_id=gone.id)

    assert caught.value.code is ErrorCode.NOT_FOUND


async def test_slices_on_a_space_and_chains_the_cursor_to_the_whole_text():
    text = " ".join(f"palavra{i}" for i in range(4000))
    wanted = _publication(text=text)
    pieces: list[str] = []
    cursor = None
    while True:
        result = await get_publication(
            _Repository(_page(wanted)), publication_id=wanted.id, cursor=cursor
        )
        pieces.append(result.text)
        cursor = result.next_cursor
        if not result.truncated:
            break

    assert len(pieces) > 1
    assert all(len(piece) <= SLICE_CHARS and piece == piece.strip() for piece in pieces)
    assert " ".join(pieces) == text


async def test_a_text_without_spaces_is_cut_at_the_limit():
    wanted = _publication(text="x" * (SLICE_CHARS + 5))
    repository = _Repository(_page(wanted))

    first = await get_publication(repository, publication_id=wanted.id)
    second = await get_publication(repository, publication_id=wanted.id, cursor=first.next_cursor)

    assert len(first.text) == SLICE_CHARS and second.text == "x" * 5 and not second.truncated


@pytest.mark.parametrize(
    "bad",
    [
        "not base64 !!",
        _encode("tjsp|2026-10-15|12345677620258260100"),
        _encode("tjsp|15/10/2026|12345677620258260100|h1"),
        _encode("tjsp|2026-10-15|123|h1"),
        _encode("tjsp|2026-10-15|12345677620258260100|"),
        _encode("nowhere|2026-10-15|12345677620258260100|h1"),
    ],
)
async def test_a_malformed_id_is_invalid_argument(bad):
    failure = await _failure(publication_id=bad)

    assert failure.code is ErrorCode.INVALID_ARGUMENT


@pytest.mark.parametrize("cursor", ["garbage", Cursor("djen", ("x",), "").encode()])
async def test_a_malformed_cursor_is_invalid_argument(cursor):
    failure = await _failure(publication_id=_publication().id, cursor=cursor)

    assert failure.code is ErrorCode.INVALID_ARGUMENT


async def test_a_cursor_of_another_publication_or_past_the_end_is_invalid_argument():
    one, other = _publication("h1"), _publication("h2")
    foreign = Cursor("djen", (3,), other.id).encode()
    past_end = Cursor("djen", (500,), one.id).encode()

    for cursor in (foreign, past_end):
        failure = await _failure(publication_id=one.id, cursor=cursor)
        assert failure.code is ErrorCode.INVALID_ARGUMENT


async def test_a_failure_of_the_source_reaches_the_caller_unchanged():
    class _Down:
        async def search(self, request):
            raise ToolFailure(ErrorCode.SOURCE_UNAVAILABLE, "down", source="djen", retryable=True)

    with pytest.raises(ToolFailure) as caught:
        await get_publication(_Down(), publication_id=_publication().id)

    assert caught.value.code is ErrorCode.SOURCE_UNAVAILABLE
