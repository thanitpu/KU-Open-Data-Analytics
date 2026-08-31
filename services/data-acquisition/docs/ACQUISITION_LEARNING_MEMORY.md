# Acquisition Learning Memory foundation

## Purpose and current boundary

Preserve structured acquisition experience now so it can support future ML-assisted KU2D.

This foundation is **not currently ML**. It has no model, training, embeddings, feature store, vector database, inference service, automatic labeling, or autonomous learning. It defines a storage-neutral `ku2d.acquisition-learning-record.v1` JSON contract, validation, canonical serialization, and opt-in exporters for sanitized deterministic evidence. Normal acquisition does not generate or store these records automatically.

Learning records follow separable layers:

Observed Evidence → Context → Semantic / Human Decision → Acquisition Outcome → Provenance

`observed_evidence` contains possible future input features such as public raw text, surface, field/DOM context, identity, and sanitized metadata. `semantic_labels` and `decision` contain the derived or reviewed target separately. A future training export must not place a final label such as `price_role = from_price` back into its model-input features; this separation prevents label leakage without rewriting historical records.

## Knowledge contract

Each record is one JSON object and can later become one JSONL line. It preserves:

- identity: record ID, schema, domain, source/platform, source and surface type;
- observation context: sanitized source surface, query/category, time, execution and public/auth context when known;
- technique: technique ID, acquisition mode, and version when known;
- observed evidence: sanitized public values and provenance references only;
- semantic labels: including explicit `unknown` and unresolved values;
- acquisition outcome: technical completion, evidence usability, challenge/auth boundaries, identity availability, and unchanged production/scheduler state;
- decision: optional system suggestion, final decision, reason, explanation, evidence references, and genuine decision source;
- provenance: source/extractor schema, origin, reviewed status, and genuine reviewer provenance only.

Unknown and unresolved labels are valuable evidence. They must not be forced into positive classes. Negative outcomes—application shells, challenges, login boundaries, HTTP failures, ceased sources, unvalidated endpoints, Edge requirements, and zero usable records—are also first-class learning examples. The current PR includes only one sanitized synthetic negative contract test; it does not fabricate operational history.

Human Review remains authoritative wherever the lifecycle requires it. A record may preserve both `system_suggestion` and `final_decision`, but it must not claim Human Review without genuine reviewer provenance. Current Lazada examples come from deterministic reviewed rules, so their system suggestions and reviewer provenance remain null.

## Safety and authorization

Learning records exclude cookies, authorization headers, tokens, sessions, browser profiles, storage state, device IDs, raw NetLogs, private user information, and credential-bearing URLs. Validation fails closed on malformed identity/provenance, sensitive material, non-JSON-safe values, contradictory canonical-price state, and fabricated Human Review provenance.

A Learning Record does not authorize:

- production acquisition or storage;
- monitoring or scheduling;
- authentication/access-control bypass;
- model training;
- automated deployment;
- production or Human Approve decisions.

## FUTURE possibilities

Subject to separate architecture, privacy, quality, and Human Review checkpoints, these records may later support technique recommendation, source classification, field-semantic classification, extraction suggestions, anomaly detection, and review prioritization. None of those capabilities exists today.
