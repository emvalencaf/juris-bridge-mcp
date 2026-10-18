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

**Legislation**:
Statutes and other normative acts (_legislação_), identified by a URN Lex and catalogued by the Senado.
_Avoid_: laws, norms

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
