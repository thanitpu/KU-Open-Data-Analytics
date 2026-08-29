# KU2D Data Acquisition Service v0.21

## Best Acquisition Technique as source of truth

The source-level acquisition contract is now:

`Explore / Find Best Tech -> persisted Best Technique Profile -> Deep Audit -> store approval -> Deep Acquire -> Repository`

Deep Audit and Deep Acquire no longer independently choose the legacy generic crawler when a Best-Technique profile exists. Deep Audit evaluates the assigned profile itself. A successful audit stores a fingerprint of the ordered technique profile. Deep Acquire requires the current profile fingerprint to match the audited fingerprint.

If Find Best Tech or Explore updates the ordered technique assignment, prior audit/store approval is invalidated and Deep Audit must be repeated. This prevents an approval obtained with one extraction method from silently authorizing another method.

## Cancellation

Long-running jobs use cooperative cancellation. Cancel requests are persisted/held as job state and are checked between sources and at safe phase boundaries. The application does not forcibly terminate Python or interrupt a repository transaction in the middle of a write.

Supported cancellation targets in v0.21:

- Find Best Data Acquisition Techniques
- Run All Enabled / monitoring acquisition campaigns
- Batch Deep Audit
- Batch Deep Acquire
- Single-source Deep Audit and Deep Acquire API jobs


## Lotus Catalog API operational contract

For Lotus's, the Product & Price data track uses a source-specific operational contract:

`Explore browser network -> verified public product API pattern -> persist operational config ->
Deep Audit same config -> approval fingerprint -> Deep Acquire same config -> repository`

The API technique and the Discovery/Sitemap technique have different roles. Sitemap enumerates product
identity/coverage; the Catalog API materializes product and price facts. Promotions remain a separate track.


## Big C / Makro multi-track commerce contract (v0.21)

Big C:
`bigc.co.th category listings -> Product & Price`
`bigc.co.th campaign pages -> Promotions`
`Big C sitemap -> Coverage / Discovery`

Makro:
`makro.pro product search/listing -> Product & Price + product-universe coverage`
`makro.co.th catalogue -> Promotions`
`Makro PRO browser network -> optional discovery/API evidence`

The monitoring source identity remains Big C/Makro, while the persisted technique evidence records the operational commerce surface. Changes to operational configuration are part of the technique-profile fingerprint and invalidate stale audit/store approval.

Deep Audit requires a Product & Price track and product yield for Lotus's, Big C and Makro. Deep Acquire executes the same audited track profile.


## Big C operational Product & Price contract
`official sitemap -> canonical /product/ identities -> bounded product-detail materialization -> semantic product gate -> audit -> acquire`

## Makro operational Product & Price contract
`makro.pro search SSR -> embedded state -> rendered DOM fallback -> product-detail SKU enrichment -> semantic product gate -> audit -> acquire`

## Monitoring Queue → Explore handoff
The Monitoring Queue Explore button carries `source_id`, URL, source name, domain, purpose and adapter into the Explore workspace. Approval/update resolves the explicit source ID first and URL second, preventing accidental duplicate monitoring sources.
