# KU2A Text Analytics migration register

This register was prepared before porting the P68 migration bundle. It records how each capability fits the current KU Open Data Analytics (KU2A) architecture.

## Keep

| Capability | Authoritative owner | Decision |
| --- | --- | --- |
| CSV/XLSX, paste, and demo loading | `src/app.js` | Keep unchanged as the ordinary local-data path. |
| Six-step journey and navigation gates | `src/journey.js` and `src/state.js` | Keep as the only workflow controller. Navigation must not reset analysis state. |
| Dataset profiling and field metadata | `src/data-profile.js` and Profile Manifest modules | Keep; text profiling is an additional view, not a replacement. |
| Question-first validated analytics | `src/ai-analytics.js`, workflow modules, and backend | Keep; text enrichment does not manufacture a validated model result. |
| Browser feature review/execution contracts | `src/fe-review.js` and `src/fe-executor.js` | Keep; text-derived features are attached only after an explicit user action. |

## Adapt

| Source capability | KU2A destination | Adaptation |
| --- | --- | --- |
| P68 core text algorithms (except its CSV parser) | `src/text-analytics/` | Port as independent deterministic modules and bind them to `KUAppState`. |
| P68 contracts and KU Open DA adapter | `src/text-analytics/contracts/` and `src/text-analytics/adapters/` | Retain versioned contracts; identify KU2A rather than the former lab as generator. |
| Semantic engine | `backend/text_analytics/semantic_engine.py` | Keep separately versioned. Always disclose `lsa-fallback`; never label it as a transformer. |
| P68 fixtures/tests | `tests/fixtures/text-analytics/` and repository tests | Port deterministic coverage and run it with existing regressions. |
| Data from KU2D | `contracts/trusted-data-asset-v1.schema.json`, `src/ku2d-data-asset.js`, and Start UI | Add a separate JSON intake path. Preserve asset and row lineage, provenance, approval, `acquired_at`, and `effective_at`. |

## Replace

| Source behavior | Replacement |
| --- | --- |
| Standalone mixed-demo presentation/state | Existing KU2A six-step shell and `KUAppState`; only reusable algorithms and contracts move. |
| P68 standalone CSV parser | Existing KU2A CSV/XLSX/paste loader and its integrity regressions; do not introduce a second parsing source of truth. |
| Implicit dataset ownership in the former lab | Explicit local-file or KU2D asset context stored in KU2A state. |
| Any ambiguous semantic label | Versioned engine metadata that states either the transformer model or `lsa-fallback`. |

## Defer

| Capability | Reason |
| --- | --- |
| `domain-examples/diving_text_analytics.py` | Review-only until hard-coded rules are a configurable domain profile/plugin. |
| Legacy mixed demo HTML | Reference-only and incompatible with the authoritative KU2A state architecture. |
| Serper, discovery, crawling, monitoring, Audit/Approve/Acquire, repository administration | KU2D responsibilities; excluded from KU2A. |
| Credentials, local database paths, production scheduling | Operational concerns outside this migration. |
| KU2B operational inference or model deployment | Future contract work; no authority in this branch. |

## Boundary decisions

- KU2D assets with `approval_status: "draft"` are inspectable and analyzable, but never presented as production-approved.
- Multi-snapshot imports require compatible schemas. An identity must be unique inside a snapshot; the same entity may recur in a different snapshot because its lineage key also includes `data_asset_id`.
- Text analysis never silently imputes, removes, or mutates source rows. Derived features remain separate until the user explicitly exports or attaches them.
- `acquired_at` and `effective_at` remain separate fields in dataset metadata and row lineage.
