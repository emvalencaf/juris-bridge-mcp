"""The Planalto static pages as the Source of norm text."""

from juris_bridge_mcp.adapters.http_client import UpstreamClient
from juris_bridge_mcp.adapters.legislation.norm_text_parser import decode_page, parse_norm_text
from juris_bridge_mcp.adapters.page_fetch import get_page
from juris_bridge_mcp.adapters.planalto.planalto_paths import candidate_paths
from juris_bridge_mcp.adapters.schema_drift import SchemaDrift
from juris_bridge_mcp.domain.errors import source_changed
from juris_bridge_mcp.domain.legislation import Urn
from juris_bridge_mcp.domain.legislation_text import TEXT_SOURCE, NormText


class PlanaltoNormTextSource:
    """Implements `NormTextSource` by fetching and parsing the norm's Planalto page."""

    def __init__(self, client: UpstreamClient, *, base_url: str) -> None:
        """Fetch pages under `base_url`, the `ccivil_03` root of the Planalto site."""
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def fetch(self, urn: Urn) -> NormText | None:
        """Return the parsed text from the first candidate page that exists, else `None`."""
        for path in candidate_paths(urn):
            url = f"{self._base_url}/{path}"
            response = await get_page(self._client, url, source=TEXT_SOURCE, name="The Planalto")
            if response is None:
                continue
            try:
                return parse_norm_text(decode_page(response.content), url=url)
            except SchemaDrift as drift:
                raise source_changed(TEXT_SOURCE, "The Planalto", str(drift)) from None
        return None
