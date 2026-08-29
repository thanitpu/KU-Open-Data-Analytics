# KU2D Data Acquisition Service

This directory is the GitHub source-of-truth target for the adaptive Data Acquisition service.

Current baseline being migrated: v0.28, Technique Engine contract 0.24.

The service lifecycle is Discover → Explore → Deep Audit → Human Approve → Scheduled Acquire → Monitor → Re-Explore on drift.

Repository rules:
- Never commit API keys, tokens, private credentials, runtime SQLite databases, or browser profiles.
- Deterministic regression tests must pass before live-source smoke tests.
- Live tests use isolated staging databases and never imply production approval.
- Production scheduling operates only on profiles that passed Deep Audit and were explicitly approved.
- Technique-profile changes invalidate prior approval until re-audited/re-approved.

See `docs/DATA_ACQUISITION_NORTH_STAR.md` for the architecture contract.
