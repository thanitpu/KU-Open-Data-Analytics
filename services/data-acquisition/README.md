# KU2D Adaptive Data Acquisition Service

**GitHub source-of-truth baseline:** v0.28 engine + adaptive-platform foundation.

Canonical lifecycle: **Discover → Explore → Deep Audit → Human Approve → Scheduled Acquire → Monitor → Re-Explore on drift**.

Explore/Audit observations are preserved as evidence; approved scheduled acquisition produces trusted observations. Secrets and runtime SQLite files are never committed.

Shopee Commerce Pulse is a separate, non-production marketplace-observation domain. Its public-signal semantics, isolated explorer, controlled pilot boundary, and bounded Windows Edge access diagnostic are documented in [docs/SHOPEE_COMMERCE_PULSE.md](docs/SHOPEE_COMMERCE_PULSE.md).

## Live validation status semantics

Live workflow execution, lifecycle technical completion, source approval, isolated staging approval, and production Human Approve are different states:

- **Workflow execution** reports whether the CI command and supporting steps ran successfully.
- **Lifecycle technical completion** means Explore and Deep Audit finished and reviewable evidence was written; it does not mean quality gates passed.
- **Source approval** means every required track and audit/domain gate passed for the exact technique-profile fingerprint.
- **Isolated staging approval** is a validation-only simulation stored in explicitly configured temporary operations and observation databases. It cannot authorize production acquisition.
- **Production Human Approve** remains the governance boundary that enables scheduled acquisition in the production operations database.

`LIVE_JIB_RETAIL_LIFECYCLE.py --require-approved` requires explicit temporary database paths and `KU2D_APPROVAL_SCOPE=isolated-staging`. It returns `0` only for a technically complete, approved isolated-staging result, `2` when evidence is complete but approval is withheld, and `1` for a technical/runtime or evidence-write failure. Detailed and compact evidence are written before an approval-withheld exit. The compact artifact uses schema `ku2d.retail-live-validation-summary.v1`; live artifacts are uploaded by CI and are not committed automatically.

## Durable JIB cross-domain validation knowledge

JIB is the first successful live validation of the supermarket-derived Retail Commerce Core Patterns in another retail domain. Workflow run `33302385382` validated canonical-detail Product & Price with `generic_retail_detail_catalog` and app-bundle Discovery with `generic_app_bundle` from an official public surface. Promotion remained optional and unassigned.

The live profile was approved only in isolated staging. It did not perform production Human Approve and does not enable production scheduling. Because GitHub Actions artifacts are retention-bound, the reviewed result is reduced to the sanitized durable record `docs/validation/jib-retail-validation-2026-08-30.json` and the non-authorizing registry `config/retail_domain_validations.json`; raw product records and the staging SQLite database are not committed.

---

# KU2D Data Acquisition Service v0.28

Operational Data Acquisition application split from the KU Text Analytics Lab v2.56 handoff.

## Current operational flow

**Discover → Explore → Find Best Acquisition Technique(s) → Deep Audit → Approve → Deep Acquire → Monitor → Store → View Acquired Data**

The application starts directly in **Acquisition Operations**. There is no active Service Home, pricing UI, package calculator, billing UI, or Text Analytics navigation.

## Run locally on Windows

Two equivalent launchers are included:

- ZIP/package root: `RUN_KU2D_DATA_ACQUISITION_SERVICE_v0.28.bat`
- App folder: `KU2D_Data_Acquisition_Service_v0.28\RUN_KU2D_DATA_ACQUISITION_SERVICE_v0.28.bat`

The launcher verifies both API and UI version markers before opening the browser.

Default endpoints:

- Operations UI: `http://localhost:8088/demo/acquisition-operations.html`
- API health: `http://127.0.0.1:8090/health`

## Best Acquisition Technique is now the acquisition source of truth

Each monitored source can have one or more persisted Best Acquisition Techniques. Explore and **Find Best Data Acquisition Techniques** benchmark available methods and save the selected profile in the operations DB.

v0.19 makes that profile authoritative for the controlled workflow:

1. **Deep Audit** runs the assigned Best-Technique profile itself rather than independently returning to the legacy crawler.
2. The audit records yield, field quality, provenance, repeatability, technique execution evidence, and a fingerprint of the ordered technique profile.
3. **Approve for Repository Store** applies to that audited profile.
4. **Deep Acquire & Store** must use the same fingerprint. If the Best-Technique assignment changes after audit, Deep Acquire is blocked until Deep Audit is run again.
5. Updating the ordered Best-Technique assignment automatically invalidates prior audit/store approval, preventing one extraction method from inheriting another method's approval.
6. Deep Acquire does not silently fall back to the legacy crawler when an audited Best-Technique profile returns zero repository-ready records; the failure is surfaced for review.

This establishes one traceable chain:

`Best Technique Found → Technique Audited → Technique Approved → Same Technique Acquires → Repository`

## Explore and adaptive technique benchmarking

Explore remains an automatic technique bench. It can use generic methods and source-specific methods where available. For Lotus's this includes its multi-surface promotion/product/sitemap/application/network strategies.

The normal Explore UI hides zero-output methods, while **Copy All Technique Results** retains full success/failure diagnostics for technical review.

The Monitoring Queue supports **Find Best Data Acquisition Techniques** across enabled sources and persists source-level assignments.

## Cooperative cancellation

v0.19 adds Cancel controls for long-running operations:

- Run All Enabled / monitoring acquisition campaigns
- Find Best Data Acquisition Techniques
- Batch Deep Audit
- Batch Deep Acquire
- Single-source Deep Acquire in the detailed audit panel
- Single-source Deep Audit / Deep Acquire API jobs

Cancellation is cooperative: it stops new source work and checks for cancellation at safe phase boundaries. It does not forcibly kill Python or interrupt a repository transaction midway through a write.

## Monitoring visibility

The Monitoring Queue retains:

- Best Acquisition Technique(s)
- Access / Quality as the separate Deep Audit/storage gate
- Last Found
- Last Added to Repo
- Select All / Unselect All
- Export Monitoring Queue
- persistent Monitoring Activity Log

`Best Acquisition Technique(s)` answers **how to extract**. `Access / Quality` answers **whether that selected extraction profile was audited and is approved for repository storage**.

## Source-of-truth rule

Configured acquired-data repositories remain authoritative. A missing configured repository must be reported as **NOT CONNECTED** and must not be silently replaced by a new empty SQLite database.

## v0.19 validation focus

The release was pre-checked for:

- Python compilation;
- JavaScript syntax on active pages;
- API `/health` version `0.17`;
- required cancellation API routes;
- Best-Technique audit execution;
- audited-technique fingerprint enforcement in Deep Acquire;
- technique-assignment change invalidating old audit/store approval;
- package root launcher presence and version consistency.


## v0.19 — Monitoring Review, Audit Export & Technique/Audit Alignment

- Monitoring Queue now supports filtering by source name, URL, domain, Access / Quality, cadence, due state, and last run status.
- Deep Audit adds **Export Results (.json)**, exporting the full batch plus source snapshots, assigned techniques, audit/quality profiles, run state, and results.
- Deep Audit action-state styling is clarified:
  - **Approve this URL** = KU Green / white text.
  - **Audit gate not passed** = gray / white text.
  - **Already Approved / Approved** = gray / KU Green text.
- Commerce technique ranking no longer treats a readable document alone as a repository-ready acquisition method.
  Document extraction remains useful evidence/context, while product/promotion/price facts are required for an acquisition-role technique.
- Find Best Data Acquisition Techniques automatically escalates commerce sources that lack storable facts to Browser-rendered DOM, Browser Network/API Discovery, and JSON/API Probe before settling on a discovery-only profile.
- Non-commerce monitoring sources can use assigned readable-document profiles in Deep Audit; Deep Acquire routes non-commerce sources through their correct repository workflow rather than forcing them into the Commerce repository.
- Failed Deep Audit cards now show the failed repository-readiness reason directly.
- Manual **Force Approved** is intentionally not introduced in this release; repository-store approval remains gated by a passed audit.


## v0.19 — Lotus Product Catalog & Price Acquisition

- Adds **Lotus Category Product & Price Catalog** as a source-specific acquisition technique.
- Category pages are rendered with local Chrome/Edge so JavaScript-created product links can be enumerated.
- Category acquisition then materializes official product detail URLs into product records with product name, brand, category and current price.
- Product-detail extraction now uses multiple signals in order: visible product text, e-commerce meta tags, JSON-LD/application JSON, then rendered DOM fallback.
- If category DOM links are not exposed, a bounded Browser Network/API probe is attempted before falling back to the official product sitemap.
- Official Lotus product sitemap coverage is connected to real product-detail materialization instead of remaining URL-only discovery evidence.
- Explore reports category product URLs, product-detail extraction success rate, full product sitemap coverage, and an evidence-based full-catalog extractability estimate.
- Routine acquisition advances through the Lotus sitemap product universe by monitoring-run offset, reducing repeated collection of the same first product URLs.
- Deep Audit now requires Lotus's to produce at least one product record and >=80% product price completeness; promotions alone can no longer make Lotus's pass the audit.


## v0.19 — Lotus Multi-Track Acquisition Profile

Lotus's is now treated as a multi-surface source with separate acquisition objectives rather than one globally ranked technique.

### Track model
- **Product & Price** — prefers `Lotus Catalog API`; falls back to `Lotus Category Product & Price Catalog`.
- **Promotions** — prefers `My Lotus’s Promotion Surface`.
- **Coverage / Discovery** — prefers `Robots / Sitemap Discovery` and remains a discovery companion rather than a business-fact extractor.

### Lotus Catalog API
Explore now captures network traffic from the exact Lotus category/search surface and immediately probes official `api-o2o.lotuss.com` product endpoints that the browser actually used. When the public `/product/v4/products` pattern is observed, official sitemap product IDs are converted to bounded SKU batches for read-only catalog requests.

Operational acquisition uses progressive SKU batches so recurring runs move through the product universe instead of requesting the same first products indefinitely.

### Rendered category-card fallback
The category DOM extractor pairs a product link/name with currency-marked price elements (`฿` / `บาท`). Bare package-size numbers such as `700 G`, `500 G`, or `1 KG` are deliberately not accepted as prices.

### Audit → Acquire contract
The persisted technique assignment stores track ownership. Deep Audit checks the same track profile that Deep Acquire will later use:
- Lotus requires a **Product & Price** track.
- Product records must be materialized.
- Current-price completeness must meet the audit threshold.
- If a Promotion track is assigned, that track must also yield promotion records.
- Discovery-only tracks are audited as coverage evidence but do not satisfy business-record yield by themselves.

Changing a technique, track assignment, or technique-engine version invalidates the prior audit/store approval and requires a fresh Deep Audit.

### Deep Acquire
Deep Acquire runs each audited track independently, merges/deduplicates the resulting facts, and reports `records_by_track` before repository ingestion. Sitemap is used as a coverage/cursor source and only falls back to detail materialization when no dedicated Product & Price track exists.


## v0.19 — Lotus Catalog API Schema Mapping & Audited API Reuse

The Lotus Product & Price track now parses the exact public O2O catalog response shape used by
`api-o2o.lotuss.com/lotuss-mobile-bff/product/v4/products`.

Mapped fields include:
- SKU / product ID / canonical Lotus product URL
- product name
- category path / category ID
- current/final price
- regular price
- member price
- promotion price when final price is lower than regular price
- availability / stock on hand
- weight and selling units
- discount amount / percent
- image URL and API provenance

Package-size numbers are never used as API prices; prices come only from explicit API price fields such as
`finalPricePerUOW`, `regularPricePerUOW`, `loyaltyMemberPricePerUOW`, and `priceRange.minimumPrice`.

### Explore → Monitoring contract
When Explore discovers a working Lotus Catalog API pattern it stores a bounded `operational_config`
inside the recommended technique evidence (batch endpoint, seller ID, batch size, search endpoint when observed).

### Deep Audit / Deep Acquire
Deep Audit and Deep Acquire reuse the persisted Catalog API configuration directly rather than launching
Chrome to rediscover the endpoint on every run. The stable API configuration is included in the technique
profile fingerprint, so changing the endpoint pattern or engine version makes prior approval stale.

Operational runs use official sitemap product identities as a progressive SKU cursor and request products
in bounded batches of up to 99 SKUs. If a persisted API configuration unexpectedly yields zero records,
one explicit browser-network rediscovery is attempted and recorded in diagnostics; there is no hidden
fallback to an unaudited legacy crawler.

### Repository provenance
Catalog API rows store the canonical Lotus product page as `source_url` and keep the actual API request
separately as `api_source_url`.


## v0.20 — Big C / Makro Commerce Surfaces & Acquire Result Export

Big C and Makro now use source-specific multi-track acquisition profiles before Deep Audit / Deep Acquire.

### Big C
- **Product & Price:** `Big C Product Catalog Surface` reads official Big C category listings (30 products/page) and enriches a bounded sample from public product-detail pages for SKU/brand/category.
- **Promotions:** `Big C Official Campaign Surface` uses explicit campaign pages and rejects generic coupon-help/navigation text as promotions.
- **Discovery:** official sitemap coverage remains a companion source.
- Product records from generic marketing text such as `ซื้อครบ = 1 baht` are penalized and can no longer satisfy the retail Product & Price track.

### Makro
- **Product & Price:** `Makro PRO Product Catalog Surface` uses the official commerce surface at `makro.pro`, not the corporate `makro.co.th` homepage/catalogue.
- The listing surface provides current product universe, product name, brand and price; bounded public product-detail pages enrich SKU/brand.
- **Promotions:** the corporate Makro catalogue remains a promotion track.
- **Coverage:** Makro PRO reported product total is kept as coverage evidence and progressive page traversal moves through the catalogue on recurring runs.

### Audit contract
Lotus's, Big C and Makro are now explicit retail-catalog sources. Deep Audit requires:
- an assigned Product & Price track;
- at least one real product record;
- >=80% product-price completeness;
- repeatability and provenance gates as before.
This prevents Big C/Makro from passing only because a generic crawler found a marketing phrase or promotion catalogue.

### Deep Acquire UI / JSON export
Deep Acquire now has a dedicated **Deep Acquire & Store Results** panel and **Export Acquire Results (.json)** button. The export points to the actual store batch (`deep-acquire-full-results`) rather than falling back to the preceding audit batch.

### Domain safety
Effective-domain handling now recognizes common multi-label suffixes such as `.co.th`. This fixes Big C/Makro source detection and prevents unrelated Thai `.co.th` sites from being treated as the same site during API candidate filtering.

### Run All compatibility
The legacy Commerce store path no longer assumes the acquisition result contains a `sector` key; it safely uses result sector, source domain, or registry sector. This removes the prior `KeyError: 'sector'` failure seen in older Monitoring runs.


## v0.21 — Retail Product Identity Gate, Big C Sitemap Materialization, Makro PRO SSR/Rendered Fallback

### Big C
- `bigc_product_catalog` is now **Big C Sitemap Product Detail Catalog**.
- The official Big C sitemap is treated as the product universe; Thai/English duplicate product URLs are canonicalized to one identity.
- Explore and operational acquisition walk a bounded set of official `/product/` detail URLs and materialize product name, SKU/ID, brand, category, current price and product provenance.
- Recurring runs use a progressive sitemap offset and try additional sitemap URLs when stale entries fail, rather than repeatedly scraping homepage coupon text.
- The generic Big C `basic_crawler` is no longer eligible for the Product & Price track.

### Makro PRO
- The Makro PRO catalog parser now reads server-rendered product-card structure directly and can parse product name, selling unit, brand, current price and product URL.
- If fetched HTML reports catalog size but does not expose cards, one explicit local Chrome/Edge rendered-DOM fallback is used on the Makro PRO search surface itself.
- A conservative embedded-state fallback is also available when product name + explicit price + product URL are exposed in hydration data.
- Product detail enrichment supplies product code/SKU and brand. Quantity-tier detail prices are preserved separately and do not overwrite the normal search-card price.

### Semantic Product Quality Gate
For Lotus's, Big C and Makro, Deep Audit now requires at least 80% of ProductCandidate rows to have plausible product identity + price evidence. Generic coupon/marketing text (`ซื้อครบ`, discount thresholds, coupon codes, `text-pattern`) cannot satisfy repository readiness even if a number was parsed as a price.

### Monitoring Queue → Explore
Each Monitoring Queue URL now has an **Explore** button. It:
1. copies the existing source URL, exact domain, purpose, name/adapter/source context into Section 2;
2. scrolls to **Explore a New URL**;
3. automatically starts Explore without requiring a second click;
4. preserves the existing `source_id`, so **Update Monitoring Techniques** updates that row instead of creating a duplicate source.

### Audit lifecycle
Technique engine version is `0.21`; therefore an older audited fingerprint is not silently reused after this extraction/audit logic change. Re-audit the source profile before Deep Acquire.

## v0.23 — Big C Detail Hydration Fallback + Makro PRO Accessible Listing Materialization

This release focuses on the remaining Product & Price materialization gap found by live Explore on Big C and Makro.

### Big C
- Keeps the official sitemap as the product universe.
- Product detail extraction now reads multiple representations of the same public page: normal DOM text, parsed readable text, decoded Next/React flight payload text, and a bounded headless render of the exact product detail when direct HTML still does not expose product-local evidence.
- Price parsing is anchored around the main product code/title block so similar-product carousel prices are not treated as the focal product price.
- Current Big C compact labels such as `แบรนด์โรซินันเต้` and `หมวดหมู่ขนมอบ ทอดกรอบ` are normalized.
- Rendered fallback is bounded to the operational batch size; challenge pages are never accepted as products.

### Makro PRO
- Adds `makro-pro-accessible-text` materialization for the public search/listing text when product cards do not expose a parser-friendly anchor/container hierarchy.
- Understands the current listing form `product name + sale unit + brand + ฿price` while using the final unit token as the separator so package sizes inside product names are preserved.
- Extracts product paths from normal or escaped SSR/React payloads and aligns them to listing observations when available.
- Existing product-detail enrichment remains responsible for SKU and quantity-tier context.
- Browser-network discovery now exposes all captured public request URLs before source-specific related-domain filtering. This allows source adapters to inspect official related infrastructure such as `*.siammakro.cloud` instead of being limited to the seed host.
- Telemetry/metrics endpoints are explicitly excluded from commerce API probing.

### Explore usability
- The Monitoring Queue `Explore` action is now an underlined link beside the URL.
- `Copy ALL Technique Results` is placed at the top of Explore results.

### Audit contract
Technique engine version is `0.24`. Existing older audit/approval fingerprints become stale when the source is updated to the v0.24 technique profile and must be audited again before Deep Acquire.


## v0.23 — Big C Explore Timeout Guard

Big C Explore is now explicitly time-bounded and non-rendering:
- Explore samples at most 4 product-detail URLs and targets at most 2 materialized products.
- Explore has a 12-second technique budget.
- Repeated headless-browser fallback is disabled during Explore.
- Deep Audit / Deep Acquire retain bounded browser fallback when needed.
- Explore status polling uses a 60-second local-API timeout with automatic retry instead of aborting after 20 seconds.
- Diagnostics expose `explore_fast_mode`, `time_budget_seconds`, and `render_fallback_attempts`.


## v0.24 — Big C Multi-Template Product Audit Hardening

- Big C product-detail materialization now supports multiple current official page shapes, including `รหัสสินค้า:` / `ID:`, unit prices such as `฿56/ แพ็ค`, `฿16/ กระป๋อง`, and `฿25/ ขวด`, plus original-price forms such as `฿62-9%`.
- Product-local price parsing is bounded to the focal product block and excludes the Similar Products carousel.
- Escaped Next/RSC and structured product-state fallbacks are anchored to the focal product ID/SKU.
- Big C ProductCandidate rows can preserve product-level promotion mechanics and source-stated expiry dates (e.g. `หมดเขต 06/09/69` → `2026-09-06`).
- Deep Audit now reports overall, Product & Price, and Promotion repeatability separately. Retail Product & Price repeatability must be >=70%; stable promotions can no longer mask a failing product extractor.
- Retail Deep Audit now requires at least 5 product records when the audit page cap is 5 or more, in addition to price completeness and semantic-quality gates.


## v0.25 — Makro PRO Resilient Listing Materialization

This release fixes the remaining Makro Product & Price gap without changing the approved Big C acquisition contract.

### Makro PRO
- Product-card DOM traversal now treats multiple image/title anchors that point to the same product as one card, instead of rejecting the container because it has more than one `/p/` anchor.
- Current Makro product routes such as `/th/p/219535-6761199108291` now supply SKU `219535` and GTIN `6761199108291` directly at listing time.
- A new rendered/accessibility sequence parser materializes repeated `product name → sale unit → brand → price` sequences even when title, unit, brand, and price are split across DOM nodes.
- The parser supports normal `brand฿49` cards, weighed items such as `1 kg ... ฿52.50`, and discounted compact cards such as `brand 1,600฿1,970฿-18%`.
- Thai package sizes inside product names (e.g. `15 กก.`) are not misread as the sale-unit separator.
- Network probing excludes image assets in addition to analytics/telemetry noise.
- Rendered-fallback diagnostics now report DOM bytes, product-link count, sale-unit token count, price-token count, and parser mode.

### Contract stability
Application release version is `0.25`, while `TECHNIQUE_ENGINE_VERSION` intentionally remains `0.24`.
The recommendation/fingerprint contract did not change; only the Makro materializer implementation changed.
This preserves an already-approved Big C v0.24 fingerprint and avoids unnecessary Big C re-audit when moving to v0.25.


## v0.27 — Tops Re-Explore with Generalized Supermarket Patterns

Tops may already be approved under an older generic profile. v0.27 intentionally does **not** auto-invalidate that approval.
The application release is `0.27.1`, while `TECHNIQUE_ENGINE_VERSION` remains `0.24`. Existing approved assignments remain authoritative until the user explicitly chooses **Update Monitoring Techniques** after reviewing Explore evidence.

New Tops-specific techniques:
- `tops_product_catalog` — **Tops Sitemap Product Detail Catalog**: Big-C pattern generalized to Tops official product sitemap shards and public product detail pages.
- `tops_campaign_catalog` — **Tops Campaign Product & Price Surface**: Makro-style product-card/listing materialization on official campaign/category pages, preserving SKU/product URL, current price, regular price and promotion mechanic.
- `tops_promotion_surface` — **Tops Official Campaign Surface**: official homepage/campaign promotion blocks with source-stated order dates.
- `tops_catalog_network` — **Tops Catalog API / App Discovery**: Lotus-style application/API discovery from publicly delivered Next.js assets and bounded read-only GET probes.

Recommender behavior for Tops now rejects weak generic text-pattern products as the Product & Price track and prefers the source-specific campaign/detail surfaces when they produce traceable product identity + price.

Deep Audit treats Tops as a retail catalog source after an explicit technique update, applying the same product coverage, semantic quality, price, provenance and Product-track repeatability gates used for Lotus's, Big C and Makro.


## v0.27 — Tops Audit Semantics + Stable Repeatability + Official Promotions

- Deep Audit quality is now scoped to the assigned business track: Product & Price quality uses only records from the assigned Product & Price technique; Promotion yield uses only the assigned Promotion technique.
- Deep Audit repeat checks use a stable source sample instead of advancing the operational catalog cursor. A smaller repeat sample is scored by reproducibility of the smaller sample; Jaccard/set similarity remains diagnostic.
- Tops product sitemap URLs are canonicalized to remove escaped leading `%20`/space artifacts.
- Tops Official Campaign Surface now uses bounded retry plus official campaign-sitemap fallback, and extracts offer/date blocks from official pages.
- Application version is `0.27`; `TECHNIQUE_ENGINE_VERSION` intentionally remains `0.24`, so unrelated approved supermarket profiles are not invalidated merely by installing this build. Tops is invalidated only if the user explicitly updates to a changed Tops technique profile.


## v0.27.1 — Launcher / Version Hygiene Hotfix

- Fixed stale launcher `VERSION=0.26` while API reported `0.27`.
- Fixed stale `ku2d-version` meta tags in Operations, Progress & Health, and Acquired Data pages.
- Launcher now stops immediately with an explicit API version-mismatch message instead of polling `/health` repeatedly.
- Technique engine contract remains `0.24`; this hotfix does not invalidate existing technique assignments by itself.


## v0.28 — Gourmet Market GraphQL + Rendered Product Identity

Gourmet Market is now evaluated with source-specific supermarket patterns learned from Lotus’s, Big C, Makro and Tops rather than accepting the generic rendered-promotion classifier.

- **Gourmet Market GraphQL Product Catalog**: probes the public `api-stark.gourmetmarketthailand.com/graphql` endpoint with a read-only GraphQL health query, mines public Next.js bundles for product/catalog query documents, replays only bounded read-only query operations whose required variables can be resolved safely, and materializes product/price rows when a compatible public operation is available. Persisted operational config keeps the successful endpoint/query for Audit/Acquire reuse.
- **Gourmet Market Rendered Product Cards**: fallback product materializer inspired by Makro. It anchors product identity to GTIN-bearing official product image URLs and then extracts the card’s product name, current price, regular price, canonical product link, and image URL. Category labels and UI controls cannot qualify as ProductCandidate records.
- **Gourmet Market Official Promotion Surface**: accepts only explicit promotion/campaign/brochure surfaces or product cards with a source-stated regular/current price relationship. The generic `lotus-promotion-listing-card` output is never eligible to own Gourmet’s Promotions track.
- **Gourmet GraphQL / Network Catalog Discovery**: combines the official GraphQL endpoint, browser network evidence, and GTIN-bearing product media requests into source-specific discovery evidence.
- Gourmet Market is now treated as a retail catalog source by Deep Audit, so Product & Price coverage, semantic product quality, price completeness and product-track repeatability use the same hard gates as the other approved supermarkets.
- The global `TECHNIQUE_ENGINE_VERSION` intentionally remains `0.24`; installing v0.28 does not invalidate the already approved Lotus’s, Big C, Makro or Tops profiles. Only an explicit **Update Monitoring Techniques** changes a persisted source profile.
