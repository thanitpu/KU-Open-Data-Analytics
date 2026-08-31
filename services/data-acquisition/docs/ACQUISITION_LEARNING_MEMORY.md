# KU2D Acquisition Learning Memory

## V1 purpose and boundary

Learning Memory preserves reviewed acquisition experience as safe, traceable JSON records. It is not ML. V1 adds no model, training, inference, embeddings, vector database, feature store, fine-tuning, automatic labeling, autonomous approval, production scheduling, or runtime dataset integration.

Normal acquisition does not emit Learning Memory. Record creation and historical replay are explicit, opt-in operations. A Learning Memory decision cannot authorize a source, mutate production approval, enable storage, or schedule acquisition.

The lifecycle remains:

```text
Codex / System Explore
  -> Observed Evidence
  -> System Proposal / Interpretation
  -> Assistant Review
  -> Human Confirmation
  -> Final Decision / Ground Truth Candidate
  -> Future ML Dataset Eligibility
```

Not every example needs every stage. The actor, authority, and evidence supporting each stage must remain explicit.

## Why preserve acquisition experience

High-value acquisition knowledge includes failures and uncertainty, not only large successful outputs. Learning Memory retains semantic corrections, technique outcomes, access boundaries, and negative evidence so future work can distinguish a verified rule from a suggestion and a challenge page from usable product evidence.

Evidence is never overwritten by a later interpretation. Corrections create new review or Ground Truth records. This makes the original suggestion, the correction reason, the reviewer class, and any genuine Human Confirmation independently auditable.

## V1 record contracts

All records are JSON-object and JSONL compatible, storage-neutral, canonically serializable, and validated without a production database.

### Acquisition Learning Record

Schema: `ku2d.acquisition-learning-record.v1`

Preserves the observation identity/context, technique, sanitized observed evidence, semantic labels, acquisition outcome, decision, and provenance. Existing v1 records remain backward compatible.

### Review Feedback Record

Schema: `ku2d.review-feedback-record.v1`

Reviews one Acquisition Learning Record. It retains the original system suggestion separately from the reviewed suggestion, review result, proposed final decision, reason, explanation, evidence references, actor type, and source/commit reference when available.

Allowed actor types are `assistant_review`, `human_review`, `deterministic_validation`, and `policy_review`. Actor type determines authority; a caller cannot relabel an assistant as a human reviewer.

### Human Confirmation Record

Schema: `ku2d.human-confirmation-record.v1`

Records an explicit human `confirmed`, `rejected`, or `deferred` decision. It requires a genuine reviewer label, timestamp, explicit-human-input provenance, and a consistent Learning Record/Review reference. It is never generated from an assistant response or deterministic rule.

### Ground Truth Decision Record

Schema: `ku2d.ground-truth-decision-record.v1`

Represents the current decision derived from preserved evidence and review history, not immutable truth forever. Status may be `candidate`, `human_confirmed`, `policy_confirmed`, `deterministic_confirmed`, `superseded`, or `withdrawn`.

A `human_confirmed` record must cite a matching genuine Human Confirmation. A revision creates a new record with `supersedes_ground_truth_record_id`; the prior record remains intact. Unknown and unresolved labels are valid. Contradictory active labels, orphan references, cross-target references, self-supersession, and supersession cycles fail closed.

### Decision Trace

Schema: `ku2d.decision-trace.v1`

A Decision Trace is a derived view, not a mutable replacement for its source records. It answers:

- what the system originally suggested;
- who reviewed it and whether it was accepted, corrected, rejected, deferred, or considered insufficient;
- why the review changed or retained the suggestion;
- whether explicit Human Confirmation exists;
- the current active label and authority;
- whether an earlier Ground Truth record was superseded.

## Evidence, suggestion, review, confirmation, and Ground Truth

These layers are deliberately separate:

- **Observed evidence** is the sanitized public fact or acquisition outcome.
- **System suggestion** is an interpretation and may be wrong.
- **Assistant review** may accept or propose a correction but is not Human Confirmation.
- **Deterministic validation** can establish a tested invariant but cannot claim human authority.
- **Human Confirmation** records an explicit human action.
- **Ground Truth** identifies the current candidate or confirmed decision while preserving its authority basis and history.

An example such as `5.5K ชิ้น` may preserve `sold` as the system suggestion, `unknown` as the assistant correction, `missing_explicit_sold_label` as the reason, and a later explicit human `unknown` confirmation without rewriting any earlier artifact.

## Authority discipline

The conceptual hierarchy is:

```text
observed
  < system_suggested
  < assistant_reviewed
  < deterministic_verified
  < human_confirmed
  < approved_ground_truth
```

This hierarchy communicates provenance and confidence; it does not force a linear workflow. Policy confirmation is separately identified and must cite its policy basis. `approved_ground_truth` is conceptual authority only in V1 and does not mean production Human Approve or source authorization.

## Bundle integrity and append-only meaning

`validate_learning_memory_bundle(...)` validates Acquisition Learning, Review Feedback, Human Confirmation, and Ground Truth records together. It checks global identifier uniqueness and all cross-record references without requiring live storage.

History is append-only in meaning:

- evidence and prior proposals are retained;
- corrections add Review Feedback;
- human decisions add Human Confirmation;
- revised labels add a superseding Ground Truth record;
- superseded or withdrawn records do not silently remain active.

The V1 serializers return deterministic JSON. No helper writes during normal acquisition, and the historical backfill builder returns an in-memory bundle only.

## Negative evidence and unresolved labels

Unknown, unresolved, rejected, failed, and access-blocked outcomes are first-class examples. Examples include application shells, challenge/login boundaries, HTTP failures, ceased sources, unvalidated endpoints, Edge requirements, zero usable records, unknown counters, and unresolved price differences.

Record count is not evidence quality. A negative example must still preserve exact sanitized evidence, technique context, decision reason, and provenance. Learning Memory does not weaken safety boundaries or encourage challenge circumvention.

## Future ML dataset eligibility

Eligibility assessment is classification for possible future export, not a training dataset and not model execution:

- `excluded`: sensitive or prohibited material;
- `ineligible`: absent evidence, broken structure, or contradictory active decisions;
- `review_required`: assistant review exists without the authority required for confirmation;
- `candidate`: safe deterministic or policy-supported evidence;
- `human_confirmed`: active label has matching explicit Human Confirmation.

No V1 process trains, exports, auto-labels, or automatically promotes an example.

## Reviewed Learning Corpus and Core Knowledge

Learning Memory is the broad evidence layer; it is not itself a training set. The narrower Reviewed Learning Corpus is a deterministic, sanitized projection whose episodes have verified repository provenance, explicit authority, contradiction checks, and non-production boundaries. See `docs/CORE_KNOWLEDGE_BACKFILL.md`.

The flow is therefore **Learning Memory → Reviewed Learning Corpus → future task-specific ML Training Dataset**. The last stage does not exist in v1. Corpus inclusion does not grant training eligibility, production approval, storage permission, scheduling authority, or Human Confirmation, and no automatic export is permitted.

## Safety and authorization

Validation rejects credentials, cookies, authorization headers, tokens, sessions, browser profiles, storage state, device identifiers, raw NetLogs, private personal data, non-JSON-safe values, malformed identity/provenance, and fabricated Human Review provenance.

A record never authorizes production acquisition/storage, monitoring, scheduling, authentication or access-control bypass, deployment, source approval, KU2A runtime use, or production Human Approve. Backfilled records keep `production_approved=false`, `production_store=false`, and `scheduler_action=null`.

## Codex Explore -> Chat Review -> Human Confirmation

GitHub remains the current shared source of truth. A review exchange in chat is useful input but is not itself a repository record.

Codex should hand off a structured review packet:

```text
Learning Record ID:
Evidence summary:
System suggestion:
Decision requested:
Uncertainty:
Reason/evidence:
Relevant source/commit:
Human confirmation required: yes|no
```

An Assistant Review should return:

```text
Learning Record ID:
Review result: accepted|corrected|rejected|insufficient_evidence|deferred
Reviewed suggestion:
Proposed final decision:
Reason code:
Explanation:
Human confirmation required: yes|no
```

Codex or another controlled repository change then validates and serializes that result as a Review Feedback Record. If human authority is required, an actual human must explicitly confirm, reject, or defer it before a Human Confirmation Record can be created. Repository review protects the evidence link and prevents chat text from silently becoming Ground Truth.

## Version roadmap

- **V1 (current):** structured Learning Memory contracts, authority validation, deterministic serialization, opt-in historical replay, and future-dataset eligibility.
- **V2 (FUTURE):** separately reviewed opt-in emission from Explore and Deep Audit.
- **V3 (FUTURE):** review UI / KU2D review workspace.
- **V4 (FUTURE):** reviewed dataset export for ML experimentation.
- **V5 (FUTURE):** ML-assisted classification and recommendations.
- **V6 (FUTURE):** agentic acquisition with explicit Human Review gates.

V2–V6 require separate architecture, privacy, security, quality, and Human Review checkpoints.
