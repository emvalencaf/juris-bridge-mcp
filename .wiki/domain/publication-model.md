---
type: Domain Model
title: "Publication model, query syntax, kind and relevance"
description: "Publication types plus the local query parser, kind classifier and per-page BM25 ranking."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/domain/publication.py
tags: [domain, publications, search]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: pub
    resource: juris_bridge_mcp/domain/publication.py
    title: publication.py
  - id: q
    resource: juris_bridge_mcp/domain/publication_query.py
    title: publication_query.py
  - id: k
    resource: juris_bridge_mcp/domain/publication_kind.py
    title: publication_kind.py
  - id: r
    resource: juris_bridge_mcp/domain/publication_ranking.py
    title: publication_ranking.py
---

# Model

`Publication` is one item of a Diário with a plain-text excerpt; `PublicationSearch` is a Court's window of days; `PublicationPage` is a page (100 items, newest first, before filtering).[^pub] `COUNT_CAP` (10,000) is where the Source stops counting.

# Query syntax

Interpreted on our side because the DJEN ignores operators:[^q]

* space = AND; `"exact phrase"` = one term; `OR` splits at most 3 groups; `-term` excludes (at most 8 overall). `AND`, `NOT` and `*` are not operators.
* Each group needs a word or phrase of ≥ 5 characters. The Source is asked one term per group (longest phrase, else longest word, matched exactly — plurals are not found); the rest filters fetched text locally, ignoring accents/case and matching by word prefix. No stemmer.

# Kind

`classify_publication` uses `tipoComunicacao`, `tipoDocumento` and the text, because DJEN labels do not separate a sentença from a despacho. It is a heuristic and answers `ambiguous` rather than guess; its weak spot is despacho vs. interlocutory decision.[^k]

# Relevance

`rank` computes page-relative BM25 in pure Python and scales the best item to 1.0 (0 for all when nothing matches). Scores are **not comparable across pages**; results stay ordered by date. Matches in the first words or the ementa weigh more (`ZONE_BOOST`).[^r]

[^pub]: publication.py
[^q]: publication_query.py
[^k]: publication_kind.py
[^r]: publication_ranking.py
