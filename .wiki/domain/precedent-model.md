---
type: Domain Model
title: "Precedent model, kinds and body table"
description: "Precedent types, the Precedent kind list, the id format and the BNP body to Court alias table."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/domain/precedent.py
tags: [domain, precedents, bnp]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: p
    resource: juris_bridge_mcp/domain/precedent.py
    title: precedent.py
  - id: b
    resource: juris_bridge_mcp/domain/precedent_bodies.py
    title: precedent_bodies.py
  - id: g
    resource: GLOSSARY.md
    title: GLOSSARY.md
---

# Model

A `Precedent` is a record that fixes a thesis (see Precedent in the glossary): `id`, `body` (BNP sigla), `court` (alias or `None`), `kind`, `number` (always text), `question`, `thesis`, the literal `status`, `status_history`, `leading_cases`, `suspensions`, `updated_on` and `matched_terms`.[^p] It is distinct from a [Publication](/domain/publication-model.md) (the text of one ruling) and from a Case.

* `LeadingCase.from_raw` links a CNJ number only when the 20 digits validate (check digit included); otherwise only `raw_number` is kept.
* `PrecedentFilters.key()` fingerprints a search so a [Cursor](/domain/cursor.md) can tell the filters changed. `PrecedentPage.total_is_capped` is true when the total reaches `COUNT_CAP` (10,000).
* `public_url` builds the BNP app link `/pesquisa?orgao=&tipo=&nr=` used as the Citation.

# Kinds

`KINDS` lists the BNP siglas: SUM, SV, OJ, IAC, IRDR, SIRDR, PN, IRR, RR, RG, ADI, ADC, ADO, ADPF, PUIL, CT, NT, NTA, ENU, RC. `resolve_kind` refuses others with the list as a hint; a new BNP kind is added there. `parse_id` accepts only `<body>-<kind>-<number>` in lowercase.[^p]

# Bodies

`precedent_bodies` maps each BNP sigla to a Court alias and back (`TRF01` ↔ `trf1`, `TRT04` ↔ `trt4`, `TRE_AC` ↔ `tre-ac`, `TJDF` ↔ `tjdft`). `stf` is a Court here though DataJud does not publish it. The TNU is in `BODIES_WITHOUT_ALIAS`: it appears with a null `court`.[^b] `resolve_precedent_court` raises `invalid_argument` for anything else.

[^p]: precedent.py
[^b]: precedent_bodies.py
