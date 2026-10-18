# DJEN `texto` query semantics

Research for issue #63 (child of map #53). Date of research: 2026-10-18.

Legend: **[O]** observed in live, read-only, unauthenticated GET probes; **[I]** inference
from those observations. The API publishes no description of the `texto` syntax, so nothing
here is **[D]** (documented). Background: `docs/research/djen-api.md` on branch
`research/djen-api`.

## Method

- `GET https://comunicaapi.pje.jus.br/api/v1/comunicacao` with `siglaTribunal`,
  `dataDisponibilizacaoInicio` = `dataDisponibilizacaoFim` = one day (2026-10-15), `texto`
  and `itensPorPagina=5`. Only the envelope field `count` was read; no item text, party or
  lawyer data was kept.
- Rate: at most ~2 req/s with a 0.5 s pause (`x-ratelimit-limit: 20`); no 429 was received.
- Main court TJSP; replicated on STJ and TRF4. Numbers below are for 2026-10-15 and are
  reproducible only for that day's data (a Publication can be added late).
- `count` is the true total only below 10000; at exactly `10000` it is the cap marker
  (see `djen-api.md`). Proofs below use terms whose count is under the cap. Unlike the
  earlier note, a single-day, single-court query with a rare term yields exact counts
  (e.g. `count` 5117 for `ementa`, TJSP).

## Summary

| Feature | Result |
|---|---|
| Multi-word query | **Exact phrase, in order**, not AND, not OR |
| Quotes `"..."` | Ignored (stripped); same as no quotes |
| `AND`, `OR`, `NOT` (any case) | **Not operators**: treated as literal words, usually giving 0 |
| `-term`, `+term`, `&`, `\|` | Characters stripped; the term is still required, in the phrase |
| Wildcard `*`, `?`, `~` | Stripped, not wildcards. No prefix search |
| Accents | Folded (`acórdãos` = `acordaos`) |
| Case | Folded |
| Stemming / plurals | **None**; singular and plural are different terms |
| Stop words | **Not removed**; `de`, `e`, `do` are real tokens inside a phrase |
| Minimum length | Trimmed query must be at least **5 characters**, else HTTP 500 |
| Separators | Whitespace, `,` `-` `/` `"` `:` `;` `(` `)` split tokens; `.` does not |

## Evidence (TJSP, 2026-10-15)

### Implicit operator: phrase, not AND/OR **[O]**

| `texto` | count |
|---|---|
| `ementa` | 5117 |
| `ementa recurso` | 222 |
| `recurso ementa` | 0 |
| `recurso especial` | 2685 |
| `especial recurso` | 49 |
| `recurso especial` as `"recurso especial"` | 2685 |
| `"recurso" "especial"` | 2685 |

222 is far below 5117, so it is not OR; but `recurso ementa` is 0 while `ementa recurso`
is 222, and `especial recurso` (49) differs from `recurso especial` (2685), so it is not a
plain AND either. The whole string behaves as an ordered, adjacent phrase **[I]**. A gap
breaks the match: `recurso do especial` and `recurso e especial` give 0, while the
adjacent `recurso especial` gives 2685. Repeating a word asks for the repeated phrase:
`recurso recurso` 30, `ementa ementa` 0.

Replicated: STJ `recurso especial` 2495 vs `especial recurso` 9; TRF4 536 vs 0.

### Quotes **[O]**

`"ementa recurso"` = 222 = unquoted. A stray quote (`"ementa`, `ementa"`) = 5117 =
`ementa`. Two quoted words separately (`"recurso" "especial"`) = 2685, i.e. still one
phrase. Quotes cannot express "these words in any order".

### Explicit operators **[O]**

| `texto` | count | reading |
|---|---|---|
| `ementa AND recurso`, `ementa and recurso` | 0 | `and` is a literal token |
| `ementa OR recurso`, `recurso OR ementa`, `ementa or recurso` | 0 | literal token |
| `ementa NOT recurso`, `ementa not recurso` | 0 | literal token |
| `ementa OR` | 0 | literal token |
| `ementa -recurso` | 222 | `-` dropped, still the phrase |
| `ementa +recurso` | 222 | `+` dropped |
| `ementa & recurso`, `ementa \| recurso` | 222 | symbol dropped |

`recurso AND especial`, `recurso OR especial`: 0 on STJ and TRF4 too; `recurso -especial`
returns the same count as `recurso especial` (STJ 2495, TRF4 536), so the negation does
not exclude anything, it requires the word. A query using `-term` to exclude therefore
returns the opposite of the intent: **a silent wrong-result risk**.

There is no way to express OR or a general AND. Combine with several calls and merge or
intersect client-side **[I]**.

### Wildcards **[O]**

`ementa*`, `ementa~`, `ementa?` = 5117 (= `ementa`). `intim*` = 35 = `intim`;
`intimaç*` = 0 (it searches the token `intimaç`, not a prefix of `intimação`). A
prefix is not matched: `ement` = 9, `intim` = 35, versus `ementa` 5117, `intimação`
over the cap.

### Accent and case folding **[O]**

| Variants | count |
|---|---|
| `acórdãos`, `acordaos` (TJSP) | 76, 76 |
| `acórdãos`, `acordaos` (STJ) | 232, 232 |
| `EMENTA`, `eMeNtA`, `ementa`, `ementa:` | 5117 each |
| `ementa recurso extraordinário` / `...extraordinario` / `...EXTRAORDINÁRIO` | 4, 4, 4 |
| `decisão`, `decisao`, `DECISÃO` (STJ) | 3874 each |
| same (TRF4) | 3177 each |

Fully folded in both directions (diacritics and case). Trailing punctuation is irrelevant.

### No stemming, no lemmatisation **[O]**

| Term | count |
|---|---|
| `recurso` | over cap |
| `recursos` | 8015 |
| `especial` / `especiais` | over cap / 5216 |
| `provido` / `providos` / `prover` | 5359 / 168 / 380 |
| `acórdãos` / `acórdão` | 76 / over cap |
| `intimar` / `intimações` | 1343 / 2083 |

Different inflections have different counts, and `intim` (35) does not match
`intimação`. Search every inflection that matters and merge client-side **[I]**.

### Stop words **[O]**

`ementa de` = 8, `recurso de` = 4443, `ano de` = 1018, `ementa recurso de` = 2:
function words are indexed and must match, not skipped. Thus `recurso do especial` (0)
cannot match `recurso especial`.

### Minimum length **[O]**

HTTP 500 with body `status: error`, message "O sistema esta muito ocupado. Tente novamente
mais tarde." ("system too busy, retry later", misleading) for any trimmed query shorter
than 5 characters, regardless of token count:

| `texto` | length | result |
|---|---|---|
| `abcd`, `ação`, `acao`, `stj`, `ano`, `de`, `e`, `2026`, `NOT`, `eme`, `emen` | 1-4 | HTTP 500 |
| `ab c`, `a bc`, `de a`, `a de` | 4 | HTTP 500 |
| `abcd ` / ` abcd` (padded) | 4 trimmed | HTTP 500 |
| `ement`, `abcde`, `ab cd`, `a b c`, `a bcd` | 5 | 9, 0, 0, 28, 0 |
| `ano de`, `ementa 1` | 6, 8 | 1018, 1 |

Short tokens are fine inside a longer phrase (`ementa de`, `a b c`). The 500 is not a
load problem: the same call succeeds at 5 characters immediately before and after, and
the `x-ratelimit-remaining` header stayed above 0 **[O][I]**. A client must not retry it
as transient.

### Special characters and separators **[O]**

| `texto` | count | note |
|---|---|---|
| `recurso especial`, `recurso  especial`, `recurso, especial`, `recurso-especial`, `recurso"especial"` | 2685 | all separate tokens |
| `recurso.especial` | 0 | `.` joins the token |
| `15/10/2026`, `15 10 2026`, `15-10-2026` | 234 | slash and hyphen split; phrase `15 10 2026` |
| `15102026` | 0 | one different token |
| `ementa (recurso)`, `(ementa)` | 222, 5117 | parentheses ignored |
| `ementa\`, `ementa/`, `ementa;` | 5117 | trailing punctuation ignored |
| `ementa ç` | 0 | a lone letter is a token |

An unmatched term never errors if the query is at least 5 characters (`xyzqwk` and
`zzzzzz` return 0).

## Surprises and risks

1. The default is a phrase, not AND: `recurso especial` is easily mistaken for "both
   words".
2. `AND`/`OR`/`NOT` and `-term` look supported but are not; the first three silently
   return 0 and `-term` silently turns into a required word.
3. Queries under 5 characters fail with a 500 whose message says "busy", inviting
   pointless retries.
4. No stemming and no prefix search: recall for "intimação", "recurso" etc. needs
   explicit variants.
5. Exact counts are available below the 10000 cap for a court and a single day, which
   makes `count` usable as a cheap probe when the term is selective.

## Implications for juris-bridge-mcp

- Treat each `texto` as one literal phrase; expose no boolean syntax to users. Implement
  OR as separate calls with the results merged, AND as intersection client-side.
- Strip or reject `AND`, `OR`, `NOT`, `-`, `+`, `*`, `"` before sending, or document that
  they are ignored.
- Validate that the trimmed phrase has at least 5 characters; map the 500 to a
  validation error, not a retry.
- No need to normalise accents or case; do not pre-stem.
