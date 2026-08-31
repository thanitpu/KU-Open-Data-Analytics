# KU2D Core Knowledge Backfill and Coverage Audit v1

Core Knowledge v1 is a deterministic, storage-neutral review layer over evidence that already exists in this repository. It does not perform acquisition, write runtime state, authorize production, schedule work, or create an ML dataset.

## Knowledge flow

```text
raw Learning Memory
        │  preserve observations, uncertainty, corrections, and failures
        ▼
Reviewed Learning Corpus
        │  sanitize, verify provenance, classify authority, reject contradiction
        ▼
future task-specific ML Training Dataset
        │  separate design/review/export checkpoint required
        ▼
training or inference (not implemented)
```

Raw Learning Memory is intentionally broad. It can include deterministic fixtures, negative outcomes, unresolved labels, review feedback, and future Human Confirmation. The Reviewed Learning Corpus is narrower: every included episode has repository provenance, explicit authority, taxonomy references, and non-production boundaries. It is a reviewed projection, not a replacement for the source artifacts.

An ML Training Dataset does not exist in v1. Corpus eligibility means only that an episode is safe and coherent enough to retain in the reviewed layer. A future dataset would still need a task-specific label definition, independent split and leakage review, privacy/security review, label-authority threshold, class-balance assessment, contradiction policy, versioned export, and explicit approval. Core Knowledge never exports examples automatically.

## Files and contracts

- `config/core_knowledge_taxonomy.json` defines separate dimensions for source characteristics, techniques, execution environments, evidence, interpretation, outcomes, boundaries, transferability, strength, authority, drift, quality/yield, request cost/latency, privacy/authorization, and provenance.
- `config/reviewed_learning_corpus.json` contains only sanitized high-confidence episodes and explicit exclusions.
- `config/candidate_learning_evidence_registry.json` records bounded evidence recovered from open unmerged Draft PRs with exact PR, commit, and file provenance. Candidates cannot self-promote.
- `config/human_confirmation_candidate_packet.json` preserves the five-item review request and its explicit disposition from `KU2D-H-000001`.
- `config/human_confirmed_core_semantic_policies.json` is the compact authority registry materialized through existing Learning Record, Human Confirmation, and Ground Truth contracts. It validates semantic policy only, never source outcomes.
- `config/core_coverage_matrix.json` assesses reusable capabilities and patterns rather than counting sites.
- `config/knowledge_gap_register.json` ranks future work by the missing pattern it would test. It starts no exploration.
- `config/ml_knowledge_map.json` records possible future supervised tasks, label authority, leakage risks, and honest readiness. It enables no training, export, embeddings, or inference.
- `acquisition/core_knowledge.py` validates these contracts as pure functions and performs no I/O.

All contracts are JSON/JSONL-compatible, versioned, deterministically serializable, and non-authorizing. The human-confirmed policy registry cites its exact `coordination/` Human Decision as authority provenance without making coordination state a runtime dependency.

## Non-negotiable semantic boundaries

- Acquisition Technique is not Execution Environment. Gourmet's rendered-card and first-party-network techniques can run in an approved Edge environment; Edge is not an extraction technique.
- Evidence is not Semantic Interpretation. A number or endpoint name is observed evidence until context supports a meaning.
- Observation is not Ground Truth. Public displays can be contextual, incomplete, rounded, personalized, or stale.
- Price Temporal Status is not Price Role. A current active official business webpage used to advertise product prices supports `current_advertised_price` at `observed_at` absent contrary historical evidence; known historical evidence is `historical_observed_price`; unresolved temporality is `temporal_status_unknown`. API, rendered DOM, structured response, export, snapshot, archive, cache, or other acquisition method alone never determines temporality. None of these temporal labels implies transaction price, all-branch price, or variant equivalence.
- Displayed Order is not Demand. Lazada and Shopee positions require exact surface/sort/time context and never imply national bestseller truth.
- Product Identity is not Variant Identity. Matching a product/item ID does not prove selected variant equivalence.
- Blocked Access is not Extraction Failure. Gourmet cloud blocking and Shopee traffic verification describe environment/access outcomes, not proof that a technique or source is impossible.
- Record count is not quality. Product & Price still requires attributable sellable-product identity plus price.

## Backfill scope and exclusions

The corpus includes reviewed or deterministic evidence for Lotus's, Big C, Makro, Tops, Gourmet Market, JIB, Shopee, Lazada, Q-Diving/YouTube, and the PunThai parser contract. Both positive and negative episodes are first-class.

The historical audit found additional bounded evidence in still-open Draft PRs #36–#41: TikTok, Agoda, and Traveloka access boundaries; LINE SHOPPING seller-collection observations; a NocNoc cessation observation; specialty Coffee evidence; Q-Diving content/service/equipment candidates; and an Akha Ama catalog observation. These are represented only in the Candidate Learning Evidence Registry because their source branches remain unmerged and the evidence lacks independent Reviewed Learning Corpus authority.

Candidate recovery changes “no evidence found” into “unmerged candidate evidence found” where supported, but it does not promote any of the 11 source candidates or change a coverage state. The exact PR head commit and source file are retained so a future independent review can merge, correct, or reject evidence without repeating a live request. The corpus now contains the original 16 source/contract episodes plus five explicitly human-confirmed semantic-policy episodes; those five additions are policy authority only, not source validation.

No exact observation time, request count, cost, latency, quality score, yield, or Human Review is introduced unless the referenced repository evidence already supports it.

## Coverage and future work

Coverage states are qualitative: `validated_multi_source`, `validated_single_source`, `partial`, `boundary_validated`, `contract_only`, or `gap`. Every state carries references and a residual gap. The Knowledge Gap Register recommends only a future pattern-shaped target; starting that work requires a new reviewed prompt.

The ML Knowledge Map currently marks tasks as small candidates, review-required, insufficient, or blocked by label authority. These are planning labels, never model-readiness or production claims.

Each reviewed and candidate episode separates candidate feature families from the target label/decision and explicitly lists fields that must be excluded to prevent leakage. Task specifications independently define feature families, label family, authority requirement, exclusion criteria, leakage risks, and readiness. No projection has `training_eligible=true`.

## Human-confirmed semantic policies

The packet requested explicit human decisions for five high-value semantic boundaries: unlabelled marketplace counters, price temporal status and price role, product-versus-variant identity, displayed-order-versus-demand, and environment-boundary-versus-technique-failure. `KU2D-H-000001` confirmed all five, with a revised price policy. Each packet item now points to a matching Human Confirmation record and exact final decision.

`materialize_human_confirmed_policy_bundle(...)` projects the compact registry into five Learning Records, five explicit Human Confirmation records, and five matching `human_confirmed` Ground Truth records. The projection preserves the prior system suggestion, explicit human provenance, and non-production outcome boundaries. It creates no Review Feedback record because the explicit coordination Human Decision is the authority source, and it creates no training dataset or runtime write.

## Safety and authority

Validation rejects sensitive/session material, missing provenance, invalid taxonomy IDs, contradictory active labels, fabricated Human Review authority, malformed coverage states, and automatic ML/production boundaries. Included episodes always retain:

```json
{
  "observation_is_ground_truth": false,
  "production_authorized": false,
  "production_store": false,
  "scheduler_action": null,
  "automatic_ml_export": false
}
```

Core Knowledge imports are prohibited from normal `api`, `control_plane`, `repository`, and `service` runtime modules. Updates occur only through explicit reviewed repository changes.
