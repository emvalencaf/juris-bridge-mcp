"""Inbound adapter: the Publication tools as a FastMCP sub-server."""

from datetime import date
from typing import Any

from fastmcp import FastMCP

from juris_bridge_mcp.adapters import wide_event
from juris_bridge_mcp.adapters.publications.publication_presenter import present_search
from juris_bridge_mcp.application.use_cases.search_publications import (
    DEFAULT_LIMIT,
    search_publications,
)
from juris_bridge_mcp.domain.errors import ToolFailure, to_tool_error
from juris_bridge_mcp.domain.publication import SOURCE
from juris_bridge_mcp.ports.publication_repository import PublicationRepository


def build_publications_server(repository: PublicationRepository) -> FastMCP:
    """Build the sub-server exposing the Publication tools over the given repository."""
    server = FastMCP("publications")

    @server.tool(name="search_publications", annotations={"readOnlyHint": True})
    async def search_publications_tool(
        court: str,
        date_from: date,
        date_to: date,
        query: str,
        limit: int = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """Search the Publications (decisions and rulings released in a Diário da Justiça
        Eletrônico) of one Brazilian Court, by release date and text.

        WARNING: Publications carry personal data (party names, sometimes lawyers and
        other people), published as the Court released it. The LGPD applies to what you
        do with it: do not store, profile or repeat it beyond what the task needs.

        `court` is an alias such as `tjsp`, `trf1` or `stj` (see list_coverage); an
        unknown alias returns `invalid_argument`. STF and the electoral courts do not
        publish in the DJEN, and a window ending before a Court's start there (about 2021
        for the oldest, later for most) returns `not_covered`. `date_from` and `date_to`
        are inclusive ISO dates (`2026-10-15`), spanning at most 31 days counting both
        ends. `query` is sent to the Source as it is, trimmed, and must have at least 5
        characters: the Source reads all of it as one phrase, words in that order and
        adjacent, ignoring case and accents but not plurals; it has no AND, OR or quotes.

        Returns up to `limit` (1-25, default 10) Publications of the first page the
        Source answers, newest first as it orders them (no relevance ranking; this tool
        does not page yet, and `hint` says when more match). Each item has an opaque
        `id`, `cnj_number` (masked) and `cnj_number_digits`, the Court's own
        `document_type` (free text, not normalized), `published_on`, a plain-text
        `excerpt` (HTML stripped, at most 500 characters), `text_length` of the whole
        text, `content_kind: "metadata"` and a `citation` whose `url` is null when the
        item has no link of its own. `total` is the Source's count, capped at 10,000
        (`total_is_lower_bound`). Despachos, intimações and editais are not filtered out
        yet. For the Case itself, call get_case with the `cnj_number`.
        """
        try:
            outcome = await search_publications(
                repository,
                court=court,
                date_from=date_from,
                date_to=date_to,
                query=query,
                limit=limit,
            )
        except ToolFailure as failure:
            wide_event.record_failure(failure)
            raise to_tool_error(failure) from None
        wide_event.annotate(
            source=SOURCE,
            court=outcome.court,
            result_count=len(outcome.publications),
            call_shape={"court_alias": outcome.court, "limit": limit},
        )
        return present_search(outcome)

    return server
