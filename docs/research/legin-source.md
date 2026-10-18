# Research: Câmara Legin as an alternative legislation text source (issue #15)

Part of #1. Researched 2026-10-18 against the live Câmara servers only (no secondary
write-ups). Requests used the User-Agent
`Mozilla/5.0 (compatible; juris-bridge-mcp/0.1; +https://github.com/emvalencaf/juris-bridge-mcp)`,
one at a time with about 1 s spacing, 4 norm pages and 1 PDF in total. Findings are
**observed** unless marked otherwise.

## Summary

- **Verdict: prototype Legin (ticket #16), as the fallback behind Planalto.** It serves the
  **consolidated current text** ("Texto Atualizado") as static HTML, plus the original
  publication, with a plain-HTTPS, no-anti-bot, honest-User-Agent access path.
- The consolidated text is **clean**: amendments are applied silently, with **no inline
  `(Redação dada ...)` / `(Revogado)` markers** (0 occurrences in the CDC text, which was changed
  by Lei 14.181/2021). Amendments, revocations and vetoes are listed **per norm, with article
  references**, on the "Dados da Norma" page, not inside the text. Revoked/superseded flags
  at article level therefore cannot come from the Legin text alone.
- URLs contain an internal numeric id and **cannot be derived from a URN or a Senado record**
  without a lookup. There is no API or bulk download for norm text.
- The host `legislacao.camara.leg.br` named in the ticket **does not resolve in DNS**; the
  live Legin lives under `www2.camara.leg.br/legin/`.
- Risks: occasional **HTTP 200 with a `504 Gateway Time-out` body**, a site-wide stated policy
  against AI crawlers (not applicable to the `/legin/` host's robots.txt, see below), and no
  published terms or rate limits.

## What Legin is

Legin ("Legislação Informatizada") is the Câmara's norm archive, a static set of pages under
`https://www2.camara.leg.br/legin/`. The directory index returns `403 Forbidden`, so there is no
listing to crawl. The pages are the "Legislação Informatizada - Dados da Norma" view in the
Câmara portal (observed title and breadcrumb).

## URL patterns

All under `https://www2.camara.leg.br/legin/fed/<type>/<year>/`, filename
`<slug>-<id>-<variant>-<origin>.<ext>`:

| Page | Example (Lei 14.133/2021) | Observed |
|---|---|---|
| Dados da Norma (metadata page) | `lei-14133-1-abril-2021-791222-norma-pl.html` | 200, 62 KB, full portal page |
| Texto Atualizado (consolidated) | `lei-14133-1-abril-2021-791222-normaatualizada-pl.html` (also `.docx`, `.pdf`) | CDC: 200, 221 KB (82 KB of text); Lei 14.133 HTML: 200 status but a 160-byte `504 Gateway Time-out` body on 3 attempts (see failure modes); Lei 14.133 `.pdf`: 200, 412 KB |
| Original publication | `lei-8078-11-setembro-1990-365086-publicacaooriginal-1-pl.html` | 200, 124 KB |
| Vetoes, promulgation of vetoes | linked from the Dados da Norma page | not fetched |

- `<type>` seen: `lei`, `leicom`, `decret`, `medpro`, `int/portar` (links on the Dados da Norma page).
  `<origin>` suffix: `pl` (Poder Legislativo), `pe` (Poder Executivo), `dg-...` (Câmara bodies).
- `<id>` (791222 for Lei 14.133, 365086 for the CDC) is an internal sequence number. It is
  **not** the law number, so the URL is **not predictable** from a URN, a number or a year.
  The ids are discoverable from the links on the Dados da Norma pages (which list neighbouring
  norms) and from the LexML URN resolver page, which links to Legin (per
  `docs/research/legislation-access.md`).
- Once the `<id>` is known, the Dados da Norma page links to the consolidated variant by a
  relative `href` (observed), so one extra request resolves it.

## Consolidated or original?

Both are served, as separate pages. Evidence:

- The Dados da Norma page for Lei 14.133 links "Texto Atualizado (HTML) / docx / pdf" first, then
  "Texto - Publicação Original", "Veto" and "Promulgação de Vetos".
- The CDC consolidated page (`...365086-normaatualizada-pl.html`) is a LibreOffice export (meta
  `generator: LibreOffice 6.4.7.2`, `changed: 2026-09-28`) headed "CÂMARA DOS DEPUTADOS, Centro
  de Documentação e Informação". It contains Art. 54-A and Art. 104-A (added by Lei 14.181/2021,
  absent from the 1990 original) and ends with the original signature block.
- The original-publication page is a different file (`publicacaooriginal`).
- Currency: the CDC Dados da Norma page lists Medida Provisória 1.393 of 2026-09-25 as an
  "Alteração" (Art. 57) and a Decreto of 2026-10-09, and the Lei 14.133 PDF has
  `Last-Modified: 2026-07-21`. So updates are kept within weeks (CDC consolidated
  file changed 2026-09-28). I did not diff the Art. 57 text against the MP.
- Not verified: lag in general, and which article text applies when an MP is not yet converted.

## Amendments and revocations: where they are marked

- **In the consolidated text: not marked.** CDC consolidated text: 0 occurrences of
  `Redação dada`, `Incluído`, `Revogado`, `Vide` or `Vetado`. This differs from Planalto's
  compiled text, which keeps `(Redação dada pela Lei ...)` inline and `(Revogado)` stubs (the
  hooks the Planalto prototype used for revoked/superseded flags, see #14).
- **On the Dados da Norma page: marked per norm with article references.** Observed sections:
  "Situação" (Lei 14.133: "Não consta revogação expressa"), "Observação" (court decisions, such as
  the STF ADI 6.890 interpretation of Art. 75, VIII), "Veto" (per article: "Mantém Veto" /
  "Rejeita Veto") and "Vide Norma(s)" listing each amending or regulating norm with its
  relation and the affected articles, for example "Lei Ordinária nº 14181 de 1º de Julho de 2021
  (Alteração). Art. 4º, caput, incisos IX, X; ... Art. 54-A ..." and "(Acréscimo e Renumeração de
  Dispositivos)", "(Regulamentação)".
- Consequence for `get_legislation`: article text can be sliced from Legin, but article-level
  `revoked`/`superseded` flags would have to be derived from the metadata page's
  article references (coarse, free-form text) or taken from Planalto.

## Formats, API, bulk

- Formats for the consolidated text: HTML, DOCX, PDF. Original publication: HTML (PDF/docx
  variants not checked).
- No API for norm text. The Câmara open-data API (`dadosabertos.camara.leg.br/api/v2`) is about
  the legislative process (bills, deputies, votes) and does not model enacted laws (see
  `docs/research/legislation-access.md`).
- No bulk download or sitemap seen for `/legin/`; the directory listing is forbidden.
- Page quality: HTML is a LibreOffice export (inline styles, an embedded base64 header image,
  `<title></title>` empty), not semantic markup. The Dados da Norma page is the portal template
  plus a list. Both are static, no JavaScript needed for the text.

## Access behaviour

- User-Agent: the Mozilla-compatible honest UA above was accepted (200) on every request. I did
  not test a non-`Mozilla/5.0` UA, so whether Legin has the same prefix filter as Planalto is
  unknown.
- Anti-bot: none observed (no challenge, no cookies required, `server: envoy`).
- Failure mode: the Lei 14.133 `normaatualizada` HTML answered HTTP **200** with a 160-byte
  `504 Gateway Time-out` (nginx) body on three attempts over about a minute while its PDF
  answered normally and the CDC equivalent worked. An adapter must validate the body
  (size and a norm title) and not trust the status code.
- Rate limits: none published, none hit at about 1 request per second. Responses carry no
  rate-limit headers. `access-control-allow-origin: *` is set.
- DNS: `legislacao.camara.leg.br` (the host in the ticket) did not resolve. `www.camara.leg.br/legislacao`
  (the portal search page, 200) is the current entry point; `www2.camara.leg.br/legin/...` is
  the static archive host.

## robots.txt and terms

- `https://www2.camara.leg.br/robots.txt` (the host serving Legin): a single `User-Agent: *`
  group; disallows search/sendto/login/folder forms, `/agencia-app`, `/cota-parlametar$`,
  `/missao-oficial$`, a committee path and a long list of individual deputy-name paths. **Nothing
  disallows `/legin/`.** No `Crawl-delay`, no sitemap.
- `https://www.camara.leg.br/robots.txt` (the portal host, not the Legin host): its header comment says it
  blocks AI bots "to avoid the content being used to train AIs" and lists `GPTBot`, `anthropic-ai`,
  `Claude-Web`, `CCBot`, `PerplexityBot` and others in a group with a path-limited
  `Disallow` list (including `/*.pdf`); the `*` group has similar path-limited rules, plus
  `Crawl-delay: 10` for Bing/Yahoo. Our UA token `juris-bridge-mcp` matches none of the named
  bots, and on-demand retrieval is not training, but the stated intent is a signal to respect:
  keep the cache, the 1 req/s spacing and attribution, and do not crawl.
- Terms: no Legin-specific terms of use or license were found. The open-data principles page
  (`dadosabertos.camara.leg.br/howtouse/sobre-dados-abertos.html`) lists "Livres de licenças"
  (not subject to copyright, trademarks, patents) as a principle for the open-data catalogue, not
  a Legin clause. Norms themselves are public acts. Confirm with the Câmara before launch
  (already listed as open in `legislation-access.md`).

## Viability as second choice for article-level extraction

- For: consolidated current text, clean Portuguese, static, no anti-bot, no UA gate observed,
  PDF/DOCX alternatives, per-norm amendment metadata with article references (more structured than
  Planalto's inline remarks for "which norm changed Art. X").
- Against: URL needs an id lookup (one hop through the Dados da Norma page, which itself needs the
  id from LexML or Senado); no inline revoked/superseded marks; flaky 504-with-200 responses;
  LibreOffice HTML with no semantic article markup (slicing by `Art. N` regexes on text, plain
  paragraphs); no published terms.
- Recommended role: **fallback behind Planalto** when Planalto fails, with flags (`revoked`,
  `superseded`) degraded to "unknown" unless the metadata page maps them. This matches the
  fallback chain in ADR 0002 (Planalto, then Câmara Legin, then metadata and links only).

## Not verified

- Whether Legin rejects non-`Mozilla/5.0` User-Agents like Planalto (not tested on purpose).
- Hit rate of article slicing on the target norms (CF/88, Lei 8.666, Lei 9.784, Código Civil, a
  decree): not fetched, left to prototype #16. Only the CDC consolidated HTML was parsed here.
- Whether revoked articles survive as stubs in the consolidated text (the CDC has none).
- A reliable way to get the `<id>` from a URN or Senado record without LexML (the Senado `urn`
  response fields were not inspected for a Legin link).
- Update lag after a new amending norm, and the status of the `504` failures over time.
- Any Câmara terms of use for the static archive or an official rate limit.

## References

- <https://www2.camara.leg.br/legin/fed/lei/2021/lei-14133-1-abril-2021-791222-norma-pl.html>
- <https://www2.camara.leg.br/legin/fed/lei/2021/lei-14133-1-abril-2021-791222-normaatualizada-pl.pdf>
- <https://www2.camara.leg.br/legin/fed/lei/1990/lei-8078-11-setembro-1990-365086-norma-pl.html>
- <https://www2.camara.leg.br/legin/fed/lei/1990/lei-8078-11-setembro-1990-365086-normaatualizada-pl.html>
- <https://www2.camara.leg.br/legin/fed/lei/1990/lei-8078-11-setembro-1990-365086-publicacaooriginal-1-pl.html>
- <https://www2.camara.leg.br/robots.txt>, <https://www.camara.leg.br/robots.txt>
- <https://www.camara.leg.br/legislacao>
- <https://dadosabertos.camara.leg.br/howtouse/sobre-dados-abertos.html>
- Earlier notes: `docs/research/legislation-access.md`, `docs/adr/0002-self-hosted-datajud-no-browser-sources.md`
