# YouTube Human Review for Q-Diving

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

## Deterministic screening suggestions

The relevance screen recognizes only transparent metadata cues:

- `core`: an exact beginner scuba/course match, including Koh Tao when the profile requires it, or diving-equipment vocabulary matching the equipment collection;
- `adjacent`: freediving in a scuba-beginner collection, diving from another location for a Koh Tao profile, or meaningful diving content without an exact collection match;
- `irrelevant`: no meaningful diving relation in the title or description.

Equipment screening supports mask, fins, wetsuit, BCD, regulator, dive computer, tank, underwater camera, accessory, maintenance, rental, purchase, and fitting/sizing vocabulary. These remain suggestions until Human Review.

Commercial screening reports the matched title/description cue and source field. It does not infer hidden sponsorship.

## Channel monitoring boundary

`create_monitoring_plan()` can return a dry `YouTubeChannelMonitoringPlan` only when:

- channel review is complete;
- `monitoring_decision` is `approve`;
- the reviewed and candidate `channel_id` values match;
- an `uploads_playlist_id` is present;
- reviewer identity and time are present.

The plan uses the uploads playlist, not repeated search. It always has `production_enabled: false` and `scheduler_action: null`. This checkpoint writes no scheduler or approval state. A later, separately reviewed production checkpoint would be required to enable scheduling.

## Price mentions are not commerce evidence

A recognizable amount in a title or description may become a `PriceMentionCandidate` with value, currency, local text context, video identity, observation time, source-statement marker, and commercial-context suggestion. It explicitly has:

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

The contract is defined in `config/youtube_knowledge_dataset_schema.json`. Only completed video reviews marked `include` or `include_with_context` enter `included_video_ids`. Only completed channel reviews with `approve` or `watch` monitoring decisions enter `included_channel_ids`. The dataset carries query profiles, research collections, a Human Review summary, provider/schema provenance, and the earliest relevant refresh date. `production_approved` is fixed to `false`.

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
