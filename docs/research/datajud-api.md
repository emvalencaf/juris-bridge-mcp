# Research: DataJud public API capabilities and limits

Resolves issue #2 (part of map #1). Researched 2026-10-17. Primary sources only:

- [W] DataJud Wiki, public API section: <https://datajud-wiki.cnj.jus.br/api-publica/> (pages: `acesso`, `endpoints`, `exemplos/exemplo1..3`, `glossario`, `termo-uso`, `consideracoes_finais`).
- [T] Terms of Use v1.2 (27 Nov 2023, PDF linked from the wiki): <https://formularios.cnj.jus.br/wp-content/uploads/2023/11/Termos-de-uso-api-publica-V1.2.pdf>.
- [L] Live probes against `api-publica.datajud.cnj.jus.br` on 2026-10-17 (one lookup, one unauthenticated call, two oversized-window calls). Observations, not documentation.

Portuguese terms: "capa processual" = case cover data; "movimentos" = case events; "sigilo" = secrecy level; "tribunal" = court.

## Summary

- DataJud exposes a raw Elasticsearch `_search` endpoint, one index per court. There is no REST resource model; the query model is Elasticsearch Query DSL sent as a POST body.
- It returns case metadata only (cover data plus event list). No documents, no decision text, no party names.
- Auth is a single shared public key, published on the wiki and changeable by the CNJ at any time.
- The terms of use forbid commercial use and redistribution of derived data, and ask for at most 120 requests per minute. Both matter for an MCP server open to others.
- It is documented as "Beta".

## Endpoints

- Base URL `https://api-publica.datajud.cnj.jus.br/` followed by a per-court alias, then `/_search`. Example: `https://api-publica.datajud.cnj.jus.br/api_publica_trf1/_search`. [W endpoints]
- Alias pattern is `api_publica_<court>`, one per court, all listed on the wiki: [W endpoints]
  - Superior courts: `tst`, `tse`, `stj`, `stm`. STF is not listed.
  - Federal: `trf1` to `trf6`.
  - State: 27 TJs (`tjac` ... `tjto`, including `tjdft`).
  - Labor: `trt1` to `trt24`.
  - Electoral: `tre-<uf>` (27, the DF one is listed as `tre-dft`).
  - Military: `tjmmg`, `tjmrs`, `tjmsp`.
- Wiki typo to know about: the TRE-BA row is labelled "Tribunal de Justica da Bahia" but its alias is `api_publica_tre-ba`. [W endpoints]
- Consequence for the tool contract: a court is selected by alias, so the adapter needs a court-code to alias map (or a rule plus an allowlist). Cases from STF cannot be fetched here.
- The 20-digit CNJ unified case number (NPU) encodes the court (segment `J` and tribunal `TR` digits), so an adapter could derive the alias from the number. That mapping comes from CNJ Resolution 65/2008, which was not fetched in this pass; verify before relying on it.

## Auth and key rotation

- Header: `Authorization: APIKey <public key>`. [W acesso]
- The key is a public key issued by the CNJ (DPJ/CNJ); "the current key will always be available in this section of the Wiki"; "the key may be changed by the CNJ at any time". [W acesso]
- On 2026-10-17 the key shown on the wiki worked against `api_publica_trf1`. [L]
- Without the header the server returns HTTP 401 `security_exception` (`missing authentication credentials`) with `WWW-Authenticate: ApiKey`. [L]
- No rotation schedule, notification channel, or overlap period is documented. [W acesso]
- Design implications: read the key from env config (already settled in the map); treat 401 as "key probably rotated" with a distinct error; the wiki page `acesso` is the only authoritative place to fetch the new key from. The ToS (3.17) forbids circumventing authentication, so do not scrape the key at runtime without checking with the CNJ.

## Query model

- Elasticsearch Query DSL in a JSON POST body; `Content-Type: application/json`. [W exemplos/exemplo1]
- The wiki states support for Elasticsearch "search and aggregation parameters" and points to the Elasticsearch "Search your data" guide. [W consideracoes_finais] Aggregations were not tested here.
- Documented examples: [W exemplos]
  1. By case number: `{"query":{"match":{"numeroProcesso":"00008323520184013202"}}}` (number without punctuation).
  2. By class and judging body: `bool.must` of `match` on `classe.codigo` (1116, Execucao Fiscal) and `orgaoJulgador.codigo` (13597).
  3. Pagination with `size`, `sort` on `@timestamp`, and `search_after`.
- Fields named in the glossary are keyword/long typed (`classe.codigo`, `orgaoJulgador.codigo`, `numeroProcesso`, `tribunal`, `grau`). `assuntos.codigo` exists for subject search. [W glossario]
- Free-text search over party names is not possible, since party data is absent (see below).

## Result caps and pagination

- Default page is 10 hits; `size` may be 10 to 10,000 per page. [W exemplos/exemplo3]
- Recommended deep paging: `size` + `sort: [{"@timestamp": {"order": "asc"}}]` + `search_after` set to the `sort` array of the last hit. [W exemplos/exemplo3]
- Confirmed live: `from + size` above 10,000 is rejected with `illegal_argument_exception: Result window is too large, from + size must be less than or equal to: [10000]`. The error text itself points to the scroll API; whether scroll or PIT is enabled on this cluster was not tested. [L]
- A sort on `@timestamp` alone is not a unique key, so ties can skip or repeat hits across pages. Adding a tiebreaker such as `_id` is an Elasticsearch concern not covered by the wiki; test before relying on it.
- Design implications: tools should take a small `limit` and cursor (wrap `search_after`), never expose raw `from`.

## Rate limits and latency

- Terms of use 3.13: the user agrees not to exceed **120 requests per minute** unless the CNJ grants written authorization. 3.14: the CNJ may impose per-user or per-key limits at any time without notice. 3.15: no overloading the service. [T]
- No rate-limit headers or documented 429 behavior were observed or documented. [L, W]
- Latency can be high: one exact-number lookup reported `"took": 9383` ms (about 9 s). [L] Set generous client timeouts and rely on caching.
- Because all users share one public key, throttling may hit regardless of an individual server's volume. Retry with backoff (already planned) and a client-side limiter at or below 120/min.

## Fields available per case

Glossary (`glossario`): [W glossario]

| Field | Type | Meaning |
|---|---|---|
| `id` | keyword | `Tribunal_Classe_Grau_OrgaoJulgador_NumeroProcesso` key (observed shape differs, see below) |
| `tribunal` | keyword | court acronym |
| `numeroProcesso` | keyword | unified CNJ number, unformatted |
| `dataAjuizamento` | datetime | filing date |
| `grau` | keyword | instance: `G1`, `G2`, `JE`, ... |
| `nivelSigilo` | long | secrecy level |
| `formato.{codigo,nome}` | object | physical or electronic |
| `sistema.{codigo,nome}` | object | source case system (e.g. PJe) |
| `classe.{codigo,nome}` | object | procedural class (TPU) |
| `assuntos[].{codigo,nome}` | array | subjects (TPU) |
| `orgaoJulgador.{codigo,nome,codigoMunicipioIBGE}` | object | court unit |
| `movimentos[]` | array | events: `codigo`, `nome`, `dataHora`, `complementosTabelados[]` (`codigo`, `descricao`, `valor`, `nome`), `orgaoJulgador.{codigoOrgao,nomeOrgao}` |
| `dataHoraUltimaAtualizacao`, `@timestamp` | datetime | internal control: source insertion time, index update time |

Observed live against a TRF1 case (2026-10-17), differences from the glossary: [L]

- `_id` and `id` were `TRF1_JE_00008323520184013202` (tribunal, grau, number), not the 5-part key in the glossary.
- `dataAjuizamento` came back as a compact string `"20181029000000"`, while `movimentos[].dataHora` and `@timestamp` are ISO-8601 UTC. Normalization must handle both.
- `movimentos[].orgaoJulgador.codigo` is a string (`"16403"`) and the glossary names it `codigoOrgao`. The top-level `orgaoJulgador.codigo` is a number.
- The sample case had no `assuntos` key; treat it as optional.
- Response envelope is plain Elasticsearch: `took`, `timed_out`, `_shards`, `hits.total.{value,relation}`, `hits.hits[]._source`, plus `sort` per hit when sorting.

No case URL or citation permalink is provided by the API. The "citation URL" required by the map must be built per court or point to the wiki/endpoint; this is a gap for the tool contract.

## Terms of use

From [T] v1.2, with the wiki restating 1.2, 3.2, 3.3, 3.6, 3.8, 3.9: [W termo-uso]

- Tacit acceptance by using the API (1.1, 1.2).
- Only lawful, **non-commercial**, authorized use (3.3). Do not modify, distribute, sell or commercially exploit the API "or any information derived from it" (3.8).
- Tell the CNJ about any public information, study, report or document produced (3.9).
- Do not use the API to collect third-party personal information (3.11). LGPD section 4: do not collect, store or process personal data from the API or cross-reference data to that end, except as LGPD allows (4.2); do not share personal data collected through the API with third parties (4.6).
- The CNJ may change or stop the API, or revoke access, without notice (3.4, 3.22), and does not guarantee accuracy, completeness or currency (3.6).
- Do not reverse engineer the interface (3.18).
- Venue: Brasilia/DF (5.1).

Implications for the plan: the MVP responsible-use/LGPD note is necessary but probably not sufficient. A public hosted server that redistributes DataJud-derived results may conflict with 3.3 and 3.8. Open question for the owner: ask the CNJ for written clarification, or keep the server self-hosted per user with their own use. Caching (in-memory TTL) is a form of storing derived data; keep it short-lived and non-persistent, which fits the current plan.

## What is absent

- **Sealed cases and party data**: the wiki says data follows Portaria CNJ 160/2020 "with protection of sealed (sigilosos) cases and party data" (<https://atos.cnj.jus.br/atos/detalhar/3453>, linked from the wiki; the act text itself was not read in this pass). [W api-publica, consideracoes_finais]
- The terms describe the API as covering "public cases" only (2.1). [T] The glossary has `nivelSigilo` but the wiki does not say what levels are returned; whether non-zero levels appear in results was not tested. The sample case had `nivelSigilo: 0`. [L]
- Not exposed: case documents, decision or judgment text, party and lawyer names, document numbers. Fields available are only those in the glossary.
- STF is not among the endpoints. [W endpoints]
- Completeness and freshness depend on each court's submission; the CNJ gives no guarantee (3.6). [T] The sample case showed `dataHoraUltimaAtualizacao` 2026-06-08, about four months before the probe, so do not present results as real-time. [L]
- Official uptime or SLA: none documented. API status is "Beta". [W consideracoes_finais]

## Shape of a recorded contract test

No real network in CI, per the map. Proposed shape, derived from the above:

- Cassette per case type, stored under `tests/` as JSON (request + response), recorded once manually against the live API with the current public key, with the key redacted from the stored request.
- Cassettes to record:
  1. Lookup by `numeroProcesso` (hit): full `_source` with `movimentos`, optional `assuntos` missing.
  2. Lookup with zero hits: `hits.total.value = 0`, `hits.hits = []`.
  3. Class + judging body search with `size` 2 and `sort` on `@timestamp`, then a second page with `search_after`.
  4. 401 missing/invalid key (`security_exception`, `WWW-Authenticate: ApiKey`).
  5. 400 result window exceeded (`illegal_argument_exception`, `status` 400).
  6. Unknown alias or court: record to learn the status code (not probed here).
  7. Timeout/5xx and 429: fake-injected, since the real behavior is undocumented.
- The test asserts on the adapter's normalized output (`source`, tribunal, case number, class, dates normalized to ISO, movements, citation URL), plus `include_raw` passing `_source` through unchanged.
- Make the contract a drift detector: a separate, opt-in (not CI) job re-runs the same requests against live DataJud and diffs the response *shape* (keys and types, not values), since the API is Beta and field formats already deviate from the glossary.
- Pin shape assumptions that were observed to be inconsistent: date formats, string-vs-number codes, optional `assuntos`.

## Open questions

1. May a hosted, multi-user MCP server legally use DataJud under the "non-commercial / no redistribution" terms? Needs owner decision or CNJ confirmation.
2. Is scroll or PIT available for result sets beyond 10,000? Not tested.
3. How are sealed cases represented (omitted, or `nivelSigilo` > 0 with masked fields)? Not tested; read Portaria 160/2020.
4. Does each court alias have the same field coverage? Only TRF1 was sampled.
5. What does an unknown alias return?
6. Court alias derivation from the CNJ number (Resolution 65/2008) needs confirmation from the primary text.
