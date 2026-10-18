"""The text of a Norm as the Planalto publishes it, and how to address one article of it."""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from juris_bridge_mcp.domain.errors import invalid_argument

TEXT_SOURCE = "planalto"
DEFAULT_MAX_CHARS = 20_000
MAX_MAX_CHARS = 100_000

REVOKED = "revoked"
SUPERSEDED = "superseded"

# `Art. 5º`, `art 5`, `5-A`, `Art. 1.045`, `Art. único`: number (dots dropped), optional
# ordinal mark, optional letter suffix.
_REFERENCE = re.compile(
    r"(?:art(?:igo)?\.?\s*)?(?:(\d[\d.]*)[º°o]?(?:\s*-?\s*([A-Za-z]{1,2}))?|(únic[oa]))\.?",
    re.IGNORECASE,
)
# In the text the suffix hugs the number (`Art. 12-A`); `Art. 12 - A` is a dash and a sentence.
_LINE_START = re.compile(
    r"art\.?\s*(?:(\d[\d.]*)[º°o]?(?:-([A-Za-z]{1,2})\b)?|(únic[oa]))", re.IGNORECASE
)


def article_key(raw: str) -> str:
    """Return the canonical key of an article reference, or raise `invalid_argument`.

    `Art. 5º`, `5` and `art 5` share the key `5`; `121-A` is `121-a`; `Art. único` is `unico`.
    """
    match = _REFERENCE.fullmatch(raw.strip())
    if match is None:
        raise invalid_argument(
            f"'{raw}' is not an article reference.", hint="Use a form such as 'Art. 5º' or '121-A'."
        )
    return _key(*match.groups())


def article_start(line: str) -> str | None:
    """Return the key of the article a line of norm text opens, or `None` for any other line."""
    match = _LINE_START.match(line.strip())
    return _key(*match.groups()) if match else None


def article_label(key: str) -> str:
    """Return the conventional label of an article key, e.g. `5` -> `Art. 5º`."""
    if key == "unico":
        return "Art. único"
    number, _, letter = key.partition("-")
    mark = "º" if number.isdigit() and int(number) <= 9 else ""
    return f"Art. {number}{mark}" + (f"-{letter.upper()}" if letter else "")


def _key(number: str | None, letter: str | None, single: str | None) -> str:
    if single:
        return "unico"
    key = (number or "").replace(".", "")
    return f"{key}-{letter.lower()}" if letter else key


@dataclass(frozen=True)
class Article:
    """One article of a norm, with the flags the Planalto marks it with.

    `flags` hold `revoked` (the Source says the article was repealed) and `superseded` (its
    wording is struck through).
    """

    key: str
    text: str
    flags: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        """Return the conventional label, e.g. `Art. 5º`."""
        return article_label(self.key)


@dataclass(frozen=True)
class NormText:
    """The plain text of a norm, with its articles located."""

    text: str
    articles: tuple[Article, ...]
    url: str
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def find_article(self, key: str) -> tuple[Article | None, int]:
        """Return the article for `key` and how many times it appears in the text.

        The Planalto keeps old wordings struck through next to the new ones, so a key can
        repeat; the first unflagged occurrence wins, else the first.
        """
        found = [a for a in self.articles if a.key == key]
        if not found:
            return None, 0
        return next((a for a in found if not a.flags), found[0]), len(found)
