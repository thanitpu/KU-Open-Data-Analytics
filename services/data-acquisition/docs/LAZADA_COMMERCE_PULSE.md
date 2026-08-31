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

## Normal-browser access diagnostic

`tools/LAZADA_BROWSER_ACCESS_DIAGNOSTIC.py` analyzes one sanitized capture from a reviewed normal, fresh, unauthenticated browser page load. It does not launch the Windows Edge Runner and never advances execution environments automatically. The capture may contain only the initial/final public URL, title, bounded visible-card fields, display order, source query, challenge/login indicators, and sanitized resource metadata. Cookies, authorization data, tokens, device identifiers, profiles, browser storage, headers, raw NetLog, and raw response bodies are excluded.

DOM evidence is usable only when a canonical Lazada item URL or explicit public item/product ID establishes identity. A contradictory URL and explicit ID is rejected; title alone is insufficient. Visible reviews remain review signals, `orders` remains an order-context display rather than sold/fulfilled units, and only explicit currency strings normalize. Unscaled structured numeric price remains raw with unknown scaling.

A public structured response becomes `validated-commerce-data` only when an official Lazada Thailand JSON response contains stable identity and at least one marketplace signal. Endpoint naming alone remains a candidate. Overall classifications are:

- `lazada-public-data-available`;
- `lazada-rendered-dom-only`;
- `lazada-login-required`;
- `lazada-traffic-verification`;
- `lazada-shell-only`;
- `lazada-technical-failure`.

Exit `0` means usable stable public evidence, `2` means the diagnostic completed but evidence was withheld or blocked, and `1` means technical/runtime/evidence-writing failure. Evidence is attempted before exit. Production approval and storage remain false and `scheduler_action` remains null for every result.

### Browser Access Experiment #1 result

The one authorized normal-browser page load for `สายชาร์จ` completed on 2026-08-31 with exit `0` and classification `lazada-rendered-dom-only`. The official catalog URL redirected to the corresponding official tag/search surface without traffic verification, CAPTCHA, access denial, or required login. An ordinary “sign in” header link is not a login-required boundary.

The rendered surface contained 40 visible product cards. The bounded evidence retained 10 samples, all with matching explicit IDs and canonical public item URLs, plus title, explicit baht price, query, observed display order, and timestamp. Every sampled price normalized from its explicit `฿` display; no structured numeric scaling was inferred.

The visible counters used bare Thai `ชิ้น` displays such as `5.5K ชิ้น`. Without a `sold` or `orders` label, their meaning and precision remain `unknown`; they are not parsed as sold, orders, or fulfilled transactions. Parenthetical counts were also visible but unlabeled in the bounded capture and therefore were not asserted as rating or review counts.

The reviewed in-app browser capture did not expose structured response bodies or trustworthy network response metadata. Zero structured endpoints were validated; endpoint discovery remains a separate question. Windows Edge was not attempted and is not required for the now-validated rendered-DOM evidence path. The outcome establishes a viable unauthenticated diagnostic technique, not production acquisition or Human Approve.

## Rendered-DOM Deep Audit

The bounded Deep Audit confirms that rendered public Lazada Thailand surfaces can support a reusable, non-production product-identity and price observation technique. It audited one keyword-search observation, one directly linked product detail, one category, and one directly linked public shop. Each surface retained no more than 10 records, used only its first visible page, and required no login, challenge handling, browser-state reuse, or Windows Edge execution.

The new keyword-search navigation did not complete in the browser-control window, so it was neither reloaded nor retried. Search/detail correlation therefore uses the previously integrated and reviewed search observation for item `5525400662`, while the detail, category, and shop observations are from the current Deep Audit. This provenance distinction is explicit in the audit result and prevents the older search observation from being presented as a same-load capture.

### Repeatability and stable identity

All 8 retained records across the four bounded surface samples exposed canonical public Lazada product URLs and stable item IDs. Every sampled identity normalized successfully. Search and detail retained the same item ID and title. The category and shop samples also retained exact source URL, timestamp, query/category/shop context, and observed display position. The generic `observation_scope` contract keeps the same item and timestamp on different source surfaces as distinct observations; only a true replay of the same scoped observation deduplicates.

This establishes an approved-candidate pattern for Product Identity & Price observation, not production approval. Layout stability over time and larger-sample yield remain unproven.

### Price semantics and product-detail correlation

Explicit baht displays normalize without hidden scaling. Each amount is now retained as a surface-scoped price observation with its raw display, explicit currency, price role, visible cue, source surface, timestamp, product identity, explicit-only variant identity, shop/seller identity, conditional state, and sanitized rendered-DOM provenance. Roles distinguish current, original, variation minimum/maximum, from-price, promotional selling price, `promotional_discount` savings amount, voucher/conditional, member/account-conditional, and unknown display prices. A promotional field name alone is not semantic evidence: selling-price cues such as `ราคาพิเศษ`, `ราคาโปรโมชั่น`, `promotional price`, or `sale price` are distinct from savings cues such as `ลด`, `ประหยัด`, `discount`, `save`, or `off`. The compatibility `current_price` scalar represents only an explicitly evidenced current or promotional selling price. From-price, variation, promotional discount/savings, voucher, member, and unlabeled display amounts remain in `price_observations` and are never silently promoted to `current_price`.

The correlated item displayed `฿25.00` on the earlier search card and `฿49.00` current plus `฿99.00` original on the current detail page. The item ID and title are consistent, but product identity does not imply purchasable variant identity. The prices are not equal and no explicit detail variation range or price-role cue explains the difference. The authoritative relation is therefore `different_unresolved`; variant equivalence is `unknown` because no explicit variant/SKU field was captured. The audit does not infer variant identity from a URL segment, assert a canonical price, treat a voucher as product price, or choose a value based on numeric magnitude. The older `price_consistent_or_within_detail_range` and `variant_equivalence_asserted` fields remain false for compatibility.

Search/detail comparisons use the explicit relations `exact_match`, `search_within_detail_variant_range`, `detail_within_search_variant_range`, `different_but_explained_by_explicit_roles`, `different_unresolved`, `not_comparable`, and `insufficient_evidence`. Even an exact amount match does not establish canonical price or variant equivalence. Category and shop prices remain observations scoped to those surfaces and do not imply demand, marketplace rank, or national popularity.

### Counter and rating/review semantics

Bare displays such as `5.5K ชิ้น`, `1.9K ชิ้น`, and `823 ชิ้น` remain `counter_type = unknown`. A safe numeric parse and its exact/rounded precision are retained, but `observed_sold_count` remains null and semantic confidence is `unlabeled-display`. These values cannot enter sales velocity. Only an explicit `sold`/`ขายแล้ว` or `orders` label may produce the corresponding typed counter, and an order display still does not become a sold count or transaction ledger.

Unlabeled parenthetical values such as `(714)` remain `unknown-not-review`. A numeric score, rating count, or review count is accepted only when it has an explicit label or a separately validated structural meaning. The live sample therefore produced no defensible rating/review count even though parenthetical numbers were visible.

### Display order and longitudinal readiness

The current search and category surfaces used default relevance, and the shop used its default order. Their DOM positions remain `observed_display_position`; none becomes a `MarketplaceRankingObservation`. A fully contextual ranking may be emitted only for an exact public surface whose selected sort explicitly means bestseller, top sales, or an equivalent validated concept. It is never a national ranking claim.

Longitudinal status is `Partial`. Stable identity, explicit price, comparable public source surfaces, timestamped provenance, and challenge-free access support repeated product/price and display-order observation. `ready_for_longitudinal_observation` is false and `sales_velocity_ready` is false because no stable, explicitly labeled sold/order counter was established.

The independent Deep Audit decisions are:

- Product Identity & Price: **Approved candidate**.
- Ranking/Display Order: **Needs review** (generic position is usable; rank semantics are not established).
- Sold/Order Counter: **Needs review**.
- Longitudinal Observation: **Partial**.

`production_approved` and production storage remain false, and `scheduler_action` remains null. Remaining uncertainties include DOM/layout drift, current-search repeatability after the incomplete navigation, larger-sample identity/price yield, explicit rating/review structure, stable shop/seller hints outside shop/detail surfaces, counter meaning, and a defensible explicit ranking surface.
