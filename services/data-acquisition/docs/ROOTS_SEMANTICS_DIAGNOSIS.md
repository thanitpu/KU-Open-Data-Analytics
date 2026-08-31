# Roots Coffee Strict-Semantics Diagnosis v1

## Outcome

The retained Roots observation failed exactly one strict normalization gate:
`coffee_product_semantics`. This is a planning diagnosis, not a correction or
a reinterpretation of the live result. `KU2D-R-000027` remains exit `2`,
`evidence_withheld`, with no retained Roots record and failed aggregate Deep
Audit. No external request was made.

The smallest deterministic parser correction is justified from repository
evidence alone: add a high-confidence semantic witness for an official,
same-host `/products/` canonical route whose slug contains an explicit coffee
token, but only when the already-required product name and attributable price
are present. A generic product route or target configuration alone must never
prove coffee semantics. The name, price, canonical, non-menu, provenance,
repeatability, and Deep Audit gates remain unchanged.

## What Roots retained—and did not retain

The durable artifact retained HTTP 200, the response size/digest, the official
final URL, canonical `https://shop.rootsbkk.com/products/house-blend-coffee`,
an empty structured offer, no labeled coffee attributes, and the exact failure
reason. It retained no raw HTML, headers, record, or field provenance.

The failure reason is built from every strict missing gate. Because it lists
only `coffee_product_semantics`, the normalizer internally found a product
name, attributable displayed price, canonical identity, and no menu-only
failure. Their exact sanitized values and extraction paths were not retained
after the composite semantic decision failed, so the historical record cannot
be reconstructed or promoted.

The current semantic matcher accepts Product JSON-LD, explicit coffee-bean or
roasted-coffee text, or a coffee name plus labeled coffee attributes. The live
sanitized row proves none of those witnesses. It does retain an official
product route with a coffee-bearing slug, but the matcher does not evaluate
that witness. This is classified as a parser/normalizer limitation. The absent
candidate values/paths are a separate diagnostic-retention gap.

## Nana comparison

Nana is a successful contract-shape comparator, not a structure that Roots is
required to copy. Nana retained two records with Product JSON-LD, an explicit
name, price/currency/availability, origin/process/tasting labels, thirteen
provenance fields per record, and 100% identity/canonical repeatability. Roots
may use a different official representation while still meeting the same
identity, price, semantics, provenance, and repeatability contract.

## Separately queued offline correction

A later implementation Prompt can add the canonical-route witness and retain
sanitized candidate values plus extraction paths when normalization is
withheld. It must include:

- a positive official product route with a coffee slug, name, and price but no
  Product JSON-LD or labeled coffee attributes;
- negative non-coffee product, menu/drink, missing-name, and missing-price
  fixtures;
- a withheld-diagnostic fixture that remains replayable without raw HTML,
  headers, cookies, credentials, or session state;
- unchanged historical artifact and frozen Roots/Nana regressions.

No live request is needed to implement or test that correction. Any later live
validation requires an independent review and separate authority.

## Boundaries

This diagnosis does not change parser/runtime code, make a request, promote
Roots or Nana, mutate Learning Memory, Reviewed Corpus, Core Knowledge, Human
Confirmation, or Ground Truth, authorize production/storage/scheduling, touch
parked refs, run cleanup, train/infer ML, or perform Survey/DoE/SEM work.
