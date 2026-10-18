# PROTOTYPE: article extraction from Câmara Legin HTML (throwaway)

Wayfinder ticket: "Prototype: article-level extraction from Câmara Legin HTML". Lives only
on a throwaway `prototype/*` branch, never merged. Builds on the Planalto prototype
(`PROTOTYPE_planalto_base.py`, copied from `prototype/planalto-article-extraction`).

Run: `PYTHONPATH=. python3 PROTOTYPE_extract.py <dir> [key article ...]` where `<dir>` holds
`<key>.htm` (or `<key>.docx`) and `<key>_meta.html` (Dados da Norma). Fixtures are not committed.

## Fetching (2026-10-18, Mozilla-compatible honest UA, 1 req/s)

1. LexML URN page (`https://www.lexml.gov.br/urn/urn:lex:br:federal:lei:1990-09-11;8078`)
   lists the Legin `...-<id>-norma-<origin>.html` link. This is how the internal id is obtained.
2. Metadata page `...-norma-pl.html` links the consolidated variant; the same stem with
   `-normaatualizada-pl.html|.docx|.pdf` also works directly once the id is known.
3. Validate the body (Legin answers HTTP 200 with a 160-byte `504 Gateway Time-out` body).

## Results (7 norms, article set vs the last numbered article)

| Norm | Source used | Keys | Last art. | Missing base numbers |
|---|---|---|---|---|
| CDC | HTML | 131 (12 -A/-B) | 119 | 0 |
| Lei 14.133 | **DOCX** (HTML 504 on 3 tries, again) | 196 | 194 | 0 |
| Código Civil | HTML | 2093 | 2046 | 0 |
| CF/88 | HTML | 276 | 250 | 0 |
| Lei 8.666 | HTML | 128 | 126 | 0 |
| Lei 9.784 | HTML | 80 | 70 | 0 |
| Decreto 10.024/2019 | **none** | - | - | Legin has no "Texto Atualizado", only the original publication |

Planalto vs Legin on the 4 norms both could serve (CDC, 8.666, 9.784, CC; same extractor core):
same article key sets (differences: 1 extra key on CDC and on CC, from range/ADCT handling).
Of the common non-revoked articles, caput text is equal after stripping remarks and case in all but
a handful: the differences are typographic (`5°` vs `5º`), a Planalto typo ("com a indicações"),
and Planalto's superseded text in the fully revoked Lei 8.666 (Legin has no struck-through text at all).

## What differs from Planalto (failure modes)

1. **Revoked ranges**: `Arts. 89 a 99. (Revogados ...)` (plural, no `Art.`), found in CC and Lei 8.666. Fixed
   with a range pattern (Planalto's was `Art. 1.620. a 1.629.`).
2. **Quoted articles of other norms** (Lei 14.133 Arts. 337-E..P): Legin HTML/DOCX has no `<a href>`
   anchors to detect them (12 phantom articles, same as Planalto). Fixed with a numeric-continuity guard
   (accept a base number only within [top-1, top+25]). The guard also correctly drops the CF's ADCT
   `-A/-B` articles (9 keys that would otherwise leak in as main text).
3. **No superseded redactions**: nothing is struck through, so the stale-text trap does not exist.
4. **Remark shape varies by norm**: CC/CF/Lei 8.666 keep inline remarks and revoked stubs in Legin
   wording (`(“Caput” do artigo revogado pela ...)`, `(Inciso acrescido pela ...)`,
   `(Artigo acrescido ... e revogado pela ...)`); CDC and Lei 9.784 carry fewer. A revoked-stub regex
   must accept `revogad[oa]s?` anywhere inside the parentheses. A `“Caput” ... revogado` remark revokes only the
   caput, not the parágrafos: a flag `revoked` at article level is too coarse.
5. **Metadata page** lists `Norm - (Relation). Art. X, ... ;` per amending/regulating norm, with article
   references. Parsed with a `<li><a>` regex: CDC 30 article keys, CF 190, CC 146, Lei 8.666 58, Lei 14.133 26.
   Relations are free text ("Alteração", "Regulamentação", "Acréscimo de Parágrafo Único", "Mantém veto"):
   useful as `amended_by`/`regulated_by` hints, not as a reliable `revoked`/`superseded` boolean.
6. **Same inherent limits as Planalto**: ADCT/annex number reuse, flat sub-item lists, tables untested.
7. **Availability**: Lei 14.133 HTML returned the 504 body in every attempt (3 now, 3 in the research);
   only the DOCX (stdlib `zipfile` + `word/document.xml`) worked. Decrees: no consolidated variant.

## Verdict

Viable fallback for consolidated statutes and the Constitution, with the Planalto slicer plus
three Legin changes (range heading, remark regex, continuity guard). Not a fallback for decrees
that Legin has no consolidated text for, and not a source of reliable `revoked`/`superseded` flags
beyond what the text remarks already say.
