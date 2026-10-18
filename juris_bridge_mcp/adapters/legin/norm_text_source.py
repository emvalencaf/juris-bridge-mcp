"""Câmara Legin as the Source of norm text, found through the LexML URN page."""

import re
from dataclasses import replace
from itertools import pairwise

from juris_bridge_mcp.adapters.http_client import UpstreamClient
from juris_bridge_mcp.adapters.legin.legin_pages import (
    MAX_HINTS,
    ChallengePage,
    Sheet,
    is_gateway_error,
    parse_sheet,
    parse_urn_page,
)
from juris_bridge_mcp.adapters.legislation.norm_text_parser import decode_page, parse_norm_text
from juris_bridge_mcp.adapters.page_fetch import get_page
from juris_bridge_mcp.adapters.schema_drift import SchemaDrift
from juris_bridge_mcp.domain.errors import ErrorCode, source_changed, source_failure
from juris_bridge_mcp.domain.legislation import Urn
from juris_bridge_mcp.domain.legislation_text import LEGIN_SOURCE, Article, NormText

_NAME = "The Câmara Legin"
_MAX_LISTED_GAPS = 5


class LeginNormTextSource:
    """Implements `NormTextSource`: URN page, then data sheet, then the text page it links.

    The challenge of the LexML portal is never worked around: it is reported as `source_blocked`.
    """

    def __init__(self, client: UpstreamClient, *, lexml_base_url: str) -> None:
        """Resolve URNs through `lexml_base_url`, the root of the LexML portal."""
        self._client = client
        self._lexml_base_url = lexml_base_url.rstrip("/")

    async def fetch(self, urn: Urn) -> NormText | None:
        """Return the parsed text, with warnings on its provenance, or `None` if Legin lacks it."""
        sheet_url = await self._sheet_url(urn)
        if sheet_url is None:
            return None
        sheet_html = await self._page(sheet_url)
        if sheet_html is None:
            return None
        try:
            sheet = parse_sheet(sheet_html, url=sheet_url)
            if sheet is None:
                return None
            text_html = await self._page(sheet.text_url)
            if text_html is None:
                return None
            text = parse_norm_text(text_html, url=sheet.text_url)
        except SchemaDrift as drift:
            raise source_changed(LEGIN_SOURCE, _NAME, str(drift)) from None
        return replace(text, source=LEGIN_SOURCE, warnings=_warnings(text, sheet))

    async def _sheet_url(self, urn: Urn) -> str | None:
        html = await self._page(f"{self._lexml_base_url}/urn/{urn.text}")
        if html is None:
            return None
        try:
            return parse_urn_page(html)
        except ChallengePage:
            raise source_failure(
                LEGIN_SOURCE,
                ErrorCode.SOURCE_BLOCKED,
                "The LexML portal asked this server to solve a security challenge, which it "
                "does not.",
                retryable=False,
                hint="Use the Citation URL to read the norm in a browser.",
            ) from None
        except SchemaDrift as drift:
            raise source_changed(LEGIN_SOURCE, "The LexML portal", str(drift)) from None

    async def _page(self, url: str) -> str | None:
        response = await get_page(self._client, url, source=LEGIN_SOURCE, name=_NAME)
        if response is None:
            return None
        html = decode_page(response.content)
        if is_gateway_error(html):
            raise source_failure(
                LEGIN_SOURCE,
                ErrorCode.SOURCE_UNAVAILABLE,
                f"{_NAME} timed out serving this page.",
                retryable=True,
            )
        return html


def _warnings(text: NormText, sheet: Sheet) -> tuple[str, ...]:
    notes = [
        "The text comes from the Câmara Legin, not the Planalto; its legislative-history notes "
        "(Annotations) are largely absent."
    ]
    if sheet.original:
        notes.append(
            "The Câmara Legin offers no updated text for this norm, so this is the text as "
            "originally published: later amendments are not applied."
        )
    if sheet.amendments:
        listed = "; ".join(line.rstrip() for line in sheet.amendments[:MAX_HINTS])
        notes.append(
            f"Amendment hints come from the Câmara data sheet, not from the text: "
            f"{len(sheet.amendments)} later norms act on this one, newest first: {listed}."
        )
    if sheet.remark:
        notes.append(f"The Câmara data sheet remarks: {sheet.remark}")
    gaps = _gaps(text.articles)
    if gaps:
        listed_gaps = ", ".join(gaps[:_MAX_LISTED_GAPS])
        notes.append(
            f"The Câmara text jumps over article numbers ({listed_gaps}); the page may be "
            "incomplete, so check the Citation URL before relying on a missing article."
        )
    return tuple(notes)


def _gaps(articles: tuple[Article, ...]) -> list[str]:
    """Return `from-to` for each hole in the article numbers, ignoring lettered articles."""
    numbers = sorted({int(m.group()) for a in articles if (m := re.match(r"\d+", a.key))})
    return [
        f"{before + 1}-{after - 1}" if after - before > 2 else str(before + 1)
        for before, after in pairwise(numbers)
        if after - before > 1
    ]
