# Coffee Recovery Next-Step Decision v1

## Outcome

Recommend **Option A: one separately queued, bounded rerun with the hardened detector on the same Roots Coffee and Nana Coffee Roasters product-detail URLs**. This is a planning recommendation, not execution authority. No request was made in this checkpoint.

The deterministic comparison scores A at 4.50, B (move next to Q-Diving recovery) at 3.15, and C (stop Coffee for now) at 1.80. The model weights expected evidence gain and direct Coffee-gap resolution at 25% each, cross-source reuse and incremental request/risk efficiency at 20% each, and dependency reduction at 10%. Higher request/risk efficiency means lower incremental cost and risk.

## What the completed observation established

The merged Coffee run remains `evidence_withheld`, not success: technical completion was true, both exact official URLs returned HTTP 200, two public read-only requests completed, zero product records were retained, repeatability was unavailable, and Deep Audit failed. The screening-only `captcha` substring was not a confirmed visible challenge.

Four uncertainties must remain separate:

- **Detector false-positive risk is material but unresolved.** The first detector matched a document-wide substring. The hardened detector now treats script-only text as a negative fixture, but raw HTML was intentionally not retained, so the old match cannot be conclusively reclassified.
- **Environment/access risk is unresolved, not confirmed.** HTTP 200 and no redirect support reachability, but the retained artifact contains neither visible challenge proof nor enough evidence to rule one out.
- **The live extraction technique was not evaluated.** The stop rule fired before normalization, so no live conclusion about canonical identity, attributable price, coffee semantics, or field provenance is justified.
- **Evidence retention was mechanically repaired while the product-evidence gap stayed open.** The request ledger and sanitized diagnostics were durably written before exit; the missing Roots/Nana product and repeat evidence was not recovered.

## Exactly three options

| Rank | Option | Score | Decision basis |
|---:|---|---:|---|
| 1 | A — same-URL hardened-detector Coffee rerun | 4.50 | Only option that can directly resolve Roots/Nana identity, price, provenance, and repeatability with a small public-surface envelope. |
| 2 | B — move to Q-Diving recovery | 3.15 | Highest breadth across content, course-service, and retail-product roles, but much larger coordination/review cost and zero direct Coffee-gap resolution. |
| 3 | C — stop Coffee for now | 1.80 | No incremental request risk, but it generates no new evidence and leaves both Coffee candidates unresolved. |

## Smallest safe Option A envelope

Execution requires a new Prompt. If separately authorized, use only the existing Roots House Blend and Nana House Blend official URLs, the hardened detector, cloud as the default environment, and the existing evidence-before-exit writer. Allow at most two observations per source, four acquisition attempts total, twelve transport requests including bounded same-host redirects, no retry, no pagination, a one-megabyte response ceiling, and a 15-second timeout.

Make one observation per source first. If a source's first observation has a confirmed hardened access boundary or cannot yield attributable product identity plus displayed price, stop that source: a second observation can no longer satisfy the required two-of-two Deep Audit. Only a passing first strict product record receives a second observation for repeatability. Never escalate to browser, Edge, authentication, session reuse, proxying, challenge handling, or automatic retry.

Outcome meanings remain exact:

- **Success / exit 0:** four retained records, two per source; stable official identity and canonical URLs; attributable displayed prices; complete field provenance; correct retail-product semantics; 100% identity/canonical repeatability; Deep Audit passed. Authority remains candidate-only pending independent review.
- **Withheld evidence / exit 2:** technical completion without a confirmed access boundary, but any identity, price, semantic, provenance, repeatability, or Deep Audit gate fails.
- **New access boundary / exit 2:** the hardened detector records explicit access-denial status, visible/title challenge, challenge widget/markup/route, authentication requirement, or off-host redirect. Stop without escalation.
- **Technical failure / exit 1:** transport, runtime, budget, or evidence-writing failure. Retain available evidence and require review before any retry.

## Boundaries

This decision does not authorize Option A, start Q-Diving work, promote Candidate Learning Evidence, mutate Learning Memory, Reviewed Corpus, Core Knowledge, Human Confirmation, or Ground Truth, touch parked refs, perform cleanup, schedule work, approve production, run ML, or perform Survey/DoE/SEM work.
