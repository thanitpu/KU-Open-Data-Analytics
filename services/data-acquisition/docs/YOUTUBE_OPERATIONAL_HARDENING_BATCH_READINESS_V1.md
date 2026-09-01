# YouTube Operational Hardening & Batch Readiness v1

## Disposition of P36

P36 ended `evidence_withheld` (exit 2) before any source request. The exact blocker was 0 of 2 durable, non-sanitized, explicitly Human-Reviewed canonical video identities. Request, quota, page, metadata, comment, reply, caption, transcript and OAuth counts stayed zero. This is not evidence of credential failure, transport failure, YouTube access failure, or comment failure; those boundaries were never opened.

## Implemented capability versus live validation

This checkpoint implements offline contracts, fail-closed validators and sanitized simulations. None of the batch behavior is live-validated. No API credential was read, no YouTube API or content request occurred, and no candidate was promoted to Human-Reviewed authority.

| Module | Repository readiness | Live-validated status |
|---|---|---|
| Reviewed identity governance | Implemented, fail-closed | No; registry has 0 usable identities |
| Exact-input metadata batching | Implemented contract | No |
| Bounded comments and replies | Implemented contract | No |
| Quota ledger and planner | Implemented against cited documentation | No observed workload |
| Checkpoint, resume, idempotency | Implemented and simulated | No |
| Per-video isolation and aggregation | Implemented and simulated | No |
| Deep Audit | Implemented source/video/module gates | No live evidence |
| KU2A intake | Sanitized storage-neutral sample | No production handoff |

## Identity governance and candidate audit

The durable registry requires canonical ID and derived watch URL, channel linkage, optional title snapshot, unique Human Review linkage, explicit human authority and timestamp, purpose/profile, public-metadata privacy classification, evidence references, status/supersession/revocation, and an explicit usability flag. Active reviewed entries alone can be usable. Duplicate, malformed, sanitized, ambiguously linked, assistant-authorized, revoked or superseded records fail closed.

The merged evidence audit found only privacy-safe sanitized fixture candidates. They remain `candidate_only_evidence`, `not_human_reviewed`, and unusable. No live discovery was performed.

## Exact-input batch, comments, and evidence order

The manifest prohibits `search.list`, fallback discovery and automatic endpoint switching. Metadata is required and uses deterministic `videos.list` batches. Comments are optional by default: `commentThreads.list` is capped at two pages per video, and `comments.list` is permitted only when embedded replies are incomplete and budget remains. `commentsDisabled`, `no_comments`, truncation, unavailable/private/deleted status and moderated/deleted incompleteness are distinct outcomes. Ordering and counts are acquisition context only—not evidence of representativeness, sentiment, popularity or demand.

Every logical request has an immutable idempotency key. Evidence and checkpoint state must be durable before the next request. Checkpoints preserve run, manifest, video and page intent; raw page tokens are not persisted. Resume skips durable request keys and fails closed if scope, caps, endpoints or fingerprint drift.

## Quota and scale

Official Google/YouTube documentation accessed 2026-09-01 records one quota unit for `videos.list`, `commentThreads.list`, and `comments.list`; every request, including each pagination request, consumes quota. The merged metadata batch-size cap of 50 is a repository policy contract. Page caps, retry limits, timeouts, two-video budget and long-run workload ranges are `proposal_not_observed`, not guaranteed duration or yield.

For `V` reviewed videos, the conservative planning ceiling is `ceil(V/50)` metadata requests plus up to `2V` comment-thread requests and proposal-defined reply requests. The long-run template remains planning-only, serialized at concurrency 1, checkpointed per durable request, and contains no identities. Per-video isolation permits remaining eligible videos to finish, while aggregate exit remains deterministic: 0 only when required evidence/audit passes, 2 for technically complete required evidence withheld, and 1 for runtime/evidence/quota/integrity failure.

## Drift and Deep Audit

The taxonomy covers unavailable/deleted video, privacy/status, comments-disabled state, pagination, reply completeness, metadata disappearance, channel relationship, quota documentation, endpoint/schema, language signal, caption authorization boundary, and evidence writer failure. Bounded comment-state re-reads may remain within a reviewed manifest; identity/channel, schema/quota, language, captions/OAuth and authority changes stop or require re-review/new human authority.

Deep Audit produces separate source, video and module gates for identity provenance, metadata identity completeness, timestamped snapshot semantics, relationships, disclosed pagination/coverage, reconciled quota, deterministic checkpoint, zero unsupported-language transcript text, zero unauthorized caption/OAuth execution, zero representativeness claims, and `production_approved=false`.

## Operational tiers

The evidence-based tiers are `batch_ready_reviewed_identity`, `bounded_only`, `identity_review_required`, `owner_authorized_caption_required`, `unavailable_or_withheld`, and `drift_review_required`. Current Q-Diving status is `identity_review_required`; this checkpoint cannot promote it.

## Human Gate Register and next action

The durable register defers: exactly two reviewed canonical Q-Diving IDs; any expansion beyond two; live search/discovery; captions or OAuth owner flow; approval of any public transcript surface; production storage/scheduling; authority promotion; and broader batch execution. Each requires the evidence and authority stated in `config/youtube_operational_hardening_v1.json`.

The smallest governed next action is Human Review that establishes exactly two non-sanitized canonical video IDs with channel relationship and provenance evidence, then records them in the registry. Only after independent review may a separate prompt authorize the existing two-video exact-input manifest. No automatic rerun is allowed.

## References

Official documentation accessed 2026-09-01: [Videos: list](https://developers.google.com/youtube/v3/docs/videos/list), [CommentThreads: list](https://developers.google.com/youtube/v3/docs/commentThreads/list), [Comments: list](https://developers.google.com/youtube/v3/docs/comments/list), [quota costs](https://developers.google.com/youtube/v3/determine_quota_cost), [API reference](https://developers.google.com/youtube/v3/docs), and [captions reference](https://developers.google.com/youtube/v3/docs/captions).
