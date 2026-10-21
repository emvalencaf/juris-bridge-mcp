"""Inbound adapter: the `list_coverage` tool as a FastMCP sub-server."""

from typing import Any

from fastmcp import FastMCP

from juris_bridge_mcp.application.use_cases.list_coverage import list_coverage
from juris_bridge_mcp.ports.coverage_catalog import CoverageCatalog


def build_coverage_server(catalog: CoverageCatalog) -> FastMCP:
    """Build the sub-server exposing `list_coverage` over the given catalog."""
    server = FastMCP("coverage")

    @server.tool(name="list_coverage", annotations={"readOnlyHint": True})
    def list_coverage_tool() -> dict[str, Any]:
        """List what this server can answer, per Source and Court (Tribunal).

        Sources are DataJud (court Cases, identified by CNJ number), the DJEN (court
        Publications) and the Senado API (federal Legislation). Each Court has a short
        alias such as `tjsp`; `citation_url` says whether a stable public URL can be
        cited for its Cases. For the DJEN, `supported` is false for STF and the TREs
        (`reason` says why, and searching them returns `not_covered`), and
        `available_from` is the first day with data seen (null if unknown). The DJEN is
        no archive: it starts about 2021 and later for many Courts, and its results can
        be non-exhaustive.
        Makes no network call, so use it to plan before querying.
        """
        return list_coverage(catalog)

    return server
