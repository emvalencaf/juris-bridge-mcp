"""The `query` syntax of a Publication search, interpreted on our side.

The DJEN reads `texto` as one ordered, adjacent phrase and ignores operators, so the query is
parsed here: a space is AND, `"exact phrase"` is one term, `OR` splits groups (at most
`MAX_GROUPS`) and `-term` excludes (at most `MAX_EXCLUSIONS` in all). The Source is asked one
term per group, and the rest of the group filters the fetched text locally, ignoring accents
and case and matching by word prefix (`recurso` finds `recursos`); there is no stemmer.
"""

import re
import unicodedata
from dataclasses import dataclass

from juris_bridge_mcp.domain.errors import invalid_argument

MAX_GROUPS = 3
MAX_EXCLUSIONS = 8
# The DJEN answers a term shorter than this with a misleading HTTP 500.
MIN_TERM_LENGTH = 5

_TOKEN = re.compile(r'(-?)"([^"]*)"|([^\s"]+)')
_WORD = re.compile(r"\w+")
_RESERVED = {"AND": "a space already means AND", "NOT": "write -term to exclude a word"}


def normalized_words(text: str) -> tuple[str, ...]:
    """Return the words of `text` lowercased and without accents, in order."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    return tuple(_WORD.findall("".join(c for c in folded if not unicodedata.combining(c))))


def _contains(haystack: tuple[str, ...], needle: tuple[str, ...], *, exact: bool) -> bool:
    size = len(needle)
    for start in range(len(haystack) - size + 1):
        window = haystack[start : start + size]
        if all(w == n if exact else w.startswith(n) for w, n in zip(window, needle, strict=True)):
            return True
    return False


@dataclass(frozen=True)
class Term:
    """A word or a quoted phrase: `text` as typed, `words` normalized."""

    text: str
    words: tuple[str, ...]

    def found_in(self, words: tuple[str, ...], *, exact: bool = False) -> bool:
        """Return whether the term's words appear adjacent and in order, by prefix unless exact."""
        return _contains(words, self.words, exact=exact)


@dataclass(frozen=True)
class QueryGroup:
    """Terms that must all be present and terms that must not, with the one sent to the Source.

    `dispatched` is the longest phrase of at least `MIN_TERM_LENGTH` characters, otherwise the
    longest such word; the Source guarantees it, so `matches` leaves it out.
    """

    required: tuple[Term, ...]
    excluded: tuple[Term, ...]
    dispatched: Term

    def matches(self, words: tuple[str, ...]) -> bool:
        """Return whether a text (as `normalized_words`) holds the rest of the group."""
        return all(
            t.found_in(words) for t in self.required if t is not self.dispatched
        ) and not any(t.found_in(words) for t in self.excluded)

    def claims(self, words: tuple[str, ...]) -> bool:
        """Return whether the Source would have returned this text for the group's own request.

        The Source matches the dispatched term exactly, so this asks it exactly, then the rest.
        """
        return self.dispatched.found_in(words, exact=True) and self.matches(words)


def parse_query(query: str) -> tuple[QueryGroup, ...]:
    """Parse `query` into OR groups, or raise `invalid_argument` explaining what is wrong."""
    if query.count('"') % 2:
        raise invalid_argument(
            "query has an unbalanced quote.", hint='Close every quoted phrase: "exact phrase".'
        )
    groups: list[tuple[list[Term], list[Term]]] = [([], [])]
    for minus, phrase, word in _TOKEN.findall(query):
        required, excluded = groups[-1]
        if word == "OR":
            groups.append(([], []))
            continue
        if word in _RESERVED:
            raise invalid_argument(
                f"{word} is not an operator here: {_RESERVED[word]}.",
                hint='Operators: space (AND), OR, "exact phrase", -term.',
            )
        if "*" in word:
            raise invalid_argument(
                "query takes no wildcards.",
                hint="Words already match by prefix: recurso finds recursos.",
            )
        if word.startswith("-"):
            minus, word = "-", word[1:]
        text = phrase or word
        words = normalized_words(text)
        if not words:
            raise invalid_argument(
                f"query has a term with no letters or digits: {text!r}.",
                hint='Write words, or a "quoted phrase" after -.' if minus else None,
            )
        (excluded if minus else required).append(Term(text.strip(), words))
    if len(groups) > MAX_GROUPS:
        raise invalid_argument(f"query has more than {MAX_GROUPS} OR groups.")
    if sum(len(excluded) for _, excluded in groups) > MAX_EXCLUSIONS:
        raise invalid_argument(f"query has more than {MAX_EXCLUSIONS} excluded terms.")
    return tuple(_group(required, excluded) for required, excluded in groups)


def _group(required: list[Term], excluded: list[Term]) -> QueryGroup:
    if not required and not excluded:
        raise invalid_argument(
            "query has an empty group.",
            hint="Put a term on each side of OR; the query is not empty.",
        )
    long_enough = [t for t in required if len(t.text) >= MIN_TERM_LENGTH]
    phrases = [t for t in long_enough if len(t.words) > 1]
    candidates = phrases or long_enough
    if not candidates:
        raise invalid_argument(
            f"Each OR group needs a word or phrase of at least {MIN_TERM_LENGTH} characters.",
            hint="The Source rejects shorter terms; an exclusion does not count.",
        )
    return QueryGroup(tuple(required), tuple(excluded), max(candidates, key=lambda t: len(t.text)))
