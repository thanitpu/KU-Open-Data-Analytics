# Acquisition-to-Analysis Handoff v1

## Boundary

Data Acquisition completes a record when it is technically valid, authorized, policy-compliant, provenance-bearing and sanitized. Completion means `accepted_for_analysis`; it does not assert semantic relevance, quality, rank, analytical uniqueness, final inclusion, production readiness, approval or scheduling.

Analysis owns semantic relevance, quality assessment, ranking, analytical grouping/deduplication and final inclusion. Those values remain `null` in the handoff until Analysis assesses them. Acquisition may remove only exact technical duplicates, and only when the retained record preserves traceability to every source observation.

An Acquisition-stage Human gate remains appropriate only for legal/policy ambiguity, restricted or personal data, material provider scope or quota expansion, new spending, production write or elevated authority. Semantic candidate selection is not an Acquisition gate.

## Versioned contract

The active schema is `knowledge/v1/acquisition-analysis-handoff.schema.json`, with policy `KU2D-KP-000003` in `knowledge/v1/acquisition-analysis-boundary-policy.json`. The pure validator is `acquisition/acquisition_analysis_handoff.py`.

Each intake manifest must:

- identify its source domain, provider, batch, Result and sanitized artifact;
- pin the immutable source packet by path, commit, Git blob SHA and SHA-256;
- index every accepted record exactly once in source-packet order;
- preserve candidate identity, channel identity, query-profile provenance and observation time;
- set `semantic_relevance`, `quality`, `analytical_rank`, `analytical_deduplication` and `final_inclusion` to `null`;
- state that production is not ready or approved and scheduling is absent;
- prove zero hidden records and a record count consistent across acceptance, handoff and retrieval sections.

Historical packets with `selection_target`, `human_review_completed`, `usable_reviewed_identity_count`, `human_adjudication_required` or `usable_for_live_acquisition` remain readable evidence of their execution-time contract. Those fields are not active authority and are not rewritten.

## P50 YouTube intake

`knowledge/v1/analysis-intake-manifests/KU2D-AI-000001.json` stages all ten records from immutable packet `KU2D-YT-QDIVING-CANDIDATES-000001`. It references P50 Result `KU2D-R-000050`, artifact `9786568183`, the packet's creating commit and exact content hashes. No record is discarded or hidden.

All ten records are `accepted_for_analysis`. Their semantic relevance, quality, rank, analytical deduplication and final inclusion remain pending Analysis. This manifest performs no provider request, consumes no quota, writes no production data, grants no production approval and schedules nothing.
