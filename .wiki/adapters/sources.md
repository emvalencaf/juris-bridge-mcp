---
type: Adapters
title: "Sources and their adapters"
description: "The five upstream Sources, what each serves, and how each adapter maps it."
tags: [adapters, sources]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: dj
    resource: juris_bridge_mcp/adapters/datajud/case_repository.py
    title: DatajudCaseRepository
  - id: djen
    resource: juris_bridge_mcp/adapters/djen/publication_repository.py
    title: DjenPublicationRepository
  - id: sen
    resource: juris_bridge_mcp/adapters/senado/legislation_repository.py
    title: SenadoLegislationRepository
  - id: plan
    resource: juris_bridge_mcp/adapters/planalto/planalto_paths.py
    title: planalto_paths.py
  - id: leg
    resource: juris_bridge_mcp/adapters/legin/norm_text_source.py
    title: LeginNormTextSource
  - id: adr2
    resource: docs/adr/0002-self-hosted-datajud-no-browser-sources.md
    title: ADR 0002
---

# Sources

| Source | Serves | Adapter | Notes |
|--------|--------|---------|-------|
| **DataJud** (CNJ) | Cases | `adapters/datajud/` | One Elasticsearch `_search` per lookup; needs the user's own API key. `case_mapper.map_case` checks every field and raises `SchemaDrift` on an unexpected shape (beta API, compact filing dates, codes number-or-string).[^dj] |
| **DJEN** | Publications | `adapters/djen/` | Keyless `comunicacao` search; `publication_mapper` maps items; shipped `issuing_bodies.json` ([ADR 0007](/decisions/adrs.md#adr-0007)).[^djen] |
| **Senado** | Norm metadata | `adapters/senado/` | `legislacao/lista` to search, `urn` to fetch; no free-text.[^sen] |
| **Planalto** | Norm text | `adapters/planalto/` | Static pages with no URN index; `candidate_paths` lists likely paths by convention, most likely first.[^plan] |
| **Câmara Legin** | Norm text fallback | `adapters/legin/` | LexML URN page → Legin data sheet → text page; `ChallengePage` detects the portal's proof-of-work challenge, which is **not** circumvented; `is_gateway_error` spots a proxy 504 served as 200.[^leg] |

`adapters/legislation/norm_text_parser.py` parses both Planalto and Legin HTML into plain text with articles located (UTF-8 else Windows-1252; struck-through lines flagged; `SchemaDrift` when no articles).

# Constraints

No browser automation or portal scraping: challenges are not circumvented, and a browser User-Agent is not spoofed (ADR 0002).[^adr2] DataJud terms allow only non-commercial use, so each user self-hosts. Failures map to [Error codes](/domain/errors.md).

# Presenters

`case_presenter`, `publication_presenter` and `legislation_presenter` turn use-case results into Normalized results; `presentation.iso_utc` formats UTC timestamps with a `Z`.

[^dj]: DatajudCaseRepository
[^djen]: DjenPublicationRepository
[^sen]: SenadoLegislationRepository
[^plan]: planalto_paths.py
[^leg]: LeginNormTextSource
[^adr2]: ADR 0002
