"""Inbound adapter: the Legislation tools as a FastMCP sub-server."""

from typing import Any

from fastmcp import FastMCP

from juris_bridge_mcp.adapters import wide_event
from juris_bridge_mcp.adapters.legislation.legislation_presenter import present_norm, present_search
from juris_bridge_mcp.application.use_cases.legislation.get_legislation import (
    DEFAULT_RELATIONS_LIMIT,
    get_legislation,
)
from juris_bridge_mcp.application.use_cases.legislation.search_legislation import (
    DEFAULT_LIMIT,
    search_legislation,
)
from juris_bridge_mcp.domain.errors import ToolFailure, to_tool_error
from juris_bridge_mcp.domain.legislation import SOURCE
from juris_bridge_mcp.domain.legislation_text import DEFAULT_MAX_CHARS
from juris_bridge_mcp.ports.legislation_repository import LegislationRepository
from juris_bridge_mcp.ports.norm_text_source import NormTextSource


def build_legislation_server(
    repository: LegislationRepository, text_source: NormTextSource
) -> FastMCP:
    """Build the sub-server exposing the Legislation tools over the given repository and text."""
    server = FastMCP("legislation")

    @server.tool(name="search_legislation", annotations={"readOnlyHint": True})
    async def search_legislation_tool(
        type: str,
        number: int | None = None,
        year: int | None = None,
        limit: int = DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Locate a Brazilian federal norm from a reference such as "Lei 14.133/2021".

        `type` is one of `lei`, `lei-complementar`, `decreto`, `decreto-lei`,
        `medida-provisoria` or `emenda-constitucional`. Pass `number`, `year` or both;
        there is no free-text search. Federal norms only.

        Returns up to `limit` (1-50, default 10) norms in `items`; an empty search
        returns `items: []`. Each item carries the `urn` (URN Lex, for example
        `urn:lex:br:federal:lei:2021-04-01;14133`), the official `name`, `summary`
        (_ementa_), signature date, and a Citation with the canonical page URL. Content
        is metadata only, not the norm text. When more follow, `next_cursor` is an
        opaque token: pass it back with the same type, number and year for the next page.
        """
        try:
            outcome = await search_legislation(
                repository, norm_type=type, number=number, year=year, limit=limit, cursor=cursor
            )
        except ToolFailure as failure:
            wide_event.record_failure(failure)
            raise to_tool_error(failure) from None
        wide_event.annotate(
            source=SOURCE,
            result_count=len(outcome.norms),
            paginated=cursor is not None,
            call_shape={
                "limit": limit,
                "cursor_sent": cursor is not None,
                "filters": [name for name, value in (("number", number), ("year", year)) if value],
            },
        )
        return present_search(outcome)

    @server.tool(name="get_legislation", annotations={"readOnlyHint": True})
    async def get_legislation_tool(
        urn: str,
        include_text: bool = False,
        article: str | None = None,
        max_chars: int = DEFAULT_MAX_CHARS,
        text_cursor: str | None = None,
        relations_limit: int = DEFAULT_RELATIONS_LIMIT,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        """Fetch one Brazilian federal norm by its URN Lex (see search_legislation).

        `urn` looks like `urn:lex:br:federal:lei:2021-04-01;14133`. Returns type,
        number, year, signature date, official `name`, `nickname`, `summary` (_ementa_),
        a Citation with the canonical page URL, `publications` (Diário Oficial edition,
        page and column) and `relations`: later norms that amend, regulate, veto or
        relate to this one, each with its `kind` (the Senado's Portuguese label), name
        and date. Heavily amended norms have many, so only the newest `relations_limit`
        (1-100, default 25) are returned, newest first, and `relations_total` gives
        the full count. An unknown URN returns `not_found`. `include_raw` attaches the
        upstream Senado document, whose shape is unstable; it is left out if too large.

        By default `content_kind` is `metadata`. With `include_text` the norm text comes
        from the Planalto as plain text (`content_kind: full_text`), in slices of at most
        `max_chars` (1-100000, default 20000): when `truncated` is true, pass
        `next_text_cursor` back as `text_cursor` with the same urn to read on. With
        `article` (for example `Art. 5º`, `121-A` or `Art. único`) only that article is
        returned, with `article.flags`: `revoked` when the Planalto notes it was repealed,
        `superseded` when its wording is struck through. An article the parser cannot
        locate returns `not_found`, never another article. If the Planalto page cannot
        be located, only metadata comes back with a warning in `warnings`; a refusal is
        `source_blocked` and a page this server can no longer read is `source_changed`.
        """
        try:
            outcome = await get_legislation(
                repository,
                text_source,
                urn=urn,
                include_text=include_text,
                article=article,
                max_chars=max_chars,
                text_cursor=text_cursor,
                relations_limit=relations_limit,
                include_raw=include_raw,
            )
        except ToolFailure as failure:
            wide_event.record_failure(failure)
            raise to_tool_error(failure) from None
        wide_event.annotate(
            source=SOURCE,
            result_count=1,
            call_shape={
                "limit": relations_limit,
                "cursor_sent": text_cursor is not None,
                "filters": [name for name, value in (("article", article),) if value],
            },
        )
        return present_norm(outcome)

    return server
