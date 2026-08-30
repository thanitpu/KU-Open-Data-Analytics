# Lazada Commerce Pulse Explore #1

Status: bounded, non-production exploration. No Lazada acquisition technique, production storage, approval, or schedule is authorized.

## Domain and safety boundary

Lazada Commerce Pulse reuses the generic `CommerceProductObservation`, `SalesCounterObservation`, `MarketplaceRankingObservation`, velocity, provisional trend-scoring, observation-scope, and append-only store contracts. It does not create a second generic marketplace model. Platform-specific code is limited to Lazada public URL identity, public field interpretation, price/counter semantics, and access diagnostics.

Commerce Market Observation remains separate from Retail Product & Price Acquisition. It observes attributable marketplace signals on an exact public surface; it is not a seller ledger, order ledger, national sales census, or production approval.

```text
Official public Lazada Thailand surface
  → Stable Lazada product identity
  → Typed public counter / price / rating / contextual position
  → Append-only observation scope
  → Provisional signal
  → Human Review
```

Only official public customer surfaces are in scope. Login, seller authorization, OAuth, app secrets, access tokens, cookies, session reuse, CAPTCHA handling, proxy rotation, challenge solving, or access-control bypass are prohibited. `production_approved` and production storage remain false, and `scheduler_action` remains null.

## Lazada Open Platform is not a public marketplace feed

The official Lazada Open Platform documentation distinguishes seller-authorized APIs from public customer surfaces. Seller business-data access requires seller authorization, and platform calls use application credentials, permissions, signing, and—where required—seller access tokens. Product APIs are framed as seller/product-management APIs. See the official [seller authorization introduction](https://open.lazada.com/apps/doc/doc?docId=108260&nodeId=10777), [getting started guide](https://open.lazada.com/apps/doc/doc?docId=108056&nodeId=10434), [calling parameters](https://open.lazada.com/apps/doc/doc?docId=108067&nodeId=10400), and [product API list](https://open.lazada.com/apps/doc/doc?docId=108146&nodeId=10557).

Explore #1 therefore does not treat Lazada Open Platform as a public marketplace-wide feed and does not request or store any Open Platform credential.

## Source playbook

The durable registry at `config/lazada_commerce_pulse_sources.json` records six candidates:

1. Official homepage and category/collection surfaces.
2. Public keyword search.
3. A visibly selected popular/bestseller/top-selling sort.
4. Public canonical product detail.
5. Public shop listing and shop-local sort.
6. Structured data directly used by an observed public customer surface without authentication.

Each entry records access class, expected fields, stable identity, counter, ranking, pagination, price, browser/Edge need, anti-bot behavior, stability, reuse, assumptions, and validation state. Endpoint names alone never validate commerce evidence.

## Identity and observation scope

A record requires an explicit public item/product ID or a canonical Lazada Thailand product URL carrying a stable item ID such as `-i100001-s200001.html`. Titles never form identity and two IDs with identical titles remain separate. Platform is always `lazada-thailand`.

The generic observation scope preserves the exact source URL/query. The same product observed at the same time on keyword search, category, campaign, or shop surfaces remains multiple observations. Only a true replay of the same logical scoped observation deduplicates. Cross-platform matching is not implemented.

## Counter semantics

Counter labels remain distinct:

- a clearly labeled `sold`/`ขายแล้ว` display may populate the sold observation while retaining exact, rounded, lower-bound, or unknown precision;
- an `orders` display remains a typed order-context counter in provenance and is not converted to sold or fulfilled units;
- review/rating counts never become sold counts;
- an unclear label remains `unknown`.

All are public marketplace displays, not transaction ledgers. Velocity is available only through the frozen generic rule for compatible repeated exact sold counters.

## Price semantics

An explicit public currency display such as `฿159.00` may normalize to `159.0` while preserving the raw display and provenance. A numeric structured field such as `15900` is retained only as raw evidence with scaling unknown; the explorer does not guess minor units, multipliers, or currency scaling. Original price and discount retain the same provenance boundary.

## Ranking semantics

Rank requires stable identity plus exact source surface, surface type, category/query, selected sort, timestamp, and provenance. Array order alone is not rank. “Rank 1” can only describe that exact observed context and must never become a national “Thailand #1” claim.

## Access ladder and explorer

The reviewed ladder is:

1. one bounded plain-public-HTTP request;
2. a separately reviewed browser observation only if plain HTTP evidence shows it is needed;
3. Windows Edge only after a distinct execution-environment review establishes it is required.

The explorer does not automatically advance this ladder. `tools/LAZADA_COMMERCE_PULSE_EXPLORE.py` supports `--url`, `--query`, `--category`, `--max-items`, `--output`, and mandatory `--no-production-store`. Maximum items is 20 and Explore #1 is capped at 10.

It attempts to write evidence before returning:

- `0`: stable identity plus a public marketplace signal was normalized;
- `2`: the request completed but access was challenged or evidence was insufficient;
- `1`: technical/runtime/evidence-writing failure.

A reachable application shell with no usable stable-identity record returns 2, never a false green.

## Cross-platform transfer boundary

Cleanly reusable from Shopee:

- generic observation, ranking, counter, velocity, trend, and store models;
- `observation_scope` and true-replay deduplication;
- explicit precision and non-ledger semantics;
- contextual ranking and prohibition on national claims;
- evidence-before-exit and production-disabled controls.

Lazada-specific extensions:

- canonical URL/item-ID grammar;
- separation of Lazada sold, orders, and reviews labels;
- explicit-currency versus unknown structured-price scaling;
- Lazada public surface routes and challenge markers;
- the official Open Platform seller-authorization boundary.

## Controlled pilot

After all deterministic tests pass, Explore #1 permits at most one live plain-HTTP request for `สายชาร์จ`, first response only, maximum 10 records:

```powershell
$env:PYTHONPATH='.'
python tools/LAZADA_COMMERCE_PULSE_EXPLORE.py --query 'สายชาร์จ' --max-items 10 --output 'C:\KU2D-Runtime\commerce\lazada-explore-cable.json' --no-production-store
```

Only a technical invocation error may be corrected once. Evidence-withheld is a valid diagnostic result and must not trigger query switching, browser escalation, Edge execution, or a wider crawl.

### Explore #1 live result

The single authorized request completed on 2026-08-31 with diagnostic exit `2`. The official catalog URL redirected to an official Lazada tag/search URL and returned HTTP `200` HTML without a challenge. The 60,501-byte response exposed an application shell and route references, but no stable product-signal records and no validated public structured commerce endpoint. Account/login, checkout, app-navigation, service-worker, and help-center routes are explicitly non-commerce; other route names remain unvalidated and are not trusted by name.

Normalized record count was zero. Technical completion was true, while `production_approved` and production storage remained false and `scheduler_action` remained null. Browser and Windows Edge were not attempted. Plain HTTP alone therefore did not establish a viable unauthenticated acquisition path; whether a normal public browser surface could do so remains a separate reviewed experiment, not an automatic escalation.
