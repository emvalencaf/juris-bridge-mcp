import pytest

from juris_bridge_mcp.adapters.legislation.fallback_norm_text_source import (
    FallbackNormTextSource,
)
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure, source_failure
from juris_bridge_mcp.domain.legislation import Urn
from juris_bridge_mcp.domain.legislation_text import NormText

LEI = Urn.parse("urn:lex:br:federal:lei:2021-04-01;14133")


class _Source:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = 0

    async def fetch(self, urn):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _text(source: str, *warnings: str) -> NormText:
    return NormText(
        text="Art. 1º Texto.",
        articles=(),
        url=f"https://{source}/x",
        source=source,
        warnings=warnings,
    )


def _failure(code: ErrorCode) -> ToolFailure:
    return source_failure("planalto", code, "refused", retryable=False)


async def test_the_primary_text_is_returned_untouched_and_the_fallback_is_not_asked():
    primary, fallback = _Source(_text("planalto")), _Source(_text("camara_legin"))

    found = await FallbackNormTextSource(primary, fallback).fetch(LEI)

    assert found is primary.outcome and fallback.calls == 0


async def test_without_a_primary_page_the_fallback_text_says_so():
    found = await FallbackNormTextSource(
        _Source(None), _Source(_text("camara_legin", "from the sheet"))
    ).fetch(LEI)

    assert found.source == "camara_legin"
    assert found.warnings[0].startswith("The Planalto has no text page")
    assert found.warnings[1:] == ("from the sheet",)


async def test_a_primary_failure_falls_back_and_names_the_failure():
    primary = _Source(_failure(ErrorCode.SOURCE_BLOCKED))

    found = await FallbackNormTextSource(primary, _Source(_text("camara_legin"))).fetch(LEI)

    assert found.source == "camara_legin"
    assert "The Planalto failed (source_blocked)" in found.warnings[0]


async def test_a_primary_failure_with_nothing_in_the_fallback_is_raised():
    failure = _failure(ErrorCode.SOURCE_BLOCKED)

    with pytest.raises(ToolFailure) as caught:
        await FallbackNormTextSource(_Source(failure), _Source(None)).fetch(LEI)

    assert caught.value is failure


async def test_when_both_fail_the_primary_failure_is_the_one_raised():
    first = _failure(ErrorCode.SOURCE_BLOCKED)
    second = source_failure("camara_legin", ErrorCode.SOURCE_UNAVAILABLE, "down", retryable=True)

    with pytest.raises(ToolFailure) as caught:
        await FallbackNormTextSource(_Source(first), _Source(second)).fetch(LEI)

    assert caught.value is first


async def test_a_fallback_failure_after_a_missing_primary_page_is_raised():
    down = source_failure("camara_legin", ErrorCode.SOURCE_UNAVAILABLE, "down", retryable=True)

    with pytest.raises(ToolFailure) as caught:
        await FallbackNormTextSource(_Source(None), _Source(down)).fetch(LEI)

    assert caught.value is down


async def test_no_page_anywhere_is_none():
    assert await FallbackNormTextSource(_Source(None), _Source(None)).fetch(LEI) is None


async def test_a_changed_primary_page_is_raised_and_the_fallback_is_not_asked():
    changed = _failure(ErrorCode.SOURCE_CHANGED)
    fallback = _Source(_text("camara_legin"))

    with pytest.raises(ToolFailure) as caught:
        await FallbackNormTextSource(_Source(changed), fallback).fetch(LEI)

    assert caught.value is changed and fallback.calls == 0
