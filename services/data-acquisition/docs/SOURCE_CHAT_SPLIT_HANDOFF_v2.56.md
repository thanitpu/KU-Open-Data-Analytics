# KU2D v2.56 Chat Split Handoff

## Development split from this checkpoint

### Data Acquisition chat
Continue development of:
- `acquisition/`
- acquisition-facing repository/operations services
- `demo/acquisition-operations.html`
- `demo/acquisition-progress.html`
- `demo/view-acquired-data.html`
- source registry, adapters, access policy, Deep Audit, Deep Acquire, monitoring, pagination/coverage/change detection
- acquisition operations DB and repository-ingestion contracts

The Data Acquisition chat should avoid changing Text Analytics algorithms/UI except when an integration contract requires it.

### Text Analytics chat
Continue development of:
- `core/`
- `contracts/` where text-analysis contracts live
- `demo/text-analytics-demo.html`
- semantic/text-analysis functions not required specifically for acquisition operations
- text profiling, language, tokenization, keywords, phrases, sentiment, topics, derived text features

The Text Analytics chat should treat acquisition output as upstream input and avoid modifying acquisition crawling/monitoring behavior unless an interface contract requires it.

## Shared integration boundary
Keep these stable and coordinate changes:
- repository schemas and repository profiles
- acquisition-to-repository record contract
- evidence/provenance fields
- semantic API endpoints consumed by both sides
- configuration files shared by both workflows

## Launchers
The distributable ZIP has one main launcher at ZIP root:
`RUN_KU_TEXT_ANALYTICS_v2.56.bat`

A self-contained copy is also stored inside:
`KU_Text_Analytics_Lab_v2.56/launchers/RUN_KU_TEXT_ANALYTICS_v2.56.bat`

The internal copy is intentionally path-adjusted so it works from inside the Lab folder.

## Current acquisition checkpoint
v2.56 includes:
- persistent Monitoring Queue stages
- business-grouped source URLs
- Batch Deep Audit
- per-URL approval
- Batch Deep Acquire of approved URLs
- live Batch Audit/Acquire progress
- Monitoring Queue selection persistence
- Audit → Approve → Deep Acquire Approved from This Audit
- audit-failed URLs retained but excluded from repository storage
- pagination/coverage/change monitoring foundation
