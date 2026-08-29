# KU2D Supermarket Acquisition Pattern Library v1

## Purpose

This library captures reusable acquisition patterns validated across five Thai supermarket sources: Lotus's, Big C, Makro, Tops, and Gourmet Market. It is intended to guide KU2D Discover → Explore → Deep Audit → Approve behavior for new retail/supermarket websites without hard-coding one crawler per site.

The corresponding machine-readable registry is `config/supermarket_acquisition_patterns.json`.

## Core conclusion

There is no single universal "best scraper" for supermarket websites. The strongest design is **split-track acquisition**:

- **Product & Price** chooses the technique with the best canonical product identity, price completeness, semantic quality, repeatability, provenance, and catalog coverage.
- **Discovery** chooses the technique that best reveals the catalog frontier and measurable coverage.
- **Promotion** uses an official campaign/catalogue surface when one is available and credible. Promotion is optional for source approval, but if a promotion technique is assigned it must produce real promotion evidence.
- **Execution Environment** is selected separately. Cloud CI remains the default for deterministic testing; an approved Edge Runner is used only when the same public official site is unavailable from datacenter runners but available from a normal operating network.

## Five-source technique comparison

| Source | Product & Price | Discovery | Promotion | Key lesson |
|---|---|---|---|---|
| Lotus's | Official O2O product API / structured catalog | Structured category/API pagination | My Lotus's official promotion surface | Prefer explicit structured commerce data when SKU, stock, regular/final/member price and pagination are available. |
| Big C | Sitemap → canonical product detail | Robots / Sitemap | Official campaign surface | Sitemap can be both a high-scale frontier and a route to strong canonical detail evidence. |
| Makro | Makro PRO catalog / SSR-visible product representation | Reported-total catalog coverage | Official promotions catalogue | Reported total + stable catalog cards provides measurable completeness even when DOM hierarchy varies. |
| Tops | Sitemap → canonical product detail | Robots / Sitemap | Official campaign surface | Same broad pattern as Big C confirms sitemap/detail is reusable across independent retailers. |
| Gourmet Market | Rendered product cards | First-party GraphQL/network catalog discovery | No promotion technique currently required/assigned | Modern SPA sites may need discovery and extraction to use different techniques; execution environment can be part of the profile. |

## Validated reusable patterns

### SM-P01 — Official Structured Product API

Use when an official public API or embedded structured catalog exposes stable product identity and price fields.

Best for: Product & Price.

Validated by Lotus's. The observed O2O representation contains SKU, stock status, regular price, final price, member price, thumbnail and canonical product URL mapping.

Why it ranks first: structured data minimizes parsing ambiguity and supports efficient pagination and repeatability checks.

### SM-P02 — Sitemap to Canonical Product Detail

Use when robots/sitemap exposes large numbers of canonical product URLs and detail pages contain focal SKU/product identity and current/regular price.

Best for: Product & Price, with sitemap also useful for Discovery.

Validated by Big C and Tops.

Why it generalizes: canonical product detail pages typically provide stronger provenance and less cross-product price contamination than generic category text extraction.

### SM-P03 — Rendered or SSR Product Cards

Use when a catalog/search surface exposes reliable product cards or accessible SSR/streamed text containing product identity and price.

Best for: Product & Price.

Validated by Makro and Gourmet Market.

Important: the card technique still needs semantic gates to reject navigation, coupon, marketing, and unrelated text.

### SM-P04 — Robots / Sitemap Discovery

Use as a low-cost frontier seed when official sitemap coverage is available.

Best for: Discovery.

Validated by Big C and Tops.

This should normally be explored early because it is deterministic, inexpensive, and often exposes canonical URLs without browser rendering.

### SM-P05 — Reported-Total Catalog Discovery

Use when an official catalog/API reports total products/pages and pagination can be mapped.

Best for: Discovery and completeness audit.

Validated by Makro and Lotus's.

This is especially valuable because coverage can be expressed quantitatively rather than inferred from a small sample.

### SM-P06 — Network / GraphQL Catalog Discovery

Use when a modern public commerce frontend reveals a first-party network or GraphQL catalog surface during ordinary public access.

Best for: Discovery.

Validated by Gourmet Market.

Important distinction: discovering a first-party endpoint does not automatically make it the best Product & Price extractor. Gourmet Market validated a split profile: network/GraphQL for Discovery and rendered cards for Product & Price.

### SM-P07 — Official Campaign / Promotion Surface

Use official promotion/campaign/catalogue pages rather than inferring promotions from generic marketing text.

Best for: Promotion.

Validated by Lotus's, Big C, Makro, and Tops.

Promotion evidence should preserve title/mechanic, validity when available, source URL, and official-site provenance.

### SM-P08 — Split-Track Acquisition

Use whenever different techniques win different tasks.

This is now the default architectural pattern for supermarket acquisition, not an exception.

Examples:

- Big C: product detail catalog + sitemap discovery + official campaign surface.
- Makro: PRO product catalog + reported-total discovery + promotions catalogue.
- Gourmet Market: rendered product cards + network/GraphQL discovery.

### SM-P09 — Approved Edge Execution

Use only when evidence shows that a public official site is inaccessible from cloud/datacenter runners but accessible from a normal operating network without authentication/challenge bypass.

Validated by Gourmet Market.

Edge is an execution-environment pattern, not an extraction technique. Deterministic tests remain in cloud CI; only live acquisition requiring normal-network access moves to the Edge Runner.

## Recommended selection waterfall for a new supermarket

1. Run low-cost discovery first: robots, sitemap, structured metadata, app/SSR payloads, official public APIs, visible catalog surfaces, and ordinary network observations.
2. Build candidate techniques by track rather than looking for one overall winner.
3. For Product & Price, prefer structured official API → canonical product detail → rendered/SSR card extraction, provided quality gates pass.
4. For Discovery, prefer sitemap or measurable reported-total pagination; use first-party network/GraphQL discovery when it materially improves frontier coverage.
5. For Promotion, prefer official campaign/catalogue surfaces and reject generic marketing text as promotion evidence unless the semantics are explicit.
6. Evaluate access environment independently. Stay cloud-hosted by default; escalate to approved Edge only with evidence.
7. Deep Audit the complete selected profile. Any material change in technique profile invalidates prior audit/approval.
8. Approve only when required tracks are present and audit hard gates pass.

## Required vs optional tracks

For the current supermarket domain contract:

- Required: `product_price`, `discovery`
- Optional: `promotion`

Optional does **not** mean weakly validated. If `promotion` is assigned, its technique must produce credible promotion records and pass the Promotion-track audit gate.

## What should not be generalized

Some details remain source-specific and should stay in adapters/technique implementations:

- Exact API paths, query hashes, seller IDs, category IDs, pagination parameter names.
- DOM selectors and Next/RSC payload shapes.
- Product identity parsing rules unique to a retailer's URL convention.
- Promotion date formats and campaign-specific structures.

The Pattern Library generalizes **how to select and combine techniques**, while adapters retain **how each source encodes its data**.

## Operational implications for KU2D

The pattern registry should eventually be consumed by Explore/Technique Strategy so new supermarket sources can be ranked using prior validated patterns. A future recommender can use evidence such as sitemap size, structured API presence, rendered-card quality, reported totals, and cloud-access status to prioritize candidate techniques before expensive probing.

The five-source supermarket phase therefore becomes training evidence for a more general adaptive acquisition system rather than a collection of five bespoke scrapers.
