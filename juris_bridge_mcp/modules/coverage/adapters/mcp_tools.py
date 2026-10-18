"""Inbound adapter: the `list_coverage` tool as a FastMCP sub-server."""

from typing import Any

from fastmcp import FastMCP

from juris_bridge_mcp.modules.coverage.application.use_cases.list_coverage import list_coverage
from juris_bridge_mcp.modules.coverage.ports.coverage_catalog import CoverageCatalog


def build_coverage_server(catalog: CoverageCatalog) -> FastMCP:
    """Build the sub-server exposing `list_coverage` over the given catalog."""
    server = FastMCP("coverage")

    @server.tool(name="list_coverage", annotations={"readOnlyHint": True})
    def list_coverage_tool() -> dict[str, Any]:
        """List what this server can answer, per Source and Court (Tribunal).

        Sources are DataJud (court Cases, identified by CNJ number) and the Senado
        API (federal Legislation). Each Court has a short alias such as `tjsp`;
        `citation_url` says whether a stable public URL can be cited for its Cases.
        Makes no network call, so use it to plan before querying.
        """
        return list_coverage(catalog)

    return server
