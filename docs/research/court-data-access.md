# Research: STF, STJ, TRF and TJ public data access

Issue: emvalencaf/juris-bridge-mcp#4 (part of map #1). Researched 2026-10-17.
Question: for STF, STJ, the TRFs and state TJs, is there an official API, open
data, or only portal scraping? What about terms of use, captchas, robots and
stability? Output: a feasibility ranking to decide the post-MVP adapter order.

Method: primary sources only (the courts' and CNJ's own pages, robots.txt files
and the STJ CKAN API). Every claim cites its source. Claims that could not be
verified from a primary source are listed under "Not verified" and must not be
treated as findings.

## Summary

| Court group | Official machine access | Verdict |
|---|---|---|
| STJ | DataJud API alias `api_publica_stj` plus a CKAN open-data portal (21 datasets, incl. judgment summaries) | Best; build first after the MVP |
| TRF1 to TRF6 | DataJud API aliases, one per TRF | Good for process metadata; no case-law text |
| State TJs (27 aliases) | DataJud API aliases, one per TJ | Good for process metadata; no case-law text |
| STF | No DataJud alias; portal blocked automated fetches (HTTP 403) | Hardest; defer |

DataJud is already in the MVP, so STJ, TRF and TJ process metadata come almost
for free by adding court aliases to the existing DataJud adapter. The new work
is the *content* sources (case-law text), which are the part DataJud does not
cover.

## 1. DataJud public API (covers STJ, TRFs, TJs)

- The API exposes process metadata ("metadados") of "all instances" of the
  Brazilian Judiciary: case headers (capas) and movements. It follows CNJ
  Portaria 160 of 2020 and withholds confidential cases and party data.
  Source: https://datajud-wiki.cnj.jus.br/api-publica/
- Base URL `https://api-publica.datajud.cnj.jus.br/` plus one alias per court,
  POST `/{alias}/_search` with an Elasticsearch-style query DSL. Aliases listed
  include `api_publica_stj`, `api_publica_trf1` to `api_publica_trf6`, and one
  per state TJ (`api_publica_tjsp`, `api_publica_tjmg`, and so on, 27 in total
  including `tjdft`). The list also has TST, TSE, STM, TRTs, TREs and the
  military TJs. There is **no STF alias**.
  Source: https://datajud-wiki.cnj.jus.br/api-publica/endpoints
- Auth: header `Authorization: APIKey <public key>`. The key is public, published
  on the wiki, and "may be changed by CNJ at any time".
  Source: https://datajud-wiki.cnj.jus.br/api-publica/acesso
  The same key is repeated in the STJ open-data entry
  (https://dadosabertos.web.stj.jus.br/api/3/action/package_show?id=api-publica-datajud),
  so it must stay environment config, not code (consistent with the map).
- Paging uses `search_after` (wiki example 3). A sample response shows
  `"took": 6679` ms, so latency can be several seconds.
  Source: https://datajud-wiki.cnj.jus.br/api-publica/exemplos/exemplo1
- Terms of use (V1.2). Highlights from the wiki summary:
  - 3.3: for "lawful, non-commercial and authorized" purposes only; abusive use
    is prohibited.
  - 3.6: CNJ does not guarantee accuracy, completeness or freshness.
  - 3.8: the user agrees not to modify, distribute, sell or commercially exploit
    the API or information derived from it.
  - 3.9: the user agrees to tell CNJ about any study or report made public.
  - Use of the API is tacit acceptance of the terms.
  Source: https://datajud-wiki.cnj.jus.br/api-publica/termo-uso
  (full PDF `Termos-de-uso-api-publica-V1.2.pdf` linked there; not read in full)
- Implication for the project: the non-commercial and no-redistribution clauses
  conflict with a hosted public service. This affects the MVP too and should be
  decided in the responsible-use note (see "Open questions").

## 2. STJ

- CKAN open-data portal at https://dadosabertos.web.stj.jus.br/. Its
  `package_list` API (https://dadosabertos.web.stj.jus.br/api/3/action/package_list)
  returned 21 datasets, including: `espelhos-de-acordaos-*` (judgment summaries,
  one dataset each for the Corte Especial, three Seções and six Turmas),
  `integras-de-decisoes-terminativas-e-acordaos-do-diario-da-justica` (full
  texts of decisions and judgments from the Diário da Justiça),
  `precedentes-qualificados`, `acervo-em-tramitacao`, `pautas-futuras`,
  `atas-de-distribuicao` and `api-publica-datajud`.
- The portal itself says the data is in "open format" and machine-readable, with
  CKAN 2.9 as the API.
  Source: https://dadosabertos.web.stj.jus.br/
- The `api-publica-datajud` entry has an empty `license_id` and `isopen: false`
  in the CKAN metadata, so no explicit licence is stated there.
  Source: the package_show URL above. Licences of the other datasets were not
  read (requests timed out).
- Launch notice: first of five release stages, May 2022, starting with judgment
  summaries; no licence named, only the CNJ definition of open data (free use
  with attribution).
  Source: https://www.stj.jus.br/sites/portalp/Paginas/Comunicacao/Noticias/20052022-Novo-Portal-de-Dados-Abertos-amplia-transparencia-de-acoes-realizadas-no-STJ.aspx
- Case-law search UI (SCON) is under robots.txt `Disallow: /SCON/` on
  `www.stj.jus.br`, and `scon.stj.jus.br/robots.txt` returned a WAF
  "Request Rejected" page to a scripted request.
  Sources: https://www.stj.jus.br/robots.txt ; https://scon.stj.jus.br/robots.txt
  So scraping SCON is both disallowed and actively blocked; the CKAN datasets
  are the supported route for case-law content.

## 3. TRFs

- Process metadata: DataJud aliases `trf1` to `trf6` (section 1).
- Portals differ per court; no common case-law API was found in primary sources.
- robots.txt:
  - TRF1 (`www.trf1.jus.br`): `User-agent: *` / `Disallow: /`, only named search
    engines are allowed. Automated access is disallowed.
    Source: https://www.trf1.jus.br/robots.txt
  - TRF4 (`www.trf4.jus.br`): disallows `/trf4/processos/` and some specific
    pages; most of the site is allowed.
    Source: https://www.trf4.jus.br/robots.txt
  - JFRJ (`www.jfrj.jus.br`, TRF2 area): `/robots.txt` returned the HTML home
    page, i.e. no robots.txt; the page loads a Cloudflare challenge script
    (`challenges.cloudflare.com`), suggesting bot challenges.
    Source: https://www.jfrj.jus.br/robots.txt
  - TRF3 robots.txt: request timed out (not verified).

## 4. State TJs

- Process metadata: 27 DataJud aliases (section 1).
- Portal example: TJSP e-SAJ first-instance consultation
  (https://esaj.tjsp.jus.br/cpopg/open.do) is a form-driven portal (search by
  number, party name, document, lawyer); it has no robots.txt (404:
  https://esaj.tjsp.jus.br/robots.txt). No official API was found on it.
- TJMG `www.tjmg.jus.br/robots.txt` disallows only a handful of specific paths.
  Source: https://www.tjmg.jus.br/robots.txt
- Terms of use and captcha policy of each TJ portal were **not verified**
  (see below). TJs run different stacks (e-SAJ, PJe, Projudi, others), so each
  would be a separate scraping adapter.

## 5. STF

- Not in the DataJud alias list (section 1), although CNJ Resolution 331/2020
  names the STF among the courts in the DataJud base. The API simply does not
  expose an STF endpoint. Sources: endpoints page above;
  https://www.cnj.jus.br/sistemas/datajud/sobre/ (not directly fetchable: 403).
- `portal.stf.jus.br/robots.txt`, `transparencia.stf.jus.br` and the Corte Aberta
  hotsite all returned HTTP 403 to scripted requests, so automated access to
  the main STF portal is actively blocked at the edge.
- STF "Corte Aberta" launched 2022-05-11 with data since 2000, downloadable as
  CSV, formalised by STF Resolution 774/2022 (CGD-STF). This comes from a news
  report, not from STF itself, so treat it as a lead only:
  https://www.conjur.com.br/?p=358627 (could not be fetched; known from a
  search snippet).

## 6. National interoperability (context)

CNJ's PDPJ (Resolution 355/2020) and the MNI standard exist for system-to-system
integration. This is for authorised judicial systems and lawyers, not for public
anonymous consumption, and no public-use API was confirmed. Status of MNI 3.0
REST endpoints was reported only as "in homologation" in a 2022 CNJ
presentation. Not a candidate for this project. Source for existence:
https://atos.cnj.jus.br/files/original18182920220503627171f515114.pdf (search
result only; not read).

## Feasibility ranking (post-MVP order)

1. **DataJud aliases for STJ, TRFs, TJs.** Same adapter and key as the MVP; only
   configuration per court. Metadata only. Gate on the terms-of-use question.
2. **STJ open-data CKAN** (judgment summaries, full decisions, precedents). An
   official, documented, machine-readable API; bulk files rather than live
   queries, so it needs ingestion or on-demand file fetch. Licence per dataset
   still to confirm.
3. **State TJ and TRF portals** (case-law text, richer case detail). No official
   API found, robots/captcha/WAF vary by court (TRF1 forbids all bots). One
   adapter per stack and court; high maintenance, legal risk. Do only if a
   concrete need appears, starting with courts whose robots.txt permits access.
4. **STF.** No DataJud endpoint, portal returns 403 to scripts, only a possible
   CSV open-data lead. Defer until an official dataset or API is confirmed.

## Not verified (needs a follow-up with browser access)

- Whether TJ and TRF portals require captcha for public consultation, and their
  per-court terms of use. Could not be tested without a browser or breaking the
  rules we are researching.
- STF Corte Aberta dataset formats, licence and any API (portal returns 403).
- DataJud rate limits and quotas: none were stated in the pages read; the wiki
  "Considerações Finais" page was not found at the URL tried.
- Per-dataset licences on the STJ CKAN portal (requests timed out).
- Full text of DataJud Termos de Uso V1.2 (PDF not read).
- Data coverage and freshness per court inside DataJud (CNJ gives no guarantee,
  clause 3.6).

## Open questions for the map

- Do the DataJud non-commercial and no-redistribution clauses (3.3, 3.8) allow a
  remote server used by third parties? Ask CNJ or document the position in the
  responsible-use note before launch.
- Is ingesting STJ CKAN files (cached, TTL) acceptable given the in-memory-cache
  decision, or does it need an ADR?
