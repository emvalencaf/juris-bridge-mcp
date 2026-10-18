# Research: CNJ number to DataJud alias, and the `search_after` tiebreaker

Resolves issue #13 (part of map #1). Researched 2026-10-17/18. Primary sources and live probes only:

- [R] CNJ Resolution 65/2008 as compiled on the CNJ acts portal (includes Res. 223/2016 and Res. 477/2022): <https://atos.cnj.jus.br/atos/detalhar/119>. The annex tables (Anexos I-VII) are images on that page and could not be read, so the code lists below come from article 1, paragraphs 4 and 5, plus the live checks.
- [W] DataJud wiki, `endpoints` and `acesso` pages: <https://datajud-wiki.cnj.jus.br/api-publica/endpoints/>.
- [L] Live calls to `api-publica.datajud.cnj.jus.br` with the wiki's public key. Observations, not documentation. About 200 calls in total, at most one every 1.2 s, sizes of 1 to 2,000 hits, `_source` restricted to `numeroProcesso`, `tribunal`, `grau` (no party data exists in DataJud anyway). The key is not recorded here.

Portuguese terms: "tribunal" = court, "grau" = instance (`G1` first instance, `G2` appeal, `JE` special court, `TR` appeals panel, `SUP` superior court), "recurso" = appeal.

## Summary

1. **Mapping is a clean rule for the regional courts, with three exceptions.** `J.TR` determines the alias for TRF, TRT, TRE, TJ and TJM courts (88 of the 91 wiki aliases). Verified for all 91 aliases: a sample hit from each index carried the `J.TR` the resolution predicts. The exceptions are: (a) the wiki's `api_publica_tre-dft` does not exist, the working alias is `api_publica_tre-df`; (b) the four superior-court indices (`tst`, `tse`, `stj`, `stm`) hold cases whose numbers belong to other courts, so a number cannot be routed to them by `J.TR`; (c) STF and CNJ have no alias, and the Military Justice of the Union uses one alias (`stm`) for TR 01-12.
2. **Do not derive the alias from the number alone for appeals.** A case that reached a superior court keeps its origin number (CNJ Res. 65 art. 4 par. 4 only numbers original proceedings; confirmed in the data: STJ, TST, TSE and STM indices are full of `8.26`, `5.02`, `6.26`, `7.01` numbers). The number gives the origin court; the superior court needs a separate lookup.
3. **`sort: [@timestamp, _id]` fails**, `_id` fielddata is disabled on the cluster. **`[@timestamp, id.keyword]` works** and paged without skipping or repeating. `numeroProcesso.keyword` also works but is a weaker tiebreaker.
4. **`@timestamp` alone is not safe.** It has ties, and a size-1 walk across a tie skipped a hit.

## 1. CNJ number structure (Resolution 65/2008)

Format `NNNNNNN-DD.AAAA.J.TR.OOOO`, 20 digits. [R art. 1]

| Field | Digits | Meaning | Source |
|---|---|---|---|
| `NNNNNNN` | 7 | sequence per origin unit, restarts every year | R art. 1 par. 1 |
| `DD` | 2 | check digits, ISO 7064 mod 97 base 10 (Anexo VIII) | R art. 1 par. 2 |
| `AAAA` | 4 | filing year | R art. 1 par. 3 |
| `J` | 1 | segment | R art. 1 par. 4 |
| `TR` | 2 | court within the segment | R art. 1 par. 5 |
| `OOOO` | 4 | origin unit (subsection, labor court, electoral zone, forum, ...) | R art. 1 par. 6 |

`J` values: 1 STF, 2 CNJ, 3 STJ, 4 Federal Justice, 5 Labor Justice, 6 Electoral Justice, 7 Military Justice of the Union, 8 State and DF/Territories Justice, 9 State Military Justice. [R art. 1 par. 4]

`TR` rules [R art. 1 par. 5]:

- Original proceedings of STF, CNJ, STJ, TST, TSE and STM: `TR = 00`.
- Original proceedings of the Council of Federal Justice (CJF) and the Superior Council of Labor Justice (CSJT): `TR = 90`.
- Federal: 01-06 (TRF1-TRF6; the sixth was added by Res. 477/2022).
- Labor: 01-24 (TRT1-TRT24).
- Electoral: 01-27, one per state plus DF, alphabetical.
- Military Justice of the Union: 01-12 are Judiciary Circumscriptions, not courts. STM is the only appellate court.
- State Justice: 01-27, states and DF, alphabetical.
- State Military Justice: only Minas Gerais = 13, Rio Grande do Sul = 21, Sao Paulo = 26, "following the alphabetical order" of the electoral and state lists.

The check digit can be validated locally: `DD = 98 - (int(NNNNNNN + AAAA + J + TR + OOOO + "00") mod 97)`. Checked on the sample number in `docs/research/datajud-api.md` (`0000832-35.2018.4.01.3202`, DD 35, valid). Useful to reject typos before calling the API (my formula, matches the Anexo VIII description "mod 97 base 10"; the annex text itself was not readable).

Alphabetical order in the resolution is by state name with the exceptions visible in the live data, so use the table below rather than recomputing it: e.g. Sergipe is 25 and Sao Paulo is 26.

## 2. `J.TR` to alias table

Alias = `api_publica_<code>`, endpoint `https://api-publica.datajud.cnj.jus.br/<alias>/_search`. Every row marked verified: a live `size:1` hit from that index had the stated `J.TR` and `tribunal` value. [L]

### Rule

| J | TR | Alias code | Verified |
|---|---|---|---|
| 4 | 01-06 | `trf1` ... `trf6` | yes |
| 5 | 01-24 | `trt1` ... `trt24` (no zero padding in alias, `trt1` not `trt01`) | yes |
| 6 | 01-27 | `tre-<uf>` per table below | yes, 26 of 27 as listed on wiki; DF differs |
| 8 | 01-27 | `tj<uf>` per table below | yes |
| 9 | 13 / 21 / 26 | `tjmmg` / `tjmrs` / `tjmsp` | yes |

### State code table (same TR for J=6 and J=8)

| TR | UF | TR | UF | TR | UF |
|---|---|---|---|---|---|
| 01 | ac | 10 | ma | 19 | rj |
| 02 | al | 11 | mt | 20 | rn |
| 03 | ap | 12 | ms | 21 | rs |
| 04 | am | 13 | mg | 22 | ro |
| 05 | ba | 14 | pa | 23 | rr |
| 06 | ce | 15 | pb | 24 | sc |
| 07 | df | 16 | pr | 25 | se |
| 08 | es | 17 | pe | 26 | sp |
| 09 | go | 18 | pi | 27 | to |

For J=8 with TR 07 the alias is `tjdft` (not `tjdf`); for J=6 with TR 07 it is `tre-df` (see exceptions). Everything else is `tj<uf>` and `tre-<uf>`.

### Exceptions and oddities

| Case | Finding | Evidence |
|---|---|---|
| TRE-DF alias | Wiki lists `api_publica_tre-dft`; that index does not exist. HTTP 404, `index_not_found_exception`, `no such index [api_publica_tre-dft]`. The working alias is `api_publica_tre-df`, `tribunal` = `TRE-DF`, sample number `J.TR = 6.07`. `tre-dfe` also 404. | [W], [L] |
| Superior courts `tst`, `tse`, `stj`, `stm` | Their indices contain origin-court numbers. In a 100-hit sample: TST was mostly `5.02`, `5.04`, `5.15`, `5.01` (TRT origins); TSE `6.00`, `6.06`, `6.26`; STJ `8.26`, `3.00`, `4.04`, `8.16`; STM `7.01`, `7.03`, `7.12`. `grau` is `SUP` for TST/TSE/STJ. A number with `J.TR` of a TRT or TJ may therefore be found both in the regional index and in a superior index. Own originals use `TR = 00` (`3.00` STJ, `6.00` TSE, `7.00` STM; TST `5.00` not in the sample but implied by R par. 5 I). | [L], [R] |
| STF (`1.00`) and CNJ (`2.00`) | No DataJud alias on the wiki. | [W] |
| CJF (`TR 90`) and CSJT (`TR 90`) | Resolution gives `TR = 90` only; the segment digits are not stated, presumably 4 and 5. No alias. | [R], inference |
| Military Justice of the Union (`J=7`) | TR 01-12 are circumscriptions; DataJud has the single alias `stm` (sample hits `7.01`...`7.12` live in it). Route all `J=7` to `stm`. | [R], [L] |
| TRE-BA label | Wiki labels the TRE-BA row "Tribunal de Justica da Bahia"; alias is correct (`tre-ba`, `6.05`). | [W], [L] |
| Wiki alias count | 91 aliases listed: 4 superior, 6 TRF, 27 TJ, 24 TRT, 27 TRE, 3 TJM. 90 work; `tre-dft` does not. | [W], [L] |
| Unknown alias response | HTTP 404, body `{"error":{"root_cause":[{"type":"index_not_found_exception",...}]},"status":404}`. | [L] |
| Auth failure response | HTTP 401 `security_exception` when the header is missing (already in `datajud-api.md`). The key also lacks index-metadata privileges: `GET /<alias>/_mapping` returns HTTP 403 `indices:admin/mappings/get is unauthorized`, so field types cannot be introspected. | [L] |

### Implications for the tool contract

- A `get_case(number)` tool can derive the first alias from `J.TR` for `J` in 4, 5, 6, 8, 9, and `7` (route to `stm`). It must treat `J=1`, `J=2` and `TR=90` as "no DataJud source".
- A number is not enough to find appeals at superior courts; those need a second query against `tst`/`stj`/`tse`/`stm` with the same `numeroProcesso`. Whether to expose that is a contract decision.
- Ship the alias table as a static allowlist (as the map already suggests) and test it against the wiki list; keep `tre-df` as a documented override of the wiki's `tre-dft`. A drift check can re-run the `size:1` probe.
- `numeroProcesso` in the index is the 20 digits without punctuation, so the adapter strips `-` and `.` from user input. Validate length and `DD` first.

## 3. `search_after` tiebreaker

### What works and what does not

All on `api_publica_tre-ac` (and `tjdft` for the tie statistics), `size` 1 to 2,000. [L]

| Sort | Result |
|---|---|
| `[{"@timestamp":"asc"},{"_id":"asc"}]` | HTTP 400 `illegal_argument_exception`: `Fielddata access on the _id field is disallowed, you can re-enable it by updating the dynamic cluster setting: indices.id_field_data.enabled`. |
| `[{"@timestamp":"asc"},{"numeroProcesso":"asc"}]` | HTTP 400 `illegal_argument_exception`: `Fielddata is disabled on [numeroProcesso] ... Please use a keyword field instead.` So `numeroProcesso` is a `text` field with a keyword sub-field. |
| `[{"@timestamp":"asc"},{"numeroProcesso.keyword":"asc"}]` | Works. Returns `sort: [<epoch ms>, "<20-digit number>"]`. |
| `[{"@timestamp":"asc"},{"id.keyword":"asc"}]` | Works. Returns `sort: [<epoch ms>, "<id>"]`, and `sort[1]` equalled the hit's `_id` for all 4,000 hits checked (2,000 each on `tre-ac` and `tjdft`). |

`id` is the document key string, e.g. `TRE-AC_279_G2_78487_00000110320176010000` (tribunal, number, grau, organ, number pattern varies by court; the TRF1 example in `datajud-api.md` is `TRF1_JE_...`). It encodes the grau and organ, so it is unique per document. `numeroProcesso` alone is probably not unique per document because the same case number can exist in several instances; that was not measured, so treat `id.keyword` as the safer tiebreaker. `hits.total` is `{"value":10000,"relation":"gte"}` (track_total_hits default), so do not report totals.

### Tests

1. **Pages vs one big page.** 5 pages of 10 vs one page of 50, same sort, `tre-ac`: paged 50 hits, 50 unique, identical order to the single page, for each of `[@timestamp, numeroProcesso.keyword]`, `[@timestamp]`, and `[id.keyword]` (2 pages of 10 vs 20). No skips, no repeats.
2. **Tie frequency.** In 2,000 hits sorted by `[@timestamp, id.keyword]`: `tre-ac` had 27 timestamps shared by two documents; `tjdft` had 4 shared (largest group 3). Ties exist but are rare in these samples. Larger or bulk-loaded indices may have more.
3. **Walking across a tie with page size 1.** Starting right before a tied pair in `tre-ac`, three consecutive pages of size 1:
   - `[@timestamp]` only: **skipped one document** of the three expected. The second document of the tied pair was never returned, which is the documented Elasticsearch failure mode of `search_after` on a non-unique key.
   - `[@timestamp, id.keyword]`: returned all three, in the same order as the reference page, no repeat.
4. **Pages of 7 across a tie, 6 pages**, `tre-ac` and `tjdft`: all three sort variants returned 42 unique hits matching the reference page. The page boundary did not fall inside the tie, so this test does not discriminate; test 3 is the one that does.

### Recommendation

- Use `sort: [{"@timestamp":"asc"},{"id.keyword":"asc"}]` and pass the last hit's whole `sort` array as `search_after`. Wrap it in an opaque cursor as the map plans. Make the cursor carry the alias too, since the sort values are only valid against the same index.
- Do not use `_id`. Do not rely on `@timestamp` alone.
- Pass `"_source"` filtering when only identifiers are needed; a size-2000 page with sort took 8-13 s in these probes, a size-1 page about 1-2 s.
- Not tested: point-in-time (PIT) pagination (would give a stable snapshot but is probably blocked like `_mapping`), behavior when the index is updated between pages (`@timestamp` is the index-update time, so a reindexed case can move; `search_after` pages can then miss or repeat it), and `sort` on `id.keyword` for every court. Field mappings may differ per court; run the same probe for any court added to the allowlist.

## Open questions

1. Annexes I-VII of Res. 65/2008 are images on the CNJ page; the `TR` lists were confirmed against live data instead of the annex. Obtain the official PDF if an authoritative citation per code is needed.
2. Segment digit for CJF and CSJT (`TR 90`) and whether any DataJud index holds them.
3. Do duplicates of `numeroProcesso` exist within one index (several `grau`)? Decides whether `numeroProcesso.keyword` is ever sufficient. Not measured.
4. Why `tre-dft` is listed on the wiki but absent; ask the CNJ or watch for a fix, and keep the override until then.
