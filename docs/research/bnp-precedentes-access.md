# Research: Banco Nacional de Precedentes (BNP / Pangea) as a source for precedent tools

Researched 2026-10-21. Question: for tools on precedents (sumulas, repercussao geral, repetitivos,
IRDR, IAC and similar), what does the CNJ Banco Nacional de Precedentes hold, and what is needed
to consume it? Related: [decision-text-by-cnj-number.md](decision-text-by-cnj-number.md) section 6
(BNP was only a lead there; this note replaces that section's "no API found").

Method: primary sources only (CNJ acts and pages, the PDPJ-Br documentation site, and the BNP
application itself: its public config file, its JavaScript bundle and read-only probes of the
backend it calls). Tags: `[V]` verified on 2026-10-21, `[I]` inferred from the application's own
code or from probes (not documented by the owner), `[U]` unverified. About 12 requests were made
to the BNP backend with an honest User-Agent; nothing was authenticated or bypassed, no volume.

## Summary

- The BNP exists in law (CNJ Res. 444/2022, Portaria 116/2022) and as a public web app,
  **Pangea/BNP**, at <https://bnp.pdpj.jus.br/> (older name `pangeabnp.pdpj.jus.br`). The CNJ and
  the PDPJ docs say it is "a public tool for all citizens". [V]
- **No documented public API exists.** No OpenAPI/Swagger, no developer page, no terms of use for
  programmatic access were found. [V that none was found]
- The web app is a single-page application that calls a **JSON backend that answers anonymously**
  (no key, no login) at `https://pangeabnp.pdpj.jus.br/api/v1`. We can read its shape from the
  app's own code and probes, so a client is technically easy, but the interface is **undocumented
  and can change without notice**, and its terms are unknown. [I]
- It holds **precedent records** (question, thesis, status history, suspensions, paradigm cases),
  not full judgments: the "decisoes" endpoint returned no texts in the two cases probed. [I]
- Coverage is broad: 93 bodies listed (STF, STJ, TST, TSE, STM, TNU, 6 TRFs, 27 TJs, 24 TRTs,
  the TREs and 3 military TJs), but the data is very uneven: STF 7,490 and STJ 3,016 hits against
  single digits for several TJs and TRF5. [I]
- Recommendation: viable as a source for `search_precedents` / `get_precedent`, on the same
  terms as the DJEN (ADR 0006): self-hosted per user, no public instance, an ADR that records the
  source is undocumented, and a written question to CNJ. Details in section 7.

## 1. Legal basis and official description

- Res. CNJ 444/2022 (25 Feb 2022) instituted the BNP "as a repository and unified technological
  platform for textual and statistical search", in succession to the bank created by art. 5 of
  Res. 235/2016. "Qualified precedents" are those in CPC art. 927 I to V; "precedents in the broad
  sense" include, among others, PUIL (STJ), and sumulas of STM, TSE, TST, TJs and TRFs.
  Source: <https://atos.cnj.jus.br/atos/detalhar/4415> (2026-10-21). [V]
- Portaria CNJ 116/2022 sets the data standard and the stages and "situacoes" (annexes). It is
  cited by the CNJ page and the manual, not read in full here (the annex fields were not
  extracted). Source cited by the manual. [U for annex content]
- Courts must send their precedents and "sobrestamentos" (suspensions of cases), identified by
  the single case number of Res. 65/2008. Sources:
  <https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/justica-4-0/banco-nacional-de-precedentes-bnp/>
  and the user manual below. [V]
- Pangea/BNP was developed by the TRT4 together with the CNJ (manual section 1). [V]
- User manual (PDPJ-Br docs): <https://docs.pdpj.jus.br/servicos-negociais/BNP-Pangea/BNP%20-%20Manual%20de%20Utiliza%C3%A7%C3%A3o>.
  It states the tool is public, searches by "any of the words" by default, supports `+word`,
  `"exact phrase"` and `-word`, and that the BNP is updated **twice a month** (mid and end of
  month). It has a statistics panel (a separate Qlik link) and a section on LGPD: minimisation,
  legal basis arts. 7 and 23, Res. CNJ 363/2021. [V]

## 2. How the application is built (what a client must reproduce)

- Public config <https://bnp.pdpj.jus.br/assets/config/env.js> (2026-10-21) names:
  `apiUrl = https://pangeabnp.pdpj.jus.br/api/v1` (read backend), `apiBnpUrl =
  https://bnp-sempj.pdpj.jus.br/v1` (a separate backend used by the court-side technical-notes
  module; it answered **401** to an unauthenticated call), and a Keycloak SSO for the court-side
  functions (`sso.cloud.pje.jus.br`). [V for the config file]
- The search UI needs no login: the read endpoints answered with no credentials, and no token
  was sent. The SSO guard applies to the staff modules (technical notes). [I]
- Endpoints used by the search module, read in the app's lazy-loaded bundle and confirmed by
  probe: [I]

| Call | Purpose | Observed |
|---|---|---|
| `GET /api/v1/parametros` | Reference lists | 200, no auth. Keys: `especies` (21), `gruposEspecies`, `gruposTribunais`, `orgaos` (93), `manualUrl`, `painelEstatisticoUrl`, `producao`, `versao` ("1.0.2") |
| `POST /api/v1/precedentes` with `{"filtro": {...}}` | Search | 200, no auth |
| `GET /api/v1/precedentes/{id}/decisoes` | Decisions of a precedent | 200, returned `relator`, `linkAcompanhamentoProcesssual` (sic) and `textos` |
| `GET /api/v1/sugestoes?texto=` | Autocomplete | 404 on my probe (shape or path may differ) |

- Filter fields from the app's client class: `buscaGeral`, `todasPalavras`, `quaisquerPalavras`,
  `semPalavras`, `trechoExato`, `atualizacaoDesde`, `atualizacaoAte` (`DD/MM/YYYY` presumed, not
  tested), `cancelados` (boolean), `ordenacao` (`"Text"` default; `"Data"` also accepted),
  `nr` (precedent number), `orgaos` (array of sigla), `tipos` (array of sigla), `pagina`
  (**1-based**, default 1) and `tamanhoPagina` (default 10; 100 and 500 were accepted). [I]
- Pitfall: a request without `orgaos` and `tipos` arrays got **HTTP 400** ("Requisicao invalida");
  with both arrays filled from `/parametros` it worked. Sending the filter without the `filtro`
  wrapper gave **500**. [I]
- Response envelope: `total`, `posicao_inicial`, `posicao_final`, `resultados[]`, `aggsEspecies[]`
  and `aggsOrgaos[]` (counts per type and per body, with `highlight` in each result for the
  matched terms in `<mark>`). `total` came back as exactly 10000 for a very broad query, so it
  looks capped at 10,000. [I]
- No robots.txt (the path serves the SPA HTML), no rate-limit headers, no terms page. Latency was
  a few seconds per call. [V that none was seen]

## 3. What a precedent record contains

From probes of an STF RG theme, an STJ RR theme and a TRT4 OJ (fields as returned). [I]

| Field | Meaning | Notes |
|---|---|---|
| `id` | Stable key like `stf-rg-1002`, `stj-rr-328`, `trt04-oj-11` | `<orgao>-<tipo>-<nr>` lowercase; good for a `get_precedent` argument |
| `orgao`, `tipo`, `nr` | Body sigla, type sigla, number | `nr` int or string (`1002` vs `"11"`): normalise |
| `questao` | Legal question (present for RG and RR; absent for the OJ) | Free text, may end in a newline |
| `tese` | Thesis or verbete | May contain HTML (`<br>`), and `highlight` HTML |
| `situacao` | Current status text | Examples: "Vigente", "Transitado em julgado", "Ha repercussao geral. Leading case: transitado em julgado". Vocabulary is free text that follows the Portaria 116 annexes |
| `historico[]` | Status history: `situacao`, `dataCriacao` (ISO with -03:00), and some `dataAdmissao`, `dataJulgamento`, `dataPublicacao` | Dates inconsistent between records |
| `processosParadigma[]` | Leading cases: `numero` (**CNJ number, 20 digits, no mask** in the TRT4 and STJ cases; a bare STF incident number `1140005` for the STF RG), `classe` (TPU code), `link` (court URL, sometimes absent) | Bridges to `get_case` via DataJud only when the number is 20-digit |
| `suspensoes[]` | `ativa`, `dataSuspensao` (`DD/MM/YYYY`), `descricao` | Present on STJ RR |
| `ultimaAtualizacao` | `DD/MM/YYYY` | Mixed formats within one record |
| `/decisoes` | `relator`, `linkAcompanhamentoProcesssual`, `textos[]` | `textos` was empty in both probes; the manual says admission and merit rulings (decisao/acordao de admissao, ementa and acordao de merito, suspension decision) are shown in the app, so texts may exist for some records [U] |

The manual lists what the UI presents: question, thesis, status, decisions (tabs), processes
(table `numero` + `link`), suspension (scope, start and end date, link to the official document).
A precedent not yet judged has the question but an empty content field. [V, manual section 4]

Types seen in `/parametros.especies` (sigla: name): SUM sumula, OJ, IAC, IRDR, PN precedente
normativo, IRR (TST), SV sumula vinculante, SIRDR, RR (STJ repetitivo), RG (STF tema), ADI, ADC,
ADO, ADPF (concentrated control), PUIL, CT controversia, NT nota tecnica, NTA nota de adesao, ENU
enunciado, RC representativo da controversia. The list also contains an entry whose sigla is the
string `"ADI ADC ADO ADPF"` (a UI group), so do not treat `sigla` as always one token. [I]

## 4. Coverage

- `/parametros.orgaos`: 93 bodies: STF, STJ, TST, TSE, STM, TNU, TRF01 to TRF06, 27 TJs (`TJDF`
  for the DF), TRT01 to TRT24, 27 TRE_xx and TJMMG/TJMRS/TJMSP. [I] Naming differs from this
  project's court codes (`TRF01`, `TRE_AC`, `TJDF`), so a mapping table is needed.
- Hits per body for a very broad query (`de`, cancelled included), top and bottom: STF 7,490; STJ
  3,016; TNU 394; TST 321; TJSP 237; TRT04 202; ... TJAC 7; TJAL 4; TRF05 4; STM 2. Several
  bodies in the list returned no entry (all TREs and the military TJs for this query). [I]
  The sum of these counts exceeds the capped `total`, so treat them as indicative. By type: ADI
  4,581; SUM about 2,150; IRDR about 1,680; RG about 1,490; RR about 1,480. [I]
- Not a complete mirror of every court's case law: the BNP only holds what courts send under
  Res. 444 and Portaria 116 (the CNJ's relaunch note says about 60 bodies integrated; the 93 in
  `/parametros` is the configured list). [V for the CNJ statement via search summary, U for the
  exact number]
- Freshness: records updated as recently as 15 Oct 2026 appeared; the manual says updates twice a
  month. [V/I]

## 5. Access, terms and limits

- Anonymous reads work; no key to manage. The CNJ describes the tool as public for citizens,
  lawyers, magistrates and researchers. [V]
- Terms of use for automated access: none found on the app, the CNJ page, or the PDPJ manual.
  The manual's LGPD section concerns the platform's own processing. Silence is not a grant (same
  position as ADR 0006 for the DJEN). [V that none found]
- The backend is meant for the app: names with typos (`linkAcompanhamentoProcesssual`),
  `500` on wrong body shape, stable `versao` "1.0.2" but no API version promise. Expect changes. [I]
- Personal data: records are precedents (law-level text) and case numbers of paradigm cases; party
  names are not in the fields seen. Some `link` values point to court documents that may contain
  them. [I]
- DataJud-style bans do not apply (this is not DataJud); but the PDPJ-Br site is CNJ's and the
  BNP is public by Res. 444 art. 1 ("consulta e divulgacao por orgaos e pelo publico em geral"). [V]

## 6. Fit with the project

- ADR 0002 forbids browser and scraping sources: this is a **JSON HTTP API without a browser**,
  so it is not a scraper in the usual sense, but it is an undocumented back end of a UI, found by
  reading the page's JavaScript. That is a grey zone to settle in an ADR, not to assume away.
- ADR 0006 pattern fits: read-only keyless source, self-hosted per user, no public instance, tool
  descriptions warning of personal data, fan-out limits stated in results (`complete` flag).
- Slice sketch (not a design decision): a `precedents` vertical slice with `search_precedents`
  (query, body, type, updated range, cancelled flag, page/limit) and `get_precedent` (by `id`);
  `list_coverage` extended with the BNP bodies and counts. Honest limits to surface in results:
  `total` capped at 10,000, status vocabulary is free text, `decisoes` may be empty, and a
  paradigm case number only links to `get_case` when it is a 20-digit CNJ number.
- Ports: a `PrecedentSource` interface with the BNP adapter behind it, so a bulk-data or STJ
  CKAN source (`precedentes-qualificados` dataset, see court-data-access.md) can replace or
  complement it.

## 7. Recommendation

1. Build the precedents slice on the BNP read API, **after** two checks: (a) ask CNJ (PDPJ/BNP
   support; the CNJ page says integrations go through `sistemasnacionais@cnj.jus.br`) whether
   programmatic use of `pangeabnp.pdpj.jus.br/api/v1` is accepted and whether a stable, documented
   endpoint exists; (b) record the answer in a new ADR ("BNP as a precedent source, undocumented
   API, self-hosted per user").
2. Record a contract cassette from a live probe (the shapes in section 3) and keep an opt-in
   drift check, as planned for DataJud, since the API is unversioned.
3. Keep a fallback in the design: STJ CKAN `precedentes-qualificados` (official, open data) for STJ
   if the BNP route is declined.
4. Do not promise coverage in the tool description: show per-body counts from `aggsOrgaos`.
5. Throttle conservatively (a few requests per second at most, jittered retries) and identify the
   client with an honest User-Agent.

## Not verified

- Terms of use for automated access, rate limits and any SLA of `pangeabnp.pdpj.jus.br`.
- Whether `pagina` 0 or an empty `buscaGeral` is valid; the maximum `tamanhoPagina`; the date
  format accepted by `atualizacaoDesde`/`atualizacaoAte`; what `ordenacao` values exist.
- The `/sugestoes` request shape (404 on my probe); the content of `textos[]` in `/decisoes` for
  records with full judgments.
- The Portaria CNJ 116/2022 annexes (data standard, list of "situacoes") and how many bodies
  actually send data today.
- Whether the STJ CKAN `precedentes-qualificados` dataset is richer (its schema was not read).
