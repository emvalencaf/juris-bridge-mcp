# Research: Playwright access to LexML and alternative legislation sources (issue #9)

Part of #1. Researched and probed live on 2026-10-17 from a WSL2 host (Brazil-reachable
network, not AWS `sa-east-1`). Primary sources only (official sites, official OpenAPI
documents, live responses). Statements marked "observed" come from my own requests; where I
could not verify something it is listed under "Not verified".

## Summary

1. **The SRU endpoint is not usable, with or without Playwright.** `/busca/SRU` (and `/sru`,
   `/busca/sru`, `/SRU`) answer `HTTP 404` from the origin (Apache Tomcat/9.0.111) once the
   anti-bot challenge is passed. The anti-bot page was masking a missing endpoint. The earlier
   LexML finding (#3) that the SRU is "behind an interstitial" needs correcting: it is behind
   an interstitial and, after it, gone.
2. **The LexML HTML portal still works**: `/busca/search?keyword=...` (search) and
   `/urn/<LexML URN>` (resolver / document page). A headless browser passes the challenge in
   under one second (observed 0.1-0.8 s per navigation). Plain HTTP clients receive the
   challenge only on uncached requests; cache hits are served normally. That makes LexML via
   HTTP flaky and via Playwright heavy, and the output is scraped HTML, not a contract.
3. **Better primary source for legislation: the Senado Federal "Dados Abertos Legislativos"
   API** (`https://legis.senado.leg.br/dadosabertos/legislacao/...`). Public, no
   authentication, JSON/XML/CSV, OpenAPI document published, documented rate limit,
   LexML-URN lookup supported. Gives metadata, publications and amendment relations of federal
   norms. It does not return the norm full text; text comes from `normas.leg.br`,
   the Câmara "Legin" static pages or Planalto static pages.
4. **Recommended Source design**: Senado API for discovery/metadata + LexML URN as the
   canonical identifier + Planalto/Câmara-Legin static HTML for text. LexML via Playwright is a
   last-resort fallback only.

## Sources

### A. LexML portal (www.lexml.gov.br)

| Item | Finding | Evidence |
|---|---|---|
| SRU endpoint | Dead. `GET https://www.lexml.gov.br/busca/SRU?operation=searchRetrieve...` returns the challenge page, then (in a browser) `404 Not Found`, body "The requested resource [/busca/SRU] is not available", server banner `Apache Tomcat/9.0.111`. Same for `/sru`, `/SRU`, `/busca/sru`. | observed with Playwright 2026-10-17 |
| robots.txt | `Disallow: /busca/`, `Disallow: /doc/`, `Disallow: /linker/`; `Allow: /urn`, `Allow: /sru`; `Crawl-delay: 5`; `Python-Requests` user agent is `Disallow: /` (with `Allow: /urn`, `/sru`); `OAI-SearchBot` crawl-delay 10. So `/busca/search` (the search UI) is disallowed to generic crawlers, `/urn/` is allowed. | <https://www.lexml.gov.br/robots.txt> |
| Anti-bot | "Verificação de segurança - Senado Federal": a page with a JS proof-of-work (SHA-256 via `crypto.subtle.digest`) that POSTs to `/_challenge`. HTML says "JavaScript is required". Returns HTTP 200 with a 9,050-byte HTML body, so it looks like success to naive clients. | observed (curl and Playwright); page source |
| When the challenge appears | Observed only on cache misses: `/busca/search?keyword=lei+14133` and several `/urn/...` pages returned real content to plain `curl` (response header `Age: 112..3227`, i.e. served from cache), while a never-seen query (`keyword=zzqx+23180`, `Age: 0`) and the SRU URLs returned the challenge. The same behaviour for different user agents (`curl`, `Mozilla/5.0`, `python-requests`). | observed 2026-10-17; cache-based explanation is an inference from `Age` |
| Search UI | `GET /busca/search?keyword=<text>` returns HTML (about 83 KB): facets (Doutrina, Jurisprudência, Legislação, Proposições Legislativas), counts, 20 hits per page via `startDoc=21,41,...`, filters via `f1-tipoDocumento=Legislação`. Query "lei 14133" gave 296 items (151 Legislação). | observed |
| URN resolver | `GET /urn/urn:lex:br:federal:lei:2021-04-01;14133` returns an HTML document page: title, ementa, "Nome Uniforme", publications, links to full text at `legis.senado.leg.br/norma/<id>`, `www2.camara.gov.br/legin/...`, Planalto and DOU. A non-existent URN returns HTTP 200 with title "Resolver de URN :: urn não encontrada" (error is in the body, not the status). Codes with large text (Código Civil 1.1 MB, CDC 386 KB) are served. | observed |
| Documented spec | Senado open-data page lists the SRU webservice, but its sub-pages are bare redirects (see #3). The URN grammar is specified in "Parte 2 - LexML URN". | #3 findings |
| Terms of use / license | Not found on any reachable LexML page. | see Not verified |

### B. Senado Federal open data: legislation API (legis.senado.leg.br/dadosabertos)

Primary source: the live OpenAPI document `https://legis.senado.leg.br/dadosabertos/v3/api-docs`
(title "Dados Abertos Legislativos do Senado Federal e Congresso Nacional", version
4.1.3.101) and Swagger UI at `https://legis.senado.leg.br/dadosabertos/docs/`.

- Access: "API de acesso público, sem necessidade de autenticação" (API description).
- Formats: `application/json`, `application/xml`, `text/csv`; choose with `Accept` header
  or `.json`/`.xml`/`.csv` suffix (API description).
- Rate limit (from the API description): more than 10 requests per second may get HTTP 429;
  HTTP 503 under heavy load; avoid bursts at round-hour timestamps. Deprecated services
  return `Deprecation`, `Sunset` and `Link: rel="successor"` headers, and several services
  are being retired during a data-model rewrite ("diversos serviços estão em processo de
  descontinuação"); the `legislacao` endpoints are not marked deprecated in the spec.
- CORS is open (`access-control-allow-origin: *`), responses carry nginx and CSP headers.
- Legislation endpoints in the spec (all `GET`):
  - `/dadosabertos/legislacao/lista` - "Pesquisa de Normas Federais"; parameters `tipo`
    (type sigla), `numero`, `ano`, `data` (AAAAMMDD), `seq`, `reedicao`, `ident`,
    `complemento`, `v`. There is no free-text/keyword parameter.
  - `/dadosabertos/legislacao/urn` - norm detail by LexML URN (`urn` parameter, example
    `urn:lex:br:federal:lei:2021-04-01;14133`).
  - `/dadosabertos/legislacao/{codigo}` and `/dadosabertos/legislacao/{tipo}/{numdata}/{anoseq}`
    - detail by internal code or by identification.
  - `/dadosabertos/legislacao/termos` - subject-term catalogue; `/classes`, `/tiposNorma`,
    `/tiposPublicacao`, `/tiposVide` - vocabularies.
- Observed: `GET .../legislacao/lista.json?tipo=LEI&ano=2021&numero=14133` returned id
  `33382036`, norm name, ementa, signature date, nickname. `GET .../legislacao/urn.json?urn=
  urn:lex:br:federal:lei:2021-04-01;14133` returned `DetalheDocumento` with `identificacao`
  (including `urlDocumento` = `https://normas.leg.br/?urn=...`), `publicacoes` (DOU
  edition/page, `temTexto`), `vides` (relations to amending/revoking norms, about 50 KB for
  this law), `edivs`, `disps` (per-article annotations), `ementa`, `catalogo`, `indexacao`,
  `classes`. HTTP 200 in about 1 s. Wrong query parameters (year 2023 with a 2021 number)
  return 200 with `"documentos": ""` (empty, not an error).
- The response gives no article text. The text is on `https://normas.leg.br/?urn=...`
  (Angular SPA, `robots.txt`: `Allow: /`; the page is a JS shell, so it needs a browser or a
  discovered back-end API, which I did not find) and `legis.senado.leg.br/norma/<id>`.
- Terms/license: the Senado open-data hub says open data are "disponibilizados sob licença
  que permita sua livre utilização"
  (<https://www12.senado.leg.br/dados-abertos>). The OpenAPI `info` object has no `license`
  or `termsOfService` field. The portal usage policy
  (<https://www12.senado.leg.br/institucional/documentos/politica-de-uso-do-portal-do-senado-federal>)
  was reached but I did not extract a clause about automated access.

### C. Câmara dos Deputados

- Open data API: `https://dadosabertos.camara.leg.br/api/v2/...`, documentation at
  `https://dadosabertos.camara.leg.br/swagger/api.html`. Public, no key needed (observed:
  `GET /api/v2/proposicoes?itens=1` returned JSON with HTTP 200 and no credentials).
- Scope is the legislative process: `proposicoes` (bills; `siglaTipo`, `numero`, `ano`,
  `ementa`, `dataApresentacao`), deputies, votes, committees. Querying
  `proposicoes?siglaTipo=LEI` returns an empty list: enacted laws are not modeled there. So it
  can answer "what bills exist/what is their status", not "what does Lei X say".
- Principle statement on the portal: data "livres de licenças" - not subject to copyright,
  trademarks, patents (<https://dadosabertos.camara.leg.br/howtouse/sobre-dados-abertos.html>).
  This is a statement of open-data principles; I did not find a per-dataset license or
  rate-limit clause.
- Legin (static norm text): `https://www2.camara.leg.br/legin/fed/lei/2021/lei-14133-1-abril-2021-791222-norma-pl.html`
  is a stable-looking, static HTML page of the consolidated norm text (HTTP 200, 62 KB, the
  old `www2.camara.gov.br` host redirects to `www2.camara.leg.br`). The LexML URN page links
  to it. The URL contains an internal numeric id, so it can not be derived from the URN
  alone; resolve it through the LexML URN page or the Senado `urn` response. Camara site
  `robots.txt` only disallows form/admin paths, not `/legin/`.

### D. Planalto (www.planalto.gov.br/ccivil_03)

- No API or open-data service. Norms are static HTML (FrontPage-era markup) at predictable
  paths, e.g. `https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm` (CDC, HTTP 200,
  171 KB) and `https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/L15100.htm` (HTTP
  200). Reliable to fetch (observed with plain `curl`, no challenge), but: the URL pattern
  varies by era (`leis/`, `_ato2019-2022/...`), "compilado" versions are separate pages,
  and the markup is irregular, so extraction is scraping.
- `https://www.planalto.gov.br/robots.txt` returns 404 (no robots policy published).
- No machine-readable terms of use found; the content is official legal text.

### E. Other

- Bulk/dump: the Senado hub has a LexML "Dados Abertos" group URL
  (`dadosabertos.senado.gov.br/group/lexml`), which now redirects to the generic
  `www12.senado.leg.br/dados-abertos` page; I found no downloadable LexML dump. LexML's
  data-provider kit uses OAI-PMH (#3), but I found no public OAI-PMH endpoint to harvest from.
- DOU (Imprensa Nacional) is linked from LexML (`pesquisa.in.gov.br`); I did not evaluate it.

## Comparison

| | LexML via SRU | LexML HTML via Playwright | LexML HTML via plain HTTP | Senado `dadosabertos/legislacao` | Câmara open data API | Câmara Legin static | Planalto static |
|---|---|---|---|---|---|---|---|
| Works today | No (404) | Yes, observed | Only on cache hits | Yes, observed | Yes (bills only) | Yes | Yes |
| Search by text | n/a | Yes (relevance, facets, 20/page) | Same, but blocked on misses | No free text; filter by type/number/year/date; term catalogue | Bills only (keywords/ementa filters) | No | No |
| Lookup by LexML URN | n/a | Yes (`/urn/`) | Cache-dependent | Yes (`/legislacao/urn`) | No | Not directly | No |
| Full text | n/a | HTML page with text | same | No (metadata, vides, per-article annotations) | No | Yes | Yes |
| Structured output | would be XML | No (scraped HTML) | No | JSON/XML/CSV + XSD + OpenAPI | JSON + OpenAPI | No (HTML) | No (HTML) |
| Auth | none | none | none | none | none | none | none |
| Published rate limit | none found; robots `Crawl-delay: 5` | same; `/busca/` disallowed to generic bots | same | 10 req/s (429 above), 503 under load | none found | none found | none found |
| ToS / license | not found | not found; robots disallows `/busca/` and the challenge is a deliberate anti-automation control | same | "livre utilização" (hub) | "livres de licenças" principle | not found | not found |
| Stability signal | endpoint removed | challenge may change at any time | same | versioned (`v=3`, API 4.1.3.101); some other services deprecating | versioned `api/v2` | stable-looking URLs | very stable URLs, irregular markup |
| Runtime cost | n/a | see below | negligible | negligible | negligible | negligible | negligible |

### Playwright cost (question 1)

Measured: the challenge is solved automatically in a real Chromium in about 0.1-0.8 s
(page navigations of 125-790 ms observed, including the proof-of-work); no cookie was
persisted (`context.cookies()` was empty), so every uncached request pays it again. The local
Playwright browser downloads are 261 MB (chromium headless shell) to 393-549 MB (full
Chromium) on disk in this machine's cache.

Not measured (no AWS runtime was used): memory under load, cold-start latency, behaviour from
AWS egress. Qualitative fit (inference from the sizes above and the Lambda and Fargate
models): a headless Chromium does not fit comfortably in a small Lambda zip package (a
container image would be needed, with several hundred MB of image and 1 GB or more of memory
to be safe), while Fargate can run it as a sidecar or in the same task at the cost of a
larger image, more memory and slower tasks. ToS risk: robots disallows `/busca/` for generic
crawlers, and the proof-of-work page is an explicit anti-bot control; automating around it
from a hosted service is a policy risk, and the Senado could change or harden it at any time.
Because the SRU is 404, there is no stable machine contract behind it; the only usable
surface would be scraped HTML.

## Ranked recommendation for the legislation Source

1. **Primary: Senado `dadosabertos/legislacao` API** for discovery, metadata and relations
   (amending/revoking norms, DOU publications, subject terms). Lookup by type/number/year or
   LexML URN. Throttle to well under 10 req/s with retry on 429/503; treat `documentos: ""`
   as "not found"; pin `v=3`; save recorded JSON as contract-test fixtures. Gaps: no free-text
   search, no article text.
2. **Text retrieval: Planalto static HTML, with Câmara Legin as second choice**, chosen via the
   `urlDocumento` / LexML URN page. Cache per URN (norm text changes rarely; consolidated
   versions change by new amending norms, which the API `vides` field reports). Treat as
   scraping with per-source parsers and snapshot tests, behind a thin adapter so it can be
   swapped.
3. **Free-text search**: a derived search index. Because no official API offers
   keyword search over legislation text, build a small local/embedded index from the Senado
   `lista` + term catalogue (+ `ementa`) and from retrieved texts, or defer free text to a
   later phase. For the MVP, support "find norm by type/number/year" and "open by URN", which
   cover most legal-citation use.
4. **Fallback only: LexML HTML via plain HTTP, then Playwright.** Use it behind a feature flag
   for text queries the API can not serve, with strong caching, a >=5 s delay (the robots
   `Crawl-delay`), and the error type "upstream blocked" for challenge pages (detect by title
   "Verificação de segurança" or body size, since the status is 200). Recommend not shipping
   Playwright in the Lambda/Fargate image unless a product need justifies it; keep it as a
   separate optional worker.
5. **Do not use**: LexML SRU (404); Câmara open data API for norms (bills only).

Deployment fit: options 1-3 are plain HTTPS clients, so they fit both Lambda and Fargate with
no extra runtime. Only option 4 (Playwright) pushes toward Fargate.

## Not verified

- Data license, ToS and acceptable automated-use policy for LexML, the Senado legislation
  API (beyond the hub's "livre utilização" phrase and the 10 req/s limit), the Câmara API
  (beyond the principles page), Legin and Planalto. Confirm with the institutions before
  launch.
- Whether the LexML SRU was ever moved elsewhere (a different host or path) or deliberately
  retired; I only probed `/busca/SRU`, `/busca/sru`, `/sru`, `/SRU`. Ask the LexML team.
- Whether the challenge hits AWS `sa-east-1` egress and how often (my observation is from a
  single non-AWS network); whether it is only cache-miss based (inferred from `Age`).
- Playwright memory, image size inside a real container, Lambda cold start and Fargate cost:
  not measured. Only disk size of local browser downloads and navigation latencies.
- How `normas.leg.br` loads norm text (back-end API not located); whether the Senado exposes
  article text through an official endpoint. The `legislacao` endpoints return metadata only
  in the samples I read.
- The Câmara API full list of rate limits/keys and the `Legin` URL derivation from a URN.
- Planalto: any official terms or reuse policy; robots.txt is absent (404).
- Case-law (jurisprudência) sources are out of scope for this note.
- I did not implement or test a non-browser solver for the proof-of-work challenge; doing so
  would be circumventing an anti-bot control and is not recommended.

## References

- <https://www.lexml.gov.br/robots.txt>, <https://www.lexml.gov.br/busca/search?keyword=lei+14133>,
  <https://www.lexml.gov.br/urn/urn:lex:br:federal:lei:2021-04-01;14133>
- <https://legis.senado.leg.br/dadosabertos/v3/api-docs>, <https://legis.senado.leg.br/dadosabertos/docs/>
- <https://www12.senado.leg.br/dados-abertos>,
  <https://www12.senado.leg.br/institucional/documentos/politica-de-uso-do-portal-do-senado-federal>
- <https://dadosabertos.camara.leg.br/swagger/api.html>,
  <https://dadosabertos.camara.leg.br/howtouse/sobre-dados-abertos.html>
- <https://www2.camara.leg.br/legin/fed/lei/2021/lei-14133-1-abril-2021-791222-norma-pl.html>
- <https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm>
- <https://normas.leg.br/?urn=urn:lex:br:federal:lei:2021-04-01;14133>
- Earlier LexML findings (issue #3): `docs/research/lexml-access.md` on branch `research/lexml-access`
