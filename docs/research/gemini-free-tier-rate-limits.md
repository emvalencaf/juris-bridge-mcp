# Research: Gemini API free-tier rate limits for the text models

Researched 2026-10-22. Questions: what are the RPM, TPM and RPD of each text Gemini model
on the Free tier, are limits per project, when does the day reset, what happens on excess,
what does "access limited" mean for the 2.5 family, is function calling supported, and does a
manual evaluation (~30 cases x 3 repetitions, several tool calls each, a Flash agent plus a
2.5 Pro judge) fit in one day?

Method: Google primary sources only (ai.google.dev docs pages: rate-limits, pricing, models,
per-model pages, api-errors, troubleshooting, changelog; one official-staff reply on the
Google AI Developers Forum). Pages were fetched on 2026-10-22 through a fetch tool that
summarises the page, so quotes are as returned by that tool. Tags: `[V]` verified (the
source was opened), `[U]` unverified (do not treat as a finding). The AI Studio rate-limit
page (`aistudio.google.com/rate-limit`) redirects to a Google login and could not be read.

## Summary

- **The official docs do not publish any free-tier RPM, TPM or RPD number for any model.**
  The rate-limits page only names the three dimensions and says limits vary by model;
  per-model values are shown in AI Studio behind a login. [V]
- Because of that, every per-model number in this file is "not published" in primary docs.
  Only unofficial/forum figures exist (see "What was NOT confirmed"), and they are [U].
- The only official free-tier signal is from Google staff on the forum: Google "did turn
  down the free tier for some models in order to free up compute", and the free tier is
  "best effort", "highly unstable and not likely to persist" (2025-12-07). [V]
- Limits are per **project**, not per API key; so several keys in one project do not add
  quota. Several keys help only if they belong to different projects. [V]
- RPD resets at **midnight Pacific time**. [V]
- All eight models are marked free of charge for input and output in the Free tier column of
  the pricing page, but "free of charge" is not a quota. [V]
- Function calling is "Supported" on the two model pages opened (gemini-3.8-flash,
  gemini-2.5-pro). [V for those two; the other six not opened]
- Fit for the evaluation: cannot be decided from primary sources. Check the numbers in the
  owner's own AI Studio rate-limit page first (the only authoritative source). The workload
  is roughly 90 runs x several tool calls = several hundred agent requests plus 90 judge
  requests; if the Pro judge limit is around 20 RPD or lower (unverified) it will not fit in
  a day.

## 1. Per-model free-tier limits

Same result for all eight models: RPM, TPM and RPD are **not published** in the docs. The
Pricing column states only what the pricing page says for the Free tier (Standard).

| Model | RPM | TPM | RPD | Pricing page, Free tier (Standard) | Source |
|---|---|---|---|---|---|
| gemini-3.8-flash | not published | not published | not published | input, output, caching "Free of charge"; Search grounding "Not available" [V] | [1] [2] |
| gemini-3.6-flash | not published | not published | not published | input, output, caching "Free of charge"; Search and Maps grounding "Not available" [V] | [1] [2] |
| gemini-3.5-flash-lite | not published | not published | not published | input and output "Free of charge"; caching "Not available" [V] | [1] [2] |
| gemini-3.1-flash-lite | not published | not published | not published | input and output "Free of charge"; caching "Not available" [V] | [1] [2] |
| gemini-3-flash-preview | not published | not published | not published | input, output, caching "Free of charge" [V]; preview models are "more restricted" per [1] | [1] [2] |
| gemini-2.5-pro | not published | not published | not published | input and output "Free of charge"; caching "Not available" [V]; access limited, see section 4 | [1] [2] [4] |
| gemini-2.5-flash | not published | not published | not published | input and output "Free of charge"; caching "Not available"; Search "up to 500 RPD (limit shared with Flash-Lite RPD)" [V]; access limited | [1] [2] [4] |
| gemini-2.5-flash-lite | not published | not published | not published | same as 2.5 Flash; Search 500 RPD shared with Flash [V]; access limited | [1] [2] [4] |

Notes:

- The 500 RPD figure is a **Google Search grounding** quota, not the request limit of the
  model. [V]
- Context and output limits (only two model pages opened): gemini-3.8-flash and
  gemini-2.5-pro both list input 1,048,576 tokens and output 65,536 tokens. [V] The other six
  model pages were not opened; the models index page does not state token limits. [V]
- Concurrent calls: no concurrency limit is published for generation requests. The only
  concurrency figure is for the Batch API (100 concurrent batch requests). [V]
- Priority inference: default 0.3x the standard limit per model and tier. [V] On the pricing
  page, Batch and Flex are "Not available" on the free tier for 3.x models. [V]
- "Specified rate limits are not guaranteed and actual capacity may vary." [V][1]

## 2. Scope, tiers and reset

- "Rate limits are applied per project, not per API key." [V][1]
- Exceeding any one of RPM, TPM or RPD triggers an error, even if the others are within
  limits. [V][1]
- RPD quotas "reset at midnight Pacific time". [V][1]
- Free tier = "an active project or free trial". Tier 1 = linked active billing account,
  upgrade "will typically take effect instantly". Tier 2 = $100 cumulative plus 3 days; Tier 3
  = $1,000 plus 30 days. [V][1]
- Spend-based limits (rolling 10-minute window): Free N/A, Tier 1 $10, Tier 2 $50, Tier 3
  $200. [V][1]
- The docs direct the reader to "View your active rate limits in AI Studio". [V][1]

## 3. Behaviour on exceeding the limit

- HTTP **429**. The API errors page maps 429 to three codes: `rate_limit_exceeded` ("exceeded
  the per-minute or per-second request or token limit", wait and retry with exponential
  backoff), `quota_exceeded` ("exceeded your daily quota", wait until reset or request an
  increase) and `too_many_requests`. [V][5]
- The rate-limits page mentions 429 `RESOURCE_EXHAUSTED` for spend-based limits. [V][1]
- Troubleshooting page: 429 and 503 are retryable; use exponential backoff with jitter and a
  maximum number of attempts; the official Python SDK retries 429 and 5xx up to four times
  (about 1 s start, 60 s cap). [V][6]
- **`Retry-After` header: not documented.** None of the error pages mention `retry-after`,
  `retryDelay` or `RetryInfo`. [V that they are absent from those pages; whether the live API
  sends them is not confirmed]

## 4. "Access limited" for the 2.5 family

Literal text on the models page and on the gemini-2.5-pro page: "we are limiting access to
the 2.5 models to users who have actively used them in the past", followed by "These models
are not deprecated and will continue to be served until further notice through the API." [V][3][4]
The changelog dates this entry **2026-09-18**. [V][7] Reading: a project that never used 2.5
models before that date may not be able to call them at all, free tier or not. Whether a given
project qualifies is not determinable from docs; test with one call. The exact phrase
"access limited" does not appear on the pricing page, which says only "Limited access to
certain models" on the Free plan card. [V][2]

## 5. Function calling

- gemini-3.8-flash: "Supported". [V][8]
- gemini-2.5-pro: "Supported" under Capabilities. [V][4]
- gemini-3.6-flash, 3.5-flash-lite, 3.1-flash-lite, 3-flash-preview, 2.5-flash, 2.5-flash-lite:
  model pages not opened; not confirmed. [U]

## Values shown in the owner's AI Studio (2026-10-22)

The owner pasted the AI Studio rate-limit page of their project (source 11). It is the
authoritative source the docs point to, but it is a copy made by the owner, not a public page,
and each value is the quota of this project on this date. [V, owner-provided]

| Model | RPM | TPM | RPD |
|---|---|---|---|
| gemini-3.6-flash | 5 | 250K | 20 |
| gemini-3.8-flash | 5 | 250K | 20 |
| gemini-3-flash (preview) | 5 | 250K | 20 |
| gemini-2.5-flash | 5 | 250K | 20 |
| gemini-2.5-flash-lite | 10 | 250K | 20 |
| gemini-3.5-flash-lite | 15 | 250K | 500 |
| gemini-3.1-flash-lite | 15 | 250K | 500 |
| gemini-2.5-pro | 0 | 0 | 0 |
| gemini-3.1-pro | 0 | 0 | 0 |
| gemini-4-argon | 0 | 0 | 0 |
| Gemma 4 26B / 31B | 30 | 16K | 14.4K |

- A limit of 0 means no free access for this project: `gemini-2.5-pro`, `gemini-3.1-pro` and
  `gemini-4-argon` cannot be called. This matches the 2026-09-18 restriction of the 2.5 family
  and the pricing page ("Not available" for the Pro models).
- The quotas are listed per model, so each model has its own daily budget.
- Gemma has the largest daily quota but a TPM of 16K, which a request carrying Publication text
  may exceed on its own.

## What was NOT confirmed

- Any free-tier RPM, TPM or RPD in the public docs. The values for this project come only from
  the owner's AI Studio copy above; they may differ for other projects and change without notice.
- Whether the live API returns `Retry-After` or `RetryInfo` on 429.
- Function calling and token limits for six of the eight models.
- Whether this owner's project is allowed to call the 2.5 models (restriction since
  2026-09-18).
- Whether a deployment with several keys under one project gains anything (the docs say no).
- Unofficial figures seen only in search results, all [U], conflicting and not to be used as
  fact: a forum thread (2025-12-06, user post, answered by Google staff without numbers)
  says Flash free RPD fell from 250 to 20; a GitHub issue in a third-party repo
  (robhunter/agentdeals #2017) says 2.5 Flash is about 5 RPM / 20 RPD after 2025-12-06; a
  July 2025 forum thread listed 2.5 Flash at 10 RPM / 250,000 TPM / 250 RPD; an awesome-list
  repo gave 15 RPM / 1,500 RPD. These describe different dates and cannot be reconciled.

## Sources

1. Rate limits, Gemini API. <https://ai.google.dev/gemini-api/docs/rate-limits> (2026-10-22)
2. Pricing, Gemini API. <https://ai.google.dev/gemini-api/docs/pricing> (2026-10-22)
3. Models, Gemini API. <https://ai.google.dev/gemini-api/docs/models> (2026-10-22)
4. gemini-2.5-pro model page. <https://ai.google.dev/gemini-api/docs/models/gemini-2.5-pro> (2026-10-22)
5. API errors. <https://ai.google.dev/gemini-api/docs/api-errors> (2026-10-22)
6. Troubleshooting. <https://ai.google.dev/gemini-api/docs/troubleshooting> (2026-10-22)
7. Changelog. <https://ai.google.dev/gemini-api/docs/changelog> (2026-10-22)
8. gemini-3.8-flash model page. <https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash> (2026-10-22)
9. Forum thread with reply by Google staff (Logan Kilpatrick, 2025-12-07).
   <https://discuss.ai.google.dev/t/do-they-really-think-we-wouldnt-notice-a-92-free-tier-quota/111262> (2026-10-22)
10. AI Studio rate limits (login required, not read). <https://aistudio.google.com/rate-limit>
11. Owner-provided copy of the AI Studio rate-limit page of their project, 2026-10-22 (login
    required; not a public URL). <https://aistudio.google.com/rate-limit>
