# Source adapters

Do not implement a site-specific crawler until the source has passed compliance screening.

Each adapter should export:

- `sourceMetadata()`
- `discover()`
- `fetchPage()`
- `parseReviews()`
- `toCanonicalRecord()`

Prefer an official API or export mechanism when available.
Do not collect usernames, profile URLs, photos, phone numbers, or other unnecessary personal data.

## Steam User Reviews POC

Status: approved as the first Lab POC because Steam documents the user-review list
endpoint and supports language filtering and cursor pagination.

Collected:
- review text
- positive/negative recommendation
- review timestamp
- language
- app metadata
- helpful vote count
- limited non-identifying review context

Excluded:
- author SteamID
- profile URL
- username/avatar
- author game-library metadata not needed for current text-analysis objectives
