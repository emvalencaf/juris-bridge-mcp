---
type: Domain Model
title: "CNJ number, Courts and Coverage"
description: "Parsing and validating the CNJ number, deriving a Court alias, and the Coverage types."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/domain/cnj_number.py
tags: [domain, cases, courts]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: cnj
    resource: juris_bridge_mcp/domain/cnj_number.py
    title: cnj_number.py
  - id: ct
    resource: juris_bridge_mcp/domain/courts.py
    title: courts.py
  - id: cov
    resource: juris_bridge_mcp/domain/coverage.py
    title: coverage.py
  - id: pc
    resource: juris_bridge_mcp/domain/publication_courts.py
    title: publication_courts.py
---

# CnjNumber

`CnjNumber.parse` accepts the formatted or 20-digit form and rejects a wrong length or a wrong mod-97 check digit with `invalid_argument`.[^cnj] Properties: `formatted`, `segment` (`J`), `tribunal` (`TR`). `derive_court` maps `J.TR` to an alias; `J=1` (STF) raises `not_covered`.

# Courts

`COURT_BY_SEGMENT` follows CNJ Res. 65/2008: `stm`, `trf1–6`, `trt1–24`, `tre-<uf>`, `tj<uf>` (`tjdft` for DF) and three military TJMs. `tst`, `tse` and `stj` are reachable **by alias only**, since their numbers hold origin cases. `resolve_court` canonicalises (e.g. `tre-dft` → `tre-df`, because DataJud's index is `api_publica_tre-df`) and rejects unknown aliases listing valid ones.[^ct]

# Publication Courts

`resolve_djen_court(alias, date_to)` accepts only Courts publishing in the DJEN on or before `date_to`; per-Court start dates drive `available_from`.[^pc]

# Coverage

`SourceCoverage` (source, kind, description, courts) and `CourtCoverage` (alias, supported, citation_url, available_from, reason) with `to_dict`.[^cov] Served by [list_coverage](/tools/list-coverage.md).

[^cnj]: cnj_number.py
[^ct]: courts.py
[^cov]: coverage.py
[^pc]: publication_courts.py
