# DJEN public API for retrieving Publications

Research for issue #54 (child of map #53). Date of research: 2026-10-18.

Legend: **[D]** documented in the API's own OpenAPI file; **[O]** observed in live,
read-only, unauthenticated GET probes on 2026-10-18; **[I]** inference.

## Sources

- OpenAPI 3.0.1 file, `info.version` 1.0.4, "last updated 04-03-2026":
  https://comunicaapi.pje.jus.br/swagger/djen.yml (Swagger UI at
  https://comunicaapi.pje.jus.br/swagger/index.html loads it).
- Live probes against https://comunicaapi.pje.jus.br (GET only, no credentials).
- Legal basis cited by the spec's license field: CNJ Resolucao 455/2022
  (https://atos.cnj.jus.br/atos/detalhar/4509). Not read in depth.
- Not found: any `swagger.json` / `v3/api-docs` (404). The `.yml` is the only machine-readable spec.

## Base URL and endpoints

Base: `https://comunicaapi.pje.jus.br` (behind CloudFront) **[D][O]**.

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/v1/comunicacao` | none | Search communications (the Publications) **[D][O]** |
| `GET /api/v1/comunicacao/tribunal` | none | Courts by UF with last-delivery date **[D][O]** |
| `GET /api/v1/comunicacao/{hash}/certidao` | none | Certidao of a communication **[D]**, not probed |
| `GET /api/v1/caderno/{sigla_tribunal}/{data}/{meio}` | none | Daily "caderno" bulk package: metadata + temporary (5 min) download URL, SHA256 `hash`, `versao`, `total_comunicacoes`; today's cadernos available from 03:00 **[D]**, not probed |
| `POST /api/v1/login`, `POST /api/v1/comunicacao`, `DELETE /api/v1/comunicacao/{id}` | Bearer | Court-only (ingest/cancel) **[D]**; irrelevant to us |

## Authentication and keys

- Spec: endpoints without a padlock need no authentication; login/ingest/cancel are
  "exclusive use by the Tribunais" **[D]**.
- Search worked with no key, header or cookie **[O]**. No API key registration exists
  for read access **[I]**.

## Query parameters of `GET /comunicacao` **[D]**

| Parameter | Notes |
|---|---|
| `texto` | Free text. Listed in the 10000-result-cap group and in the "at least one of" group. (Described only indirectly; no own description.) |
| `siglaTribunal` | Court acronym (e.g. `STJ`, `TJSP`, `TJRS`) **[O]** |
| `dataDisponibilizacaoInicio` / `dataDisponibilizacaoFim` | `yyyy-mm-dd` |
| `numeroProcesso` | CNJ number; the sample item shows digits only (`50680908920254047100`); a masked form is returned separately **[O]**. Digits-only query returned the expected 2 items **[O]**; masked form not tested |
| `nomeParte`, `nomeAdvogado`, `numeroOab`, `ufOab` | Party / lawyer / OAB filters |
| `numeroComunicacao`, `orgaoId` | Communication number; internal body id |
| `meio` | `D` = Diario Eletronico, `E` = Edital |
| `pagina`, `itensPorPagina` | Paging. Spec: "valid values: 5 and 100" |

Rules from the spec **[D]**: at least one of `siglaTribunal`, `texto`, `nomeParte`,
`nomeAdvogado`, `numeroOab`, `numeroProcesso` is required, or `itensPorPagina` must be 5.
Queries with textual/OAB fields, with 5 or fewer items per page, with different start/end
dates, or with a process number are "limited to 10000 results".

Observed **[O]**: `itensPorPagina=100` and `=5` work; `=7` returned 200 (not rejected in that
probe). Without any filter and `itensPorPagina=100`, the call returned 200 (data across
courts) although the spec says one filter is required. `count` came back as exactly
`10000` on every broad query, so it is a cap marker, not the true total **[O][I]**.
Unknown parameters are silently ignored: `tipoDocumento=Despacho` had no effect **[O]**.

### Communication type

No query parameter for `tipoComunicacao` or `tipoDocumento` exists **[D]** and the
undocumented attempt was ignored **[O]**. These are response fields only; filter client-side.

## Response shape

Envelope: `{status, message, count, items[]}` **[D][O]**. Each item **[O]** (spec fields
plus extras the spec omits: `idOrgao`, `status`, `motivo_cancelamento`, `data_cancelamento`):

`id`, `data_disponibilizacao` (ISO), `datadisponibilizacao` (dd/mm/yyyy), `siglaTribunal`,
`tipoComunicacao`, `nomeOrgao`, `idOrgao`, **`texto`**, `numero_processo`,
`numeroprocessocommascara`, `meio`, `meiocompleto`, `link`, `tipoDocumento`, `nomeClasse`,
`codigoClasse`, `numeroComunicacao`, `ativo`, `hash`, `status`, `destinatarios[]`
(`nome`, `polo` A/P/T/D), `destinatarioadvogados[]` (`advogado.{nome,numero_oab,uf_oab}`).

**Published text field: `texto`** ("Teor da Comunicacao") **[D]**. Its format varies by court
**[O]**: STJ returns an HTML document (table with relator/parties/advogado, then the
decision text, with e-STJ cites), 1.3k-8.5k chars in the sample; TJSP returns plain text for
acordao notices, including an `EMENTA:` section. `link` points to the court's own
full-content page (e.g. processo.stj.jus.br, dje.tjsp.jus.br) **[O]**.

`tipoComunicacao` spec values: Citacao, Intimacao, Edital, Pauta de julgamento, Lista de
distribuicao, Ata de sessao **[D]**.

## Filtering to decisoes, acordaos and ementas

- No server-side filter by document kind **[D][O]**. It must be done client-side on
  `tipoDocumento` and `texto`.
- Observed `tipoDocumento` values (free text, court-specific, inconsistent casing) **[O]**:
  `Intimação de acórdão` (81 of 100 TJSP items), `DESPACHO/DECISÃO`, `Despacho`, `Edital`
  (TJSP); `DESPACHO / DECISÃO`, `EDITAL DE CITAÇÃO` (STJ). Not a closed vocabulary **[I]**.
- Acordao notices at TJSP include the ementa inline (`EMENTA:` in all 100 items for
  `texto=ementa`, which is expected as the query itself matched it) **[O]**. What is published
  is a notice of intimation, so it is not guaranteed to carry the full acordao or a
  structured ementa field **[I]**. STJ items quote an ementa inside a decision **[O]**.
- Conclusion **[I]**: DJEN is a feed of intimacoes/editais published in the Diario. It
  covers decisoes and acordao notices (often with ementa text), but is not a jurisprudence
  database; selection needs `texto` search plus `tipoDocumento` heuristics.

## Rate limits

- Per-IP rate limit; headers `x-ratelimit-limit` and `x-ratelimit-remaining`; on 429 wait
  1 minute; using multiple IPs to evade is "abusive use" and may be blocked **[D]**.
- Observed `x-ratelimit-limit: 20` **[O]**. Window length is not documented and was not
  measured; remaining dropped about 1 per request (15, 16, 15, 11 over ~8 calls, so it
  refills) **[O]**. Treat as roughly 20 requests per unknown window **[I]**.
- Responses carry `cache-control: max-age=120, private` **[O]**.

## Stability signals

- OpenAPI `version: 1.0.4`; path prefix `/api/v1` **[D]**. Last update note 04-03-2026
  (new caderno availability time; better endpoint docs) **[D]**.
- Spec and reality drift **[O]**: `/comunicacao/tribunal` returns a list grouped by
  UF (`uf`, `nomeEstado`, `instituicoes[{sigla,nome,dataUltimoEnvio,active}]`; 28 groups,
  119 institutions) while the spec shows a flat list with `id/nome/sigla/jurisdicao`.
  Responses have extra undocumented fields. Parse defensively.
- Court coverage and delivery lag differ: `dataUltimoEnvio` varies (e.g. TSE 09/10/2026,
  CNJ 08/07/2020 vs. others 16/10/2026) **[O]**; the endpoint is the way to check freshness.
- The 10000 cap means deep history requires narrow date windows or the caderno download **[I]**.

## Implications for juris-bridge-mcp

- Use `GET /comunicacao` with `siglaTribunal` and narrow date windows, 100 per page, paging
  through; keep client-side retry/backoff on 429. Whether a single-day window (start == end)
  with 100/page escapes the 10000 cap was not verified (the STJ single-day probe used 5/page
  and still reported 10000).
- Do not rely on `count` for totals.
- Verify before design: the exact rate-limit window, whether `pagina` beyond the 10000
  cap fails, and caderno content format (not probed).
