"""Use case: state what the server can and cannot answer."""

from typing import Any

from juris_bridge_mcp.ports.coverage_catalog import CoverageCatalog


def list_coverage(catalog: CoverageCatalog) -> dict[str, Any]:
    """Return the Coverage per Source and Court, without any network call."""
    return {
        "sources": [
            {
                "source": s.source,
                "kind": s.kind,
                "description": s.description,
                "courts": [c.to_dict() for c in s.courts],
            }
            for s in catalog.sources()
        ]
    }
