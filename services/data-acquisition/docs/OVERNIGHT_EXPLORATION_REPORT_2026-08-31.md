# Overnight Data Acquisition Exploration Report — 2026-08-31

## Executive summary

The campaign safely integrated only reviewed PR #34, then completed eight
independent Draft review checkpoints from the same integration baseline. It
made 16 new public requests/page loads across 12 sources, retained at most 10
records per source/surface, stopped at every challenge boundary, and performed
no login, authenticated session reuse, CAPTCHA handling, proxying, bypass,
production storage, scheduling, or approval.

The strongest new evidence is: Lazada stable rendered-DOM identity/price across
four correlated surfaces; LINE SHOPPING seller-collection identity/price;
Akha Ama first-page catalog identity/price; and three distinct Q-Diving source
classes yielding 10 bounded records each over plain HTTP. No new source became
production-approved. Lazada counter semantics and cross-surface price mismatch,
Watsons Product & Price, and all public-marketplace demand claims remain open.

## Repository and publication ledger

- Integration HEAD at campaign start: `7d45e4a4efaa1d77b00a6b9f1480165689fe036a`.
- Reviewed PR #34 head: `173f7cb122d51b99f7b3cf6e7fd4f311d824323b`.
- PR #34 squash/integration HEAD: `820994f7521ef5f181e96826fdaaee40202b91ba`.
- Main HEAD throughout: `9f18a702e7959a9f333c671f171e8fbb54777b39`.
- PR #34 merge-triggered checks: Data Acquisition Platform CI #168 success;
  Frontend CI #872 success.
- No overnight Draft PR was merged.

| Branch | Commit | Draft PR | CI at report time |
| --- | --- | --- | --- |
| `codex/lazada-rendered-dom-deep-audit` | `f0bfe93cb09abf52eeda7fb2b352008813e5b28d` | #35 | Data Acquisition #169, Frontend #874, Preview #91: success |
| `codex/overnight-tiktok-shop-commerce-pulse-explore` | `9f62c33f933989bb12581fdb3b2a6fb21a1ca6b5` | #36 | Data Acquisition #170, Frontend #876, Preview #92: success |
| `codex/overnight-marketplace-source-inventory` | `0e99926c72cec7e83e259408c153fd6c99fd1492` | #37 | Data Acquisition #171, Frontend #878, Preview #93: success |
| `codex/overnight-ota-source-expansion` | `8c8ac59c5ef852bf2bbd33be6c8ff44e55e00c73` | #38 | Data Acquisition #172, Frontend #880, Preview #94: success |
| `codex/overnight-coffee-source-expansion` | `441c71d678a30cc62b742ea58f23f629a9d1e2d6` | #39 | Data Acquisition #173, Frontend #882, Preview #95: success |
| `codex/overnight-qdiving-source-expansion` | `5f972d456415dbd0d8ae695f02c056e4a7c76e56` | #40 | Data Acquisition #174, Frontend #884, Preview #96: success |
| `codex/overnight-cross-domain-source-gap-scan` | `408e4a3889a70b89b71cbd076b0b980d1aaae2d3` | #41 | Data Acquisition #175, Frontend #886, Preview #97: success |
| `codex/overnight-acquisition-technique-transfer-matrix` | `4c024a480dafda27b0064b3059e34eebaadf353d` | #42 | Data Acquisition #176, Frontend #888, Preview #98: success |
| `codex/overnight-exploration-summary` | This report branch | #43 | Checks triggered by report publication |

## Task/source evidence table

| Task | Domain | Source | Branch | Draft PR | New live requests / page loads | Access outcome | Usable evidence | Stable identity | Price | Demand/counter signal | Structured endpoint | Browser requirement | Edge requirement | Technique status | Production status | Recommended next action |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Integration | Lazada browser foundation | Reviewed PR #34 | merged | 0 in this campaign task | Reviewed foundation integrated | Yes | Canonical Lazada item URL | Explicit THB | Bare counters remain unknown | 0 validated | Normal browser proven | No | Foundation proven | Disabled | Use as bounded baseline only |
| 1 | Commerce Observation | Lazada search/detail/category/shop | `codex/lazada-rendered-dom-deep-audit` | #35 | 3 new browser loads; 1 prior search observation reused | All public surfaces reachable; no challenge | 8 records across four surfaces | 100% | 100%; same item search 25 THB vs detail 49 THB | Bare item counters unknown; display order contextual | None validated | Yes | No | Promising Deep Audit under review | `production_approved=false` | Review price mismatch and counter semantics |
| 2 | Commerce Observation | TikTok Shop Thailand product detail | `codex/overnight-tiktok-shop-commerce-pulse-explore` | #36 | 1 HTTP | HTTP 200 challenge/required-login marker; stopped | No, 0 records | No | No | No | Seller/creator APIs require authorization and are not a public national feed | Not attempted | No | Failed public detail attempt | Disabled | Pause until a separately reviewed public technique exists |
| 3 | Marketplace inventory | NocNoc | `codex/overnight-marketplace-source-inventory` | #37 | 1 HTTP + 1 normal browser | Official page announces platform cessation | No, 0 records | Not applicable | Not applicable | Not applicable | No | Browser confirmed closure | No | Reject | Disabled | Do not continue |
| 3 | Commerce Observation | LINE SHOPPING seller collection | same | #37 | 1 HTTP + 1 normal browser | Public collection reachable | 10 of 28 products | 10/10 product + shop + collection IDs | 10/10 explicit | “Recommended” is seller-local order, not demand | No validated endpoint | Yes for complete DOM | No | Promising; priority-1 | Disabled | Deep Audit surface identity and replay semantics |
| 3 | Candidate research | Kaidee | same | #37 | 0 | Research only | Architecture finding | Classified-listing identity needed | Ask price differs from product price | Not marketplace demand | Not assessed | Not assessed | No | Priority-2, separate contract | Disabled | Design Classified Listing Observation first |
| 4 | OTA | Agoda Bangkok fixed context | `codex/overnight-ota-source-expansion` | #38 | 1 HTTP | HTTP 200 challenge marker; stopped | No | No | No | No | No | Not escalated | No | Failed/paused | Disabled | Do not retry without reviewed compliant surface |
| 4 | OTA | Traveloka Thailand hotels | same | #38 | 1 HTTP | HTTP 403 challenge; stopped | No | No | No | No | No | Not escalated | No | Failed/paused | Disabled | Do not retry automatically |
| 5 | Coffee product | Roots Coffee detail | `codex/overnight-coffee-source-expansion` | #39 | 1 HTTP | Request completed; console evidence not durably retained | Indexed research only; 0 live records claimed | Canonical detail candidate | Indexed 450 THB only | None | Not retained | No | No | Promising, not live-validated | Disabled | Reviewed rerun writing bounded evidence file |
| 5 | Coffee product | Nana Coffee Roasters detail | same | #39 | 1 HTTP | Request completed; console evidence not durably retained | Indexed research only; 0 live records claimed | Canonical detail candidate | Public detail price semantics candidate | None | JSON-LD/DOM candidate | No | No | Promising, not live-validated | Disabled | Reviewed rerun writing bounded evidence file |
| 5/7 | Coffee product | Akha Ama first catalog page | Gap-scan evidence; Coffee PR #39 documents candidate | #41 / #39 | 1 HTTP | HTTP 200, no challenge | 10 products | 10 canonical product URLs | 10 explicit THB prices | None | Not assessed | No | No | Promising; priority-1 | Disabled | Catalog-to-detail implementation and Deep Audit |
| 6 | Q-Diving content | SSI Blog | `codex/overnight-qdiving-source-expansion` | #40 | 1 HTTP | HTTP 200, public static content | 10 content candidates | Canonical article URL | Not applicable | Not applicable | Not needed | No | No | Promising | Disabled; Human Review required | Repeatability/topic Deep Audit |
| 6 | Q-Diving service | Scubadoo Koh Tao price list | same | #40 | 1 HTTP | HTTP 200, public static course cards | 10 course-service offers | Host + normalized service identity | 10 explicit THB service prices | None | Not needed | No | No | Promising | Disabled; no booking | Deep Audit service/package changes |
| 6 | Q-Diving retail | Aquamaster equipment sale catalog | same | #40 | 1 HTTP | HTTP 200, public WooCommerce cards | 10 equipment products | 10 canonical product URLs | 10 explicit THB prices/ranges | Catalog order is not demand | HTML product metadata | No | No | Promising | Disabled | Detail correlation and price-semantics Deep Audit |
| 7 | Cross-domain | LINE, Akha Ama, Watsons, Pantip, Expedia gaps | `codex/overnight-cross-domain-source-gap-scan` | #41 | 1 new Akha load; LINE evidence reused | Inventory complete | Ranked evidence/recommendations | Source-specific | Source-specific | No unsupported claims | Source-specific | No new browser | No | Research complete | Disabled | Follow P0/P1 review order |
| 8 | Cross-domain | Technique transfer matrix | `codex/overnight-acquisition-technique-transfer-matrix` | #42 | 0 | Analysis only | PROVEN/PROMISING/FAILED/UNTESTED matrix | Assessed per technique | Assessed per technique | Assessed per technique | Public vs authorized separated | Environment separated | Environment separated | Analysis complete | Disabled | Review matrix before next source build |
| 9 | Campaign | Master report | `codex/overnight-exploration-summary` | #43 | 0 | Analysis only | Consolidated report | Not applicable | Not applicable | Not applicable | Not applicable | No | No | Review artifact | Disabled | Morning review |

## Request accounting

New campaign traffic totals **16 requests/page loads across 12 sources**:

- Lazada: 3 new normal-browser loads; one prior integrated search observation
  reused and not counted as new traffic.
- TikTok Shop: 1 HTTP request.
- NocNoc: 1 HTTP + 1 normal-browser load.
- LINE SHOPPING: 1 HTTP + 1 normal-browser load.
- Agoda: 1 HTTP request; Traveloka: 1 HTTP request.
- Roots Coffee: 1 HTTP request; Nana Coffee Roasters: 1 HTTP request.
- SSI Blog, Scubadoo, and Aquamaster: 1 HTTP request each.
- Akha Ama: 1 HTTP request.

There was one local Coffee import failure before network execution; it counts as
zero public requests. There were no retries around denial/challenge, no
pagination, no Edge dispatch, and no wide crawl.

## Biggest successes

1. Lazada correlated a stable item ID across search and detail and preserved
   eight bounded records across four surfaces. The audit correctly refused to
   convert `5.5K ชิ้น` or parenthetical counts into sold/review facts.
2. LINE SHOPPING produced complete identity and price for 10 products while
   preserving collection/shop/position context and rejecting national-rank
   overclaiming.
3. Akha Ama produced 10 static official catalog products with canonical URLs,
   THB prices, package-size cues, and roast/process vocabulary.
4. Q-Diving gained three separable non-YouTube evidence classes with 30 total
   bounded records and no browser requirement.
5. TikTok, Coffee, and Q-Diving code branches added deterministic safety and
   semantic tests without weakening frozen Retail/Supermarket behavior.

## Access failures and pauses

- TikTok Shop public detail: challenge/required-login marker; exit/evidence
  withheld, no browser or Edge escalation.
- Agoda: challenge marker; Traveloka: HTTP 403/challenge. Both stopped.
- NocNoc: platform ceased operations; acquisition should not continue.
- Roots/Nana: source potential is strong, but live evidence was not durably
  retained; false-green validation was explicitly refused.
- Shopee: no new attempt. Its previously reviewed Edge diagnostic ended at
  traffic verification, so live access remains paused.
- YouTube: no request. Acquisition remains paused by campaign instruction.

## Technique-transfer findings

- **Proven:** official structured product API; sitemap/canonical detail;
  rendered/SSR cards for validated Supermarkets; Gourmet browser-network
  discovery; approved source-specific Edge environment for Gourmet; YouTube
  official metadata/Human Review contracts.
- **Promising:** Lazada/LINE rendered DOM; Akha Ama/Aquamaster static catalogs;
  Scubadoo service cards; SSI/PADI public content indexes; Coffee JSON-LD/detail
  normalization; contextual OTA cards.
- **Failed/insufficient:** TikTok challenged detail; Agoda/Traveloka public
  attempts; Shopee Edge traffic-verification result; seller-authorized APIs as
  substitutes for national public marketplace observation.
- Identity/price techniques transfer well across domains. Demand semantics do
  not transfer from display order, unlabeled counters, or source size.
- Edge is an execution-environment decision, never an extraction technique or
  bypass mechanism.

## Readiness decisions

### Ready for Deep Audit after Draft review

- LINE SHOPPING seller collection.
- Akha Ama catalog-to-detail.
- SSI content index, Scubadoo course cards, Aquamaster product cards.
- Lazada is already at Draft Deep Audit; it needs review of price mismatch,
  counter meaning, and longitudinal readiness rather than wider crawling.

### Ready for Human Review

- SSI content candidates after repeatability evidence.
- Existing PADI/YouTube content packages only through their current review
  contracts; YouTube acquisition itself remains paused.

### Paused or rejected

- Pause TikTok Shop, Agoda, Traveloka, and Shopee access attempts.
- Reject NocNoc as a continuing source.
- Pause Roots/Nana live claims until a reviewed evidence-file rerun.
- Do not use seller/affiliate credentials to obtain a purported national feed.

### Edge and official API decisions

- No newly explored source requires Edge based on successful evidence tonight.
  Lazada and LINE worked in a normal browser; SSI, Scubadoo, Aquamaster, and
  Akha Ama worked over plain HTTP.
- Shopee Edge remains paused after traffic verification. Do not dispatch again.
- YouTube should use only the official Data API v3 metadata provider when its
  pause is separately lifted. TikTok/Lazada/Shopee seller APIs are not a public
  marketplace-wide substitute and were not authorized.

## Regression and security status

- PR #35: 34/34 local deterministic scripts; CI #169 success.
- PR #36: 34/34 local deterministic scripts; CI #170 success.
- PR #37: 33/33 local deterministic scripts; CI #171 success.
- PR #38: 33/33 local deterministic scripts; CI #172 success.
- PR #39: 32/32 local deterministic scripts; CI #173 success.
- PR #40: 33/33 local deterministic scripts; CI #174 success.
- PR #41: 31/31 integration deterministic scripts; CI #175 success.
- PR #42: analysis-only local parse/compile/diff/security checks; CI #176
  success confirms the integration deterministic corpus.

Every code branch ran applicable JSON/YAML parsing, Python compilation, new
targeted tests, complete deterministic Data Acquisition tests, Shopee, Lazada,
YouTube, Retail, JIB, and Supermarket regressions. No existing test was disabled.

All branch diffs passed the credential/cookie/session/token/proxy value scan.
No credential, token, cookie, authorization header, session identifier, proxy
configuration, personal profile, raw NetLog, or browser state was committed.

## Morning review priorities

### P0 — architecture/decision review

1. PR #35 Lazada: reconcile 25 vs 49 THB for the same item, keep bare counters
   unknown, and decide whether Partial longitudinal readiness is acceptable.
2. Watsons Product & Price: choose a canonical-detail/rendered-card architecture
   without weakening Beauty required-track or provenance gates.

### P1 — promising next steps

1. PR #37 LINE SHOPPING Deep Audit.
2. PR #39 Coffee source contract, followed by Akha Ama catalog-to-detail work.
3. PR #40 SSI/Scubadoo/Aquamaster repeatability and detail-correlation audit.
4. PR #41 cross-domain gap ranking and PR #42 technique matrix.

### P2 — useful but incomplete

1. PR #36 TikTok contract and blocked evidence; keep access paused.
2. PR #38 OTA blocked outcomes; consider Expedia/Trip.com only through a newly
   reviewed fixed-context experiment.
3. Pantip public-community privacy and Human Review contract.

### P3 — defer / do not continue

1. NocNoc (platform ceased operations).
2. Shopee live retry/Edge dispatch until a reviewed compliant technique exists.
3. Seller-authorized marketplace APIs without explicit separate authorization.
4. YouTube acquisition until its pause is explicitly lifted.

All results remain exploration or review evidence. `production_approved=false`,
`production_store=false`, and `scheduler_action=null`.
