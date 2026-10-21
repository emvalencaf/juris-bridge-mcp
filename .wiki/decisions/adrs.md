---
type: Decision Summary
title: "Architecture decisions (ADR 0001–0007)"
description: "One-paragraph digest of each ADR in docs/adr/ and how they shape the code."
tags: [decisions, adr]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: adr1
    resource: docs/adr/0001-vertical-slices-on-fastmcp.md
    title: ADR 0001
  - id: adr2
    resource: docs/adr/0002-self-hosted-datajud-no-browser-sources.md
    title: ADR 0002
  - id: adr3
    resource: docs/adr/0003-stateless-lambda-reference-deployment.md
    title: ADR 0003
  - id: adr4
    resource: docs/adr/0004-wide-event-logging-to-stdout.md
    title: ADR 0004
  - id: adr5
    resource: docs/adr/0005-layers-at-the-top.md
    title: ADR 0005
  - id: adr6
    resource: docs/adr/0006-djen-publications-self-hosted.md
    title: ADR 0006
  - id: adr7
    resource: docs/adr/0007-issuing-body-catalog-from-a-maintainer-script.md
    title: ADR 0007
---

# ADR 0001 — vertical slices (superseded)
Per-concept `modules/<concept>/` folders; superseded by 0005.[^adr1] Kept lesson: tools are mounted without a namespace, so names are unique.

# ADR 0002 — self-hosted DataJud, no browser sources
DataJud terms (3.3, 3.8) allow non-commercial use only and forbid redistribution, so no public instance; each user self-hosts with their own key. Playwright and challenge circumvention are excluded.[^adr2] See [Sources](/adapters/sources.md).

# ADR 0003 — stateless Lambda reference deployment
Lambda container image with Lambda Web Adapter behind a Function URL, Terraform under `deploy/aws/`. FastMCP stateless with JSON responses; Bearer auth in-app; portability boundary is "the container plus environment variables".[^adr3] See [request pipeline](/architecture/request-pipeline.md).

# ADR 0004 — wide event logging
One JSON line per request on stdout; no content logged.[^adr4] See [wide event](/adapters/wide-event.md).

# ADR 0005 — layers at the top
Replaces 0001: `domain/`, `ports/`, `application/`, `adapters/`, `infrastructure/` directly under the package.[^adr5] See [architecture](/architecture/overview.md).

# ADR 0006 — DJEN as Source of Publications
Self-hosted per user like 0002; fans out over court/day/orgaoId, classifies kinds locally, states non-exhaustive results; STF and TREs `not_covered`.[^adr6] See [search_publications](/tools/search-publications.md).

# ADR 0007
The DJEN lists no Issuing bodies of a Court, so a catalog (`orgaoId`, name) ships as `adapters/djen/issuing_bodies.json` with a `version` and `generated_on`, built by hand with `scripts/build_issuing_body_catalog.py`. A day at the 10,000 cap is split by every catalog body plus any seen on page 1 that the catalog lacks. The Cursor carries the catalog index and `version`; a different version is `invalid_argument`. `slice_cap` is reported only when a body slice itself caps or page 1 shows a missing body. Residual gap: a body missing from both is undetectable.[^adr7]

[^adr1]: ADR 0001
[^adr2]: ADR 0002
[^adr3]: ADR 0003
[^adr4]: ADR 0004
[^adr5]: ADR 0005
[^adr6]: ADR 0006
[^adr7]: ADR 0007
