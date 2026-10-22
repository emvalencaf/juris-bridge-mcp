# Juris Bridge MCP

An MCP server that exposes Brazilian judicial and legal data sources to AI agents through one normalized interface.

## Language

**Case**:
A judicial proceeding (_processo_) identified by a CNJ number, as registered in a court.
_Avoid_: lawsuit, process, docket

**CNJ number**:
The unified 20-digit case identifier (_Numeração Única_, `NNNNNNN-DD.AAAA.J.TR.OOOO`) defined by the National Council of Justice (CNJ).
_Avoid_: case ID, process number

**Court**:
A judicial body (_tribunal_) such as STF, STJ, a TRF or a TJ, identified by an alias.
_Avoid_: tribunal (in code and tool descriptions)

**Source**:
An external data origin (DataJud, the Senado legislation API, a court portal) that the server queries on the agent's behalf.
_Avoid_: provider (reserved for the code module that talks to a Source)

**Case law**:
Published court decisions (_jurisprudência_), including rulings (_acórdãos_) and their summaries (_ementas_).
_Avoid_: jurisprudence

**Publication**:
A decision or ruling (_decisão_, _acórdão_) as released in a Diário da Justiça Eletrônico, with its release date and text; distinct from the Case it belongs to.
_Avoid_: intimação, notice, case law (when a single released item is meant)

**Issuing body**:
The unit of a Court (_órgão_, such as a chamber, panel or office) that issues a Publication, identified by an `orgaoId` in the DJEN.
_Avoid_: organ, chamber, vara (these are kinds of Issuing body, not the concept)

**Precedent**:
A record of the Banco Nacional de Precedentes (_precedente_) that fixes a thesis, such as a súmula, a repercussão geral theme, a repetitive appeal, an IRDR or an IAC, with its question, thesis, status and leading Cases; distinct from a Publication (the text of one ruling) and from a Case (one proceeding).
_Avoid_: jurisprudence, case law (when a thesis record is meant), súmula (only one Precedent kind)

**Precedent kind**:
The species of a Precedent (_espécie_), identified by the BNP sigla such as `SUM`, `SV`, `RG`, `RR`, `IRDR`, `IAC` or `OJ`.
_Avoid_: type, category

**Relevance**:
How a Publication fits a search query among the others of the same page: a `score` from 0 to 1 (BM25 scaled so the page's best item is 1.0) and the `matched_terms` found in its text. It is only meaningful within one response; results stay ordered by date and no global relevance ordering exists. A Precedent carries only the `matched_terms` the Source highlights and no `score`, because the BNP returns none.
_Avoid_: rank, ranking (the order is by date), global score

**Legislation**:
Statutes and other normative acts (_legislação_), identified by a URN Lex and catalogued by the Senado.
_Avoid_: laws

**Norm**:
A single federal normative act (a law, decree, constitutional amendment...) as the Senado catalogues it, identified by its URN Lex.
_Avoid_: law, statute (when the act may be a decree or an amendment)

**Normalized result**:
The source-independent shape returned by a tool, carrying the originating Source and a Citation.
_Avoid_: response, payload

**URN Lex**:
The LexML Uniform Resource Name that canonically identifies a norm (for example `urn:lex:br:federal:lei:2021-04-01;14133`).
_Avoid_: norm ID, law ID

**Reference deployment**:
The documented, supported way for a user to run the server on their own AWS account; other targets run the same container but are not provisioned by this project.
_Avoid_: production, hosted instance

**Citation**:
The human-readable reference to an item plus, when the Source offers a stable one, its URL; present on every Normalized result.
_Avoid_: reference, link

**Annotation**:
A note the Source adds to a provision of a Norm to record its legislative history (wording given, inclusion, cross-reference), as opposed to the mark that the provision was revoked.
_Avoid_: footnote, amendment note

**Content kind**:
Whether an item carries only descriptive data (`metadata`) or the full document text (`full_text`), so an empty text is never mistaken for absence.
_Avoid_: type, mode

**Cursor**:
The opaque token an agent passes back to receive the next page of a search or the next slice of a text; it never exposes a position in the Source.
_Avoid_: offset, page number

**Coverage**:
What the server can and cannot answer, by Source and Court, stated by the `list_coverage` tool.
_Avoid_: support matrix

**Error code**:
One of a closed set of values (`invalid_argument`, `not_found`, `not_covered`, `rate_limited`, `source_unavailable`, `source_auth_failed`, `source_changed`, `source_blocked`) that tells an agent why a call failed and whether to retry.
_Avoid_: error type, status
