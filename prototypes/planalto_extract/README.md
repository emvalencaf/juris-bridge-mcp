# PROTOTYPE: article extraction from Planalto HTML (throwaway)

Wayfinder ticket: "Prototype: article-level extraction from Planalto HTML". This
folder lives only on a throwaway `prototype/*` branch and is never merged.

Run: `python3 -I PROTOTYPE_extract.py <dir-with-*.htm> [norm article ...]`

Sample set (fetched 2026-10-18, one request per norm, 1 s apart): CDC (Lei 8.078,
compiled), Lei 14.133/2021, Código Civil (compilada), CF/88, Lei 8.666/1993
(fully revoked), Lei 9.784/1999, Decreto 10.139/2019.

## Fetching: User-Agent finding (contradicts an earlier assumption)

`www.planalto.gov.br` only answers clients whose User-Agent starts with
`Mozilla/5.0`. An honest `juris-bridge-mcp/0.1 (+url)` UA gets a connection reset
within ~0.3 s; `curl/…` and `python-requests/…` hang until timeout. A
`Mozilla/5.0 (compatible; juris-bridge-mcp/0.1; +<repo url>)` UA returns 200 in
~0.7 s. So "honest UA" must mean Mozilla-compatible with an identifying token.
URLs are not predictable (`ccivil_03/leis/l8078compilado.htm`,
`ccivil_03/_ato2019-2022/2021/lei/l14133.htm`, `.../2002/l10406compilada.htm`):
the Senado API record must supply the text URL.

## Results

Ground truth = the last numbered article of each norm. After three fixes
(below), the extracted article set matched it for all 7 norms:

| Norm | Article keys | Last art. | Missing base numbers |
|---|---|---|---|
| CDC | 130 (11 with -A/-B) | 119 | 0 |
| Lei 14.133 | 196 | 194 | 0 |
| Código Civil | 2092 | 2046 | 0 |
| CF/88 (permanent text) | 284 | 250 | 0 |
| Lei 8.666 | 128 | 126 | 0 |
| Lei 9.784 | 80 | 70 | 0 |
| Decreto 10.139 | 28 | 23 | 0 |

Extra keys are `-A`/`-B` articles and revoked-range expansions. Structure checks
by hand: CDC Art. 6 = 13 incisos + 1 parágrafo (exact); CF Art. 5 = 79 incisos
vs 78 expected (flat list, one misclassified line, not chased).
Not done: a full text-vs-gold comparison, so text fidelity is spot-checked only.

## Failure modes found (each fixed in ~5-15 lines, except the unfixable ones)

1. Revoked range heading `Art. 1.620. a 1.629. (Revogados…)` hid 9 articles. Fixed.
2. Amending articles quote other norms' articles (Lei 14.133 quotes Código Penal
   `Art. 337-E…`) and produced 12 phantom articles. Fixed by checking that the
   `Art.` link points to another file's `#art…` anchor.
3. Superseded redaction kept: Planalto shows old text struck through and the new
   text next to it, so first-occurrence returns stale text (Lei 14.133 Art. 191,
   Decreto 10.139: 12 articles). Fixed by preferring the non-struck duplicate.
4. My own ground truth for Lei 9.784 (80) was wrong, the law has 70 articles.
5. Not fixed, inherent: CF and any norm with ADCT/annex reuse article numbers
   (`article=5` is ambiguous: 159 CF keys have duplicate headings); sub-items are
   a flat list and nesting (inciso under § vs caput) is only derivable by order;
   amendment annotations live in links and trailing text, not in structured
   fields; tables were not exercised; a fully revoked norm (Lei 8.666) is
   struck through end to end, so the `struck` flag is the only revocation signal.
6. Câmara Legin (second choice) was not tested.

## Verdict

Reliable enough to be a first-class slicing mode for Planalto consolidated texts
(article location is exact on the sample; stale-redaction and quoted-article
traps are detectable), but not for sub-article precision beyond caput, § and
inciso. Return the article text plus `revoked` and `superseded` flags, and fall
back to the full text (or a not-found error) when the heading is ambiguous or
absent, rather than guessing.
