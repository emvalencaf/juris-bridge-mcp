# DataJud is self-hosted per user; MVP sources need no browser

The DataJud terms of use (3.3, 3.8) allow only non-commercial use and forbid
redistributing derived information, so the maintainer does not run a public
instance with DataJud enabled. Each user self-hosts the container with their own
key and answers for their own use; a maintainer instance, if any, is personal and
non-commercial, and a shared instance needs written CNJ authorization. The AWS
target is a reference for each user's own deployment, and the simple API key
serves one user or team.

The MVP sources are DataJud for cases and the Senado `dadosabertos/legislacao`
API for legislation, with norm text from Planalto or Câmara Legin over plain
HTTPS and an honest User-Agent. Playwright is excluded from the image with no
fallback: LexML SRU is gone (404) and its portal is guarded by a proof-of-work
challenge that we do not circumvent. This keeps the image small and portable to
Lambda and Fargate.

## Considered

- **Public hosted instance:** easiest for users, but conflicts with the DataJud
  terms. Revisit only with written CNJ authorization or a replacement source that
  allows commercial use.
- **LexML via Playwright:** works today, but robots.txt disallows `/busca/`, the
  challenge is a deliberate anti-bot control, and it forces a heavy image.
- **Spoofing a browser User-Agent for Planalto:** passes its filter (observed
  2026-10-17) but is a workaround of a block; instead we fall back to Câmara
  Legin, then to metadata and links only.

## Consequences

Case-law text, an own legislation index, judge and party search, and magistrate
decision history are follow-ups that need other sources (STJ CKAN, court
portals); the public DataJud has no party or judge fields.
