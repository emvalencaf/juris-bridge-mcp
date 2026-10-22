---
type: Adapters
title: "BNP source adapter"
description: "How the BNP adapter reads the undocumented JSON backend of the BNP app, with its quirks."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/adapters/bnp/precedent_source.py
tags: [adapters, precedents, bnp]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: src
    resource: juris_bridge_mcp/adapters/bnp/precedent_source.py
    title: BnpPrecedentSource
  - id: map
    resource: juris_bridge_mcp/adapters/bnp/precedent_mapper.py
    title: precedent_mapper.py
  - id: cache
    resource: juris_bridge_mcp/adapters/bnp/cached_precedent_source.py
    title: CachedPrecedentSource
  - id: res
    resource: docs/research/bnp-precedentes-access.md
    title: BNP research and live probe
  - id: adr8
    resource: docs/adr/0008-bnp-as-the-source-of-precedents.md
    title: ADR 0008
---

# Overview

The Banco Nacional de Precedentes has no documented API. The adapter calls the JSON backend its public web app uses (`pangeabnp.pdpj.jus.br/api/v1`), keyless, read-only and self-hosted per user.[^adr8] The backend is unversioned, so an answer in an unknown shape is `source_changed`; an opt-in test (`JURIS_BRIDGE_LIVE_BNP=1`) checks it against the live service.[^res]

# Quirks the adapter hides

* **Search**: `POST /precedentes` with a `filtro`. Both `orgaos` and `tipos` arrays are required (400 without), so a search naming none asks for all 93 bodies and all kinds. `ordenacao` is required (500 without). Page size is capped to 50 by the tool.[^src]
* **No read-by-id**: `GET /precedentes/{id}` is 404; [get_precedent](/tools/get-precedent.md) searches by body, kind and `nr`. `GET /precedentes/{id}/decisoes` works; a 404 reads as no decisions.
* **Dates**: the filter reads `DD/MM/YYYY` only (ISO is ignored silently); the mapper reads both formats the BNP mixes in results.[^map]
* **Aggregates**: `aggsOrgaos` is global, not per query, so it is not exposed.
* **Errors**: 403 → `source_blocked`, 5xx and timeouts → `source_unavailable`, 429 and 503 retried by the [upstream client](/architecture/upstream-http.md) then `rate_limited`, other statuses or bad JSON → `source_changed`.

# Mapping

`map_precedent` strips HTML to plain text keeping line breaks, takes `matched_terms` from the `<mark>` highlights and raises `SchemaDrift` when a result lacks body, kind or number.[^map]

# Bodies

93 bodies: STF, STJ, TST, TSE, STM, TNU, six TRFs, 27 TJs, 24 TRTs, 27 TREs and three military TJs. Coverage is very uneven (STF and STJ far fuller than most TJs), and the BNP updates about twice a month.

# Cache

`CachedPrecedentSource` keeps searches, found Precedents and decisions that have text for an hour (256 entries). A missing, failing or empty answer is asked again, and `retrieved_at` stays the moment the BNP was asked.[^cache]

[^src]: BnpPrecedentSource
[^map]: precedent_mapper.py
[^cache]: CachedPrecedentSource
[^res]: BNP research and live probe
[^adr8]: ADR 0008
