import json
from datetime import date

import pytest

from juris_bridge_mcp.application.use_cases.legislation.get_legislation import (
    DEFAULT_RELATIONS_LIMIT,
    get_legislation,
)
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.legislation import Norm, NormRecord, Relation
from juris_bridge_mcp.domain.legislation_text import Article, NormText

URN = "urn:lex:br:federal:lei:2021-04-01;14133"
NORM = Norm(URN, "lei", 14133, 2021, date(2021, 4, 1), "Lei nº 14.133 de 01/04/2021")


class _Repository:
    def __init__(self, record):
        self.record = record
        self.asked: list[str] = []

    async def find_by_urn(self, urn):
        self.asked.append(urn.text)
        return self.record


class _TextSource:
    def __init__(self, text=None):
        self.text = text
        self.fetched = 0

    async def fetch(self, urn):
        self.fetched += 1
        return self.text


def _text(*articles: Article, full: str | None = None) -> NormText:
    body = full if full is not None else "\n".join(a.text for a in articles)
    return NormText(body, tuple(articles), "https://planalto.test/l1.htm")


def _record(relations=(), raw=None) -> NormRecord:
    return NormRecord(NORM, (), tuple(relations), raw if raw is not None else {})


def _relation(day: int, kind="Declaração de Alteração Permanente") -> Relation:
    return Relation(kind, f"Lei nº {day}", date(2022, 1, day), str(day))


async def _failure(record, **arguments) -> ToolFailure:
    with pytest.raises(ToolFailure) as caught:
        await get_legislation(_Repository(record), _TextSource(), **arguments)
    return caught.value


async def test_fetches_the_norm_by_urn():
    repository = _Repository(_record())

    result = await get_legislation(repository, _TextSource(), urn=f" {URN} ")

    assert repository.asked == [URN] and result.norm == NORM
    assert result.relations == () and result.relations_total == 0 and result.raw is None


async def test_keeps_the_most_recent_relations_up_to_the_limit():
    record = _record([_relation(d) for d in (3, 9, 1, 7)])

    result = await get_legislation(_Repository(record), _TextSource(), urn=URN, relations_limit=2)

    assert [r.norm_id for r in result.relations] == ["9", "7"]
    assert result.relations_total == 4


async def test_collapses_a_norm_repeated_with_the_same_kind():
    record = _record([_relation(5), _relation(5), _relation(5, kind="Declaração de Veto Original")])

    result = await get_legislation(_Repository(record), _TextSource(), urn=URN)

    assert result.relations_total == 2 and DEFAULT_RELATIONS_LIMIT == 25


async def test_an_unknown_urn_is_not_found():
    failure = await _failure(None, urn=URN)

    assert failure.code is ErrorCode.NOT_FOUND and failure.source == "senado"


@pytest.mark.parametrize("urn", ["lei 14133", "urn:lex:br:sao.paulo:estadual:lei:2021-04-01;1"])
async def test_a_malformed_urn_is_invalid(urn):
    failure = await _failure(_record(), urn=urn)

    assert failure.code is ErrorCode.INVALID_ARGUMENT and "search_legislation" in failure.hint


@pytest.mark.parametrize("limit", [0, 101])
async def test_relations_limit_is_bounded(limit):
    failure = await _failure(_record(), urn=URN, relations_limit=limit)

    assert failure.code is ErrorCode.INVALID_ARGUMENT


async def test_no_text_is_fetched_unless_asked_for():
    source = _TextSource(_text(Article("1", "Art. 1º Text.")))

    result = await get_legislation(_Repository(_record()), source, urn=URN)

    assert result.text is None and source.fetched == 0


async def test_include_text_slices_the_plain_text_and_hands_back_a_cursor():
    source = _TextSource(_text(full="abcdefghij"))
    repository = _Repository(_record())

    first = await get_legislation(repository, source, urn=URN, include_text=True, max_chars=4)
    second = await get_legislation(
        repository,
        source,
        urn=URN,
        include_text=True,
        max_chars=4,
        text_cursor=first.text.next_cursor,
    )
    last = await get_legislation(
        repository,
        source,
        urn=URN,
        include_text=True,
        max_chars=4,
        text_cursor=second.text.next_cursor,
    )

    assert (first.text.text, first.text.truncated) == ("abcd", True)
    assert (second.text.text, second.text.truncated) == ("efgh", True)
    assert (last.text.text, last.text.truncated, last.text.next_cursor) == ("ij", False, None)
    assert last.text.url == "https://planalto.test/l1.htm"


async def test_text_that_fits_is_not_truncated():
    result = await get_legislation(
        _Repository(_record()), _TextSource(_text(full="short")), urn=URN, include_text=True
    )

    assert (
        result.text.text == "short"
        and not result.text.truncated
        and result.text.next_cursor is None
    )


async def test_an_article_returns_only_that_article_in_any_spelling():
    text = _text(Article("4", "Art. 4º Four."), Article("5", "Art. 5º Five.", ("revoked",)))

    result = await get_legislation(
        _Repository(_record()), _TextSource(text), urn=URN, article="art 5"
    )

    assert result.text.text == "Art. 5º Five." and result.text.article.flags == ("revoked",)
    assert result.text.article.label == "Art. 5º"


async def test_an_article_the_parser_cannot_locate_is_not_found():
    text = _text(Article("4", "Art. 4º Four."))

    with pytest.raises(ToolFailure) as caught:
        await get_legislation(_Repository(_record()), _TextSource(text), urn=URN, article="Art. 9º")

    assert caught.value.code is ErrorCode.NOT_FOUND and caught.value.source == "planalto"
    assert "Art. 9º" in caught.value.message


async def test_a_repeated_article_returns_the_first_current_one_with_a_warning():
    text = _text(
        Article("2", "Art. 2º old", ("superseded",)),
        Article("2", "Art. 2º new"),
        Article("2", "Art. 2º other"),
    )

    result = await get_legislation(_Repository(_record()), _TextSource(text), urn=URN, article="2")

    assert result.text.text == "Art. 2º new" and "3 times" in result.warnings[0]


async def test_a_norm_with_no_text_page_returns_metadata_and_a_warning():
    result = await get_legislation(
        _Repository(_record()), _TextSource(None), urn=URN, include_text=True
    )

    assert result.text is None and "only metadata" in result.warnings[0]


async def test_an_article_slice_continues_with_its_own_cursor():
    text = _text(Article("1", "Art. 1º abcdef"))
    repository, source = _Repository(_record()), _TextSource(text)

    first = await get_legislation(repository, source, urn=URN, article="1", max_chars=10)
    rest = await get_legislation(
        repository, source, urn=URN, article="1", max_chars=10, text_cursor=first.text.next_cursor
    )

    assert first.text.text + rest.text.text == "Art. 1º abcdef" and not rest.text.truncated


@pytest.mark.parametrize(
    "arguments",
    [
        {"max_chars": 0},
        {"max_chars": 100_001},
        {"article": "section five"},
        {"text_cursor": "abc"},
        {"include_text": True, "text_cursor": "not-a-cursor"},
    ],
)
async def test_bad_text_arguments_are_invalid(arguments):
    failure = await _failure(_record(), urn=URN, **arguments)

    assert failure.code is ErrorCode.INVALID_ARGUMENT


async def test_a_cursor_for_another_article_is_rejected():
    repository, source = _Repository(_record()), _TextSource(_text(Article("1", "Art. 1º abcdef")))
    first = await get_legislation(repository, source, urn=URN, article="1", max_chars=3)

    with pytest.raises(ToolFailure) as caught:
        await get_legislation(
            repository, source, urn=URN, include_text=True, text_cursor=first.text.next_cursor
        )

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


async def test_raw_is_attached_on_request_and_marked_unstable():
    result = await get_legislation(
        _Repository(_record(raw={"a": 1})), _TextSource(), urn=URN, include_raw=True
    )

    assert result.raw == {"unstable": True, "payload": {"a": 1}}


async def test_raw_larger_than_the_cap_is_dropped_with_a_warning():
    record = _record(raw={"blob": "x" * 300_000})

    result = await get_legislation(_Repository(record), _TextSource(), urn=URN, include_raw=True)

    assert result.raw is None and "raw payload omitted" in result.warnings[0]
    assert len(json.dumps(record.raw)) > 256 * 1024


async def test_a_cursor_past_the_end_of_the_text_is_rejected():
    repository, source = _Repository(_record()), _TextSource(_text(full="abcdef"))
    first = await get_legislation(repository, source, urn=URN, include_text=True, max_chars=3)
    shorter = _TextSource(_text(full="abc"))

    with pytest.raises(ToolFailure) as caught:
        await get_legislation(
            repository, shorter, urn=URN, include_text=True, text_cursor=first.text.next_cursor
        )

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


_NOTED = "Art. 1º Texto um. (Redação dada pela Lei nº 2)\n(Vide Decreto nº 3)\n§ 1º Dois."


async def test_annotations_are_kept_by_default():
    source = _TextSource(_text(full=_NOTED))

    result = await get_legislation(_Repository(_record()), source, urn=URN, include_text=True)

    assert result.text.text == _NOTED and result.warnings == ()


async def test_annotations_can_be_left_out_and_the_result_says_so():
    source = _TextSource(_text(full=_NOTED))

    result = await get_legislation(
        _Repository(_record()), source, urn=URN, include_text=True, include_annotations=False
    )

    assert result.text.text == "Art. 1º Texto um.\n§ 1º Dois."
    assert len(result.warnings) == 1 and "include_annotations" in result.warnings[0]


async def test_no_warning_when_there_was_nothing_to_leave_out():
    source = _TextSource(_text(full="Art. 1º Texto um."))

    result = await get_legislation(
        _Repository(_record()), source, urn=URN, include_text=True, include_annotations=False
    )

    assert result.warnings == ()


async def test_an_article_loses_its_annotations_but_keeps_its_flags():
    article = Article("1", "Art. 1º Texto. (Redação dada pela Lei nº 2)", ("superseded",))
    source = _TextSource(_text(article))

    result = await get_legislation(
        _Repository(_record()), source, urn=URN, article="1", include_annotations=False
    )

    assert result.text.text == "Art. 1º Texto."
    assert result.text.article.flags == ("superseded",)


async def test_slices_count_the_text_without_annotations_and_rebuild_it():
    source = _TextSource(_text(full=_NOTED))
    repository = _Repository(_record())
    pieces, cursor = [], None
    while True:
        result = await get_legislation(
            repository,
            source,
            urn=URN,
            include_text=True,
            include_annotations=False,
            max_chars=7,
            text_cursor=cursor,
        )
        pieces.append(result.text.text)
        cursor = result.text.next_cursor
        if cursor is None:
            break

    assert "".join(pieces) == "Art. 1º Texto um.\n§ 1º Dois."
    assert all(len(piece) <= 7 for piece in pieces) and len(pieces) > 1


async def test_a_cursor_issued_under_the_other_annotations_choice_is_rejected():
    repository, source = _Repository(_record()), _TextSource(_text(full=_NOTED))
    first = await get_legislation(
        repository, source, urn=URN, include_text=True, max_chars=5, include_annotations=False
    )

    with pytest.raises(ToolFailure) as caught:
        await get_legislation(
            repository, source, urn=URN, include_text=True, text_cursor=first.text.next_cursor
        )

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
