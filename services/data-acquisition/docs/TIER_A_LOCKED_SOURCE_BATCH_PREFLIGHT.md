# Tier-A Locked-Source Batch Preflight

This is a deterministic planning report for `KU2D-TABM-000001`. It authorizes
nothing and cannot execute acquisition. A later live batch requires separate
human authorization and an executor that enforces the machine-readable
`config/tier_a_locked_source_batch_manifest.json` contract request by request.

The scope is exactly the four sources already classified Tier A by merged KU2D
readiness evidence: Lotus's (`SRC-002`), Big C (`SRC-004`), Makro (`SRC-005`),
and Tops (`SRC-001`). Gourmet Market, JIB, and every Tier-C source are excluded.
Promotion methods remain recorded as approved context but are not scheduled.

## Campaign envelope

| Control | Preflight value | Evidence status |
|---|---:|---|
| Source order | Lotus's, Big C, Makro, Tops | proposal, deterministic serial order |
| Global transport-request ceiling | 264 | proposal; sum of 80 + 80 + 24 + 80 |
| Primary page/batch units | 32 | derived; four registry caps of 8 |
| Repeat page/batch units | 20 | derived; four Deep Audit caps of 5 |
| Expected records | min 20 / target 235 / max 968 | minimum/maximum derived; target proposed, not promised yield |
| Wall-clock target / ceiling | 45 / 120 minutes | proposal, not observed duration |
| Concurrency | 1 | proposal; serial and evidence-first |

Every transport request must be followed by an atomic sanitized evidence
checkpoint before another request begins. The ledger records the response
classification, normalized records or withholding reason, source/profile
fingerprint, and running request/page/time counters. A source exit `1` or `2`
stops that source only; later sources may continue in fixed order only while
global integrity and their independent locks remain valid. A manifest change,
failed evidence write, ambiguous coordination state, global ceiling, or need for
authentication/challenge handling stops the campaign globally.

Resume is allowed only from a durable checkpoint with the same manifest,
method-lock fingerprint, environment and auth state, no in-flight request, and
persisted budget counters. A terminally failed or withheld source is never
resumed automatically. Resume cannot rediscover endpoints or switch technique,
environment, browser mode, auth state, or extraction strategy.

## Source preflight

| Source | Locked Product & Price / Discovery method | Environment and surface | Proposed workload | Request ceiling | Duration class | Status |
|---|---|---|---:|---:|---|---|
| Lotus's | `lotus_catalog_api` / `lotus_catalog_api` | cloud, public official product API v4; official sitemap SKU frontier; browser disabled | 8 primary + 5 repeat units; min 5, target 99, max 792 records | 80 | medium | `ready_for_separately_authorized_live_batch` |
| Big C | `bigc_product_catalog` / `generic_sitemap` | cloud, official robots/sitemap to canonical public product detail; browser fallback disabled | 8 primary + 5 repeat units; min 5, target/max 8 records | 80 | medium | `ready_for_separately_authorized_live_batch` |
| Makro | `makro_pro_catalog` / `makro_pro_catalog` | cloud, official Makro PRO SSR listing and bounded same-host detail enrichment; rendered fallback disabled | 8 primary + 5 repeat units at 20 items/page; min 5, target 120, max 160 records | 24 | medium | `ready_for_separately_authorized_live_batch` |
| Tops | `tops_product_catalog` / `generic_sitemap` | cloud, official sitemap shards to canonical public product detail; browser disabled | 8 primary + 5 repeat units; min 5, target/max 8 records | 80 | medium | `ready_for_separately_authorized_live_batch` |

The numeric targets, transport ceilings, time limits, concurrency, timeout and
retry settings marked `proposal_not_observed` in the manifest are conservative
planning bounds. They are not historical measurements. Registry page caps,
runtime batch/page sizes, Deep Audit minima, and derived maximums retain their
merged evidence references.

## Caveats and quality gates

- Lotus's is locked to the persisted O2O v4 API family and configured seller
  and batch semantics. Missing configuration, schema drift, or a need for
  browser rediscovery withholds the source.
- Big C is locked to the official sitemap/canonical-detail path. A challenge,
  shell, or loss of an attributable identity-price pair withholds the source;
  there is no rendered fallback.
- Makro is locked to public SSR listing evidence. Loss of SSR identity/price,
  reported-total semantic drift, or any rendered fallback requirement withholds
  the source.
- Tops is locked to official sitemap shards and canonical product detail.
  Sitemap-family, SKU/path, or price-role drift withholds the source.

All four sources require attributable sellable-product identity and price,
provenance of at least 95 percent, price and semantic quality of at least 80
percent, assigned-technique execution of at least 80 percent, and product
repeatability of at least 70 percent. Large counts do not substitute for these
gates. Current, regular, member, promotion, bulk and tier prices remain distinct
when evidenced and otherwise remain unknown.

Each source uses the same exits: `0` means technical completion with evidence
and every locked-track/Deep Audit gate passing; `2` means technical completion
with evidence but approval withheld; `1` means technical, manifest-integrity,
runtime, coordination, or evidence-writing failure. Campaign `0` requires all
four source exits to be `0`; any source `2` makes the campaign `2`; global
integrity or evidence failure makes it `1`.

## Readiness conclusion

All four Tier-A sources pass this offline preflight and are ready only for a
separately authorized live batch. None is authorized now. The manifest performs
zero requests, stores nothing in production, schedules nothing, changes no
knowledge authority, touches no parked reference, and enables no browser, Edge,
login, cookie, session, private API, proxy, CAPTCHA, or challenge behavior.
