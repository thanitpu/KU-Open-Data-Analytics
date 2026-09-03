# Q-Diving Non-YouTube Source Expansion — 2026-08-31

## Outcome

Three representative official public sources were explored with one plain-HTTP
page load each and a 10-record retention cap. Static HTML was sufficient for
all three. No normal browser or Edge Runner was required, and YouTube
acquisition remained paused.

| Source | Evidence class | Retained | Stable identity | Price semantics | Technique status |
| --- | --- | ---: | --- | --- | --- |
| SSI Blog | Diving content metadata | 10 | Canonical article URL/slug | Not applicable | Promising; Deep Audit next |
| Scubadoo Koh Tao | Dive-course service | 10 | Official host + course name | Explicit THB service price | Promising; Deep Audit next |
| Aquamaster Thailand | Sellable dive equipment | 10 | Canonical product URL/slug | Explicit THB price/range | Promising; Deep Audit next |

The public pages returned HTTP 200 and complete record-bearing HTML. Scubadoo
and Aquamaster include dormant CAPTCHA/form-plugin strings in page source;
because the public course and product content was present and no verification
interaction was requested, those strings are not an access-control event.

## Evidence contracts

### SSI Blog

The static article-card index provides official canonical URLs, titles, short
summaries, and observation provenance. Relative display dates are not converted
into exact publication timestamps; `published_at` remains null. Content
relevance and authority remain Human Review decisions. The current page may
include scuba, freediving, mermaid, conservation, and other adjacent topics.

### Scubadoo Koh Tao

Course cards provide course/service name, explicit THB price, duration, number
of dives, and accommodation context where displayed. The technique writes
`DiveCourseServiceCandidate`, not a Retail or Commerce Market Observation
record. No booking link was followed and no form was submitted.

### Aquamaster Thailand

WooCommerce catalog cards provide canonical product identity, title, equipment
categories, and one price or a variant range. Sale-page display position is
stored only as source-surface provenance. It is not a sold counter, popularity
rank, or national demand signal.

## Technique transfer

- OTA contributes the rule that service price needs package and location
  context, but a dive course is not a room/rate observation.
- Retail detail/catalog patterns transfer to Aquamaster identity and price,
  while Commerce Pulse demand semantics do not.
- Existing PADI public-feed work transfers to SSI content metadata, with Human
  Review preserved for relevance and authority.
- YouTube Human Review knowledge can inform future curation but does not
  authorize or contaminate these public-web records.

## Safety and next steps

Request accounting is three page loads, zero retries, zero pagination, and zero
browser/Edge loads. No login, cookies, session reuse, CAPTCHA handling,
proxying, bypass, booking, form submission, production write, scheduling, or
approval occurred.

Recommended next action is a separate deterministic Deep Audit for repeatability
and change semantics. SSI needs topic/relevance review; Scubadoo needs service
identity stability and package-change checks; Aquamaster needs product-detail
correlation and current/original/range price semantics.

`production_approved=false`, `production_store=false`, and
`scheduler_action=null` remain mandatory.
