# KU2D Acquisition Consolidation & Readiness v1

This repository-only campaign consolidates durable acquisition evidence into a
common map, two pattern libraries, a recovery backlog, conservative source
tiers, and a future locked-source batch template. It made zero live requests,
did not use a browser or Edge Runner, did not mutate parked refs or knowledge
authority, and did not approve production acquisition or scheduling.

The machine-readable source of truth is
`config/acquisition_consolidation_readiness.json`. The future campaign skeleton
is `config/locked_source_batch_campaign_template.json`. Neither artifact is an
execution instruction.

## Evidence and interpretation rules

Every retained claim cites a durable repository artifact. Observation remains
separate from interpretation. Code, Theme, Descriptor, and Interpretation are
not interchangeable. Extraction technique remains separate from execution
environment. When repository evidence does not justify a conclusion, the
artifact uses `candidate`, `unresolved`, `insufficient_evidence`,
`no_existing_code_fits`, or `novel_pattern_candidate` rather than forcing a
taxonomy or promoting authority.

Historical outcomes are preserved. In particular:

- Nana Coffee Roasters is evidence-recovery-complete for the Coffee phase, but
  remains candidate-only and single-route evidence.
- Roots Coffee remains the sole open Coffee gap; the durable result is still
  evidence-withheld with zero retained product records.
- Coffee remains `complete-with-open-gap`.
- JIB remains validated only in isolated staging. Production Human Approve is
  false.
- Shopee remains paused at an access boundary. This is not extraction failure,
  impossibility, or proof that data is absent.
- Parked LINE, OTA, Coffee, and Q-Diving evidence remains candidate-only.

## Current acquisition capability

KU2D has durable support for official structured product metadata, canonical
product-detail identity and price, rendered/SSR product cards, official
campaign metadata, catalog-frontier discovery, official API metadata under a
provider policy, split-track selection, evidence-before-exit diagnostics,
profile fingerprints, and Deep Audit gates.

The strongest domain is Supermarket: Lotus's, Big C, Makro, and Tops have
validated required tracks without a retained execution caveat. Gourmet Market
also has validated tracks, but public acquisition depends on an independently
approved Thailand Edge environment when cloud access is blocked. JIB is the
strongest cross-domain Retail transfer, with five of five product samples and
all recorded IT Retail gates passing, but the approval scope is isolated
staging and production approval remains false.

Marketplace and cross-domain candidates must remain narrower:

- Lazada has bounded rendered-DOM identity and price evidence. Counter meaning,
  variant equivalence, canonical price, structured acquisition, velocity, and
  production readiness remain unresolved.
- Shopee has only a durable compliant access-boundary result.
- YouTube Q-Diving has an official-API provider, quota accounting, Human Review
  contracts, and dry monitoring plans. Automated suggestions are not semantic
  authority and production scheduling is disabled.
- Watsons has Discovery clues but no validated required Product and Price track.
- Nana is strong bounded candidate evidence, not catalog batch evidence; Roots
  remains withheld.

## Acquisition Pattern Library v1

The library contains ten evaluated patterns:

1. Official Structured Product API.
2. Sitemap to Canonical Detail Discovery.
3. Structured or SSR Product Detail Catalog.
4. Rendered Product Detail or Listing.
5. First-party App-Bundle Discovery.
6. Official API Metadata Acquisition.
7. Source-detail Normalization.
8. Search-versus-detail Price Comparison.
9. Official Campaign Surface.
10. Explicit Execution-environment Boundary.

Each pattern defines prerequisites, a minimum evidence threshold,
applicability and non-applicability, failure modes, provenance, repeatability,
Deep Audit expectations, examples, and transferability. A reusable technique
never makes its source adapter reusable automatically. `APL-010` is explicitly
an environment policy, not an extraction technique. JIB is the only durable
domain-live app-bundle example, so that transfer remains single-source.

## Failure & Boundary Pattern Library v1

The library contains fifteen evidence-gated safe-stop patterns: cloud access
boundary; confirmed challenge versus screening false positive; semantic matcher
limitation; insufficient retained evidence; source discovery failure;
extraction failure; rendering dependency; product/variant ambiguity;
price-role ambiguity; displayed order not demand; blocked access not extraction
failure; request-retention/diagnostic gap; wrong-host/canonical ambiguity;
application shell without stable signal; and evidence-authority conflation.

Each pattern specifies what evidence is required before classification, how to
stop safely, what must not be inferred, and whether recovery is offline,
bounded-live, environment-specific, or human-adjudicated. A locked method never
falls through automatically to another technique or environment.

## Recovery backlog

The current backlog reconciles KG001–KG008 plus Roots, Watsons, and the batch
contract. Scores use six transparent 1–5 dimensions: value, unresolved
uncertainty, reuse/generalization, inverse recovery cost, evidence availability,
and inverse live/human dependency. A score ranks planning value only and does
not grant execution authority.

Disposition totals are:

- `close_now_offline`: 4
- `next_bounded_live_candidate`: 4
- `human_adjudication`: 2
- `monitor`: 1
- `defer`: 0
- `obsolete/superseded`: 0

No live or human-gated backlog item was executed.

## Source readiness tiers

Tier A — Locked & Repeatable requires a validated official technique, required
tracks, provenance, repeatability, and audit evidence without an unresolved
execution caveat. It contains four sources: Lotus's, Big C, Makro, and Tops.

Tier B — Locked with Caveat has validated method/audit evidence but retains an
explicit environment or approval-scope caveat. It contains two sources:
Gourmet Market and JIB.

Tier C — Not Batch Safe covers candidate-only, access-paused,
Human-Review-dependent, single-route-only, or required-track-incomplete sources.
It contains twelve sources: Watsons, Lazada Thailand, Shopee Thailand, YouTube
Q-Diving, Nana Coffee Roasters, Roots Coffee, LINE SHOPPING, Agoda, Traveloka,
SSI Blog, Scubadoo Koh Tao, and Aquamaster Thailand.

The repository is ready to plan—but not execute—a separately reviewed,
Tier-A-only, locked-method batch. A Tier B source may be included only when its
recorded caveat is explicitly accepted in that future manifest. Tier C is
excluded until new evidence or authority changes its status.

## Locked-source batch template

The template requires one technique lock, one environment lock, bounded request,
page, record, timeout and retry budgets, an expected bounded objective,
provenance, repeatability and Deep Audit gates, drift/anomaly metrics, stop
conditions, and explicit exit 0/1/2 semantics.

If a locked method fails, the source stops and writes boundary/drift evidence.
It may not switch extraction technique, environment, browser/Edge, login,
authentication, CAPTCHA/challenge handling, private API, proxy/session, budget,
or production/scheduling authority. Other sources may continue only if their
independent locks remain valid.

## KU2D to KU2A readiness

The one-way Dataset Intake boundary is contract-ready only for independently
reviewed datasets with immutable dataset identity, source/profile provenance,
authority class, and quality/Deep Audit results. Candidate and diagnostic
evidence cannot enter KU2A automatically, and KU2A cannot write conclusions
back into KU2D authority.

## Next actions

The five highest-value next actions are: prepare a reviewed Tier-A-only manifest
without execution; implement the offline generic drift-event contract (KG-004);
normalize retained request cost/latency ledgers (KG-005); consider a separately
authorized minimum Roots same-URL validation if the remaining Coffee gap is
worth closing; and prepare a bounded Watsons Product and Price objective without
assuming a technique.

Low-value work includes repeating stable supermarket exploration without drift,
retrying Shopee/OTA boundaries without a new compliant technique, using record
count as quality, automatically promoting candidates, or building a generic
browser/Edge fallback.

## Hardening result

No accepted runtime acquisition behavior needed a safe semantic change in this
campaign. Hardening is deliberately contract-only: a fail-closed validator,
64 deterministic assertions across evidence/authority/tier/backlog/template
invariants, cross-file provenance checks, and a non-executable batch template.
Larger work—generic drift events, normalized cost/latency, browser abstraction,
and app-bundle transfer—remains in the backlog rather than being refactored into
the platform without evidence.

