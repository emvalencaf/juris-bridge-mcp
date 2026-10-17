# Research: LexML Brasil access (issue #3)

Part of #1. Researched 2026-10-17 against primary sources only. Where a primary
source could not be reached, the gap is stated instead of filled from memory or
third-party write-ups.

## Summary

- LexML exposes a search web service that follows the SRU (Search/Retrieval via
  URL) standard and returns XML. Source: Senado Federal open-data page,
  <https://www12.senado.leg.br/dados-abertos/legislativo/legislacao/acervo-do-portal-lexml>.
- The documentation pages on that Senado site do not hold the spec: each
  sub-page answers with an HTTP 302 redirect (to loc.gov/standards/sru, to the
  endpoint, or to the portal home). There is no official LexML page listing
  CQL indexes, record schemas, limits or terms of use that we could reach.
- The live endpoint is currently behind an anti-bot interstitial, which is the
  most important finding for our adapter (see Stability).
- The identifier scheme (LexML URN, "URN LEX" Brazilian profile) is fully
  specified in the official LexML document "Parte 2 - LexML URN".

## Endpoint and protocol

| Item | Finding | Source |
|---|---|---|
| Protocol | SRU, queried by URL, XML response | Senado open-data page above |
| Endpoint | `http://www.lexml.gov.br/busca/SRU` (the "Webservice do acervo" sub-page redirects here) | 302 `Location` from `.../webservice-do-acervo-do-portal-lexml` |
| Official usage example | `http://www.lexml.gov.br/busca/SRU?operation=searchRetrieve&query=urn+=%22senado.federal+pls+2008%22` (`urn` is therefore a CQL index; the value is a URN fragment, not a full URN) | 302 `Location` from `.../exemplo-de-utilizacao-do-webservice-do-portal-lexml` |
| SRU standard | Operations and parameters as defined by the Library of Congress SRU spec; the "Documentacao do Webservice" sub-page redirects to <http://www.loc.gov/standards/sru/> | 302 `Location` from `.../documentacao-do-webservice-do-portal-lexml` |
| Search UI | `https://www.lexml.gov.br/` (the "pagina de pesquisa" sub-page redirects here) | 302 `Location` |

## Query syntax, indexes, returned fields, limits

NOT VERIFIED from a primary source. We could not retrieve:

- the `explain` response (list of CQL indexes/context sets, supported
  `recordSchema` values, default and maximum `maximumRecords`);
- a real `searchRetrieve` response (record fields such as title, date, type,
  locality, authority, PDF/text links).

Reason: both `operation=explain` and `operation=searchRetrieve` returned the
anti-bot page (below) to our clients. The only index confirmed by an official
artifact is `urn`. Standard SRU/CQL grammar (operation, version, query,
startRecord, maximumRecords, recordSchema) is defined by the Library of
Congress: <https://www.loc.gov/standards/sru/>. Also checked: the
`projeto.lexml.gov.br` Downloads page lists only a CSJT resolution and the "Kit
Provedor de Dados 3.4.3" (database schema installer, validator and OAI-PMH
server for data providers); there is no published SRU manual there
(<https://projeto.lexml.gov.br/downloads>). The FAQ mentions only a "Manual de
Pesquisa" (end-user search manual) (<https://projeto.lexml.gov.br/faq>).

Follow-up needed (a human, or a network that passes the challenge): run
`explain` and a sample `searchRetrieve` from a normal browser or the
deployment network and record the real XML as a contract-test fixture.

## Coverage: legislation vs case law

- The portal is described by the Senado as a single search for legal norms,
  bills, case law (jurisprudencia), doctrine and related documents (Senado
  open-data page). The FAQ confirms the search can be limited to "Legislacao,
  Jurisprudencia e Proposicoes Legislativas"
  (<https://projeto.lexml.gov.br/faq>).
- The per-court list of institutions and document types lives on the portal's
  "Acervo" page; `https://www.lexml.gov.br/acervo` returned HTTP 404, so
  per-court coverage is NOT VERIFIED.
- The LexML URN profile reserves a case-law document type
  (`<tipo-jurisprudencia>`) and judicial jurisdictions (e.g.
  `br;justica.federal;regiao.1;secao.judiciaria;goias`,
  `br;justica.trabalho;regiao.13`), so case law is representable, but this
  does not prove which courts actually feed the index.
- Data enters LexML from providers via OAI-PMH (the project ships an OAI-PMH
  data-provider kit: <https://projeto.lexml.gov.br/downloads>). Case-law
  coverage therefore depends on each court's provider; treat it as partial and
  uneven (inference, not a stated fact). Metadata records do not guarantee
  full text.

## URN LEX (LexML URN) - identifier format

Source: official LexML Brasil "Parte 2 - LexML URN", v1.0 RC1, Dec 2008,
<https://projeto.lexml.gov.br/documentacao/Parte-2-LexML-URN.pdf>.

- Form: `urn:lex:br:<autoridade>:<tipo>:<data>;<numero>` plus optional
  `@<versao>` (version), `~<forma>` (form) and `!<fragmento>` (fragment, e.g.
  an article).
- `<local>` examples: `br`, `br;sao.paulo`, `br;sao.paulo;campinas`,
  `br;justica.trabalho;regiao.13`, `br;justica.eleitoral;paraiba`.
- The representative date is the signature date for norms and the judgment date
  for rulings; a year alone is allowed in the canonical URN; multiple values
  are separated by `,`.
- Examples from the document: `urn:lex:br:federal:lei:lei.maria.penha`
  (alias form), `urn:lex:br:federal:decreto:1999-12-21;seq-sf-32`.
- The generic URN LEX syntax is also published as RFC 9676 (May 2025,
  Independent Submission, Informational):
  <https://datatracker.ietf.org/doc/draft-spinosa-urn-lex/>. The Brazilian
  profile above is the one LexML uses.

## Terms of use / license

NOT FOUND in any reachable primary page. Observations only:

- The Senado publishes the LexML acervo under its open-data section, and a
  "Dados Abertos" group exists at <http://dadosabertos.senado.gov.br/group/lexml>
  (linked from the project site); its license was not read.
- LexML software repositories under <https://github.com/lexml> are GPL-2.0 or
  GPL-3.0; that licenses the code, not the data.

Action: confirm the data license and rate-limit policy with the Senado before
launch.

## Stability

- Both `http://www.lexml.gov.br/busca/SRU...` and
  `https://www.lexml.gov.br/busca/SRU...` returned a "Verificacao de seguranca -
  Senado Federal" proof-of-work interstitial (HTML form posting to
  `/_challenge`, "Verificando sua conexao") instead of XML, for `curl` with a
  browser User-Agent and for a fetch tool. As of 2026-10-17 a plain HTTP client
  does not get SRU XML from at least some networks.
- The documentation URLs on `www12.senado.leg.br` are bare redirects, and the
  spec document is dated 2008: documentation is sparse and old.
- Consequences for design: the adapter must treat non-XML / challenge responses
  as a distinct error ("upstream blocked"), cache aggressively and back off;
  contract tests must use recorded fixtures (already the plan in #1). Whether
  the challenge also applies to AWS `sa-east-1` egress is unknown and must be
  tested.

## Open questions (for the plan)

1. Real index list and record schema (explain + sample responses).
2. Whether server-side clients can pass the anti-bot challenge, or whether the
   Senado offers an allowlist or API key.
3. Data license and rate limits.
4. Which courts actually appear in the index (check the portal Acervo page from
   a browser).

## Sources

- <https://www12.senado.leg.br/dados-abertos/legislativo/legislacao/acervo-do-portal-lexml> (and its four sub-pages, via redirects)
- <https://projeto.lexml.gov.br/documentacao/Parte-2-LexML-URN.pdf>
- <https://projeto.lexml.gov.br/downloads>, <https://projeto.lexml.gov.br/faq>
- <https://www.loc.gov/standards/sru/>
- <https://datatracker.ietf.org/doc/draft-spinosa-urn-lex/> (RFC 9676)
- <https://github.com/lexml>
