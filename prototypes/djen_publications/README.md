# PROTOTYPE: DJEN Publication search end to end (throwaway)

Wayfinder ticket #62 (child of map #53). Lives only on the throwaway
`prototype/djen-publications` branch and is never merged.

Question: can the DJEN support the Publication search as designed (v1: court,
period, free text; decisões and acórdãos selected on our side), and where does it break?

Run (stdlib only; raw output stays outside the repo, it contains party names):

    python3 -I PROTOTYPE_probe.py search <out.jsonl> "prescrição" TJSP,STJ,TRF4 2026-10-13 2026-10-14
    python3 -I PROTOTYPE_probe.py report <out.jsonl>     # aggregates only
    python3 -I PROTOTYPE_probe.py sample <out.jsonl> 30  # hand-check; do not commit the output
    python3 -I PROTOTYPE_probe.py limits                 # paging/cap/rate probes

Probes ran 2026-10-18, read-only GETs, >= 1.5 s apart, no key, honest
Mozilla-compatible UA, ~130 requests in total, no 429 seen. Nothing but aggregates
is committed. Run: topic "prescrição", TJSP + STJ + TRF4, 2026-10-13..14, sliced court x day
(23 requests, 1987 items, median 0.5 s, max 1.9 s).

## What works

- **Court + day slicing with free text works and `count` is a real total below the cap.**
  STJ 226 / 133, TRF4 217 / 211, TJSP 3401 on one day; the cap marker is `count == 10000` exactly.
  (Earlier research read `count` as always capped; true only for busy court-days.)
- **`texto` is phrase-like:** `prescrição intercorrente` and the quoted form both returned 29 on STJ one day
  (vs 226 for `prescrição`). A nonsense term returns `count=0`, no error. Not verified: stemming, accents, OR.
- **`orgaoId` is a working extra slice axis** (TJSP 10-13: 155 distinct órgãos in a 600-item sample; one órgão = 213 hits).
  Items have no duplicate `id` or `hash` across the run.
- **CNJ numbers match DataJud cleanly:** 1951 distinct `numero_processo`, all 20 digits and
  all pass the CNJ check digit (mod 97); the masked form `numeroprocessocommascara` is present on 100% of items.
  36 processes appear more than once (several publications of the same case). Matching is a plain key join.
- **Latency is fine:** 0.2-0.5 s for 5-100 items, 1-2 s for 1000 items.
- **Rate limit did not bind:** `x-ratelimit-limit: 20`, but `remaining` oscillated 16-19 (not a monotonic counter; likely per
  edge node) at 0.2 s spacing for 12 requests and never 429'd. Still design for 429 + 60 s backoff.

## Where it breaks

1. **Depth ceiling, undocumented, ~10-14k records.** At 100/page page 103 answers, page 120 is HTTP 500; at 1000/page
   page 12 answers, page 15 is HTTP 500. `itensPorPagina=1000` is accepted although the spec says 5 or 100.
   So a busy court-day (TJSP 10-13: `count=10000`) cannot be fully read even per day: needs `orgaoId`
   slicing (or a narrower phrase). STF is not a sender (HTTP 500).
2. **Order is neither by date nor relevance** (ids in no monotonic order). No ranking: "relevance" in the Publication
   search would be ours, or none. Page N+1 under a 10k+ result set is only safe inside the depth ceiling.
3. **`tipoDocumento` cannot classify on its own.** Live distribution:
   - TJSP: `Intimação` 85% (holds sentenças, decisões, despachos and boilerplate notices), `Intimação de acórdão` 6.5%,
     `Sentença` 3%, `Despacho` 3%, `Edital` 1.6%.
   - STJ: `DESPACHO / DECISÃO` 99% (a monocratic decisão, or a despacho; never says which).
   - TRF4: `Sentença` 98%.
   Only the text separates them. TJSP's boilerplate "Ficam as partes ... cientificados que o processo passará a tramitar
   no Eproc" is 38% of TJSP hits for "prescrição" (matches the case class "Prescrição e Decadência", not the topic).
4. **`texto` shape differs by court.** TJSP: plain text (HTML in only 5% of items), starts with `Processo <CNJ> - <classe> - <assunto>
   - <parties> - ...`. STJ and TRF4: 100% HTML tables/divs with party/advogado header before the body.
   Length (plain chars) median / p90 / max: TJSP 1.6k / 5.4k / 29k; STJ 12.8k / 27k / 68k; TRF4 1.4k / 2.9k / 10k.
   STJ texts are full monocratic decisions (can be tens of thousands of chars: needs truncation/pagination in the tool output).
5. **Ementa is inline only where the court writes it in:** TJSP `Intimação de acórdão` carries `EMENTA:`; 104 of 359 STJ
   items contain the word "ementa" but they are decisões *quoting the lower court's ementa*, not acórdãos. TRF4: none.
   There is no structured ementa field.
6. **`link` is not always a per-document URL:** TJSP's `link` was just `https://esaj.tjsp.jus.br`.
7. **Personal data is in `texto` by design** (party and lawyer names, OAB numbers; some minors appear as initials).
   The contract must decide on truncation/redaction; the prototype never stores raw text in the repo.

## Classification accuracy (hand-checked)

Rule classifier `classify()` in the script: `tipoComunicacao` / `tipoDocumento` first, then text markers
(`EMENTA:`, dispositivo phrases such as "julgo procedente", "ante o exposto", notice boilerplate, "Vistos."), else `ambiguous`.

- v1 (word "ementa" = acórdão), 40 random items read by hand: 32 right (80%), 5 wrong (12.5%), 3 ambiguous (7.5%).
  Four of the five wrong were STJ decisões quoting an ementa classed as acórdão; fixed by requiring `EMENTA:` and not trusting
  it under a `DESPACHO/DECISÃO` label. The fifth was a TJSP despacho read as a decisão.
- v2, fresh 30 non-notice items read by hand: 22 right, 4 flagged `ambiguous` (two were a plural-regex bug, "procedentes", since
  fixed), 4 wrong, all on the same boundary: **despacho vs decisão interlocutória** (TJSP "Vistos. ... Defiro/declaro ..." read as despacho).
  Sentenças and monocratic decisões (TRF4, STJ, TJSP "Ante o exposto ... JULGO") were all right.
- Not measured: acórdão recall (only 82 TJSP and 1 STJ `EMENTA / ACORDÃO` in the sample; no TRF4), other courts, other topics.
- Takeaway: decisão/sentença/acórdão vs notice is reliably separable (about 90%+ here); despacho vs decisão interlocutória is
  not, and does not need to be for a jurisprudence-style search. Expect to carry a per-court rule table plus an `ambiguous` bucket.

## What the contract must absorb

- Input: court (required), period (day slices internally), text; optional `orgaoId`. A request is a *fan-out*: courts x days x pages.
- Output must say it is **not exhaustive** when any slice returned `count == 10000` or hit the depth ceiling, and must name which
  slices were truncated.
- Return a normalized `kind` (`acordao | decisao | despacho | notice | edital | ambiguous`) plus the raw `tipoDocumento`,
  never only ours; filter by kind on our side.
- Return `texto` as plain text (strip HTML, drop the party header), truncated with a length field; offer a way to fetch the rest.
- Return both CNJ forms; the key to DataJud is the 20-digit `numero_processo`.
- Cost of a realistic search: one court, one phrase, 7 days ~ 7-15 requests (about 10 s polite); three courts x 30 days ~ 100-300
  requests (several minutes). A busy-court week with a one-word query can exceed the depth ceiling and needs `orgaoId` slicing.
- Honour 429 with 60 s backoff; the limit did not bind at 4-5 req/s but is per-IP and undocumented in window length.

## Not done

Stability across days, caderno bulk download, the `certidao` endpoint, other courts than TJSP/STJ/TRF4, multi-word AND/OR semantics,
exact depth ceiling (only bracketed), whether the ceiling is per-query or per-IP.
