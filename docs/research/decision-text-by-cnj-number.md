# Research: fetching decision text by CNJ case number, beyond the DJEN

Researched 2026-10-21. Question: besides the DJEN, what other options exist to fetch the
text of judicial decisions given a CNJ-format case number (`NNNNNNN-DD.AAAA.J.TR.OOOO`)?
Output: a per-option record (what it returns, lookup by CNJ number, access, coverage, legal
limits, fit with ADR 0002 and 0006) and a recommendation.

Method: primary sources only (CNJ acts and wiki, the courts' own hosts, the STJ CKAN API,
and read-only probes of the DJEN). Sibling notes are not repeated; see
[datajud-api.md](datajud-api.md), [court-data-access.md](court-data-access.md) and
[djen-tribunal-endpoint.md](djen-tribunal-endpoint.md). Claims are tagged `[V]` verified on
2026-10-21, `[P]` already verified in a sibling note, or `[U]` unverified (do not treat as a
finding). Probes used an honest User-Agent, one request each, no captcha or challenge was
bypassed.

## Summary

| # | Option | Decision text? | Lookup by CNJ number? | Fit with ADR 0002 / 0006 |
|---|---|---|---|---|
| 0 | DJEN (baseline) | Yes, in `texto` (HTML) of each communication | Yes (`numeroProcesso`) [V] | In use |
| 1 | DataJud public API | No | Yes, but metadata only | In use, cannot help |
| 2 | STJ open data (CKAN) | Yes, full text of terminative decisions and judgments | No server-side lookup; bulk daily ZIPs | Compatible, STJ only |
| 3 | MNI SOAP / Escritorio Digital | Yes (documents) | Yes | Not fit: needs credentialed party or lawyer |
| 4 | Court public-consultation systems (PJe, eSAJ, eproc, Projudi) | Yes, by right (Res. 121/2010) | Yes in the UI | Excluded: captcha, robots, browser |
| 5 | Court case-law portals (STF, TST, STJ SCON, TRFs, TJs) | Yes (judgments) | Partly, per court | Excluded: robots/WAF; STJ via option 2 |
| 6 | CNJ BNP / Pangea | Binding precedents only | Not a case lookup | No documented API |
| 7 | Third-party aggregators | n/a | n/a | Out of scope (not primary) |

Bottom line: there is no second national, anonymous, machine-readable API that returns
decision text by CNJ number. The DJEN is the only one. The only compatible complement found
is the STJ CKAN open-data set, limited to STJ.

## 0. Baseline: what the DJEN gives, re-probed

- `GET https://comunicaapi.pje.jus.br/api/v1/comunicacao?numeroProcesso=<20 digits, no mask>`
  returned `count` 12 for a TJSP case (`10014651520248260219`), each item with `texto`
  (HTML, 550 to 3,500 characters), `tipoComunicacao` (`Intimação`, `Edital`),
  `siglaTribunal`, `numeroprocessocommascara`, `link` and `hash`. A TRF1 case from the
  DataJud examples returned `count` 0. Probes 2026-10-21. [V]
- So lookup by CNJ number works, but the `texto` is the content of each published
  communication. Whether it contains the decision text or only a notice varies by item
  (the sampled items were short); the project already classifies kinds (ADR 0006). The
  DJEN reaches only about 2021 onward and not STF or most TREs. [P: ADR 0006,
  djen-tribunal-endpoint.md]
- No Swagger/OpenAPI document was found at `/v3/api-docs` (404, 2026-10-21). [V]

## 1. DataJud public API

- What it returns: cover data and movements, with `complementosTabelados` per movement.
  Portaria CNJ 160/2020 lists exactly what the public API exposes: number, court, class,
  subjects, system, movements, "complementos dos movimentos nacionais, resguardados os dados
  das partes", and the judging body of each movement. It does not list documents or decision
  text, and states that the API will not contain cases in secrecy.
  Source: <https://atos.cnj.jus.br/atos/detalhar/3453> (read 2026-10-21). [V]
- The "complementos" are the TPU table complements of a movement (codes, descriptions,
  values), not free text of a decision. The glossary page of the wiki, re-fetched on
  2026-10-21, returned only 58 characters of text (page rendered client-side), so the
  field-level definition could not be re-read now; the field list in
  [datajud-api.md](datajud-api.md) (read 2026-10-17) shows no text field. [P]
- Lookup by CNJ number: yes (`match` on `numeroProcesso`). [P]
- Legal: Portaria 160/2020 as amended by Portaria 374 of 2026-08-14 now carries, in its own
  text, the ban on "modification, distribution, sale or any kind of commercial exploitation"
  of the data (par. 3) and the duty to cite CNJ and DataJud as source (par. 5). Previously
  this was only in the terms of use. [V, from the compiled act as served by atos.cnj.jus.br]
  Review `RESPONSIBLE_USE.md` against par. 5.
- Verdict: useful to resolve the court, class and movements of a number (and to learn that a
  "julgamento" or "sentenca" movement exists), never to get the text.

## 2. STJ open data (CKAN): `integras-de-decisoes-terminativas-e-acordaos-do-diario-da-justica`

- What it returns: full texts and metadata of terminative decisions and judgments
  published in the Diario da Justica, as a daily ZIP of texts, a JSON of metadata and a CSV
  data dictionary. Monocratic decisions are only those marked as terminative by the
  ministers' offices, in listed procedural classes (Agravo, Embargos de Declaracao,
  Recurso Extraordinario, Peticao, and others). Secret cases are excluded. Daily updates
  add the previous day's publication. The resource listing had 10,000 entries on
  2026-10-21 (the CKAN page cap; the real count is [U]), last modified 2026-10-09.
- Licence: `cc-by` (Creative Commons Atribuicao) in the CKAN metadata of this dataset,
  which resolves the "licence per dataset" gap in court-data-access.md for this dataset
  only. Publisher: Superior Tribunal de Justica.
  Source: <https://dadosabertos.web.stj.jus.br/api/3/action/package_show?id=integras-de-decisoes-terminativas-e-acordaos-do-diario-da-justica>
  (2026-10-21). [V]
- Lookup by CNJ number: no server-side search. The metadata JSON should carry the process
  number (the dictionary CSV was not read; [U]), so a lookup means downloading and
  scanning daily files, or ingesting them into an index. Without knowing the publication
  date this is a scan of the whole history.
- Access: no key; plain HTTPS. Coverage: STJ only, from the dataset's first file
  (2021-01-04 is the earliest file name seen) to yesterday.
- Fit: legitimate and official (ADR 0002 forbids only browser and scraping sources), but it
  is bulk data, so it needs ingestion or a date-guided on-demand fetch, which touches the
  "no persisted cache" stance in known-limits.md. A narrow, date-guided path is feasible:
  the DJEN gives the publication date of an STJ communication for the same number, then
  one daily ZIP is fetched. This is a design idea, not tested. [U]
- Related datasets on the same portal: `espelhos-de-acordaos-*` (judgment summaries per
  body). [P]

## 3. MNI (Modelo Nacional de Interoperabilidade) and Escritorio Digital

- What it is: SOAP interface between judicial systems, instituted by Resolucao Conjunta
  CNJ/CNMP 3/2013 (amended by CNJ Res. 456/2022). CNJ asks courts to implement version 2.2.2
  and at least `consultarAvisosPendentes`, `consultarTeorComunicacao` and
  `consultarProcesso`; the Escritorio Digital acts as a client "accessing remotely the case
  base of the court's electronic system".
  Source: <https://www.cnj.jus.br/integracao-para-os-tribunais/> (2026-10-21). [V]
- The CNJ-hosted WSDL and PDF guide linked from that page returned 404 on 2026-10-21, so
  `consultarProcesso`'s response (documents) is not re-verified here. [V that links are
  dead; the contents are U]
- Lookup by CNJ number: yes by design (`consultarProcesso` takes the number).
- Access: each court exposes its own endpoint after enrolment with CNJ and credentialing
  (the CNJ page asks the court for an email with its production MNI URL; a lawyer client
  needs the court's credentials; the TJMA publishes its own access manual per search
  results, not fetched [U]). Not anonymous.
- Fit: no. It serves authenticated lawyers and parties, outside a keyless public MCP, and
  fan-out over ~90 court endpoints with credentials per user is a different product. Park.
  Also in court-data-access.md section 6 ("not a candidate"). [P]

## 4. Court public-consultation systems (PJe, eSAJ, eproc, Projudi)

- Right of access: CNJ Resolution 121/2010, art. 1 and 2 make the "basic data" of a
  non-secret case freely available online to anyone without registration or proof of
  interest, and art. 2 lists "inteiro teor das decisoes, sentencas, votos e acordaos"
  (full text of decisions, sentences, votes and judgments) among them, together with number,
  class, subjects, party and lawyer names and movements. Art. 4 requires public consultation
  by number (and by party name, CPF/CNPJ, lawyer and OAB). The compiled text on
  atos.cnj.jus.br also shows an amendment dated 2026-10-08 (Res. 700) to art. 6 (certidoes);
  read it before citing article numbers.
  Source: <https://atos.cnj.jus.br/atos/detalhar/92> (2026-10-21). [V]
- Consequence: the text is legally public, but the Resolution gives a right of human access,
  not an API. It says nothing on automated access, terms of use or captcha.
- Probes of robots.txt on 2026-10-21, one request each:
  - `pje.trt2.jus.br/robots.txt`: `User-agent: *` / `Disallow: /`. [V]
  - `portal.stf.jus.br/robots.txt`: `Disallow: /processos` for all agents. [V] (This
    contrasts with the 403 seen on 2026-10-17 in court-data-access.md; the host now answers.)
  - `eproc1g.tjsp.jus.br/robots.txt` and `pje-consulta-publica.tjmg.jus.br/robots.txt`: 404
    (no robots file). [V]
  - `consultaunificadapje.tse.jus.br` ("Consulta Publica Unificada - PJe", it states it
    searches public cases across instances): `/robots.txt` served the SPA HTML, so no
    robots file. Its terms and whether it enforces captcha were not read. [U]
- Captcha and terms per system: not verified (needs a browser, which ADR 0002 excludes). [U]
- Fit: excluded by ADR 0002 and ADR 0006 ("no portal is scraped"). The text may be there
  legally, but there is no sanctioned machine path. Each stack is a separate adapter.

## 5. Court case-law search portals

- STF (`jurisprudencia.stf.jus.br`, SPA; `portal.stf.jus.br`): `/processos` disallowed. No
  official API or bulk download of full text was found; a search for Corte Aberta
  documentation found only third-party articles and the R package `courtsbr/stfstj` (not
  official, may be stale). [U: any STF open-data text dataset]
- TST (`jurisprudencia.tst.jus.br`): `robots.txt` is `Disallow: /` for all agents. [V]
- STJ SCON and TRF1: disallowed by robots and WAF, see court-data-access.md. [P] STJ text is
  reachable through option 2 instead.
- TRF4 and TJMG: partly allowed by robots, but still forms without a documented API. [P]
- Lookup by CNJ number: most portals search by free text or process number, and returned
  items are judgments (acordaos, some monocratic), not every decision in a case.
- Fit: excluded (ADR 0002). Revisit a court only if it publishes a documented API or bulk
  dataset; that is the pattern STJ follows.

## 6. CNJ Banco Nacional de Precedentes (BNP / Pangea)

- Created by Res. CNJ 444/2022 as a unified textual and statistical search of binding
  precedents (CPC art. 927); courts must send precedents (Portaria 116/2022). The relaunch
  announcement says it is public and integrated with about 60 bodies.
  Sources: <https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/justica-4-0/banco-nacional-de-precedentes-bnp/>
  and <https://www.cnj.jus.br/cnj-relanca-o-banco-nacional-de-precedentes-bnp/> (surfaced by
  search 2026-10-21, pages not opened). [U for details]
- No developer documentation or public API was found. It indexes precedents, not "the
  decisions of case X", so it is not a lookup by CNJ number.
- Searches found no CNJ-wide "jurisprudencia unificada" service for ordinary decisions. [U:
  absence of evidence]

## 7. Not considered

Commercial aggregators and scraping libraries are not primary sources and conflict with
ADR 0002; they are out of scope. The PDPJ "Portal de Servicos" (`portaldeservicos.pdpj.jus.br`)
returned 403 to a script on 2026-10-21; a search found it is a user portal launched
2024-12-02, with no public API documented. [U] CNJ Res. 455/2022 (DJEN) is what links
courts to the DJEN, per CNJ's own public consultation document (search result, not opened). [U]

## LGPD and secrecy constraints common to all options

- Res. 121/2010 art. 1 par. unico excludes cases under secrecy; DataJud (Portaria 160) and the
  STJ dataset also exclude them. [V]
- Full texts carry party names, CPF fragments and sometimes health or family data. The
  tool descriptions already warn about personal data (ADR 0006); the same applies to any
  new text source. The DataJud terms forbid collecting third-party personal data (3.11, 4.2,
  4.6). [P] Whether the DJEN or STJ licence imposes extra duties on personal data: STJ
  states CC-BY only. [V]

## Recommendation

1. Keep the DJEN as the one text source reachable by CNJ number. Document in the README that
   it returns what the court published as a communication, so a decision that was never
   published (or published before about 2021, or by STF and most TREs) has no text here.
2. If a second source is wanted, build only the STJ CKAN `integras-de-decisoes-...` path, as
   its own slice with a new ADR: official, `cc-by`, no key, full text. Start with the
   date-guided fetch (get the publication date from the DJEN or from the user, download one
   daily ZIP and filter by number, discard after the request) so nothing is persisted,
   and keep the ingestion variant as a later decision. Prove it first with a probe of the
   metadata JSON and the dictionary CSV (not read here) to confirm the process-number field.
3. Do not add DataJud as a text source (it has none), and keep using it for court, class and
   movements only. Review attribution (Portaria 160 par. 5, as amended 2026-08-14) in
   `RESPONSIBLE_USE.md`.
4. Reject, with the reasons above, MNI (credentialed), court consultation systems and case-law
   portals (robots, captcha, WAF; ADR 0002). Tell users who need other courts' text to use
   the tribunal's own portal through the `link` field the DJEN returns, not through the server.
5. Ask CNJ (sistemasnacionais@cnj.jus.br, per its own page) whether a sanctioned public API
   for decision text by number exists or is planned; none is documented today.

## Not verified

- Whether DJEN `texto` contains the full decision text or only notices, per court and kind.
- The STJ dataset's real file count, the process-number field in the metadata JSON, and the
  history start (only file names were seen).
- MNI 2.2.2 `consultarProcesso` response fields (CNJ links dead), TJMA's manual, and whether
  MNI has a REST successor in production.
- Captcha, terms of use and bot policy of PJe/eSAJ/eproc/Projudi consultation, the TSE
  unified PJe consultation, and the PDPJ portal (403).
- STF open-data text datasets and any STF API.
- BNP/Pangea API existence and DataJud wiki field-level definition of `complementosTabelados`
  (page not rendered to a script).
- The 2026-10-08 amendment (Res. 700) to Res. 121/2010 as shown on atos.cnj.jus.br: read only
  in the compiled text, its effect on arts. 1 to 4 was not checked.
