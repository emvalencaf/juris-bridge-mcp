# Research: DataJud publication movements and linking a Case to the DJEN

Resolves issue #56 (part of map #53). Researched 2026-10-18. Builds on [datajud-api.md](datajud-api.md). Primary sources only:

- [SGT] CNJ Sistema de Gestão de Tabelas Processuais Unificadas, public SOAP service `https://www.cnj.jus.br/sgt/sgt_ws.php?wsdl` (operations `pesquisarItemPublicoWS`, `getArrayFilhosItemPublicoWS`, `getComplementoMovimentoWS`). This is the machine-readable form of the TPU movement table also shown at `https://www.cnj.jus.br/sgt/consulta_publica_movimentos.php`.
- [W] DataJud Wiki, public API (`acesso`, `glossario`): <https://datajud-wiki.cnj.jus.br/api-publica/>.
- [D] Live DataJud probes on 2026-10-18 (`api-publica.datajud.cnj.jus.br`): `size: 0` count queries and 50 single-number lookups. Observations, not documentation.
- [J] Live DJEN probes on 2026-10-18: `https://comunicaapi.pje.jus.br/api/v1/comunicacao` (public, no key), 10 requests of 5 items each. The DJEN API has no documentation read in this pass; only its observed response is used.

## Summary

- **Four TPU movements relate to publication**, all children of item 48 ("Movimento" processual): `92` Publicação, `928` Republicação, `1061` Disponibilização no Diário da Justiça Eletrônico, `1062` Redisponibilização no Diário da Justiça Eletrônico. The one that means "went out in the Diário" is **1061** (and 1062 for a re-issue). `92` is the legal publication date, which for the DJe is by definition the first business day after 1061. [SGT]
- **A movement is not a publication record.** It carries no text, no Diário edition, no DJEN id and no link to the decided act. It only says that something was published on a date. It cannot stand in for the DJEN text.
- **Fill rate varies a lot by court.** Share of all cases that carry at least one of 92/928/1061/1062: 36% to 98% across 11 courts (table below). Only some courts use 1061 at all (TST: 17% of cases carry 1061 but 92% carry 92). [D]
- **Linking works by CNJ number plus date, but only partly.** DJEN `numero_processo` is the same 20-digit unformatted string as DataJud `numeroProcesso`, so the key join is exact. The date join worked in 15 of 39 sampled cases found in DataJud (all of TRF1, TRF3 and TST in the sample); it failed elsewhere because DataJud lagged the DJEN, or because the case is absent from DataJud. [D, J]
- **Recommendation for the map:** treat DataJud publication movements as a hint (`"has a recorded publication on date X"`), never as the source of truth. Use DJEN as the source of publications and DataJud only to enrich a Case. Link by `numeroProcesso` first, then match `data_disponibilizacao` against movement `1061` on the same day (or `92` on the next business day), and degrade to number-only when the date does not match.

## The TPU movements

Queried through [SGT]. Parent 48 is the "Movimento" node whose children are the procedural movements.

| Code | Name | Meaning (TPU glossary, paraphrased) | Complement |
|---|---|---|---|
| 92 | Publicação | Publication of an act (despacho, acórdão, pauta, intimação...). The date is mandatory. Not the same as disponibilização in the DJe (Lei 11.419/2006). | `ato_publicado` (template `Publicado #{ato_publicado} em #{data}.`) |
| 928 | Republicação | Publication repeated after an error, restarting the deadline. | `ato_publicado` |
| 1061 | Disponibilização no Diário da Justiça Eletrônico | Date the act became available in the DJe. The publication date is the first business day after it. | `data` |
| 1062 | Redisponibilização no Diário da Justiça Eletrônico | Date the act was made available again in the DJe. | `data` |

Related but not publication: `12263` Intimação (children Eletrônica `12264`, Em audiência, Em Secretaria, Intimação Expedida `15729`, Intimação Realizada `15728`) and `12281` Comunicação eletrônica (Expedida/Certificada, Confirmada, Erro ou Recusa). These record that a party was notified, not that the Diário carried the act.

Implications:

- The decision/ruling type is not in the movement. Which act was published is a `complementosTabelados` entry with `nome` such as "sentença", "decisão" or "acórdão" only when the court filled the `ato_publicado` complement. In the 50 sampled cases the complement was **almost always empty** (TJMG sometimes filled values like `preliminar`, `designada`, `sorteio`, `julgamento`, which are other TPU complement tables, not the act type). So a filter "decisions published in the Diário" cannot be built from DataJud. [D]
- Movement dates: `dataHora` is an ISO-8601 UTC timestamp. Compare on the date part only; it shows the Brasília day as the court recorded it.

## Fill rate across courts

Counts are exact `track_total_hits` totals per court index (population, not a sample). "Any pub" is `terms movimentos.codigo in [92, 928, 1061, 1062]`. [D]

| Court | Cases | Any pub | Share | With 92 | With 1061 | With 928 | With 1062 |
|---|---|---|---|---|---|---|---|
| STJ | 3,684,932 | 3,621,491 | 98.3% | 98.1% | 98.2% | 0.4% | 0 |
| TRT2 | 5,368,453 | 5,013,958 | 93.4% | 93.4% | 93.4% | 0 | 0 |
| TST | 4,610,727 | 4,238,135 | 91.9% | 91.9% | 17.0% | 0.1% | 0 |
| TRF3 | 17,594,308 | 13,069,456 | 74.3% | 72.5% | 47.7% | 0.05% | 0.07% |
| TJDFT | 543,297 | 382,036 | 70.3% | 69.0% | 70.3% | ~0 | ~0 |
| TJRS | 14,385,741 | 7,847,690 | 54.5% | 33.3% | 54.5% | ~0 | 0.08% |
| TJBA | 15,723,042 | 8,204,768 | 52.2% | 43.9% | 51.7% | ~0 | ~0 |
| TJRJ | 24,221,920 | 11,843,838 | 48.9% | 47.6% | 30.0% | ~0 | 0 |
| TRF1 | 12,850,179 | 5,346,151 | 41.6% | 41.5% | not measured | 0.2% | 0 |
| TJMG | 37,439,546 | 13,650,955 | 36.5% | 35.7% | 15.0% | 0.2% | 0 |
| TJSP | 75,661,482 | 26,071,475* | 34.5%* | 48.6% | 4.5% | 0.7% | ~0 |

\* TJSP's "any pub" count (26.07M) is lower than its count for code 92 alone (36.79M), which is impossible for an exact count. The cluster likely returned a partial result for the `terms` query under load. Treat the TJSP row as a lower bound; the true share is at least 48.6%. All other rows were internally consistent (any >= each code). The TRF1 row comes from an earlier run in which the 1061 query hit HTTP 429.

Reading the table:

- The shares are over **all** cases in the index, including recent filings that have not had a publication yet and old cases without one. They are not a quality score per case, only "how many cases ever show a publication movement".
- The two codes are used differently per court. Some courts record only `92` (TST, TRT, TJSP in part), some only `1061` (TJDFT, TJRS, TJBA), some both a day apart (TRF1, TRF3, STJ, TRT2). A client must look for any of the four codes.
- `928` and `1062` are rare (under 1% everywhere). Do not depend on them.
- Not sampled: the other 24 TRTs, 25 TJs, TRF2/4/5/6, TREs, military courts. Extrapolate only with caution.

## Linking a DataJud Case to a DJEN publication

DJEN item fields seen on 2026-10-18 [J]: `numero_processo` (20 digits, unformatted), `numeroprocessocommascara` (formatted), `siglaTribunal`, `data_disponibilizacao` (ISO date) and `datadisponibilizacao` (dd/mm/yyyy), `tipoComunicacao`, `tipoDocumento`, `nomeOrgao`, `codigoClasse`, `texto`, `link`, `hash`, `status`. Items also contain party and lawyer names and OAB numbers, which are personal data (see the LGPD note in [datajud-api.md](datajud-api.md)).

**Key join.** `DJEN.numero_processo == DataJud.numeroProcesso`. Same format, no normalization needed beyond stripping punctuation. A number can return several documents in DataJud, one per `grau` (G1, G2, JE, SUP): several of the 39 found cases (TJMG, TRF3, TRF1) had two. Match on `tribunal` and, if known, class code too.

**Date join.** For each DJEN item with `data_disponibilizacao = D`, a DataJud case "confirms" it when a movement `1061` has `dataHora` date D, or a movement `92` has a date on D or on the next business day. The sample (one DJEN item per case, dated 2026-09-15, 50 cases) gave: [D, J]

| Court | Sampled | Found in DataJud | Date matched |
|---|---|---|---|
| TRF1 | 5 | 5 | 5 (92 and 1061 on 2026-09-16, one day after the DJEN date; see below) |
| TRF3 | 5 | 5 | 5 (1061 on 2026-09-15 for the first three; 92 and 1061 on 2026-09-16 for the other two) |
| TST | 5 | 5 | 5 (92 on 2026-09-16, or 1061 and 92 on 2026-09-15) |
| TRT2 | 4 | 4 | 0 (latest publication movements were 2026-08-27; DataJud updated 2026-09-10) |
| TJSP | 5 | 5 | 0 (DataJud last updated before or around the date) |
| TJRJ | 5 | 5 | 0 |
| STJ | 4 (+1 timeout) | 4 | 0 on that date (closest 2026-09-16/17 not recorded as 1061) |
| TJMG | 5 | 4 | 0 |
| TJDFT | 5 | 1 | 0 |
| TJRS | 5 | 0 | 0 (none of the five numbers exist in the TJRS index) |

Total: 49 lookups answered, 39 found in DataJud (80%), 15 date-matched (38% of found, 31% of all). Small sample, one date; read it as a direction, not a rate.

Why the date join fails:

1. **Freshness lag.** `dataHoraUltimaAtualizacao` often precedes or trails the DJEN date by days or weeks, so the publication of 2026-09-15 had not reached DataJud when it was probed a month later for TRT2, TJSP, TJRJ and TJMG.
2. **Missing cases.** TJRS (5 of 5) and TJDFT (4 of 5) numbers returned zero hits, so a DJEN item can describe a Case that DataJud does not serve under that alias at all. The cause (not yet ingested, sealed, different index) was not determined.
3. **Off-by-one day.** The DJEN `data_disponibilizacao` was 2026-09-15 while TRF1 and TST recorded the publication movements on 2026-09-16, and TRF3 recorded 1061 on 2026-09-15 and 92 on 2026-09-16. So match `1061` on D and `92` on D or the next business day, as the TPU glossary says. TRF1 recorded no 1061 on 09-15 for those cases, so a DJEN-to-1061 match alone would have missed it.
4. **Mixed granularity.** DataJud holds many publications per case (up to 41 `92` movements in one sampled TJSP case) with no id tying one to a DJEN item, so a date match can be coincidental on a busy case.

## Rate limits and reliability observed

- One run was throttled with HTTP **429** after five heavy aggregation queries in about 3 minutes. The count queries over 10-75 million documents took tens of seconds each. After that, queries were spaced 5 s apart with backoff on failure. [D]
- One lookup returned HTTP **504** Gateway Time-out (STJ). Retry with backoff, as already planned in [datajud-api.md](datajud-api.md). [D]
- The DJEN API answered 10 requests spaced 3 s apart without error. No limit is documented. [J]
- The terms of use limit of 120 requests per minute still applies ([datajud-api.md](datajud-api.md)).

## What this means for the design

- Do not build a "published decisions" filter on DataJud movements. The act type is rarely filled, and coverage of any publication movement is 36% to 98% depending on the court.
- A Case tool may expose "publication dates known to DataJud" as supplementary fields (movement codes 92, 928, 1061, 1062 with `dataHora` and complements) flagged as best effort, per court.
- A Publication tool should read the DJEN and then link back to the Case by `numero_processo`, with the DataJud alias derived from the number (still unverified for all courts, see Open questions in [datajud-api.md](datajud-api.md)). Report the link state explicitly: `case-found`, `case-not-in-datajud`, `date-matched` or `date-unmatched`, rather than assuming a match.
- The DJEN response carries party names and OAB numbers: filter them out of any cached or returned payload unless the tool contract explicitly needs them.

## Open questions

1. Why are some DJEN cases (TJRS, TJDFT in the sample) absent from DataJud? Needs a larger sample per court and a check for sealed levels (`nivelSigilo`).
2. How long is the typical DataJud lag after the DJEN disponibilização, per court? Needs repeated probes over several dates.
3. TRF2, TRF4, TRF5, TRF6, the other TRTs and TJs were not sampled.
4. The DJEN API has no documentation read here; its contract (pagination, rate limit, terms of use) is a separate research item.
5. Whether the `terms` count inconsistency for TJSP is a partial result or an index quirk was not determined.
