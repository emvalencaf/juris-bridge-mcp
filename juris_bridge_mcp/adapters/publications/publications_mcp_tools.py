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
        date_from: date,
        date_to: date,
        court: str | None = None,
        query: str | None = None,
        cnj_number: str | None = None,
        kind: str | None = None,
        limit: int = DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Search the Publications (decisions and rulings released in a Diário da Justiça
        Eletrônico) of one Brazilian Court, by release date and text.

        WARNING: Publications carry personal data (party names, sometimes lawyers and
        other people), published as the Court released it. The LGPD applies to what you
        do with it: do not store, profile or repeat it beyond what the task needs.

        Pass `cnj_number` (masked `NNNNNNN-DD.AAAA.J.TR.OOOO` or its 20 digits; a wrong length or
        check digit is `invalid_argument`) to list the Publications of one Case in the window:
        `court` is then derived from the number, or checked against it when given (a mismatch is
        `invalid_argument`), and `query` is optional; when present it filters locally, with the
        same syntax, and its terms need not be 5 characters. Each item carries only the CNJ
        number: call get_case for the Case. The Source is asked for the whole window at once, not
        day by day, so a Case costs one request however long the window. A number with no
        Publications in the window returns an empty, complete page. Without `cnj_number`,
        `court` and `query` are required.

        `court` is an alias such as `tjsp`, `trf1` or `stj` (see list_coverage); an
        unknown alias returns `invalid_argument`. STF and the electoral courts do not
        publish in the DJEN, and a window ending before a Court's start there (about 2021
        for the oldest, later for most) returns `not_covered`. `date_from` and `date_to`
        are inclusive ISO dates (`2026-10-15`), spanning at most 31 days counting both
        ends. `query` is interpreted here, since the Source reads its text as one ordered,
        adjacent phrase and has no operators: a space is AND, `"exact phrase"` keeps words
        together, `OR` joins up to 3 alternative groups, `-term` (or `-"phrase"`) excludes, up to
        8 in all; AND, NOT and `*` are not operators. Each group needs a word or phrase of at
        least 5 characters, else `invalid_argument` (as for malformed input, with the reason).
        Per group the Source is asked for its longest phrase, otherwise its longest word, and the
        other words and the exclusions filter the text here, ignoring case and accents and
        matching by word prefix (`recurso` finds `recursos`; no stemming). The groups' results are
        united without duplicates. The word asked of the Source is matched exactly by it, so a
        plural of that word is not found: put the likelier form in the query or add an OR group. An
        item two OR groups both match is returned once, by the first; if that group was truncated
        by the Source, `incomplete_reason` says so.
        `kind` keeps one kind only: `acordao`, `sentenca`, `decisao_monocratica`,
        `decisao_interlocutoria` or `ambiguous`; by default every decision is returned,
        `ambiguous` included.

        Returns up to `limit` (1-25, default 10) decisions, newest day first (the window is
        walked back from `date_to`, one day at a time). Each item has an
        opaque `id`, `cnj_number` (masked) and `cnj_number_digits`, `kind` (our classification,
        see below), the Court's own `document_type` (free text, not normalized),
        `published_on`, a plain-text `excerpt` (HTML stripped, at most 500 characters),
        `text_length` of the whole text, `content_kind: "metadata"` and a `citation` whose
        `url` is null when the item has no link of its own. It also has `matched_terms`, the
        query terms found in its text, and `score`, a BM25 relevance from 0 to 1 computed over
        the texts of this response only (accents and case ignored; the start of the text and the
        ementa weigh more) and scaled so the best item of the page is 1.0, which a page of one
        item always is. `score` is not comparable across pages, and the order is by date: there is
        no global relevance ordering, so compare scores within a response and read on with
        `next_cursor` for the rest.

        A call makes at most 10 requests to the Source. `complete` is true when the search
        reached the end of the window and the Source truncated nothing. Otherwise
        `incomplete_reason` is `budget` (more follows: pass `next_cursor`, an opaque token, back
        as `cursor` with the same court, dates, query and kind; a different search returns
        `invalid_argument`), `slice_cap` (a day matched 10,000 or more items, where the Source
        stops counting; it is split by issuing body, so some items may be missing) or
        `depth_ceiling` (the Source refuses to page deeper); the last two are reported once the
        window is done, and `hint` says what to narrow. `not_decisions_dropped` says how many
        despachos, intimações and editais the pages read in this call held. `kind` is inferred
        from the text, since the Source's labels do not say it (TJSP files most acts as
        "Intimação", STJ as "DESPACHO / DECISÃO"): it is heuristic, wrong now and then at the
        line between a despacho and an interlocutory decision, and `ambiguous` is returned
        instead of a guess. A 429 from the Source is waited out for 60 s once, then
        `rate_limited`. For the Case itself, call get_case with the `cnj_number`.
        """
        try:
            outcome = await search_publications(
                repository,
                court=court,
                date_from=date_from,
                date_to=date_to,
                query=query,
                cnj_number=cnj_number,
                kind=kind,
                limit=limit,
                cursor=cursor,
            )
        except ToolFailure as failure:
            wide_event.record_failure(failure)
            raise to_tool_error(failure) from None
        wide_event.annotate(
            source=SOURCE,
            court=outcome.court,
            result_count=len(outcome.publications),
            paginated=cursor is not None,
            call_shape={
                "court_alias": outcome.court,
                "limit": limit,
                "cursor_sent": cursor is not None,
            },
        )
        return present_search(outcome)

    return server
