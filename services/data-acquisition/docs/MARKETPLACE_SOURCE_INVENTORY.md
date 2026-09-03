# Thailand Marketplace Candidate Inventory

Observed 2026-08-31. This is research evidence for Commerce Market Observation, not production approval.

## Scope and ranking method

The existing marketplace baseline is Shopee, Lazada, and TikTok Shop. Additional candidates were ranked by Thailand relevance, public accessibility, stable identity, explicit price, demand/ranking evidence, compliant technical access, KU2D value, and redundancy with existing Retail acquisition.

Public listing or catalog visibility does not imply transaction truth. Seller asking prices, contextual collection order, sold displays, reviews, and platform rankings remain distinct signals. No candidate may set `production_approved=true`, enable production storage, or create a scheduler action.

## Ranked candidates

| Priority | Source | Finding | Recommended next action |
|---|---|---|---|
| priority-1 | LINE SHOPPING | Public seller collections expose stable product IDs, titles, explicit baht prices, shop/collection context and display position. No demand counter was established. | Deep Audit collection/detail correlation and public identity URLs. |
| priority-2 | Kaidee | Highly Thailand-relevant public classifieds with listing identity, seller/location context and asking price. Heterogeneous new/used goods, property, vehicles and services make Commerce Product semantics unsafe. | Architecture review for a separate Classified Listing Observation contract. |
| defer | Central Online | Strong official retail product and price source, but primarily Retail rather than marketplace demand and highly redundant with Retail transfer work. | Route through Retail prioritization. |
| defer | Temu | Cross-border product catalog may be valuable, but localization, destination, tax, price personalization and compliant public access are unresolved. | Research terms and destination-explicit context before requests. |
| defer | AliExpress | Similar cross-border value, with unresolved Thailand destination/currency/shipping context and likely access instability. | Defer until a destination-aware observation contract exists. |
| reject | NocNoc | Current official site announces shutdown; new orders ended 2026-02-09 and the platform ended 2026-05-09. | No further acquisition. |
| reject | JD Central | Thailand consumer e-commerce operations closed in 2023. | Historical reference only. |

Primary public evidence includes the [LINE SHOPPING collection](https://shop.line.me/@dosethailand/collection/4069), [Kaidee marketplace](https://www.kaidee.com/th), and current [NocNoc notice](https://nocnoc.com/).

## Bounded NocNoc check

One plain HTTP request returned HTTP 200 HTML with no product links or prices. One normal-browser page load then exposed the current official closure notice. NocNoc stopped taking new orders on 2026-02-09 and states that all platform service ended on 2026-05-09. No catalog/product navigation or additional request followed. Total: 1 HTTP request, 1 browser page load, 0 retained commerce records.

The correct classification is `reject`, despite historical indexed catalog pages. Stale indexed pages are not current marketplace evidence.

## Bounded LINE SHOPPING check

One plain HTTP request to a public seller collection returned HTTP 200 HTML, 201,832 bytes, and 28 explicit baht displays. One normal-browser page load of the same collection exposed 28 visible products. The bounded sample retained the first 10:

- stable numeric product IDs: 10/10;
- titles: 10/10;
- explicit baht prices: 10/10;
- shop identity (`@dosethailand`): 10/10;
- collection identity (`4069`) and display position: 10/10;
- sold/order/review/demand counters: 0/10.

The visible selected order was `Recommended`. It is seller-collection context and must not become bestseller, marketplace-wide, or national rank. The observation supports product identity and price exploration, not demand or sales velocity.

The browser was used to confirm DOM identity attributes. Whether the same identifiers can be extracted reliably from the already returned static HTML was not tested because the page was not requested again. Normal browser rendering was sufficient and Windows Edge is not required.

## Boundaries and next steps

LINE SHOPPING is ready for a reviewed Deep Audit with a maximum of one collection, one directly linked product, and at most 10 retained records. The Deep Audit should validate canonical public product URLs, seller-local identity, price/original-price semantics, availability, product-detail correlation, and whether collection IDs and product IDs survive refreshes.

Kaidee should not be forced into `CommerceProductObservation` without architectural review: an asking-price classified for a used vehicle or property is not equivalent to a sellable SKU, and listing popularity is not sales demand. NocNoc and JD Central should not receive additional acquisition work.
