# Acquisition Technique Transfer Matrix — 2026-08-31

## Interpretation

This matrix is evidence-based at integration commit
`820994f7521ef5f181e96826fdaaee40202b91ba` plus the explicitly identified
overnight Draft PRs. It does not infer success from code existence.

- **PROVEN**: live or durable domain evidence and regression coverage support
  the stated use.
- **PROMISING**: bounded evidence or deterministic coverage supports a next
  audit, but lifecycle validation is incomplete.
- **FAILED**: the attempted path did not produce usable evidence or crossed a
  stop boundary.
- **UNTESTED**: architecture suggests a fit, but no bounded source evidence is
  available.

Execution environment and extraction technique are separate decisions. A
Windows Edge Runner never turns a failed parser into a successful technique,
and it never authorizes challenge solving.

## Matrix

| Technique | Evidence status | Domains / sources proven | Promising transfers | Failed / insufficient sources | Access requirement | Identity quality | Price quality | Demand-signal quality | Stability / cost / maintenance | Automation and production readiness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Official structured product API | **PROVEN** | Supermarket: Lotus's | Retail sources exposing equivalent first-party catalogs | No public national-marketplace API established for Shopee, Lazada, or TikTok Shop | Public first-party API; no seller token | High | High when price is attributable to SKU | Low unless endpoint explicitly defines rank/counter semantics | High stability; low runtime cost; moderate schema maintenance | Strong automation fit. Production only after source Deep Audit and Human Approve |
| Sitemap to canonical product detail | **PROVEN** | Supermarket: Big C, Tops; canonical detail principle also validated for JIB | Beauty Watsons required-track gap; Coffee specialty roasters | Not a solution where sitemap/detail is absent or blocked | Plain HTTP, official sitemap/detail | High | High on explicit detail price | None | Stable identity; moderate request cost; moderate change burden | Strong for Product & Price, not demand. Source approval still required |
| Rendered or SSR product cards | **PROVEN** | Supermarket: Makro and Gourmet Market | Lazada rendered DOM (Draft PR #35); LINE SHOPPING seller collection (Draft PR #37) | Shopee Edge run stopped at traffic verification; TikTok detail challenged | Normal browser only when static HTTP is insufficient | Medium-high when canonical ID/URL is visible | High when card price is explicitly attached | Low until counter/rank semantics are independently evidenced | Medium stability; higher cost; selector maintenance | Bounded automation possible. Lazada/LINE remain non-production |
| Static HTML catalog cards | **PROMISING** | No new domain promoted by this analysis | Akha Ama: 10 products/one page; Aquamaster: 10 equipment products; Scubadoo: 10 service cards | SSI content is not a price catalog; generic marketing text is insufficient | Plain HTTP | High with canonical product URL; medium for service-name identity | High for explicit THB display, but service and retail semantics differ | None | Low cost; medium theme/template maintenance | Ready for deterministic Deep Audit, not production approval |
| JSON or JSON-LD embedded in HTML | **PROVEN** for existing Retail/Supermarket shapes; **PROMISING** for Coffee transfer | Big C embedded application state; existing retail detail transport | Nana Coffee product detail fixture/shape in Draft PR #39 | Roots/Nana live console evidence was not durably retained, so no live Coffee success is claimed | Plain HTTP | High when Product schema and canonical URL agree | High when Offer is current and attributable | None | Low-medium cost; schema/theme variation risk | Excellent fit after live evidence-file capture and repeat audit |
| Public structured endpoint discovered through browser network | **PROVEN** for discovery | Gourmet Market GraphQL/network discovery | Lazada network candidates remain unvalidated | Shopee had zero validated network endpoints; endpoint names alone were insufficient | Normal browser/network metadata; public official response only | Potentially high after response validation | Potentially high | Only as defined by response semantics | Medium-high diagnostic cost; high maintenance | Discovery can automate after review; never replay private signatures or headers |
| Rendered-DOM product/detail correlation | **PROMISING** | Supermarket correlations provide the pattern | Lazada search/detail/category/shop audit in Draft PR #35 | Lazada price mismatch across surfaces requires review | Normal browser; bounded surfaces | High when item ID and canonical URL agree | Needs surface/time reconciliation | Unknown bare counters remain unknown | Higher cost and selector churn | Deep Audit candidate; not production-ready |
| Public search/category surface | **PROMISING** | Existing supermarket catalogs prove catalog traversal generally | Lazada, LINE SHOPPING, Akha Ama, Aquamaster | Agoda and Traveloka stopped on challenge; TikTok challenged | Plain HTTP first, normal browser only if justified | Medium-high with stable links | Medium-high with explicit card prices | Usually low; display order is contextual, not national rank | Medium cost; changing sort/personalization risk | Suitable for discovery and observation with exact surface provenance |
| Shop/catalog surface | **PROMISING** | Existing official Retail catalogs | LINE SHOPPING seller collection; Akha Ama catalog; Aquamaster catalog | NocNoc ceased platform operations | Public official catalog | High for shop + item + surface identity | High for explicit price | Low without explicit, defined counter | Medium stability; low-medium cost | Deep Audit next. Never generalize one shop collection to marketplace-wide demand |
| RSS / Atom content feed | **PROMISING** | No source promoted solely from current code | PADI deterministic feed technique; SSI content-index transfer | None established; live repeat evidence not included in the baseline | Plain HTTP | High canonical article identity | Not applicable | Not applicable | High stability; low cost; low maintenance | Strong content-index candidate, but relevance/authority needs Human Review |
| Static HTML article-card index | **PROMISING** | — | SSI Blog: 10 public content candidates in Draft PR #40 | Generic article text without canonical identity | Plain HTTP | High canonical article URL | Not applicable | Not applicable | Low cost; moderate layout maintenance | Automatable metadata staging; no automatic authority or knowledge approval |
| Static HTML service/course cards | **PROMISING** | — | Scubadoo Koh Tao: 10 THB course offers in Draft PR #40; possible OTA-adjacent transfer | Context-free or personalized OTA rate displays | Plain HTTP | Medium-high using official host + course identity | High as service price with package context | None | Low cost; moderate content-change burden | Deep Audit candidate. Must remain distinct from retail product price |
| Contextual OTA result/card acquisition | **PROMISING** | Booking deterministic pattern | Future Expedia or Trip.com fixed-context Explore | Agoda challenge marker; Traveloka HTTP 403/challenge | Public search only; exact dates, occupancy, currency | Medium-high for property IDs | Only valid with full query context | Rating/review is separate, not demand | High volatility and personalization risk; medium-high cost | Not production-ready; no authenticated booking/member flow |
| Official documented metadata API | **PROVEN** for bounded metadata workflow | YouTube Data API v3 Q-Diving foundation and reviewed pilot learning | Approved-channel uploads monitoring after Human Review | Arbitrary transcripts/comments and HTML scraping are prohibited | API key for public metadata; owner OAuth only for separately authorized owner data | High video/channel IDs | Not applicable | API statistics are metadata, not unreviewed authority | Stable contract; quota cost; policy/refresh maintenance | Human Review staging only; production storage and scheduling remain disabled |
| Seller-authorized / affiliate API | **FAILED** for public national-market observation objective | — | Could serve a separately authorized seller-owned use case | Shopee/Lazada/TikTok seller APIs do not establish a public national marketplace feed | Seller authorization, scopes, signing, tokens | Potentially high for authorized seller scope only | High within authorized scope | Not representative of national market without evidence | High integration/governance burden | Not authorized for this campaign; do not request merchant access |
| Human-reviewed content evidence | **PROVEN** as a non-authorizing contract | Q-Diving YouTube video/channel review and KU2A handoff contracts | SSI/PADI public content staging | Automated suggestions alone are insufficient | Public metadata plus explicit reviewer decision | High after provenance validation | Not applicable; price mentions are context only | Not applicable | Human cost; stable governance; moderate maintenance | Authoritative for inclusion decisions, not production acquisition approval |
| Temporal Commerce Market Observation | **PROMISING** architecture; live access mixed | Deterministic Shopee/Lazada observation contracts | Lazada/LINE repeated public observations | Shopee live access paused; TikTok challenged; no national bestseller claim | Public surface only; append-only isolated observation store | High only with stable product + surface identity | High when explicit/current | Counter/rank semantics require direct evidence | Recurring cost; high semantic maintenance | Non-production until repeat audit and approval; raw and normalized velocity remain separate |
| Windows Edge execution environment | **PROVEN** as an environment decision for Gourmet | Gourmet Market public access where cloud was blocked | A separately reviewed source may qualify after ordinary access succeeds | Shopee Edge diagnostic reached traffic verification and produced no usable evidence | Approved self-hosted Windows/Thailand runner; no personal profile or secrets | Determined by extraction technique | Determined by extraction technique | Determined by evidence semantics | High operational cost and maintenance | Never an extraction technique, bypass, or automatic escalation. Source-specific approval required |

## Cross-domain conclusions

1. Canonical detail identity and explicit price transfer well from Supermarket
   to Retail, Coffee products, and dive equipment. They do not create demand
   evidence.
2. Rendered cards transfer to marketplaces only when source-surface identity,
   item identity, and price remain attributable. Display order and bare counters
   fail closed as contextual/unknown.
3. OTA query context transfers to dive-course services only as a discipline for
   package and location context; a course service is not a room rate.
4. Q-Diving content feeds and article indexes can stage metadata, while Human
   Review remains the authority for relevance, source class, and knowledge use.
5. Official seller APIs are not a compliant shortcut to public marketplace-wide
   observation. Edge execution is likewise not a shortcut around access control.

## Recommended next technique reviews

- **P0:** Watsons canonical-detail Product & Price architecture.
- **P1:** LINE SHOPPING surface-aware Deep Audit.
- **P1:** Akha Ama catalog-to-detail Coffee Deep Audit.
- **P1:** Lazada rendered-DOM price/counter reconciliation.
- **P1:** SSI/Scubadoo/Aquamaster repeatability Deep Audit after Draft PR #40
  review.

No matrix entry sets production approval. `production_approved=false`,
`production_store=false`, and `scheduler_action=null` remain unchanged.
