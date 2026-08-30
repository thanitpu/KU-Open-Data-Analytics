# YouTube Source Foundation for Q-Diving

Status: metadata-only foundation; Human Review required; production scheduling disabled.

This foundation turns the legacy Q-004 and Q-005 YouTube search-page references into traceable query profiles for four Q-Diving research collections. Learning-to-dive research includes beginner training, Open Water skills, safety procedures, brief/debrief practice, and common mistakes. Equipment research covers masks, fins, exposure protection, BCDs, regulators, computers, tanks, underwater cameras, and rent/buy/maintenance decisions. Destination research covers Thailand (including Koh Tao, Similan, Richelieu Rock, Phuket, Phi Phi, Krabi, Chumphon, and Koh Lipe) and international regions such as Southeast Asia, Maldives, Raja Ampat, Komodo, Sipadan, Palau, Red Sea, and Great Barrier Reef. It does not make YouTube content authoritative and does not approve or store candidates automatically.

## Lifecycle and scope

YouTube metadata follows the KU2D lifecycle:

`Discover → Explore → Deep Audit → Human Approve → Scheduled Acquire`

This checkpoint stops at Human Review staging. It uses only official public metadata returned by documented YouTube Data API v3 methods:

- `search.list` for bounded query-profile discovery;
- `videos.list` and `channels.list` to hydrate stable identities and metadata;
- optional `playlists.list` and `playlistItems.list` for playlist metadata;
- approved-channel monitoring through `channels.list` → uploads playlist → `playlistItems.list` → batched `videos.list`.

`commentThreads.list` is disabled. YouTube HTML pages, internal APIs, captions, transcripts, comments, audio, and video are not scraped or downloaded. Authentication, access controls, private/unlisted content, CAPTCHA, and anti-bot measures are never bypassed.

## Configuration

Set `KU2D_YOUTUBE_API_KEY` outside the repository. `.env.example` deliberately contains a blank placeholder. The API key authorizes the configured public Data API project and applies its quota; it does not grant access to private data or caption text. OAuth is a separate user/owner authorization mechanism and is not implemented in this checkpoint. `tools/YOUTUBE_API_STATUS.py` reports only whether a key is configured, the provider name, and policy version; it never prints the key.

Policy is versioned in `config/youtube_api_policy.json`. Query profiles are versioned in `config/q_diving_youtube_query_profiles.json`. Profile labels and research collections are KU2D curation metadata, not YouTube video categories.

The future controlled pilot command is deliberately explicit:

```text
python tools/LIVE_YOUTUBE_Q_DIVING_DISCOVERY.py \
  --profile QYT-BEGINNER-EN \
  --max-search-calls 1 --max-results 10 --max-pages 1 --quota-budget 20 \
  --no-approve --no-production-store
```

It refuses a missing key, unknown profile, unsupported endpoint, invalid budget, approval, or production storage. No live command or secret-backed workflow is included in this checkpoint.

## Quota and request discipline

The pilot permits at most 10 results per search, eight selected query profiles, eight actual `search.list` transport attempts, and two logical pages per query. `--max-search-calls` means actual `search.list` attempts: initial requests, transient retries, and next-page requests all consume the same cap. It does not count metadata hydration calls. `videos.list` is batched at 50 IDs. Every request produces a sanitized quota observation containing endpoint, request time/count, quota bucket, configured estimated cost, query profile, result count, next-page token, status, and error. Request URLs and keys are excluded.

Discovery preserves selected-profile order and performs one first-page attempt for every profile before allocating any retry or second page. Remaining attempts use a deterministic round-robin queue; a profile without `nextPageToken` is not queued for page two. Result evidence reports logical operations, actual attempts, transient retries, the maximum and exhaustion state, plus per-profile initial coverage, pages, attempts, retries, next-page availability, status, and error code. The compatibility field `search_calls_used` has the same meaning as `actual_search_attempts_used`.

Endpoint costs are configurable estimates rather than permanent guarantees. Quota errors stop the run and are not retried. Transient transport/server errors have bounded backoff and honor `Retry-After`. Multiple API projects must not be used to avoid quota limits.

## Captions and transcripts

Every video has:

- `caption_available`: `true`, `false`, or `unknown` from public metadata;
- `transcript_access_status`: `metadata-only`, `owner-authorization-required`, `creator-provided`, `user-provided`, `authorized-download`, or `unavailable`;
- `transcript_text`: always `null` in this foundation.

A caption-availability flag is not transcript authorization. A future transcript pathway must be separately reviewed and must use creator-provided text, user-provided text, or owner-authorized OAuth access with the required video permissions. It must preserve that authorization provenance and the 30-day/API policy boundary where applicable. Third-party transcript scrapers are prohibited.

## Retention, provenance, and deletion

Non-authorized API data is refreshed or deleted within 30 days. Normalized candidates record `observed_at`, `api_refreshed_at`, `refresh_due_at`, `source_endpoint`, query-profile provenance, `etag`, and `data_status`. A requested ID missing from `videos.list` is an unavailable, non-usable tombstone with reason `missing-from-videos-list` and `deletion_confirmed: false`; absence alone never claims deletion. Explicitly unavailable, restricted, private, or independently confirmed deleted items also remain non-usable. Raw API snapshots are not retained.

## Foundation quality gates

A review batch requires at least five public videos, 100% video identity, at least 95% channel identity, at least 95% titles, at least 90% publication times, 100% canonical URL/provenance/refresh-due fields, no more than 5% duplicates, and no unauthorized transcript text. Restricted/private items never count as publicly usable. Views and likes are observations, not quality or authority gates.

Authority, influencer status, safety, trust, audience, sentiment, monetization, and rankings are not calculated. The separated manual fields may classify a reviewed source as `training_authority`, `equipment_manufacturer`, `dive_operator`, `independent_instructor`, `equipment_reviewer`, `travel_dive_creator`, or `community_creator`, with a human note, research collection, approver, and approval time. These values are KU2D annotations, never YouTube metadata. Candidate metadata is staged for Human Review and cannot trigger approval, repository storage, or scheduling.
