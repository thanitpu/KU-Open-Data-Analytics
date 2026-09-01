# YouTube Content Acquisition v2

> P51 boundary alignment: Acquisition hands every technically valid, authorized, policy-compliant, provenance-bearing and sanitized record to Analysis. Human Review in this document governs downstream Analysis inclusion or separate production/monitoring authority; it is not a semantic-selection prerequisite for Acquisition completion.

Status: offline contract ready; no live content validation; no acquisition,
OAuth, production storage, scheduling, or authority is granted.

YouTube Acquisition Pattern v2 is:

```text
Channel Discovery
→ Playlist/Video Enumeration
→ Metadata
→ Thai/English Transcript/Caption
→ Comments/Replies
→ Normalize
→ Provenance
→ Quality/Deep Audit
→ Dataset Intake
```

The machine-readable contract is
`config/youtube_content_acquisition_v2.json`. The storage-neutral KU2D-to-KU2A
shape is `config/youtube_content_dataset_schema_v2.json`. The validator and
offline normalizers are in `acquisition/youtube_content_acquisition_v2.py`.
They have no network transport, credentials, OAuth, browser, repository write,
approval, or scheduler capability.

## Existing foundation and v2 boundary

The merged v1 foundation remains unchanged. Its official Data API provider
supports bounded `search.list`, `channels.list`, `playlists.list`,
`playlistItems.list`, and `videos.list`; it stages metadata for Human Review,
uses uploads playlists for dry monitoring, retains no raw API snapshots, and
keeps comments, arbitrary transcripts, production storage, and scheduling
disabled.

V2 adds a durable capability and normalization design, not live endpoint
execution. Existing `youtube_api_policy.json` remains the active provider
policy and still has `comments_enabled: false`,
`comment_acquisition_enabled: false`, and
`arbitrary_transcript_acquisition_enabled: false`.

## Expanded metadata capability

Public API-key reads can represent:

- channel identity, description, custom URL, country, publish time,
  thumbnails, uploads playlist, and timestamped statistics;
- playlist identity, channel relationship, description, publish time,
  item count, thumbnails, and privacy status;
- playlist-item identity, video relationship, position, and publish time,
  with complete enumeration requiring explicit pagination;
- video identity, channel relationship, title, description, tags, category,
  duration, default metadata/audio language, caption-availability flag,
  live/upcoming state, public status, region restriction, thumbnails,
  timestamped statistics, topic categories, and live-stream timing when present;
- video-category identity/title through `videoCategories.list`.

The official [`videos.list` documentation](https://developers.google.com/youtube/v3/docs/videos/list)
defines selectable resource parts and a one-unit list cost. The
[`video` resource](https://developers.google.com/youtube/v3/docs/videos)
documents `snippet`, `contentDetails`, `status`, `statistics`,
`topicDetails`, and `liveStreamingDetails`. File, processing, and suggestion
details remain owner-authorized and outside the public-read contract.

Publish timestamps are retained exactly where the resource exposes them.
There is no generic public `updated_at` for channel, playlist, or video
metadata, so V2 does not invent one. Comment edit time is separately available.
Statistics are timestamped observation snapshots. They are not causes,
popularity truth, relevance, sentiment, or demand.

## Thai/English transcript and caption contract

The canonical language scope is exactly:

```json
{"allowed_languages":["th","en"]}
```

Transcript text in any other language is rejected. Other-language track
availability may be retained without text. Automatic language substitution is
forbidden.

For each allowed language, deterministic track precedence is:

1. manual original;
2. manual translated;
3. auto-generated original;
4. auto-generated translated.

Selected-language output order is Thai then English, so both may coexist. A
translated track must identify its original language and translation method.
Manual/auto, original/translated, source surface, acquisition time, track ID,
and authorization provenance remain independent fields.

The public `videos.list` caption flag says only whether captions are available;
it exposes neither track identity nor text. Official
[`captions.list`](https://developers.google.com/youtube/v3/docs/captions/list)
returns track metadata but requires OAuth and costs 50 units. Official
[`captions.download`](https://developers.google.com/youtube/v3/docs/captions/download)
costs 200 units and requires permission to edit the video. Its `tlang`
translation is machine-generated and must be identified as translated.

V2 approves no arbitrary public transcript scraper or undocumented endpoint.
Creator/user-provided text can enter only as a separately reviewed input with
its own authorization and provenance; it is not represented as Data API
acquisition.

`transcript_segment` carries video and track identity, segment order,
start/end/duration when available, text, language, caption kind, original/
translated/auto flags, source surface, acquisition time, provenance, and
completeness. Missing timestamps remain null with an explicit gap indicator.

No captions, unsupported-language-only, captions unavailable/disabled,
owner-authorization-required, partial transcript, and unavailable video are
separate states. None automatically means extraction failure or irrelevance.

## Comments and replies contract

Official
[`commentThreads.list`](https://developers.google.com/youtube/v3/docs/commentThreads/list)
returns published top-level threads, supports one to 100 items per page, time
or relevance ordering, pagination, and embedded replies; the method costs one
unit. Embedded replies may be incomplete. When reply coverage is required,
bounded [`comments.list`](https://developers.google.com/youtube/v3/docs/comments/list)
calls retrieve replies by parent ID, also at one unit per call.

V2 normalizes top-level `comment` and `comment_reply` separately, preserving
video/thread/parent relationships, text, exposed author/channel fields,
timestamped like count, `publishedAt`, `updatedAt`, availability/moderation
state when observable, requested source order, API surface, acquisition time,
provenance, and coverage indicators.

The future pilot page default is a proposal—not observed coverage—and stops at
two pages per method. Every additional page is another quota-bearing request.
Quota/page ceilings, `commentsDisabled`, video unavailability, relationship
errors, provenance/evidence-write failure, or need for authorization stop the
module.

Requested order is acquisition context only. Time/relevance order, displayed
position, comment count, likes, or the observed sample must never be interpreted
as population representativeness, sentiment, popularity, or demand. Moderated,
deleted, hidden, or partially returned content makes coverage potentially
incomplete. Disabled comments, no comments, and zero replies are distinct from
technical failure.

## Semantic and authority boundaries

- Transcript text is not the video description.
- Creator speech is not viewer opinion.
- Comment count is not sentiment.
- Ordering is not representativeness.
- Transcript absence is not irrelevance.
- Metadata statistics are observations, not causal explanations.
- Provenance identifies evidence origin; it does not grant semantic authority.
- Analysis remains authoritative for semantic inclusion; Human authority remains separate for monitoring, production and elevated-scope decisions.

Metadata is required by default. Transcript and comments are optional by
default and can be configured as required, optional, or disabled. Optional
absence preserves its explicit status and can still exit `0`. A required
unresolved module exits `2` after evidence is written. Exit `1` is reserved for
technical/runtime, quota-accounting, relationship/contract-integrity, or
evidence-writing failure.

## KU2D-to-KU2A Dataset Intake

The V2 dataset contains storage-neutral channel, playlist, video,
transcript-segment, comment, and comment-reply tables. Identity and relationship
keys are explicit. Every entity carries acquisition time, source publish/update
time where available, provenance, module status, completeness, and quality.

KU2A can perform text analytics, sampling-aware sentiment work, topic analysis,
semantic search, and temporal analysis without importing YouTube acquisition
logic. This checkpoint implements none of those analytics. Dataset
`production_approved` and `production_store` are fixed to false and
`scheduler_action` is null.

## Offline quality and fixture coverage

The sanitized fixture covers channel/playlist/video metadata; manual Thai and
English captions; automatic Thai and English; both languages; translated
tracks; same-language precedence; unsupported-language-only; no captions;
captions disabled; unavailable video; owner-authorization-required; partial
transcript and timestamp gaps; comment/reply pagination; embedded/fetched reply
deduplication; edited comments; zero replies; disabled/no comments; unavailable
video; and quota boundary.

Deep Audit requires complete metadata identity and provenance, typed statistics
snapshots, unique entity identity, Thai/English-only text, track provenance,
segment relationships, disclosed timestamp gaps, comment relationships,
pagination disclosure, separate publish/update times, zero representativeness
claims, and complete cross-entity relationships. Record count is not a quality
substitute.

## Readiness and smallest future pilot

| Module | Readiness |
|---|---|
| Metadata | Existing provider and offline V2 contract validated; not live revalidated in this queue |
| Thai transcript | Offline selection/normalization ready; official acquisition needs separate owner authorization |
| English transcript | Offline selection/normalization ready; official acquisition needs separate owner authorization |
| Comments/replies | Offline normalization ready; v1 live policy remains disabled and public behavior is not live validated |

The smallest future pilot is a separately governed Q-Diving run over two
already Human-Reviewed public video candidates, requiring metadata, bounding
comments to two pages per video, and observing both a Thai and an English
language case. Caption list/download may run only if the owner separately grants
permission to edit those videos and the OAuth flow is independently approved;
otherwise the transcript module must record `owner_authorized_only` or
`evidence_withheld` without downloading content.

This recommendation is `proposal_not_observed`. It does not authorize the
pilot, credentials, OAuth, comments, caption download, live API calls,
production storage, scheduling, or knowledge promotion.
