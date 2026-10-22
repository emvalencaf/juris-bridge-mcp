---
type: MCP Tool
title: "get_publication"
description: "Read the full plain text of one Publication in cursor-chained slices."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/adapters/publications/publications_mcp_tools.py
tags: [tool, publications, djen]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: uc
    resource: juris_bridge_mcp/application/use_cases/get_publication.py
    title: get_publication.py
  - id: dom
    resource: juris_bridge_mcp/domain/publication.py
    title: publication.py
---

# Overview

The DJEN has no read-by-id endpoint, so a Publication is addressed by an opaque id that encodes **Court, day, CNJ number and item hash** (`PublicationRef`).[^dom] The id comes from [search_publications](/tools/search-publications.md). The use case re-fetches that item and returns one slice of its full plain text, cut at a space and chained by a [Cursor](/domain/cursor.md).[^uc]

Plain text is produced by `plain_text`, which strips the markup and collapses whitespace.

[^uc]: get_publication.py
[^dom]: publication.py
