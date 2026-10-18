"""The Planalto static pages as the Source of norm text."""

import httpx

from juris_bridge_mcp.adapters.http_client import UpstreamClient
from juris_bridge_mcp.adapters.planalto.norm_text_parser import parse_norm_text
from juris_bridge_mcp.adapters.planalto.planalto_paths import candidate_paths
from juris_bridge_mcp.adapters.schema_drift import SchemaDrift
from juris_bridge_mcp.domain.errors import ErrorCode, source_changed, source_failure
from juris_bridge_mcp.domain.legislation import Urn
from juris_bridge_mcp.domain.legislation_text import TEXT_SOURCE, NormText

_BLOCKED_STATUSES = frozenset({401, 403, 406, 451})


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
            response = await self._get(url)
            if response is None:
                continue
            try:
                return parse_norm_text(_decode(response.content), url=url)
            except SchemaDrift as drift:
                raise source_changed(TEXT_SOURCE, "The Planalto", str(drift)) from None
        return None

    async def _get(self, url: str) -> httpx.Response | None:
        """Return the page, `None` when absent; raise the failure for any other answer."""
        try:
            response = await self._client.request("GET", url, follow_redirects=True)
        except httpx.HTTPError:
            raise source_failure(
                TEXT_SOURCE,
                ErrorCode.SOURCE_UNAVAILABLE,
                "The Planalto did not answer in time.",
                retryable=True,
            ) from None
        status = response.status_code
        if status == 200:
            return response
        if status in (404, 410):
            return None
        if status in _BLOCKED_STATUSES:
            raise source_failure(
                TEXT_SOURCE,
                ErrorCode.SOURCE_BLOCKED,
                f"The Planalto refused this server (HTTP {status}).",
                retryable=False,
                hint="Use the Citation URL to read the norm in a browser.",
            )
        if status >= 500:
            raise source_failure(
                TEXT_SOURCE,
                ErrorCode.SOURCE_UNAVAILABLE,
                f"The Planalto is unavailable (HTTP {status}).",
                retryable=True,
            )
        raise source_changed(TEXT_SOURCE, "The Planalto", f"HTTP {status}")


def _decode(content: bytes) -> str:
    """Decode UTF-8 when the page is, else Windows-1252, which the older pages use."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("cp1252", errors="replace")
