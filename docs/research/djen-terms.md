# DJEN terms of use and LGPD for reusing published decisions

Resolves issue #55 (child of map #53). Researched 2026-10-18.

> This is research, not legal advice. Open legal questions are listed in the
> last section and need a Brazilian lawyer before they are treated as settled.

## Question

What do the DJEN terms and the applicable rules (CNJ acts, LGPD, publicity of
procedural acts) allow for an open-source MCP server that fetches published
decisions from the DJEN and serves them to AI agents? Covers reuse,
redistribution, commercial use, caching, attribution, and party names and
personal data in published text. Decides whether ADR 0002's self-hosted-per-user
model must extend to this source.

## Short answer

- There is no standalone "terms of use" document for the DJEN that I could
  find. The operative rules are the public API's OpenAPI description plus
  Resolução CNJ 455/2022.
- The DJEN has an official, public, unauthenticated API. Its own description
  says it is a public API, bars only abusive use, and rate-limits per IP.
- Nothing I read grants or forbids redistribution, commercial use, caching or
  republication. The API's declared license field points to Resolução 455/2022,
  which has no reuse clause. Silence is not a grant; see open questions.
- Published text contains party names by design (Res. 455, art. 12, §1), but
  the CNJ expects judicial decision databases to avoid search by party name
  where possible (Res. 121/2010, art. 5) and secrecy cases are excluded.
- The LGPD applies to a private operator that processes this text. Public
  availability does not remove it (LGPD art. 7, §3).
- Recommendation: keep ADR 0002's self-hosted-per-user model for this source.
  Do not run a shared hosted service that stores or republishes DJEN text.

## 1. What the DJEN is and what it publishes

Source: Resolução CNJ 455/2022, compiled text, <https://atos.cnj.jus.br/atos/detalhar/4509>
(fetched with curl, read in full for arts. 11-22).

- Art. 12: "O DJEN substitui os atuais diários de justiça eletrônicos mantidos
  pelos órgãos do Poder Judiciário e estará disponível no Portal de Serviços e
  no sítio do CNJ na rede mundial de computadores."
- Art. 13: published items are "o conteúdo dos despachos, das decisões
  interlocutórias, do dispositivo das sentenças e da ementa dos acórdãos",
  intimations to lawyers, distribution lists, edital acts, and other acts whose
  publication is required by procedural law.
- Art. 14: "O conteúdo das publicações incluídas no DJEN deverá ser assinado
  digitalmente."
- Art. 11, §3 (wording from Res. 569/2024): procedural deadlines run from DJEN
  publication when personal intimation is not required.

Consequence: what the DJEN carries is mostly the operative part of decisions
(dispositivo, ementa), not full reasoning. Full "inteiro teor" lives in each
tribunal's system. Source for the scope claim: CPC art. 205, §3: "Os despachos,
as decisões interlocutórias, o dispositivo das sentenças e a ementa dos
acórdãos serão publicados no Diário de Justiça Eletrônico." (Lei 13.105/2015,
<https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm>).

CNJ's own page describes the same, and gives the portal address
"https://comunica.pje.jus.br/":
<https://www.cnj.jus.br/programas-e-acoes/processo-judicial-eletronico-pje/comunicacoes-processuais/>.

## 2. The terms: the DJEN public API description

Source: the OpenAPI document served by the API itself,
<https://comunicaapi.pje.jus.br/swagger/djen.yml> (version 1.0.4, "Última
atualização em 04-03-2026"). Quoted verbatim:

- "API pública do DJEN."
- "Endpoints sem cadeado não exigem autenticação."
- "Endpoints autenticados e de login são de uso exclusivo pelos Tribunais."
- "Uso abusivo está sujeito a bloqueios. Observe os cabeçalhos de rate limit."
- On `GET /api/v1/comunicacao`: queries are "sujeitas a controle de taxa de
  requisições por IP"; on HTTP 429 "orienta-se aguardar 1 minuto"; and "A
  utilização de múltiplos IPs por um mesmo cliente para contornar o controle da
  taxa de requisições é considerado uso abusivo e poderá resultar em
  bloqueios."
- Some queries "são limitadas em 10000 resultados", `itensPorPagina` accepts
  only 5 or 100, and a query needs at least one of `siglaTribunal`, `texto`,
  `nomeParte`, `nomeAdvogado`, `numeroOab`, `numeroProcesso` or must be limited
  to 5 items per page.
- `info.license` is `name: Resolução Nº 455 de 27/04/2022`,
  `url: https://atos.cnj.jus.br/atos/detalhar/4509`. `info.contact` is CNJ.
- A "Cadernos" endpoint serves compressed daily gazette files per tribunal,
  with a temporary (5 minute) download URL; the day's cadernos are available
  from 03:00. This is the intended bulk path, instead of crawling search.
- Write endpoints (insert, cancel communications) are "uso exclusivo pelos
  Tribunais".

Direct check on 2026-10-18: `GET /api/v1/comunicacao?...&itensPorPagina=1`
without any credentials returned HTTP 200, with `x-ratelimit-limit: 20` and
`access-control-allow-origin: *`. The response includes the `texto` field with
the published text and party names or initials.

Reading of these facts:

- Consumption of the read endpoints is permitted to anyone, without
  registration. This is the strongest primary evidence for use by a self-hosted
  tool.
- The only stated restrictions are about load: per-IP rate limit, no
  multi-IP evasion, abusive use may be blocked.
- The document contains no terms about redistribution, commercial use, caching
  duration, attribution or derivative works. That is a gap, not permission.

## 3. Publicity rule and its limits

- CPC art. 189 (<https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm>):
  "Os atos processuais são públicos, todavia tramitam em segredo de justiça os
  processos: ... II - que versem sobre casamento, separação de corpos, divórcio,
  separação, união estável, filiação, alimentos e guarda de crianças e
  adolescentes; III - em que constem dados protegidos pelo direito
  constitucional à intimidade ..."
- Res. 455, art. 12, §2: "A divulgação dos dados processuais no DJEN observará,
  nos processos sujeitos a sigilo ou segredo de justiça, o disposto na lei e na
  Resolução CNJ nº 121/2010."
- Res. 455, art. 12, §1: an intimation published in the DJEN must state "os
  nomes das partes, de seus advogados e os respectivos números de inscrição na
  OAB", under penalty of nullity. So party names are a mandated part of the
  published record.
- Resolução CNJ 121/2010 (<https://atos.cnj.jus.br/atos/detalhar/92>):
  - art. 1: consultation of basic case data is on the internet, "assegurado o
    direito de acesso a informações processuais a toda e qualquer pessoa,
    independentemente de prévio cadastramento ou de demonstração de interesse";
    secrecy cases are excluded.
  - art. 2: basic data of free access include "nome das partes e de seus
    advogados" and "inteiro teor das decisões, sentenças, votos e acórdãos".
  - art. 5: "A disponibilização de consultas às bases de decisões judiciais
    impedirá, quando possível, a busca pelo nome das partes."
  - art. 4, §2: "Os nomes das vítimas não se incluem nos dados básicos dos
    processos criminais."
  Note: the fetched compiled page shows a later amendment ("Resolução n. 700, de
  8.10.2026" on art. 6), so the text may keep changing; I did not review it
  exhaustively.

Observation, not a rule: a sample from the live API for a family-law
execution showed parties as initials, which suggests tribunals mask some
secrecy-adjacent cases at source. I did not verify this is systematic.

## 4. LGPD

Source: Lei 13.709/2018, <https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm>
(page read; text matched with a recent compiled version that includes 2025/2026
amendments).

- Art. 7, §3: "O tratamento de dados pessoais cujo acesso é público deve
  considerar a finalidade, a boa-fé e o interesse público que justificaram sua
  disponibilização." Public availability of a party's name in the DJEN does not
  make free reuse lawful; the purpose of the original publication (procedural
  notice and publicity of acts) bounds later purposes.
- Art. 7, §4: consent is waived for data "tornados manifestamente públicos pelo
  titular"; this does not fit court-published data, which the data subject did
  not make public.
- Art. 6, I and III: principles of finalidade and necessidade ("limitação do
  tratamento ao mínimo necessário").
- Art. 4, I: the LGPD does not apply to processing "por pessoa natural para fins
  exclusivamente particulares e não econômicos". A person running the tool
  locally for strictly private, non-economic use may fall here; an open-source
  project distributed to others, or any professional use (for example a law
  office), does not clearly fit.
- Art. 4, II, b: academic-only processing is exempt but arts. 7 and 11 still
  apply.
- Art. 26, §1: the restriction on transfer by the Public Power to private
  entities, with exception III for data "acessíveis publicamente". This binds
  the CNJ and courts, not the downstream tool, and supports that the CNJ
  publishes the data on purpose.

Who is controller: in a self-hosted-per-user model the user runs the software
and decides the purposes, so the user is plausibly the controller, and the
project maintainer only distributes code. In a hosted multi-user service the
operator would be the controller or operator for every retrieved person's data.

## 5. Dimension by dimension

| Dimension | What the sources say | Status |
|---|---|---|
| Reuse (reading via API) | Public API, no auth for read endpoints (swagger `djen.yml`) | Permitted on its face |
| Redistribution / republication | No clause anywhere I read | Unaddressed; LGPD art. 7 §3 limits it for personal data |
| Commercial use | No clause; license field points only to Res. 455 | Unaddressed |
| Caching | No clause; the API only demands rate limits and no multi-IP evasion | Unaddressed; caching is a load reducer, but a persistent store raises LGPD retention issues |
| Attribution | No clause | Unaddressed; cite source tribunal and DJEN anyway as good practice |
| Party names | Mandatory in the published text (Res. 455 art. 12 §1); searching decision bases by name should be prevented "quando possível" (Res. 121 art. 5) | Tension: the API has a `nomeParte` filter, yet CNJ's own policy discourages name search of decision bases |
| Secrecy cases | Excluded by CPC 189 and Res. 455 art. 12 §2 | Server must not surface or store anything flagged secret |

## 6. Effect on ADR 0002

Note: `docs/adr/` on this branch only contains ADR 0001, so I could not read
ADR 0002 itself; this section assumes it states a self-hosted, per-user model.

Findings favour extending that model to the DJEN source:

- The API is anonymous and rate-limited per IP, so each user running their own
  instance gets their own quota and stays within the stated usage rules. A single
  shared hosted instance would concentrate all traffic on one IP and sit
  close to the "abusive use" language.
- A hosted service that stores or serves DJEN text to third parties becomes a
  personal-data controller for party names across all tribunals, with LGPD art.
  6 and art. 7 §3 exposure and no stated reuse license from the CNJ.
- Self-hosted use keeps the maintainer a code distributor and the user the
  responsible party.

Design suggestions that follow (for the implementation issues, not decided here):

- Fetch on demand; keep any cache local, short-lived and user-controlled.
- Respect `x-ratelimit-*` and 429 (wait 1 minute); single IP per instance.
- Prefer the `cadernos` bulk endpoint for bulk work over broad searches.
- Do not offer party-name search as a headline feature; prefer process number,
  OAB, tribunal and date filters.
- Pass tribunal and date metadata through, and cite the DJEN as the source.
- Do not log full texts or party names.

## 7. What I could not read

- Any DJEN portal terms of use or privacy notice: `comunica.pje.jus.br` is an
  Angular single-page app; its HTML shell has no such text, and I did not render
  it in a browser. I searched the 1.6 MB main script for "termos de uso",
  "LGPD", "dados pessoais" and "política de privacidade" and found nothing, but
  lazy-loaded chunks were not checked.
- Resolução CNJ 455/2022 original PDF and Res. 569/2024 PDF
  (`atos.cnj.jus.br/files/...`): the PDF text is font-encoded and I had no
  PDF text tool. I relied on the compiled HTML page of Res. 455 and on the HTML
  page of Res. 569 (read only up to its art. 3).
- The SwaggerHub "pcp" complementary spec and the test environment
  (`hcomunicaapi.cnj.jus.br`) mentioned in secondary results: not read, and only
  found in a freelance job posting (unreliable).
- CNJ's LGPD policy for courts (Res. CNJ 363/2021 and related) and any CNJ
  guidance on data-protection for AI use of decisions: not read.
- ANPD guidance on processing publicly accessible personal data: not read.
- ADR 0002 (absent from this branch).
- Per-tribunal masking behaviour: only one live sample.

## 8. Open legal questions (need a lawyer)

1. Does a tool that republishes or locally indexes DJEN text count as a new
   processing with a new purpose under LGPD art. 7, §3 and art. 6, I? What is
   its legal basis (art. 7, IX legitimate interest? art. 7, X?), for an
   open-source distribution versus a private user?
2. Is the user running a self-hosted instance for professional work the
   controller, and what are their obligations (information, retention,
   data-subject requests)?
3. Is serving published text to a third-party AI model (the agent's LLM provider)
   an international transfer or disclosure to another controller under the
   LGPD?
4. Res. 121/2010 art. 5 says decision databases should avoid name search "quando
   possível". Does that bind downstream tools, and does exposing a `nomeParte`
   filter through MCP contradict its spirit?
5. Absence of any reuse license: is "public API + public-law publicity" enough
   for redistribution and commercial use, or should the project ask CNJ for
   written confirmation (CNJ is listed as contact; `dpje@cnj.jus.br` appears in
   CNJ's PJe contact page per search results, not verified)?
6. Retention and deletion: Res. 455 art. 22 says communications stay available
   in the Domicílio for 24 months. Is there an expectation about DJEN retention
   that a local cache should mirror?
7. Handling of leaked secrecy cases: duty if the cache contains text later
   cancelled (the API replaces content with a cancellation reason).

## Sources

- Resolução CNJ 455/2022 (compiled): <https://atos.cnj.jus.br/atos/detalhar/4509>
- Resolução CNJ 569/2024 (page): <https://atos.cnj.jus.br/atos/detalhar/5691>
- Resolução CNJ 121/2010: <https://atos.cnj.jus.br/atos/detalhar/92>
- DJEN public API description: <https://comunicaapi.pje.jus.br/swagger/djen.yml>
- DJEN portal: <https://comunica.pje.jus.br/>
- CNJ communications page: <https://www.cnj.jus.br/programas-e-acoes/processo-judicial-eletronico-pje/comunicacoes-processuais/>
- Lei 13.709/2018 (LGPD): <https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm>
- Lei 13.105/2015 (CPC): <https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm>
