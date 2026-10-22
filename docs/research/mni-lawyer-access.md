# Research: the MNI (Modelo Nacional de Interoperabilidade) for an ordinary lawyer

Researched 2026-10-21. Follow-up to [decision-text-by-cnj-number.md](decision-text-by-cnj-number.md)
section 3. Questions: how does the MNI work, can an ordinary lawyer use it, is authenticating
enough, what resources does it give a lawyer, and which courts does it cover?

Method: primary sources only (CNJ acts and pages, the CNJ-published XSD, a court's own
public MNI page and a court's own Escritorio Digital FAQ). Tags: `[V]` verified on
2026-10-21, `[U]` unverified (do not treat as a finding). One request per URL, honest
behaviour, nothing was authenticated or tested against a live MNI endpoint.

## Summary

- The MNI is a **standard (XSD plus SOAP WSDL)**, not a central service. Each court
  implements and hosts its own endpoint; there is no national MNI gateway. [V]
- An ordinary lawyer does **not** call an MNI endpoint directly by default: the endpoint
  is opened to **credentialed consumers**, and the lawyer-facing product on top of it is the
  CNJ/OAB **Escritorio Digital**. Authenticating is necessary but not the whole story: the
  consumer also needs prior enrolment with each court. [V for TJMA and the Escritorio
  Digital flow; whether every court works that way is U]
- For a lawyer the resources are: query a case, list pending notices, read the content of a
  communication (and mark it as known), submit procedural filings. Documents come back only
  if requested. [V from the CNJ XSD v2.1]
- Coverage is **partial and uneven**. The only published list is old (21 bodies, updated to
  2019-10-31). No current national list was found. [V for the list; U for today]
- Fit with this project: none for the public server (ADR 0002 and 0006): it needs per-user
  credentials and per-court enrolment. It only makes sense as a separate, user-credentialed
  product.

## 1. What the MNI is and who must offer it

- Resolucao Conjunta CNJ/CNMP 3/2013 (16 Apr 2013) instituted the MNI "to provide full
  interoperability between the systems of the Judiciary, the Public Ministry and other bodies
  of the Justice System". Its art. 2 obliges the courts of CF art. 92 I-A to VII to
  implement it in their case-processing systems; art. 1 par. 2 lets "public and private
  bodies and institutions" use the MNI without joining Technical Cooperation Agreement
  58/2009. Amended by CNJ Res. 456/2022 and Joint Res. CNMP/CNJ 9/2022 (art. 2 pars. 3 to 5:
  courts must install the newest MNI version within 180 days of its release and keep the
  previous one running for at least 180 days).
  Source: <https://atos.cnj.jus.br/atos/detalhar/1721> (also /4510 and /4787), 2026-10-21. [V]
- The act says the documents and artefacts live on the CNJ and CNMP sites and are maintained
  by a Comite Tecnico Gestor (art. 1 par. 1). [V]
- Note: the "private bodies may use the MNI" clause (art. 1 par. 2) is about adhering to the
  standard without the cooperation agreement. It is **not** a grant of anonymous access to
  any court's endpoint; access control is each court's. (My reading of the act; the act
  itself says nothing on credentialing. [V on text, interpretation flagged])

## 2. How it works technically

- SOAP web service, WSDL published by the CNJ per version. CNJ's current page for
  court integration names version 2.2.2 and a minimum of three operations:
  `consultarAvisosPendentes`, `consultarTeorComunicacao`, `consultarProcesso`.
  Source: <https://www.cnj.jus.br/integracao-para-os-tribunais/> (2026-10-21). [V]
  The WSDL and PDF guide URLs on that page returned 404 on 2026-10-21. [V]
- The XSD `tipos-servico-intercomunicacao_2_1.xsd` (v2.1, 2 May 2012), published by the CNJ
  at <https://www.cnj.jus.br/wp-content/uploads/2012/05/tipos-servico-intercomunicacao_2_1.pdf>,
  was read in full (text extracted locally). It is the schema of **v2.1**, older than the
  2.2.2 that courts run now, so field names may differ in later versions (for example the
  TJPR Projudi example uses `idManifestante`, see section 4). [V for 2.1; U for 2.2.x/2.2.3]
- Every consulting operation takes `idConsultante` and `senhaConsultante`: "the identifier
  of the body of procedural representation (MP, public defender, public advocacy, law firm or
  lawyer) making the query", ideally the CPF/CNPJ (or RIC). The password is for when there is
  no client-certificate authentication; "if there is client-certificate authentication, the
  parameter must be ignored in favour of it". So the protocol allows **two** authentication
  styles: mutual TLS with a client certificate, or id plus password. [V, XSD v2.1]
- The case number is the one in CNJ Res. 65/2008 format (`tipoNumeroUnico`). [V]
- No public/anonymous mode is described in the XSD; the id is documented as the representing
  body. Whether a court accepts a generic or blank consultant for public cases is
  court-specific. [U] (TJMA below says public cases can be queried through the MNI by
  credentialed entities.)

## 3. Resources available to a lawyer (v2.1 XSD)

| Operation | What it does | Notes |
|---|---|---|
| `consultarAvisosPendentes` | List pending communication notices (intimacoes, citacoes) for the consultant, optionally for one represented person (`idRepresentado`) and from a `dataReferencia` | Returns notices not yet acknowledged; acknowledged ones drop out |
| `consultarTeorComunicacao` | Read the content of a pending communication by case number or notice id | Reading it counts as acknowledgement ("ciencia") per the XSD text |
| `consultarProcesso` | Query a case by CNJ number; flags `movimentos` (events, from `dataReferencia`) and `incluirDocumentos` (all documents), or `documento` (a list of specific document ids) | Documents of a not-yet-seen communication may come back **encrypted** (SHA-1-derived key, key delivered by `consultarTeorComunicacao`) |
| `entregarManifestacaoProcessual` | Submit a filing: either to a running case (by number) or an initial petition with basic data | Needs `idManifestante`/password or certificate; filing is outside this project's read-only scope |

Source: the XSD above. [V] Conclusion for the original question: via the MNI a lawyer
**can** get the documents, including decisions, of a case where they have access, which no
public API gives; this is the one real route to full text beyond the DJEN.

Limits seen:

- Secrecy: TJMA's page says all **public** cases can be queried through the MNI; cases in
  secrecy only when the requester is a representative electronically linked to the case (and
  a procuradoria must be linked to a party). Source: TJMA, section 4. [V for TJMA; U for other
  courts]
- Escritorio Digital integration at TJSP covers only **digital** cases and only the **main**
  case, not incidental proceedings, executions or incidental actions, and the case must be
  queried by its CNJ number (NNNNNNN-DD.AAAA.J.TR.OOOO). Source: TJSP FAQ, section 4. [V]

## 4. Can an ordinary lawyer use it? Is authenticating enough?

Two layers exist.

**A. Direct MNI endpoint of a court (credentialed consumer).** Example, TJMA (Maranhao):
- Access requires a request for credentialing by **official document** to the IT directorate,
  which gives an opinion and asks the Presidency for authorisation. [V]
- Authentication is **user and password**; a query password is given to entities with
  credentialed access. For "bodies of representation", operations beyond queries use the
  same credentials as PJe (user and password). [V]
- MNI is available for PJe 1st and 2nd instance, versions "2.2.2.2 and 2.2.3", with the CNJ
  developing and supporting the MNI operations inside PJe. The public WSDLs are
  `https://pje.tjma.jus.br/pje/ConsultaPJe?wsdl` and `https://pje2.tjma.jus.br/pje2g/ConsultaPJe?wsdl`.
  Source: <https://www.tjma.jus.br/midia/tecnologia/pagina/hotsite/509870/consulta-de-processos-judiciais>
  (2026-10-21). [V]
- Meaning: just authenticating with OAB/gov.br is **not** enough. A first step of
  credentialing per court, a decision by the court, and a distinct credential per court. This
  is aimed at institutions (law firms' systems, agencies), not at a single lawyer typing
  commands. [V for TJMA; U for the other 90-odd courts]

**B. Escritorio Digital (the lawyer-facing product built on the MNI).**
- A CNJ software, developed with the OAB Federal Council, giving lawyers "a single door to the
  Judiciary"; it acts as a client that "remotely accesses the case base of the court's
  electronic system" (<https://www.cnj.jus.br/sistemas/escritorio-digital/> and
  `/como-funciona/`, 2026-10-21). [V]
- First access: sign-up checks the **Cadastro Nacional de Advogados (CNA)**; if the person is
  registered with the OAB, a password is e-mailed and can be changed inside the system
  (`/como-o-advogado-acessa-o-sistema/`). Address: <https://www.escritoriodigital.jus.br>.
  [V] (This page may be outdated: a gov.br login is not mentioned and was not tested. [U])
- After sign-up the lawyer must **pick the courts** and register their **login and password of
  each court's own system**; "the court must be consulted to learn how to obtain it"
  (`/vinculacao-dos-tribunais-de-atuacao/`). [V]
- It runs on demand: the user registers their cases, then clicks "Atualizar" and the system
  queries the court over the internet; if a court is down, it issues a certificate of
  unavailability (`/tecnologia/`). Lawyers can share cases with others. [V]
- Meaning: for an ordinary lawyer, authentication is OAB (CNA) for the product **plus** an
  existing valid account in each court system. There is no documented API for third-party
  programs on the Escritorio Digital itself; it is a web application. [U for absence of an
  API; none was found]
- Court-side enrolment: for a court to appear, it must implement MNI, send the CNJ its WSDL in
  homologation, its J/TR code, a technical contact and a production URL, plus a homologation
  user/password used in `idConsultante`/`senhaConsultante` for CNJ tests
  (<https://www.cnj.jus.br/integracao-para-os-tribunais/>). [V]

## 5. Court coverage

- PJe courts: "all courts that adopted PJe are apt to integrate, since PJe already comes with
  the MNI"; also courts that adopted the MNI per Joint Res. 3/2013 (`/como-funciona/`). [V]
  Whether each PJe court actually configured it for the Escritorio Digital depends on the
  court: "the expansion depends on the adhesion of the courts and on mobilising their
  configuration teams" (`/expansao/`). [V]
- Published list ("Quem ja esta no Escritorio Digital", **updated to 31 Oct 2019**, page not
  changed since; 21 bodies): CNJ, TRF1 to TRF5, TJAC, TJAL, TJBA, TJDFT, TJMA, TJMT, TJMS,
  TJMG, TJPI, TJRS, TJRO, TJSC, TJSE, TJSP, TJTO. [V] Not in the 2019 list: TRF6 (created
  2022), TJAM, TJAP, TJCE, TJES, TJGO, TJPA, TJPB, TJPE, TJPR, TJRJ, TJRN, TJRR, STF, STJ, TST
  and the TRTs/TREs. Many of these may have joined since; the list was **not** refreshed, so
  today's coverage is **unknown**. [U]
- TJSP runs an Escritorio Digital integration with its own FAQ (section 3 limits; filings in
  forums enabled in e-SAJ; support split between CNJ and the court)
  (<https://www.tjsp.jus.br/Download/Pdf/EscritorioDigital/FAQEscritorioDigital.pdf>). [V]
- Labor justice (TRTs) and electoral justice use PJe, so they could be reachable, but no
  primary source on their MNI access was read. [U]

## 6. Fit with the project and recommendation

- Public, keyless server (ADR 0002 and 0006): **not compatible**. Access needs a per-court
  credential or a lawyer's own court login, which the project would have to hold; it is also
  nominally restricted by the credentialing of each court. Responsible-use and LGPD
  duties (full case files carry personal data and may include secrecy) would increase.
- If a text route beyond the DJEN is wanted for lawyers, the honest design would be a separate
  **opt-in adapter run by the user with their own credentials** (the user supplies the court,
  id and password, or a client certificate; nothing stored), limited to courts that publish
  an MNI WSDL and document the credentialing. It needs a new ADR; start with one court as a
  contract probe (TJMA publishes the most open documentation of those found).
- Before any code: confirm with a court or the CNJ (`g-escritorio.digital@cnj.jus.br` per the
  CNJ integration page) whether third-party software of a lawyer may call the MNI with the
  lawyer's own credentials, and which MNI version (2.2.2, 2.2.3, 3.0) each court runs.

## Not verified

- The MNI 2.2.2 / 2.2.3 / 3.0 schemas (the CNJ links 404). Only v2.1 was read; later
  versions may add or rename fields and operations.
- Current coverage per court (the only list is from 2019), and whether TRF6, other TJs, TRTs,
  TREs or the superior courts expose an MNI to external consumers.
- Whether any court offers MNI credentials to an individual lawyer without an institutional
  request, and each court's terms of use, rate limits and SLA.
- Whether the Escritorio Digital now accepts gov.br login, and whether it has an API for
  third-party programs.
- A live MNI call: none was made (it needs credentials).
- MNI 3.0 REST status: a 2022 CNJ presentation reportedly said "in homologation" (see
  court-data-access.md section 6); not re-read.
