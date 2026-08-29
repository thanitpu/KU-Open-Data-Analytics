# Source Approval Lifecycle — v2.51

Repository-store approval is persistent per source URL.

Normal rule:
- Once a source URL has passed Deep Audit and is approved, routine Deep Acquire does not require a new Audit or re-approval.
- Approval remains valid across browser refreshes and application versions because it is stored in Acquisition Operations DB.

Re-audit should be triggered when material conditions change, for example:
- repeated access/block/rate-limit behavior changes,
- extraction schema/adapter materially changes,
- pagination/site structure changes enough to reduce coverage,
- data-quality/readiness falls below policy thresholds,
- source URL/domain/policy/authentication conditions change.

A re-audit does not need to erase the historical approval silently. Future policy can mark approval as stale/review-required with a reason.

Monitoring Queue visually highlights currently approved source URLs with a light-green background.
