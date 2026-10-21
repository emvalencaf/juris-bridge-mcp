"""Page-relative BM25 over the texts a search returned, in pure Python.

The score only says which item of a page fits the query best: document frequencies and the
average length come from the page itself, so scores are not comparable across pages and there
is no global relevance ordering. The scores are then scaled so the best item of the page is
1.0 (0 for all when nothing matches): when every item holds every term the raw values are all
near zero and say nothing to a reader, and a page of one item reads as 1.0. Nothing is indexed
or kept. Accents and case are folded (see `normalized_words`); a term counts by word prefix, a
phrase by adjacent words. An occurrence in the first `HEAD_WORDS` words or in the ementa (found
among the first `EMENTA_SEARCH_WORDS`) weighs `1 + ZONE_BOOST` times.
"""

import math
from collections.abc import Sequence
from dataclasses import replace

from juris_bridge_mcp.domain.publication import Publication, Relevance
from juris_bridge_mcp.domain.publication_query import QueryGroup, Term, normalized_words

K1 = 1.2
B = 0.75
HEAD_WORDS = 150
EMENTA_WORDS = 150
EMENTA_SEARCH_WORDS = 100
ZONE_BOOST = 2.0


def query_terms(groups: tuple[QueryGroup, ...]) -> tuple[Term, ...]:
    """Return the required terms of all groups, once each, in order of appearance."""
    unique = {t.words: t for group in groups for t in group.required}
    return tuple(unique.values())


def _boosted(words: tuple[str, ...]) -> set[int]:
    """Return the indexes of the head of the text and of the ementa."""
    zone = set(range(min(HEAD_WORDS, len(words))))
    # An ementa heads the text; a later "ementa" is a mention in the body.
    if "ementa" in words[:EMENTA_SEARCH_WORDS]:
        start = words.index("ementa") + 1
        zone.update(range(start, min(start + EMENTA_WORDS, len(words))))
    return zone


def rank(terms: Sequence[Term], texts: Sequence[str]) -> list[Relevance]:
    """Return a `Relevance` per text, scored against the other texts of the page."""
    docs = [normalized_words(text) for text in texts]
    zones = [_boosted(words) for words in docs]
    counts = [
        [sum(1 + ZONE_BOOST * (i in zone) for i in term.positions(words)) for term in terms]
        for words, zone in zip(docs, zones, strict=True)
    ]
    size = len(docs)
    average = (sum(len(words) for words in docs) / size) if size else 1.0
    average = average or 1.0
    idf = []
    for column in range(len(terms)):
        holding = sum(1 for row in counts if row[column] > 0)
        idf.append(math.log(1 + (size - holding + 0.5) / (holding + 0.5)))
    scored = []
    for words, row in zip(docs, counts, strict=True):
        norm = K1 * (1 - B + B * len(words) / average)
        score = sum(
            w * (K1 + 1) / (w + norm) * rarity for w, rarity in zip(row, idf, strict=True) if w
        )
        matched = tuple(t.text for t, w in zip(terms, row, strict=True) if w)
        scored.append((score, matched))
    best = max((score for score, _ in scored), default=0.0)
    return [
        Relevance(round(score / best, 3) if best else 0.0, matched) for score, matched in scored
    ]


def rank_publications(
    terms: Sequence[Term], publications: Sequence[Publication]
) -> tuple[Publication, ...]:
    """Return the publications in the same order, each with its `relevance` and no text.

    The text was only needed to filter and score; it is not carried into the result.
    """
    relevance = rank(terms, [p.text for p in publications])
    return tuple(
        replace(p, text="", relevance=r) for p, r in zip(publications, relevance, strict=True)
    )
