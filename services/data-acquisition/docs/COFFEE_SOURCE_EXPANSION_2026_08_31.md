# Coffee Source Expansion — 2026-08-31

## Outcome

Official specialty-roaster product detail is a promising transfer of the
Retail detail technique into Coffee, but it is not live-validated by this
checkpoint. Deterministic fixtures prove that canonical identity, price,
origin, process, tasting notes, roast, size, availability, and provenance can
be normalized without mixing roasted-bean products with cafe drink menus.

Two bounded requests were made: one Roots Coffee product detail and one Nana
Coffee Roasters product detail. Both requests completed, but the exploratory
console result exceeded the retained output boundary and was not written to a
durable evidence file. The campaign did not retry either source. Therefore the
live result is explicitly **not evidence of a successful acquisition**.

## Source assessment

| Source | Public evidence | Identity | Technique | Status | Next action |
| --- | --- | --- | --- | --- | --- |
| Roots Coffee | Official indexed detail exposes 450 THB, Pangkhon/Chiang Rai origin, processes and notes | Canonical product URL | Official product detail | Promising, not live-validated | Bounded Deep Audit with evidence-file output |
| Nana Coffee Roasters | Official indexed detail exposes multi-country origin, process, notes, roast and sizes | Canonical product URL | JSON-LD/DOM product detail | Promising, not live-validated | Bounded Deep Audit with evidence-file output |
| Akha Ama Coffee | Official catalog exposes products, prices, roast information and geographic story | Not audited | Catalog to detail correlation | Untested candidate | First bounded Explore |

Indexed pages were used only to characterize source potential. They do not
replace captured live acquisition evidence.

## Technique boundary

`roaster_product_record()` accepts only HTTPS official product details with a
stable URL slug, a product name, an attributable price, and coffee-product
semantics. Explicit labels or structured product data may supply origin,
process, tasting notes, roast, package size, and availability. It writes no
production state.

The following remain distinct:

- roasted coffee product price;
- cafe drink-menu price;
- producer or geographic provenance;
- availability at the observation time.

Missing origin/process/roast fields remain null. They are never inferred from
the source name or from generic marketing copy.

## Request and safety accounting

- Roots Coffee: 1 public request, 0 retained live records.
- Nana Coffee Roasters: 1 public request, 0 retained live records.
- Akha Ama Coffee: research only, 0 campaign requests.
- One local import failure occurred before network execution and is not a
  public request.
- No retry, pagination, browser, Edge Runner, authentication, cookies,
  CAPTCHA handling, proxying, session reuse, or production write occurred.

`production_approved=false`, `production_store=false`, and
`scheduler_action=null` remain mandatory.
