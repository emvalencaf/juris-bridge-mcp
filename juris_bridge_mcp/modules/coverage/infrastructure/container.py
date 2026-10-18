"""Wiring of the coverage module."""

from fastmcp import FastMCP

from juris_bridge_mcp.modules.coverage.adapters.mcp_tools import build_coverage_server
from juris_bridge_mcp.modules.coverage.adapters.static_coverage_catalog import (
    StaticCoverageCatalog,
)


def build_server() -> FastMCP:
    """Build the coverage sub-server with its static catalog."""
    return build_coverage_server(StaticCoverageCatalog())
