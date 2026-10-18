# Research: STF Corte Aberta as a source of STF decisions

Issue: emvalencaf/juris-bridge-mcp#61 (part of map #53). Researched 2026-10-18.
Starting point: `docs/research/court-data-access.md` section 5 (it lives on
branch `docs/research-and-glossary`, not on this branch's base).
Question: is the STF "Corte Aberta" data (launched 2022-05-11, STF Resolution
774/2022) a usable source of STF decisions and acordaos for Publications?

Method: STF pages read with plain read-only requests and an honest user agent
(`juris-bridge-mcp-research`), no browser automation, no header spoofing.
Each fact is tagged **[documented]** (stated by an STF page) or **[observed]**
(seen in a response during this research, 2026-10-18).

## Verdict

**Not usable as a source of decisions or acordaos.** Corte Aberta publishes
statistics (counts, dashboards), not decision texts, ementas or per-document
records, as far as any STF page I could read says. No dataset catalogue, API,
licence or update schedule was found. The STF case-law search
(`jurisprudencia.stf.jus.br`) sits behind an AWS WAF challenge, so there is no
confirmed official, scriptable path to STF decision text. Defer STF in the
adapter order, as the earlier note already recommended.

## What is published

- Program created by STF Resolution 774/2022 (dated 2022-05-09), published in
  DJe 2022-05-10 (`DJE_20220510_090.pdf`). [documented, linked from the hotsite]
  Source: https://portal.stf.jus.br/hotsites/corteaberta/
- The hotsite describes statistical dashboards ("paineis estatisticos"): cases
  in progress, decisions issued, Repercussao Geral themes, appeal success rates,
  Covid-19 actions "and several others". It lists **no downloadable dataset,
  no file format and no licence**. The only data link is "Ver todos os
  paineis" to
  https://transparencia.stf.jus.br/extensions/corte_aberta/corte_aberta.html.
  [documented]
- The hotsite's axis II states an *aim* of free export of "dados brutos ou
  semiestruturados"; the page does not say this exists today. [documented]
- STF launch press release (2022-05-11): the program offers cases in progress,
  Plenario Virtual judgments, the *number* of decisions issued and the history
  of Repercussao Geral themes; data "since the year 2000" (before: since 2010);
  users can download data as `.csv`; interactive panels with filters by party
  and processing time. Update frequency is not stated. [documented]
  Source: https://noticias.stf.jus.br/postsnoticias/stf-lanca-programa-corte-aberta-com-ampla-base-de-dados-e-maior-transparencia-aos-cidadaos/
  This confirms the earlier Conjur-based lead from a first-party source:
  2000 start, CSV download. The CSV is a panel export; its columns are unknown.
- The "Transparencia e Prestacao de Contas" page lists Corte Aberta panels, the
  Ouvidoria panels (data since 2021-01), internal normative acts and contracts.
  It has no "dados abertos" section, no API documentation and no decisions
  download. [documented]
  Source: https://portal.stf.jus.br/transparencia/

## Resolution 774/2022

- Art. 1 creates the Corte Aberta program for judicial data governance; art. 2
  requires compliance with the access-to-information law, Marco Civil and LGPD;
  art. 5 organises four axes, one on data availability that calls for raw or
  semi-structured, machine-readable export "where possible"; art. 8 creates the
  CGD-STF governance committee. [documented, but read only through a search
  result summary and a secondary article, jus.com.br/artigos/98001; see "Not
  read"]
- It is a governance resolution. Nothing I could read says it obliges STF to
  publish decision texts as open data, and it names no licence.

## Reachability (ADR 0002)

| URL | Result 2026-10-18 | Basis |
|---|---|---|
| `portal.stf.jus.br/robots.txt` | HTTP 200: `User-agent: *` `Disallow: /processos`; AhrefsBot `Disallow: /` | [observed] |
| `portal.stf.jus.br/hotsites/corteaberta/` | HTTP 200, readable | [observed] |
| `portal.stf.jus.br/transparencia/` | readable | [observed] |
| `transparencia.stf.jus.br/extensions/corte_aberta/corte_aberta.html` (panels) | HTTP 403 to curl and to the fetch tool | [observed] |
| `jurisprudencia.stf.jus.br/pages/search` and `/robots.txt` | HTTP 202, empty body, header `x-amzn-waf-action: challenge` | [observed] |
| `www.stf.jus.br/arquivo/norma/resolucao774-2022.pdf` | returns an HTML 404 page, not the PDF | [observed] |

Findings:
- The earlier note recorded a 403 for `portal.stf.jus.br/robots.txt`; with an
  honest user agent it returned 200 today. The block is not uniform.
- The panels host (`transparencia.stf.jus.br`) is blocked to scripts, so the CSV
  exports cannot be reached without a browser, and using one to get past the
  block is the circumvention ADR 0002 rules out. Recorded as blocked; not
  worked around.
- The case-law search is a WAF challenge (needs JavaScript execution), the same
  situation as STJ SCON. Not attempted further.
- `Disallow: /processos` on the portal covers case-detail pages, so process
  scraping is also disallowed.

## Other official STF paths

- **DataJud**: no STF alias (see `court-data-access.md` sections 1 and 5); not
  rechecked here.
- **dados.gov.br** (federal open-data portal): a web search for an STF dataset
  found nothing, and the portal is a JavaScript app whose listing I could not
  read with plain requests. Inconclusive, not evidence of absence.
- **STF case-law search** (`jurisprudencia.stf.jus.br`): the official place for
  acordaos, but WAF-challenged; no documented API found.
- **DJe** PDFs at `www.stf.jus.br/arquivo/djEletronico/` are plain files (the
  2022-05-10 issue downloaded fine). Whether this is a stable, permitted bulk
  route for STF decisions was not investigated; it is a PDF gazette, not
  structured data. A candidate for follow-up, not a finding.
- Secondary evidence (search results, not first-party): academic work built STF
  corpora by scraping, and a 2013 commentary says STF does not publish every
  collegiate decision. Context only.

## Not read / could not verify

- Full text of Resolution 774/2022: the DJe PDF downloaded, but its text is
  compressed and no PDF tool was available here; the standalone PDF URL is a
  404. Article statements above come from a search summary and jus.com.br.
- The Corte Aberta panels, their CSV columns, any ementa or process-number
  fields, update frequency and terms of use (host returns 403).
- Any licence for STF data: none stated on any page read.
- dados.gov.br listing for the STF organisation.
- Whether STF offers any API or bulk export for case law (nothing found, not
  proven absent).

## Recommendation for the map

Treat Corte Aberta as statistics, not as a Publications source. Keep STF last
in the adapter order. Reopen only if STF publishes a documented dataset or API
for decisions, or if the project owner approves a manual, human-obtained export
that is then ingested as a file.
