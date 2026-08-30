# TikTok Shop Commerce Pulse Explore #1

Status: bounded, non-production exploration. No production acquisition, storage, approval, or schedule is authorized.

## Domain boundary

TikTok Shop uses the existing `CommerceProductObservation` contract. Commerce Market Observation records attributable signals on an exact public marketplace surface; it is separate from Retail Product & Price Acquisition and is not a transaction ledger or national market census.

Only official public TikTok Shop customer surfaces are eligible. Login, Seller Center, Creator/Alliance authorization, stored cookies, authenticated sessions, access tokens, seller or merchant credentials, CAPTCHA handling, traffic-verification bypass, stealth automation, proxy rotation, and wide crawling are prohibited. `production_approved` and production storage remain false and `scheduler_action` remains null.

## Official API boundary

The official TikTok Shop API is not a national public marketplace feed. TikTok's official documentation describes seller, creator, and partner authorization flows. Product and local-shop APIs require an authorized seller access token and may additionally require a `shop_cipher`; creator and affiliate data use creator or partner authorization. API requests require an app key, app secret-backed signature, scopes, and the correct access-token type.

Relevant official documentation:

- [Authorization overview](https://partner.tiktokshop.com/docv2/page/authorization-overview-202407)
- [Connecting shops](https://partner.tiktokshop.com/docv2/page/connecting-shops)
- [API entity tags and token boundaries](https://partner.tiktokshop.com/docv2/page/api-entity-tags)
- [Access scopes](https://partner.tiktokshop.com/docv2/page/access-scope)
- [Get Product](https://partner.tiktokshop.com/docv2/page/get-product)
- [Request signing](https://partner.tiktokshop.com/docv2/page/sign-your-api-request)

This explorer does not create an app, request seller or creator consent, obtain a token, sign an API call, or access an authorized shop.

## Public-surface candidates

The source registry separates four candidates:

1. Public Thailand keyword/category pages.
2. Public canonical product detail pages.
3. Public shop or creator-linked product surfaces reached from a customer page.
4. Structured state embedded in, or directly returned to, an unauthenticated public customer page.

Stable identity requires a canonical official product URL carrying a numeric product ID, or a matching explicit product ID in public structured state. Title alone is never identity. A URL/structured-ID contradiction is rejected.

Explicit `฿` or `THB` values may normalize as baht while retaining raw provenance. Bare numeric structured values do not receive inferred scaling. Public `sold`/`ขายแล้ว`/`จำหน่ายไป` and `orders` displays remain distinct non-ledger observations. Unlabeled numbers remain unknown. Generic DOM order is contextual display position, not a marketplace or national rank.

## Bounded explorer

`tools/TIKTOK_SHOP_COMMERCE_PULSE_EXPLORE.py` performs one public HTTP request to an exact official customer URL or one Thailand keyword surface. It retains at most 10 records, never paginates, requires `--no-production-store`, and writes evidence before returning:

- `0`: stable public product evidence was obtained;
- `2`: the request completed but evidence was insufficient or an access boundary was reached;
- `1`: technical, validation, or evidence-writing failure.

A challenge or required-login result is final for that surface and must not trigger retries or circumvention. A browser experiment is eligible only when plain HTTP reaches an unchallenged shell without product evidence. Windows Edge is a separate reviewed execution-environment decision and is not automatically selected.

## Explore #1 live result

The single bounded request ran on 2026-08-31 against one official public Thailand product-detail URL discovered through public indexing. The response was HTTP `200 text/html`, 5,506 bytes, but it contained a challenge or required-login marker. No stable product record was normalized. Technical completion was true, evidence was written, and the explorer returned exit `2`.

This is an access-boundary result, not a technical failure and not evidence that TikTok Shop has no public product data. No retry, alternate product, search page, shop page, normal-browser experiment, Edge execution, login, seller/creator authorization, cookie/session reuse, or access-control circumvention followed. The public unauthenticated acquisition path is therefore **paused after one request** pending review of a distinct compliant technique.

The deterministic fixtures demonstrate how canonical identity, explicit baht price, shop hints, ratings/reviews, and explicitly labeled sold/order displays would normalize if a public customer response exposed them. Fixture success is not live-source validation. Production approval and storage remain false and `scheduler_action` remains null.
