"""The Planalto static pages as the Source of norm text."""

import httpx

from juris_bridge_mcp.adapters.http_client import UpstreamClient
from juris_bridge_mcp.adapters.planalto.norm_text_parser import parse_norm_text
from juris_bridge_mcp.adapters.schema_drift import SchemaDrift
from juris_bridge_mcp.domain.errors import ErrorCode, source_changed, source_failure
from juris_bridge_mcp.domain.legislation import Urn
from juris_bridge_mcp.domain.legislation_text import TEXT_SOURCE, NormText

# Planalto groups acts by presidential term from 2004 on; the first year of each range.
_ERA_STARTS = (2023, 2019, 2015, 2011, 2007, 2004)

# Norm type -> (directory, file prefix) under the term folder; the file is `<prefix><number>.htm`.
_TERM_FOLDERS = {
    "lei": ("lei", "l"),
    "decreto": ("decreto", "d"),
    "medida-provisoria": ("mpv", "mpv"),
}
_BLOCKED_STATUSES = frozenset({401, 403, 406, 451})


def candidate_paths(urn: Urn) -> list[str]:
    """Return the page paths (under `ccivil_03`) a norm may live at, most likely first.

    Planalto has no index by URN, so paths are built by convention. The folder names are
    case-insensitive and the server redirects a wrong file-name case.
    """
    number, year = urn.number, urn.signed_on.year
    paths: list[str] = []
    if urn.norm_type in _TERM_FOLDERS and year >= _ERA_STARTS[-1]:
        start = next(s for s in _ERA_STARTS if year >= s)
        end = start + 3 if start != 2004 else 2006
        folder, prefix = _TERM_FOLDERS[urn.norm_type]
        paths.append(f"_ato{start}-{end}/{year}/{folder}/{prefix}{number}.htm")
    elif urn.norm_type == "lei":
        paths += [f"leis/{year}/l{number}.htm", f"leis/l{number}.htm"]
    elif urn.norm_type == "decreto":
        paths.append(f"decreto/d{number}.htm")
    elif urn.norm_type == "lei-complementar":
        paths.append(f"leis/lcp/lcp{number}.htm")
    elif urn.norm_type == "decreto-lei":
        paths.append(f"decreto-lei/del{number:04d}.htm")
    elif urn.norm_type == "emenda-constitucional":
        paths += [
            f"constituicao/emendas/emc/emc{number}.htm",
            f"constituicao/emendas/emc/emc{number:02d}.htm",
        ]
    return list(dict.fromkeys(paths))


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
