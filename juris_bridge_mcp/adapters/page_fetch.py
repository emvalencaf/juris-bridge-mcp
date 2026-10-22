"""Fetches one static page of a Source, turning every unexpected answer into a failure."""

import httpx

from juris_bridge_mcp.adapters.http_client import UpstreamClient
from juris_bridge_mcp.domain.errors import ErrorCode, source_changed, source_failure

_BLOCKED_STATUSES = frozenset({401, 403, 406, 451})


async def get_page(
    client: UpstreamClient, url: str, *, source: str, name: str
) -> httpx.Response | None:
    """Return the page at `url`, `None` when the Source has none; raise the failure otherwise.

    `name` is how the Source is called in messages, e.g. `The Planalto`.
    """
    try:
        response = await client.request("GET", url, follow_redirects=True)
    except httpx.HTTPError:
        raise source_failure(
            source,
            ErrorCode.SOURCE_UNAVAILABLE,
            f"{name} did not answer in time.",
            retryable=True,
        ) from None
    status = response.status_code
    if status == 200:
        return response
    if status in (404, 410):
        return None
    if status in _BLOCKED_STATUSES:
        raise source_failure(
            source,
            ErrorCode.SOURCE_BLOCKED,
            f"{name} refused this server (HTTP {status}).",
            retryable=False,
            hint="Use the Citation URL to read the norm in a browser.",
        )
    if status >= 500:
        raise source_failure(
            source,
            ErrorCode.SOURCE_UNAVAILABLE,
            f"{name} is unavailable (HTTP {status}).",
            retryable=True,
        )
    raise source_changed(source, name, f"HTTP {status}")
