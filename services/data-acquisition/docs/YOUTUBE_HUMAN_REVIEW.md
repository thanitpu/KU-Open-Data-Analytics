# YouTube Human Review for Q-Diving

> P51 boundary alignment: semantic video relevance, quality, ranking, analytical deduplication and final inclusion are Analysis responsibilities. The review contracts below remain relevant to downstream Analysis and to separate monitoring/production authority; they are no longer an Acquisition completion gate. Every technically accepted sanitized Acquisition record is handed to Analysis.

This layer turns sanitized YouTube Data API v3 foundation metadata into a compact, non-production review package. It does not approve videos or channels, acquire transcripts or comments, write scheduler state, or create Product & Price records.

The controlled flow is:

```text
Foundation Candidate
  → Human Review
  → Knowledge Include / Include with context / Exclude
  → Separate Channel Monitoring Decision
  → Non-production KU2A Dataset Handoff
```

## Review records are separate

`YouTubeVideoReview` and `YouTubeChannelReview` are separate records keyed by YouTube identity. Foundation metadata is not edited in place. Every staged review starts with `review_status: pending`; the decision fields and reviewer provenance remain blank.

A video reviewer records relevance, content roles, research collections, commercial context, knowledge use, a note, and reviewer identity/time. A channel reviewer separately records source class, domain focus, monitoring decision, a note, and reviewer identity/time.

Automated relevance, equipment, commercial-context, source-class, and domain-focus outputs are labelled as suggestions. They are screening aids, not authoritative facts and never change a review to `reviewed`.

**Video approval is not Channel monitoring approval.** A video may be suitable for a knowledge dataset without authorizing ongoing monitoring of its channel. Conversely, a channel monitoring decision requires its own completed Human Review.

**Commercial context is not automatic rejection.** Disclosed affiliate, sponsorship, promotional, product-promotion, or operator self-promotion cues give reviewers context. Their presence does not decide knowledge use, and their absence is `unknown` rather than proof that no sponsorship exists. The YouTube-supplied paid-product-placement flag is preserved separately; a false or missing flag is not interpreted as “not sponsored.”

## Prepare a Human Review package

From `services/data-acquisition`, run:

```text
python tools/PREPARE_YOUTUBE_HUMAN_REVIEW.py \
  --input <foundation-result.json> \
  --output <review-package.json>
```

The package contains compact candidate video/channel metadata, profile provenance, review suggestions, pending review records, and contextual `PriceMentionCandidate` records. It deliberately omits API credentials, raw API responses, thumbnails, transcript text, comments, and unnecessary personal data. A non-null transcript in the input is rejected rather than copied.

Only public, current, usable foundation candidates enter the package. Each candidate retains provider, endpoint, query-profile, observation, and refresh provenance.

Before a KU2A handoff is built, `validate_review_package_integrity()` rejects malformed or contradictory manual edits. Candidate and review identities must be non-empty, unique, and one-to-one. Included candidates must retain an official YouTube Data API provider, current/public foundation status, source channel attribution, refresh timing, and a valid query-profile provenance path. Pending reviews cannot carry final decisions or reviewer provenance. Irrelevant videos must be excluded, while included videos must be core or adjacent. Duplicate and unknown identities are reported explicitly before any aggregation occurs.

## Deterministic screening suggestions

The relevance screen recognizes only transparent metadata cues:

- `core`: an exact beginner scuba/course match, including Koh Tao when the profile requires it, or diving-equipment vocabulary matching the equipment collection;
- `adjacent`: freediving in a scuba-beginner collection, diving from another location for a Koh Tao profile, or meaningful diving content without an exact collection match;
- `irrelevant`: no meaningful diving relation in the title or description.

Equipment screening supports mask, fins, wetsuit, BCD, regulator, dive computer, tank, underwater camera, accessory, maintenance, rental, purchase, and fitting/sizing vocabulary. It also recognizes transparent equipment intent such as scuba/dive gear, equipment assembly and setup, beginner gear, what to buy first, and equivalent Thai phrases for choosing, buying, or assembling dive equipment.

Activity scope remains part of the suggestion. Snorkeling-only, spearfishing-only, and freediving-only equipment stays adjacent to the scuba equipment collection unless the metadata also contains explicit scuba context. Generic equipment wording such as `อุปกรณ์ดำน้ำ` is therefore not sufficient by itself to turn an adjacent activity into core scuba equipment. All results remain suggestions until Human Review.

Commercial screening reports independent, evidence-bearing dimensions rather than forcing mutually compatible facts into one label:

- `sponsorship_status`: `disclosed_sponsored`, `explicitly_not_sponsored`, or `unknown`;
- `affiliate_status`: `disclosed` or `not_observed`;
- `operator_self_promotion`: whether a transparent self-promotion cue was observed;
- `promotional_offer`: whether a transparent offer cue was observed.

Negated phrases such as “not sponsored,” “this video is not sponsored,” and “unsponsored” are explicit negative sponsorship evidence and are not reused as positive sponsored matches. No sponsorship cue still means `unknown`, never “not sponsored.” Likewise, affiliate status `not_observed` means only that no transparent affiliate cue was found; it is not proof that no affiliate relationship exists. A conservative `compatibility_summary` is retained for older consumers; it is not the authoritative representation. For example, “not sponsored” plus disclosed affiliate links has sponsorship status `explicitly_not_sponsored`, affiliate status `disclosed`, and compatibility summary `affiliate`.

Commercial screening reports the matched title/description cue and source field. It does not infer hidden sponsorship.

Channel suggestions distinguish `equipment_retailer` when public metadata explicitly describes a scuba/dive store, shop, retailer, or equivalent Thai equipment seller. Manufacturer, reviewer, dive-operator, and community classifications remain separate. Generic affiliate creators are not treated as retailers without store/retailer evidence. Retailer or other commercial source status supplies provenance for Human Review; it does not imply rejection.

## Channel monitoring boundary

`create_monitoring_plan()` can return a dry `YouTubeChannelMonitoringPlan` only when:

- channel review is complete;
- `monitoring_decision` is `approve`;
- the reviewed and candidate `channel_id` values match;
- an `uploads_playlist_id` is present;
- reviewer identity and time are present.

The plan uses the uploads playlist, not repeated search. It always has `production_enabled: false` and `scheduler_action: null`. This checkpoint writes no scheduler or approval state. A later, separately reviewed production checkpoint would be required to enable scheduling.

## Price mentions are not commerce evidence

A recognizable amount in a title or description may become a `PriceMentionCandidate` with value, currency, local text context, video identity, observation time, source-statement marker, the multidimensional commercial suggestion, and a conservative compatibility context. It explicitly has:

```json
{
  "current_commerce_price_evidence": false,
  "product_price_acquisition_record": false
}
```

YouTube metadata is not a Product & Price acquisition source in this checkpoint.

## KU2A knowledge handoff

`YouTubeKnowledgeDataset` is the versioned, non-production contract for:

```text
KU2D → reviewed YouTube metadata → KU2A Workspace
```

The contract is defined in `config/youtube_knowledge_dataset_schema.json`. Only completed video reviews marked `include` or `include_with_context` enter `included_video_ids`.

`included_channel_ids` is source-channel provenance: it contains the unique channel IDs attached to included video candidates. It is not a monitoring authorization list. Rejecting monitoring for a general travel/lifestyle channel does not remove that channel's source attribution from an included video.

Monitoring decisions are represented separately:

- `monitoring_approved_channel_ids` contains only completed channel reviews whose decision is `approve`;
- `monitoring_watch_channel_ids` contains only completed channel reviews whose decision is `watch`;
- rejected and pending channels appear in neither monitoring list.

Only an approved channel can produce a dry monitoring plan; `watch` remains an observation decision rather than authorization. The dataset also carries query profiles, research collections derived from candidate provenance, a Human Review summary, provider/schema provenance, and the earliest relevant refresh date. `production_approved` is fixed to `false`.

This checkpoint does not integrate the dataset with `app.html` or any KU2A UI.

## Equipment Pilot #2 preparation

The next controlled pilot is limited to these two profiles:

- `QYT-EQUIPMENT-BEGINNER-TH`
- `QYT-EQUIPMENT-SETUP-EN`

After separate review and local credential setup, the recommended command is:

```text
python tools/LIVE_YOUTUBE_Q_DIVING_DISCOVERY.py \
  --profile QYT-EQUIPMENT-BEGINNER-TH \
  --profile QYT-EQUIPMENT-SETUP-EN \
  --max-search-calls 2 \
  --max-pages 1 \
  --max-results 10 \
  --quota-budget 10 \
  --no-approve \
  --no-production-store \
  --output <external-runtime-path>
```

Do not place `KU2D_YOUTUBE_API_KEY` in the command, repository, output file, logs, or review package. The command is documentation only for this checkpoint; no Equipment pilot is dispatched here.

## Deterministic fixtures

`fixtures/youtube_human_review/sanitized_foundation_result.json` represents Thai and English beginner courses, freediving adjacency, non-Koh-Tao scuba adjacency, dive-operator and travel/lifestyle channels, an affiliate equipment example, and irrelevant content. IDs and metadata are synthetic. The fixture contains no pilot raw response or credential.
