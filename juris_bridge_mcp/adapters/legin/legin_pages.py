"""Reads the two metadata pages that lead to a Norm's text on Câmara Legin.

The LexML URN page links the Legin data sheet of the norm; the sheet links the text. Neither
link can be derived from the URN, as Legin paths carry an internal id.
"""

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from juris_bridge_mcp.adapters.legislation.norm_text_parser import visible_lines
from juris_bridge_mcp.adapters.schema_drift import SchemaDrift

_CAMARA_HOSTS = ("camara.leg.br", "camara.gov.br")
_CHALLENGE_MARKERS = ("verificação de segurança", "/_challenge")
_NOT_FOUND = "urn não encontrada"
_SHEET_LINK = re.compile(r"/legin/.*-norma-[a-z-]+\.html$", re.IGNORECASE)
_AMENDING = re.compile(r"\((?:altera|acréscimo|revoga|renumera|republica)[^)]*\)", re.IGNORECASE)
_MAX_REMARK_CHARS = 600
MAX_HINTS = 5


class ChallengePage(Exception):  # noqa: N818 - names the situation, not an error class
    """The page is the proof-of-work challenge of the portal, not the page asked for."""


@dataclass(frozen=True)
class Sheet:
    """What the Câmara data sheet of a norm says: where its text is, and what it notes.

    `original` is set when the sheet offers no updated text, only the text as first published.
    `amendments` holds the lines that name a later norm altering this one, newest first.
    """

    text_url: str
    original: bool
    remark: str | None
    amendments: tuple[str, ...]


class _Anchors(HTMLParser):
    """Collects every link of a page with its text."""

    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href, self._text = dict(attrs).get("href"), []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.anchors.append((self._href, " ".join("".join(self._text).split())))
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)


def _anchors(html: str) -> _Anchors:
    reader = _Anchors()
    reader.feed(html)
    reader.close()
    return reader


def camara_url(href: str, *, base: str) -> str:
    """Return `href` resolved against `base` as an https URL on the Câmara site, else raise.

    The links come from a page we do not control, so a host outside the Câmara is refused. The
    old `camara.gov.br` host is rewritten to `camara.leg.br`, where it redirects.
    """
    parts = urlsplit(urljoin(base, href.strip()))
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not any(
        host == d or host.endswith("." + d) for d in _CAMARA_HOSTS
    ):
        raise SchemaDrift(f"a link leaves the Câmara site ({host or 'no host'})")
    host = host.replace("camara.gov.br", "camara.leg.br")
    return parts._replace(scheme="https", netloc=host).geturl()


def parse_urn_page(html: str) -> str | None:
    """Return the Legin data sheet URL the LexML URN page links, or `None` when it has none.

    Raise `ChallengePage` for the portal's challenge and `SchemaDrift` for any other page.
    """
    lowered = html.lower()
    # The not-found page has a malformed `<meta>` that swallows its own `<title>`, so match text.
    if _NOT_FOUND in lowered:
        return None
    for href, _ in _anchors(html).anchors:
        if _SHEET_LINK.search(urlsplit(href).path) and "camara" in href:
            return camara_url(href, base="https://www2.camara.leg.br")
    if any(marker in lowered for marker in _CHALLENGE_MARKERS):
        raise ChallengePage
    if "nome uniforme" in lowered:
        return None
    raise SchemaDrift("the LexML page is not a norm page")


def parse_sheet(html: str, *, url: str) -> Sheet | None:
    """Read the Legin data sheet at `url`, or return `None` when it links no text at all."""
    anchors = _anchors(html).anchors
    updated = next((h for h, text in anchors if text.lower().startswith("texto atualizado")), None)
    original = next((h for h, text in anchors if "publicação original" in text.lower()), None)
    chosen = updated or original
    if chosen is None:
        return None
    lines = [line for line, _ in visible_lines(html)]
    remark = next(
        (
            line.removeprefix("Observação:").strip()
            for line in lines
            if line.startswith("Observação")
        ),
        None,
    )
    return Sheet(
        text_url=camara_url(chosen, base=url),
        original=updated is None,
        remark=remark[:_MAX_REMARK_CHARS] if remark else None,
        amendments=tuple(line for line in lines if _AMENDING.search(line) and " - (" in line),
    )


def is_gateway_error(html: str) -> bool:
    """Tell a proxy's error page served with status 200 (`504 Gateway Time-out`) from a norm."""
    return re.search(r"<title>\s*5\d\d\b", html[:2_000], re.IGNORECASE) is not None
