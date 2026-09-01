# KU2D Adaptive Data Acquisition — North Star

The v1 source-onboarding formula is **Shared Connector Kit + Domain Capability Profile + Thin Source Adapter + Source-specific Parser + Analysis-owned Semantic Quality**. Sources progress through Technique Library reuse → Explore → Deep Audit → Minimum Trusted Connection → Integration → Closure in one Source Completion Queue. Minimum Trusted Connection promotes useful reproducible capabilities with provenance and known limitations; it does not require universal capability completeness or grant production approval.

## Mission
KU2D Data Acquisition is an adaptive, evidence-preserving acquisition platform for studying changing online domains and sources. It should discover useful sources, learn suitable public-access acquisition techniques, validate them, approve trusted profiles, acquire on schedule, detect drift, and re-enter Explore when a previously valid profile degrades.

## Canonical lifecycle

Discover → Explore → Deep Audit → Human Approve → Scheduled Acquire → Monitor → Re-Explore on drift

Approval is a governance boundary, not a daily action. Once a source is approved, the scheduler may acquire automatically while the validated technique-profile fingerprint remains current and health gates continue to pass.

## Knowledge hierarchy

1. Generic Technique Library — HTTP/HTML, structured data, sitemap, app-state, browser DOM, browser network, REST/JSON, GraphQL, official campaign surfaces, source-specific parsers.
2. Domain Playbooks — ordered strategies and quality gates for domains such as supermarket, hotel, restaurant, marketplace, property, travel, finance, etc.
3. Source Profiles — the validated technique mix and operational configuration for one source.
4. Operational History — success/yield/latency/schema/access events and profile fingerprints over time.

A new source should first try techniques learned from its domain playbook. Unresolved sources return to Explore, where new techniques may be added to the library and then generalized carefully to other sources.

## Evidence model

Data is preserved by confidence state rather than discarded simply because it was collected during Explore.

### RAW
Public response evidence and diagnostics: URL, observed_at, HTTP metadata, content hash, technique, parser version, optional bounded raw payload or rendered snapshot with retention policy.

### OBSERVED
Parsed candidate facts: ProductCandidate, PromotionCandidate, DocumentCandidate, etc., including source URL, observed_at, technique, profile fingerprint, confidence, and validation status.

### TRUSTED
Observations produced by a currently approved technique profile and accepted by acquisition quality gates.

Rejected candidates remain useful negative evidence. They should retain rejection_reason instead of being silently deleted.

## Acquisition-to-Analysis boundary

Every technically valid, authorized, policy-compliant, provenance-bearing and sanitized acquisition record is durably handed to Analysis as `accepted_for_analysis`. Acquisition does not select records by semantic relevance or analytical quality. Analysis owns relevance, quality, ranking, analytical deduplication/grouping and final inclusion, with unassessed values preserved as unknown/null rather than inferred.

The lifecycle's Human Approve stage remains a governance boundary for approved technique profiles, production write/scheduling, elevated authority, legal/policy ambiguity, restricted or personal data, material provider scope/quota expansion and new spending. It is not a per-record semantic-selection gate between Acquisition and Analysis.

## Scheduling policy

Suggested default operating model:

- Acquire: source cadence (hourly/daily/weekly as configured)
- Light health check: every acquisition run
- Light audit: weekly or domain-specific cadence
- Deep Audit: monthly, after profile changes, or on drift
- Re-Explore: automatically requested when health/deep-audit gates fail or repeated access/schema failures occur
- Human re-approval: required when the persisted technique profile changes materially

## Drift signals

Examples: materialized yield collapse, price completeness drop, semantic-quality drop, repeatability drop, provenance degradation, increased 403/429/challenge responses, schema/GraphQL-operation change, product identity loss, campaign-parser degradation, or profile fingerprint mismatch.

## Safety / access policy

Use public official-site access only. Respect configured delays/page caps and source access policies. Do not bypass authentication, access controls, CAPTCHAs, or anti-bot challenges. A blocked cloud runner is an access-state observation, not a reason to circumvent controls.

## Test architecture

Every acquisition-engine change should run deterministic regression tests first. Live smoke tests are separate because external sites and cloud IP behavior are nondeterministic. Full lifecycle acceptance uses an isolated operations/repository database so Explore → Audit → Approve → Acquire tests cannot mutate production state.

The first domain regression corpus is Supermarket: Lotus's, Big C, Makro, Tops, and Gourmet Market.
