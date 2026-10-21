---
type: Domain Model
title: "Legislation model: URN Lex, Norm and article text"
description: "Federal Norm types, URN parsing, relations, and article addressing/annotation rules."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/domain/legislation.py
tags: [domain, legislation]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: l
    resource: juris_bridge_mcp/domain/legislation.py
    title: legislation.py
  - id: lt
    resource: juris_bridge_mcp/domain/legislation_text.py
    title: legislation_text.py
---

# Norms and URN Lex

`NORM_TYPES` maps the agent-facing key to (Senado `tipo` sigla, URN type), e.g. `lei` → (`LEI`, `lei`). `Urn.parse` accepts `urn:lex:br:federal:<type>:<date>;<number>` and raises `invalid_argument` on a bad shape or impossible date; an unsearchable URN type (e.g. `mensagem`) keeps its raw type.[^l] A `NormRecord` bundles the Norm, its `Publication`s (Diário edition) and `Relation`s; `latest_relations` collapses repeats per provision and sorts newest first.

# Articles and annotations

`article_key` canonicalises `Art. 5º`, `5` and `art 5` to `5`; `121-A` to `121-a`; `Art. único` to `unico`. `article_start` and `article_range` locate article lines and range stubs such as `Arts. 757 a 777. (Revogados...)` (bounded by `MAX_RANGE_ARTICLES`).[^lt] Flags are `revoked` and `superseded`.

An **Annotation** is a parenthesised note opening with a known prefix (`redação dada`, `incluído`, `vide`, `vigência`, `regulamento`, `renumerado`, `produção de efeito`). `strip_annotations` removes only those: an unknown note stays, since a few extra tokens beat cut legal text.

Text defaults: `DEFAULT_MAX_CHARS` 20,000, max 100,000. Text sources are `planalto` and `camara_legin`.

[^l]: legislation.py
[^lt]: legislation_text.py
