# Diagrams

Overview diagrams of the server, embedded in the READMEs.

| # | Diagram | Type | Answers |
|---|---|---|---|
| 01 | [Architecture](assets/01-architecture.svg) | Architecture | Where do I touch to add a Source? |
| 02 | [MCP request flow](assets/02-request-flow.svg) | Sequence | What happens between an MCP call and its Normalized result or Error code, and what does the wide event hold? |
| 03 | [get_legislation text fallback](assets/03-get-legislation.svg) | Flowchart | Why does the text sometimes come from another Source, and what do `content_kind` and `warnings[]` say? |
| 04 | [AWS Reference deployment](assets/04-aws-deployment.svg) | Deployment | Which AWS services run, and where is the portability boundary? |
| 05 | [search_publications flow](assets/05-search-publications.svg) | Flowchart | How is a window read within the request budget, and how is a day at the DJEN count cap split by Issuing body? |

## Folders

- `code/`: the source of each diagram, a self-contained `NN-name.html` with
  inline SVG, made with the `diagram-design` skill (default skin).
- `code/icons/`: the official AWS Architecture Icons used by diagram 04, with
  attribution and terms in [its README](code/icons/README.md).
- `assets/`: the rendered `NN-name.svg`, the image the READMEs embed. Never
  edit it by hand.

## Regenerate

The HTML in `code/` is the source of truth; the SVG is exported from it.

```bash
python3 .agents/skills/diagram-design/scripts/export_svg.py \
  docs/diagrams/code/01-architecture.html \
  docs/diagrams/assets/01-architecture.svg --system-fonts
```

`--system-fonts` makes the SVG fall back to system fonts, because GitHub
renders embedded SVG without loading web fonts. Check the result with
`python3 .agents/skills/diagram-design/scripts/self_check.py <file>.html` and
by opening the SVG in a browser.

Edit the HTML, then export again. Diagram 04 reads the icon files from
`code/icons/` as they are; do not alter them.

## When to regenerate

A module, flow or ADR illustrated by a diagram changed → regenerate it. This
is checked on the release PR from `development` to `master` only (see
[CODE_STANDARDS.md](../../CODE_STANDARDS.md)), not on every PR.
