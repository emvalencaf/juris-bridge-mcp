# Research: STJ open data as a historical case-law source (issue #60)

Part of map #53. Researched 2026-10-18. Starting point:
`docs/research/court-data-access.md` section 2.

**Outcome: partial.** The STJ CKAN portal (`dadosabertos.web.stj.jus.br`) was
unreachable for the whole session, so none of the per-dataset facts the issue
asks for (formats, sizes, fields, date range, update frequency, licence) could
be read. Nothing below about dataset contents is a finding. What is recorded is
(a) what is documented by primary sources, (b) what was observed about the
portal's availability, and (c) what that implies for the Lambda question, each
labelled. A follow-up with a working connection is needed.

Labels: **Documented** = stated by a primary source cited next to it.
**Observed** = seen first-hand in this session. **Inference** = reasoning from
the above, not verified.

## What was observed about availability

All requests were read-only GETs against the public CKAN API, unauthenticated.

- **Observed:** `GET /api/3/action/package_list` and
  `GET /api/3/action/package_show?id=precedentes-qualificados` on
  `dadosabertos.web.stj.jus.br`. DNS resolved to Cloudflare IPs
  (104.16.162.229, 104.16.163.229) and the TLS handshake completed (TLS 1.3,
  HTTP/2 accepted). The request was then sent and no response bytes arrived for
  60 to 100 s (four attempts with curl, one with WebFetch; also `/`, `/robots.txt`).
- **Observed:** later in the session Cloudflare answered `HTTP 504` with a
  16-byte `text/plain` body (`server: cloudflare`, `cache-control: no-store`) in
  about 15 s, on both `package_list` and `package_show`. A WebFetch of
  `/dataset/integras-de-decisoes-terminativas-e-acordaos-do-diario-da-justica`
  also returned 504 with `Retry-After: 120`.
- **Inference:** Cloudflare is reachable but the STJ origin behind it is not
  responding (down, overloaded or slow to respond to this client). This
  matches the earlier pass in `court-data-access.md`, which also timed out. It
  is a single sample, from one network (WSL2, Brazil-adjacent GIG edge node
  per `cf-ray`), not proof of general instability. No bot challenge page was
  seen; the failure is a gateway timeout, not a block.
- **Implication (Inference):** if the origin is this slow or down regularly, an
  on-demand adapter that depends on it at request time would inherit that
  unavailability. Worth measuring over days before committing.

## Documented facts

| Fact | Source |
|---|---|
| Portal runs CKAN 2.9, data in open, machine-readable format | https://dadosabertos.web.stj.jus.br/ (as recorded in `court-data-access.md`; not re-read this session) |
| 21 datasets listed by `package_list`, including `espelhos-de-acordaos-*`, `integras-de-decisoes-terminativas-e-acordaos-do-diario-da-justica`, `precedentes-qualificados` | `court-data-access.md` section 2 (earlier pass; not re-verified this session, the endpoint was down) |
| `api-publica-datajud` entry has empty `license_id` and `isopen: false` | same earlier pass |
| Launch: first of five release stages, May 2022, starting with "espelhos de acordaos" (jurisprudence), data is "formato legivel por maquina", offered for bulk download rather than through custom robots; no licence named, cites the CNJ definition of open data ("licenca aberta que permita sua livre utilizacao") | https://www.stj.jus.br/sites/portalp/Paginas/Comunicacao/Noticias/20052022-Novo-Portal-de-Dados-Abertos-amplia-transparencia-de-acoes-realizadas-no-STJ.aspx (read this session via WebFetch summary; the later four stages are not described there) |
| CKAN DataStore: `datastore_search` queries one DataStore resource with filters, full-text, sort, pagination; 100 rows default, 32000 max unless configured; `datastore_search_sql` runs one SELECT with a timeout and may be disabled by the operator; a DataStore resource must be tied to a CKAN resource and is loaded by the DataPusher from suitable files (CSV, Excel as examples) | https://docs.ckan.org/en/2.9/maintaining/datastore.html (read this session via WebFetch summary) |
| Case-law UI SCON is `Disallow`ed in robots.txt and the WAF rejects scripted requests | `court-data-access.md` section 2 (earlier pass) |

## Answers to the issue's questions

| Question | Status |
|---|---|
| Which datasets matter | Candidates named above (documented in the earlier pass). Which ones carry usable ementa/full text is **not verified**. |
| Formats, size, update frequency, date range | **Not read.** Portal unreachable. The launch notice only says "machine readable" and "bulk download". |
| Fields: ementa, full text, CNJ number, relator, publication date | **Not read.** Do not assume the espelhos carry a CNJ number: STJ uses its own registro number, and mapping to CNJ format is unconfirmed. |
| Licence per dataset | **Not read.** Only the launch notice's reference to the CNJ "open licence, free use" definition is documented; no licence identifier. `api-publica-datajud` is documented (earlier pass) as having an empty `license_id`. Expect the same for others, but verify. |
| Queryable on demand (datastore, range requests) or bulk only | **Not determined.** CKAN can offer `datastore_search` only for resources loaded into the DataStore (documented). Whether STJ enabled it, and whether its file host supports HTTP `Range`, needs `package_show`/`resource_show` (look for `datastore_active`, `format`, `size`, `url`) and a `HEAD` request on one resource. The launch notice describes bulk download. |

## What it means for a stateless Lambda (Inference)

Conditional on facts not yet verified:

- If resources have `datastore_active: true`, an adapter can call
  `datastore_search` with filters and `q` per request. No cache needed, one
  HTTP call, bounded response (100 rows default). This is the only path that
  fits a stateless Lambda cleanly, and it depends on the origin being up.
- If only bulk files are offered (what the launch notice suggests), a stateless
  Lambda without persistent cache would have to download the file on each cold
  request, which is infeasible for large archives (Lambda response/time/`/tmp`
  limits apply; check AWS docs before relying on exact numbers). Options then:
  HTTP `Range` reads if the file host supports them and the format is seekable
  (not true of a compressed JSON/ZIP stream), or a separate ingestion job that
  loads the data into a store the Lambda queries. The latter conflicts with the
  in-memory-cache decision and likely needs an ADR, as `court-data-access.md`
  already asks.
- Either way, a historical-only source with a multi-day publication lag cannot
  serve fresh Publications; DJEN/DataJud remain the live sources.

## Next steps to close this issue

1. Retry from a different network or time of day: `package_list`, then
   `package_show` for the three datasets, recording `license_id`/`license_title`,
   `metadata_modified`, resource `format`, `size`, `datastore_active`, `url`.
2. `HEAD` one resource URL for `Content-Length`, `Accept-Ranges`, `Content-Type`.
3. If `datastore_active`, run one `datastore_search?limit=2` to record the
   field names.
4. Measure availability (a handful of requests over several days) to size the
   dependency risk.
5. Only then decide between on-demand query and ingestion.

## Not verified

Everything in the "Answers" table marked not read; the CKAN version and
configuration actually deployed; the 21-dataset list (carried over from the
earlier pass); rate limits; the later four release stages of the portal.
