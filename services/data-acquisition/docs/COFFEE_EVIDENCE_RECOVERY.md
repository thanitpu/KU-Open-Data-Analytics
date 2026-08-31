# Coffee Evidence Recovery v1

This checkpoint repairs the evidence-retention gap recorded for Roots Coffee
and Nana Coffee Roasters in parked Draft PR #39. Human Decision
`KU2D-H-000009` authorizes only this bounded public, read-only recovery. The
machine-readable request contract is
`config/coffee_evidence_recovery_package.json`.

## Evidence package defined before access

The only targets are the reviewed official product-detail URLs for Roots House
Blend and Nana House Blend. The budget is two observations per source: four
acquisition attempts total, no retry, no pagination, at most two same-host
redirects per attempt, at most 12 transport requests including redirects, a
1,000,000-byte response bound, and a 15-second timeout.

Before the first request, the CLI writes a prepared evidence document. Before
each request, it appends and writes a pending request-ledger entry. After each
response, it retains the sanitized response metadata, digest, explicit public
field subset, normalized record, and field-level raw-to-normalized provenance
before another request or process exit. Raw HTML, headers, cookies, browser
state, credentials, and session material are not retained.

The captured fields are stable product identity, canonical URL, name,
attributable displayed price and currency, temporal availability and explicit
variant evidence where present, origin, process, tasting notes, roast, package
size, source/surface, and observation time. Missing fields remain null. Price
or availability changes are temporal deviations; they are not transaction
prices, demand signals, variant equivalence, or cross-branch truth.

## Deep Audit and stop behavior

Each source must yield two attributable retail roasted-coffee product records,
stable official HTTPS identity/canonical URL, and complete provenance for every
non-null normalized field. Retail bean product evidence remains separate from
cafe drink-menu pricing. Repeat observations preserve identity and explicitly
record any price, availability, variant, or attribute deviation.

The run stops at the four-attempt ceiling, on an authentication/CAPTCHA/
challenge/access-control signal, on an off-host redirect, on the response-size
bound, or when durable evidence cannot be written. It never escalates to a
browser, Edge Runner, proxy, session reuse, private API, or circumvention.
Access/environment boundaries are recorded separately from strict extraction
contract failures.

Exit `0` means the bounded evidence package passed these candidate Deep Audit
gates. Exit `2` means execution completed and diagnostic evidence was retained,
but candidate evidence was withheld. Exit `1` means a technical, transport, or
evidence-writing failure. None of these exits grants Human Approve, production
storage, scheduling, Reviewed Corpus status, Core Knowledge status, or Ground
Truth.

## Authority

Any recovered records remain candidate evidence for `KU2D-CLE-000006` and
`KU2D-CLE-000007` pending independent review. The existing Candidate Learning
Evidence Registry and every higher-authority knowledge layer remain unchanged.
`production_approved=false`, `production_store=false`, and
`scheduler_action=null` are invariant.

## Bounded run outcome

The authorized run completed technically and retained
`docs/validation/coffee-evidence-recovery-2026-08-31.json` before exit. It used
two acquisition attempts and two transport requests: one per source, with no
redirect, retry, pagination, browser, authentication, or production action.
Both exact official URLs returned HTTP 200 HTML. The first detector version
found the string `captcha` somewhere in each bounded document and followed the
reviewed stop condition, so it did not make the second observation or attempt
extraction. Because raw HTML was intentionally not retained, those string
matches cannot be independently classified as a visible challenge rather than
script-only text. The durable evidence therefore labels them screening-only,
not confirmed CAPTCHA challenges.

Exit classification is `2`: `technical_completion=true`, candidate evidence
withheld, zero retained product records, repeatability unavailable, and Deep
Audit failed. The CLI now requires explicit HTTP status, visible/title/widget,
challenge-markup, or route evidence for future boundary classification; a
script-only occurrence of the word `captcha` is a deterministic negative
fixture. This checkpoint did not rerun after improving that detector.

## Separately authorized hardened rerun

Human Decision `KU2D-H-000010` and Prompt `KU2D-P-000027` separately
authorized exactly one same-URL rerun. The request package now validates that
authority, and the runner stops a source after an unusable first observation;
it makes observation two only after a strict first product record. The durable
result is `docs/validation/coffee-hardened-rerun-2026-08-31.json`.

The rerun completed technically with exit `2`, three acquisition attempts,
three transport requests, no retry, no pagination, and no access boundary.
Roots returned HTTP 200, but its first response did not meet the strict coffee
product-semantics gate, so no Roots record was retained and the source stopped
without a second request. Nana returned two attributable House Blend records
at 470 THB. Both Nana records retained field-level provenance, stable identity
and canonical URL, and 100% identity/canonical repeatability; the Nana source
audit passed. The aggregate Deep Audit failed because Roots retained zero
records.

This result is candidate-only evidence pending independent review. It does not
promote either Candidate Learning Evidence record and does not authorize a
Reviewed Corpus, Core Knowledge, Human Confirmation, Ground Truth, production,
storage, or scheduler mutation. No automatic rerun or environment escalation
occurred.
