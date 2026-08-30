# Shopee Commerce Pulse exploration

Status: non-production exploration foundation. No Shopee acquisition technique, production storage, approval, or schedule is authorized by this document.

## Domain boundary

Retail Product & Price Acquisition asks, “What is product X priced at now?” Commerce Market Observation asks, “What products appear to be selling strongly or gaining momentum on an observed marketplace surface now?” They are separate domains with separate evidence and approval contracts.

Commerce Pulse observes public marketplace displays. It does not provide a transaction ledger, seller analytics, national sales totals, or a claim about all commerce in Thailand.

```text
Marketplace Surface
  → Product Observation
  → Repeat Observation
  → Sales Delta / Velocity Estimate
  → Ranking Signal
  → Trend Candidate
  → Human Review
```

Human Review remains required. `production_approved`, production storage, and scheduling remain false/disabled.

## Public-surface findings

A bounded 2026-08-30 audit used only two official public surfaces: `https://shopee.co.th/` and `https://shopee.co.th/top.selected`. Normal local HTTP returned `200 text/html` for both, but the same application-shell-sized response exposed no usable product cards or sold displays. The shell referenced `/api/v4/pages/is_short_url/`; this is navigation support, not validated commerce data.

The official `top.selected` and collection pages are search-indexed with rendered product titles, display prices, ratings, Thai `ขายแล้ว` counters, explicit `TOP` positions, and sort labels such as `สินค้าขายดี`. This establishes that public observation surfaces exist, but it does not validate an extraction transport.

The current environment matrix is deliberately incomplete:

| Environment | Finding |
| --- | --- |
| Normal local HTTP | Reachable, but static response is an application shell with no usable product signal evidence |
| In-app browser context | Redirected to `/verify/traffic/error?type=4` with “Login Required”; no login or bypass attempted |
| Windows Edge Runner | Not required or tested; never selected automatically |
| GitHub-hosted runner | Not tested; deterministic CI makes no live Shopee request |

If a future HTTP or cloud probe receives a CAPTCHA, authentication requirement, challenge, `403`, or `429`, the result is evidence-withheld. KU2D must not solve the challenge, rotate proxies, replay private signatures, or add user cookies/session tokens. The bounded in-app browser check already reached an authentication/traffic-verification boundary and stopped. If another reviewed public browser environment later works while plain HTTP or cloud is blocked, the evidence must say so; that fact alone does not authorize Edge execution.

## Source playbook

The registry at `config/shopee_commerce_pulse_sources.json` describes six candidates:

1. Public collection/category/campaign ranking surfaces.
2. Public keyword search.
3. Bestseller/popular/top-selling sort modes where visibly available.
4. Public product detail reached from the bounded surface.
5. Public shop-local popular/bestseller surfaces.
6. Structured network responses directly observed from the public customer surface without authentication.

Structured responses are preferred only when they are genuinely public, lawful to use, bounded, and validated against the rendered display. Undocumented response shapes are unstable. Price scaling, counter meaning, pagination, ranking order, and identity must be established before an endpoint can become an acquisition technique.

## Sold-count semantics

`ขายแล้ว` is a platform-observed display, not necessarily a live transaction ledger. The parser preserves uncertainty:

| Display | Stored count | Precision |
| --- | ---: | --- |
| `123 sold` / `ขายแล้ว 123 ชิ้น` | 123 | `exact` |
| `1.2k sold` / `ขายแล้ว 1.2พัน` | 1,200 | `rounded` |
| `10k+` | 10,000 | `lower_bound` |
| `ขายแล้ว 300พัน+` | 300,000 | `lower_bound` |

Thai `พัน`, `หมื่น`, `แสน`, and `ล้าน` suffixes are supported. A rounded or lower-bound display is never converted into an exact transaction count.

## Velocity estimates

Velocity requires the same platform, the same stable platform product ID, a later timestamp, and compatible counter precision. The conservative v1 rule calculates a number only from two exact counters.

`1201 → 1325` over 12 hours yields an observed counter delta of 124 and an estimated 10.33 units/hour. The estimate retains `is_transaction_ledger: false`.

`300k+ → 300k+` produces an indeterminate estimate with no delta or units/hour. A decreasing exact counter fails closed as a possible reset, variant merge, listing change, or unreliable observation; it is not silently treated as negative sales.

## Contextual ranking

A rank is invalid without all of the following:

- source surface;
- surface type;
- category, collection, campaign, or query;
- selected sort mode;
- observed time;
- stable platform product identity;
- provenance.

Rank #1 for a keyword sorted by bestseller is different from rank #1 in a category, on a campaign collection, or inside a shop. Generic search results never justify “Thailand’s #1 best-selling product.”

One product may therefore have multiple observations at the same timestamp. Surface context is part of observation identity. Ranking scope deterministically includes source surface, surface type, category/query, and sort mode; product scope includes source surface and query; sales-counter scope includes its explicit surface and stable ranking/query context from provenance. Deduplication removes a replay of the same logical observation, not a distinct marketplace context.

Preferred labels are:

- Highest Observable Sold Count
- Fastest Rising
- Strongest Marketplace Rank
- Cross-observation Trending

## Scoring foundation

`commerce-pulse-provisional-v1` combines normalized sales velocity, rank strength, rank improvement, review growth, and repeated-surface presence. Its weights are provisional and explicitly non-authoritative. Every candidate stores the scoring version, component values, weights, raw cumulative counter, raw velocity estimate, observed time, and pending Human Review status.

Sales velocity has two deliberately separate values:

- `raw_velocity_signal` / `raw_signals.estimated_units_per_hour` is the non-negative finite units/hour estimate and may be greater than 1;
- `normalized_velocity_signal` / `component_values.normalized_sales_velocity` is the explicit `[0,1]` component used by provisional scoring.

KU2D does not yet define an authoritative normalization method. Normalization is an upstream, reviewable input; the trend builder never treats raw units/hour as already normalized and never converts a normalized component back into raw velocity.

Cumulative sold count and current velocity remain distinct signals. No cross-platform product matching is implemented.

## Longitudinal store

`CommerceObservationStore` is append-only by `record_type + platform + product_id + observed_at + observation_scope`. The normalized scope uses stable marketplace context rather than the entire volatile payload. A true replay is ignored, while simultaneous keyword-search, category-bestseller, campaign-collection, and shop-popular observations remain separate. It requires an explicit `KU2D_COMMERCE_OBSERVATION_DB` (or an explicit constructor path), rejects reuse of `KU2D_OPERATIONS_DB`, and hard-codes production approval to false. The explorer never opens this store.

## Explorer contract

`tools/SHOPEE_COMMERCE_PULSE_EXPLORE.py` supports `--url`, `--query`, `--category`, `--max-items`, `--output`, and mandatory `--no-production-store`.

It always attempts to write a diagnostic JSON result containing attempted techniques, HTTP/browser/environment outcomes, access/challenge status, discovered endpoint candidates, detected fields, normalized samples, confidence, and failure reason.

Exit classifications are:

- `0`: usable stable product identity plus marketplace-signal evidence was normalized;
- `2`: the probe completed, but access was challenged or evidence was insufficient;
- `1`: technical/runtime/evidence-writing failure.

An HTTP `200` application shell with no normalized evidence returns `2`, never a false green.

## Controlled first pilot

The registry contains broad Beauty, Mobile Accessories, Household, Fashion, Food/Snacks, and Pet Supplies seeds with Thai queries. The reviewed first pilot is one query, first page, at most 10 items:

```powershell
$env:PYTHONPATH='.'
python tools/SHOPEE_COMMERCE_PULSE_EXPLORE.py --query 'สายชาร์จ' --max-items 10 --output "$env:TEMP\ku2d-shopee-commerce-pulse.json" --no-production-store
```

Run from `services/data-acquisition`. This command performs one public, no-auth diagnostic request. It does not approve, store, schedule, authenticate, or bypass a challenge. Review its evidence before any browser/network pilot.
