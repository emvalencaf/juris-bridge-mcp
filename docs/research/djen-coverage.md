# DJEN coverage by court, period and publication type

Resolves issue #57 (child of map #53). Probes run on 2026-10-18.

Legend: **[D]** documented in a primary source; **[O]** observed in a live read-only probe (reproducible, but may change); **[I]** inference.

## Answer in brief

1. The DJEN is the legally mandated replacement for every court's own DJe **[D]**, and the live API lists 99 distinct sender codes (119 entries, since TRFs repeat per UF): TRF1-TRF6, all 24 TRTs, TST, STJ, 26 TJs plus TJDFT, three military TJs, STM, CJF, SEEU, PJeCor, CNJ (dormant), and all 27 TREs plus TSE **[O]**.
2. Not every court is fully on it. Observed gaps: **STF is not a sender at all** (not in the sender list; queries by `siglaTribunal=STF` return HTTP 500), and the electoral courts are essentially absent (24 of 27 TREs had zero items in the sampled week; TRE-PR 194, TRE-MG 2, TRE-SP 3, TSE 5) **[O]**.
3. Start dates are staggered per court, not a single go-live. Everything before roughly late 2024 / early 2025 is sparse or absent for most courts (table below) **[O]**. The DJEN is therefore **not usable as a historical archive**; it is a going-forward feed for most courts.
4. Type field: `tipoComunicacao` is a small clean enum (Intimação, Edital, Lista de distribuição, Citação); `tipoDocumento` is free text, court-specific, and only partially distinguishes a decision from a despacho. Do not rely on it to classify without per-court normalization **[O]**.

## Primary sources

- CNJ Resolução n. 455/2022 (consolidated, as amended by Res. 624/2025): https://atos.cnj.jus.br/atos/detalhar/4509
  - Art. 11: DJEN, created by Res. 234/2016, is regulated by this act, is the CNJ's editais platform and the instrument for publishing judicial acts **[D]**.
  - Art. 12: "O DJEN substitui os atuais diários de justiça eletrônicos mantidos pelos órgãos do Poder Judiciário" **[D]**. §1 requires court, órgão julgador, unified case number, party names and OAB numbers in each intimação, on pain of nullity **[D]**.
  - Art. 13: what is published: (I) content of despachos, interlocutory decisions, the dispositivo of sentences and the ementa of acórdãos (CPC art. 205 §3); (II) intimações to lawyers in electronic systems that need no personal intimation; (III) distribution lists (CPC 285); (IV) editais; (V) other acts required by procedural law or court rules **[D]**.
  - Art. 14: publications must be digitally signed **[D]**.
- Live API (public, no auth for these reads): `https://comunicaapi.pje.jus.br/api/v1/comunicacao` (search) and `/api/v1/comunicacao/tribunal` (sender list). No public OpenAPI spec found (`/v3/api-docs` and `/swagger-ui/index.html` return 404) **[O]**, so all field semantics below are observed, not documented.
- Not found/verified here: CNJ's per-court migration schedule for the DJEN. Resolution text gives no per-court dates in the sections read **[I]**; the observed start dates below stand in for it.

## What the API returns **[O]**

Per item: `id`, `data_disponibilizacao`, `siglaTribunal`, `tipoComunicacao`, `nomeOrgao`, `numero_processo` (20 digits), `meio` (`D` = DJEN publication, `E` = edital), `tipoDocumento`, `nomeClasse`/`codigoClasse`, `texto` (HTML), `link` (court-hosted document, often with a hash), `destinatarios`, `destinatarioadvogados` (with OAB number/UF), `status`, `ativo`, cancellation fields.

Query behaviour **[O]**: `count` is capped at 10000 (it is a ceiling, not a true total, for any busy court-week). `itensPorPagina=1000` worked; page 101 at 100/page returned HTTP 500, so deep pagination fails and queries must be sliced by date and court. A malformed date also yields 500.

## Coverage table by court **[O]**

"Week count" = `count` for 2026-10-05..09 (10000 means capped). "First data" = earliest of the sampled one-week windows with count > 0; granularity is coarse (sampled weeks only), so true first dates are earlier or equal within the gaps stated. "Last send" is `dataUltimoEnvio` from the sender list.

| Group | Court(s) | Week count 2026-10-05..09 | First data (sampled) | Last send |
|---|---|---|---|---|
| Superior | STJ | 10000+ | 2024-12 (none 2024-09) | 2026-10-16 |
| Superior | TST | 10000+ | 2024-09 (none 2024-06) | 2026-10-16 |
| Superior | STM | 316 | 58 in 2025-04 week; zero in the March weeks of 2020-2025 | 2026-10-16 |
| Superior | TSE | 5 | only 1 item in sampled 2026-02 week | 2026-10-09 |
| Superior | **STF** | HTTP 500 | not a listed sender | n/a |
| Federal | TRF1 | 10000+ | 2021-03 (5.6k/wk in 2022) | 2026-10-16 |
| Federal | TRF2, TRF3, TRF4, TRF5 | 10000+ each | TRF3 2021-03; others: not individually sampled | 2026-10-16 |
| Federal | TRF6 | 10000+ | 2023-03 | 2026-10-16 |
| Federal | CJF | 2745 | 2022-03 | 2026-10-16 |
| State | TJSP | 10000+ | 2025-03 (none 2025-02-03, first sampled hit week of 2025-03-10; partial week of 03-24) | 2026-10-16 |
| State | TJRJ | 10000+ | 2024-12 (none 2024-09) | 2026-10-16 |
| State | TJMG | 10000+ | 2023-03 | 2026-10-16 |
| State | TJDFT | 10000+ | 2021 (139 in Jan 2021, 287 Jun 2021), then 59 in Mar 2022 and zero from 2022-09 through 2023-06, full from 2023-12 | 2026-10-16 |
| State | TJPR | 10000+ | 2021-03 | 2026-10-16 |
| State | TJRS | 10000+ | 2023-03 | 2026-10-16 |
| State | TJAC | 8726 | not sampled | 2026-10-16 |
| State | all other TJs (AL, AM, AP, BA, CE, ES, GO, MA, MS, MT, PA, PB, PE, PI, RN, RO, RR, SC, SE, TO) | 10000+ each | not sampled | see sender list |
| Military state | TJMMG / TJMRS / TJMSP | 288 / 156 / 352 | not sampled | see sender list |
| Labor | TRT2 | 10000+ | 2024-09 (none 2024-06) | 2026-10-16 |
| Labor | TRT20 / TRT22 | 9636 / 6548 | not sampled | see sender list |
| Labor | other 21 TRTs | 10000+ each | not sampled | see sender list |
| Electoral | TRE-PR | 194 | 2025-08 (none before in sampled weeks) | not recorded |
| Electoral | TRE-MG / TRE-SP | 2 / 3 | not sampled | see sender list |
| Electoral | 23 other TREs | 0 | none | TRE-AC last send 2026-08-03 |
| Cross-cutting | SEEU, PJeCor | 10000+ / 392 | not sampled | 2026-10-16 |
| Cross-cutting | CNJ | 0 | n/a (last send 2020-07-08) | 2020-07-08 |

Other observations **[O]**:
- Sender list: 119 entries (99 distinct codes) across 27 UFs plus a national group; only the CJF entry carries `active: true`, so that flag is not a usable health signal.
- Sampled weeks of 2026-04-01..05 returned zero for STJ, TST, TRT2 (Holy Week); likely a calendar effect **[I]**.
- "Is every court's DJe fully migrated?" Cannot be proven from the DJEN side. Positive evidence of coverage exists for STJ, TST, all TRTs, TRFs, 27 TJ-level senders. Negative evidence exists for STF and most TREs. Whether those courts still publish only in their own DJe was not checked against their own sites and remains **open**.

## Publication types and reliability

Normative scope **[D]**: despachos, decisões interlocutórias, dispositivo of sentences, ementa of acórdãos, intimações, distribution lists, editais. Note that for sentences and acórdãos only the dispositivo / ementa is required to be published, so DJEN text is not the full decision.

`tipoComunicacao` values seen **[O]**: `Intimação`, `Edital`, `Lista de distribuição`, `Citação`. `meio`: `D` (DJEN) or `E` (edital). Clean and consistent across courts.

`tipoDocumento` is **free text per court** **[O]**. Aggregated over the first 100 items of each court's sampled week (biased: results come back grouped, e.g. exactly 50/50 Edital vs other for TST/TRT2/SEEU, so counts are not frequency estimates):

| Seen value (examples) | Where | Maps to |
|---|---|---|
| `Sentença`, `Sentença Tipo A/B/C`, `Sentença Extinção Fiscal` | TRF1, TJs | decision (sentence) |
| `Acórdão`, `Ementa de Acórdão`, `EMENTA / ACORDÃO` | TRTs, STJ | decision (ruling) |
| `Decisão`, `DECISÃO INICIAL` | TRF1, others | decision |
| `DESPACHO/DECISÃO`, `DESPACHO / DECISÃO`, `DECISÃO/DESPACHO`, `Despacho_Intimação_Intimação (Outros)` | TJSP, TJRJ, STJ | **ambiguous**: decision and despacho in one label |
| `Despacho` | TST | despacho |
| `Ato ordinatório` | TJs, TRF1 | administrative act (not a decision) |
| `Intimação`, `Notificação`, `Intimação polo ativo`, `EXPEDIENTE`, `Vistas Diversas`, `VISTA à(s) parte(s)...` | TRFs, TRTs, STJ | notice |
| `Edital`, `EDITAL DE INTIMAÇÃO`, `Edital/Citação`, `Citação` | many | edital / citação |
| `Distribuição`, `DISTRIBUICAO DE PROCESSO`, `Outros` | TRTs, CJF, TJs | distribution list or unclassified |
| `Apelação`, `Agravo de Instrumento`, `Relatório (<name>)`, `87`, `Devedores`, `Outros` | assorted | **unreliable**: class names, person names, numeric codes, catch-all |

Reliability conclusions **[I, from the above]**:
- `tipoDocumento` can identify a decision/ruling when it contains Sentença, Acórdão/Ementa or Decisão, but the same field also holds class names, a person's name, numeric codes and `Outros`. Vocabulary and capitalization differ per court and drift within a court.
- The most common combined label in TJSP/TJRJ/STJ (`DESPACHO/DECISÃO`) cannot separate despacho from decision without reading `texto`.
- A usable classifier needs a per-court normalization table plus a text fallback. `nomeClasse`/`codigoClasse` describe the case class, not the act, and must not be used for act type.
- Items classified as `Intimação` by `tipoComunicacao` frequently carry a decision in `tipoDocumento` (e.g. `Intimação` + `Sentença`): the communication type describes the delivery, not the act.

## Implications for the map (#53)

- Do not promise historical search before about 2024-12 for superior/most state courts; plan for a per-court `since` date.
- STF requires another source (not the DJEN).
- Treat `count` as capped at 10000 and slice queries by court and day.
- Normalize `tipoDocumento` per court; keep the raw value alongside.

## Method and limits

Read-only GETs, one UA string, about 1 request/second, roughly 330 requests total, no authentication, no browser automation. Date sampling used 5-day windows at chosen anchors, so "first data" is bounded, not exact. One probe window (starting 2025-03-31) hit a malformed-date HTTP 500 (my error) and is excluded. Items sampled are the first page only. No document `texto` was stored or reproduced here; personal data in responses was not retained.
