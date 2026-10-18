"""Reads a Planalto norm page (FrontPage-era HTML) into plain text with its articles located."""

import re
from html.parser import HTMLParser

from juris_bridge_mcp.adapters.schema_drift import SchemaDrift
from juris_bridge_mcp.domain.legislation_text import (
    REVOKED,
    SUPERSEDED,
    Article,
    NormText,
    article_start,
)

_BREAKS = frozenset({"p", "br", "div", "tr", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6"})
_VOID = frozenset({"br", "hr", "img", "meta", "link", "input", "col", "area", "base", "param"})
_SKIPPED = frozenset({"script", "style", "head"})
_STRUCK = frozenset({"strike", "s", "del"})
_HEADING = re.compile(r"(parte|livro|título|capítulo|seção|subseção|anexo)\b", re.IGNORECASE)
_MAX_HEADING_CHARS = 150
_MIN_TEXT_CHARS = 200


class _Lines(HTMLParser):
    """Collects the visible lines of a page, each marked when it opens struck through."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[tuple[str, bool]] = []
        self._chunks: list[str] = []
        self._struck_line = False
        self._open: list[tuple[str, bool]] = []
        self._skipping = 0

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self._chunks)).strip()
        if text:
            self.lines.append((text, self._struck_line))
        self._chunks, self._struck_line = [], False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED:
            self._skipping += 1
        if tag in _BREAKS:
            self._flush()
        if tag in _VOID or tag in _BREAKS:
            return
        style = dict(attrs).get("style") or ""
        self._open.append((tag, tag in _STRUCK or "line-through" in style))

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED and self._skipping:
            self._skipping -= 1
        if tag in _BREAKS:
            self._flush()
            return
        for index in range(len(self._open) - 1, -1, -1):
            if self._open[index][0] == tag:
                del self._open[index:]
                break

    def handle_data(self, data: str) -> None:
        if self._skipping:
            return
        if data.strip() and not "".join(self._chunks).strip():
            self._struck_line = any(struck for _, struck in self._open)
        self._chunks.append(data)


def parse_norm_text(html: str, *, url: str) -> NormText:
    """Return the plain text of the page at `url`, or raise `SchemaDrift` if it has no articles.

    A line that opens with `Art.` starts an article, which runs to the next article, to a
    heading (`CAPÍTULO`, `Seção`...) or to the closing `Brasília, ...` line.
    """
    reader = _Lines()
    reader.feed(html)
    reader.close()
    lines = reader.lines
    text = "\n".join(line for line, _ in lines)
    if len(text) < _MIN_TEXT_CHARS:
        raise SchemaDrift("the page holds almost no text")
    blocks: list[tuple[str, list[tuple[str, bool]]]] = []
    current: list[tuple[str, bool]] | None = None
    for line, struck in lines:
        key = article_start(line)
        if key is not None:
            current = [(line, struck)]
            blocks.append((key, current))
        elif _closes_article(line):
            current = None
        elif current is not None:
            current.append((line, struck))
    if not blocks:
        raise SchemaDrift("no article found in the page")
    articles = tuple(
        Article(key, "\n".join(line for line, _ in block), _flags(block)) for key, block in blocks
    )
    return NormText(text=text, articles=articles, url=url)


def _closes_article(line: str) -> bool:
    return line.startswith("Brasília,") or (
        len(line) <= _MAX_HEADING_CHARS and _HEADING.match(line) is not None
    )


def _flags(block: list[tuple[str, bool]]) -> tuple[str, ...]:
    """Flag a revoked article by its own "(Revogado ...)" note and a struck one as superseded."""
    first, struck = block[0]
    noted = "(revogad" in first.lower() or (
        len(block) > 1 and block[1][0].lower().startswith("(revogad")
    )
    if noted:
        return (REVOKED,)
    return (SUPERSEDED,) if struck else ()
