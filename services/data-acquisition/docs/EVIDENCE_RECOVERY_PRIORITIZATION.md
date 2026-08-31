# KU2D Evidence Recovery Prioritization v1

## Decision

Recommend **PR #39 Coffee** as the first targeted evidence-recovery rerun. This is a planning recommendation only. It does not authorize a request, rerun, candidate promotion, knowledge write, parked-ref mutation, cleanup, production action, scheduler action, or automatic follow-on.

The decision uses only the merged Parked Evidence Disposition Plan, Parked Candidate Review, Parked Synthesis Review, Candidate Learning Evidence Registry, Branch/PR Governance, and Core Knowledge artifacts. Fresh GitHub state confirmed PRs #37, #39, and #40 remain open, Draft, unmerged, and unchanged at their reviewed heads.

## Transparent scoring

Scores are integers from 0 to 5, where higher is better. The normalized score is `sum(score × weight) / 100`. Ties are resolved by evidence-gap leverage, feasibility/compliance, dependency reduction, then lower PR number.

| Criterion | Weight | Rationale |
|---|---:|---|
| Cross-source/domain reuse value | 20% | Prefer evidence that validates reusable semantics across sources or roles. |
| Evidence-gap leverage | 25% | Prefer work that directly closes explicit gaps toward possible future Reviewed status. |
| Expected learning gain | 20% | Reward uncertainty reduction for identity, price, provenance, repeatability, and transfer. |
| Feasibility/compliance | 15% | A high score means bounded official public access with low compliance/access risk. |
| Dependency reduction | 10% | Reward resolution of linked CLE and reviewed-claim dependencies without scope expansion. |
| Effort/cost | 10% | A high score means lower engineering, review, request, and maintenance cost. |

| Rank | Candidate | Reuse | Gap leverage | Learning | Feasibility | Dependency | Effort | Score |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | PR #39 Coffee | 4 | 5 | 4 | 5 | 4 | 5 | **4.50** |
| 2 | PR #40 Q-Diving | 5 | 4 | 5 | 4 | 5 | 2 | **4.30** |
| 3 | PR #37 Marketplace | 5 | 4 | 4 | 2 | 3 | 3 | **3.70** |

## Exact recovery gaps

### PR #39 — Coffee: first

Historical head: `441c71d678a30cc62b742ea58f23f629a9d1e2d6`

- **Roots / KU2D-CLE-000006:** retain one bounded sanitized official detail response plus its normalized identity, attributable price, availability, and field provenance. This targets PCR-000029, PCR-000030, and PCR-000032.
- **Nana / KU2D-CLE-000007:** retain the equivalent evidence-before-exit package. This targets PCR-000029, PCR-000031, and PCR-000033.
- **Both sources:** repeat the same bounded details and audit identity, price role, temporal availability, origin/process/roast/package fields, and raw-to-normalized provenance. This targets PCR-000029 and PCR-000037.
- PCR-000034 is already durable semantic knowledge; PCR-000035 is stale; PCR-000036 remains a historical ledger. A rerun must not restore or promote those claims.

Coffee ranks first because the known failure is evidence retention rather than an access challenge: two small official-detail observations can directly repair both CLE records and test a reusable retail-detail pattern at the lowest expected effort and compliance risk.

### PR #40 — Q-Diving: wait

Historical head: `5f972d456415dbd0d8ae695f02c056e4a7c76e56`

- **SSI / KU2D-CLE-000008:** sanitized canonical article evidence, raw date strings, identity repetition, and Human Review of relevance/authority (PCR-000038, PCR-000044).
- **Scubadoo / KU2D-CLE-000009:** service identity, package composition/change, duration, dive count, THB price, provenance, and repeatability (PCR-000039, PCR-000042, PCR-000045).
- **Aquamaster / KU2D-CLE-000010:** product/variant identity, detail correlation, price-role provenance, availability, and repeatability (PCR-000040, PCR-000042, PCR-000046).
- **All roles:** raw-to-normalized provenance, parser fingerprints, negative fixtures, role/registry review, and source-specific transfer evidence (PCR-000041, PCR-000047, PCR-000048). PCR-000043 remains historical request accounting.

Q-Diving has the highest breadth and dependency leverage but requires three source-role audits plus Human Review and registry decisions. It should wait for the smaller Coffee package to prove the evidence-before-exit recovery pattern. If reviewed fixtures and approved Human Review capacity raise its effort score from 2 to 5, its score becomes 4.60 and it moves first.

### PR #37 — Marketplace: wait

Historical head: `0e99926c72cec7e83e259408c153fd6c99fd1492`

- **LINE / KU2D-CLE-000002:** sanitized per-record collection/request evidence (PCR-000011), then static-versus-rendered identity comparison, detail correlation, price/availability roles, repeatability, and replay deduplication (PCR-000013, PCR-000014).
- **NocNoc / KU2D-CLE-000003:** a durable sanitized official cessation notice and independent lifecycle review (PCR-000019).
- Kaidee/Temu/AliExpress gaps (PCR-000015, PCR-000017, PCR-000018) require separately scoped future research and are not silently included in the targeted rerun.
- PCR-000012 and PCR-000016 use current durable equivalents; PCR-000020 is historical; PCR-000021 is a stale priority that must not govern this decision.

Marketplace should wait because LINE requires a wider static/rendered/detail protocol and NocNoc may no longer expose the observed notice. Current official evidence that LINE identity/detail extraction is stable without session state, plus a retained cessation notice, would justify rescoring feasibility and dependency reduction.

## Authority boundary

The machine-readable artifact is `config/evidence_recovery_prioritization.json`. Its validator rejects stale branch/head provenance, omitted dependencies, score or weight drift, multiple recommendations, executable fields, rerun authority, candidate promotion, knowledge writes, parked-ref actions, production/scheduler/ML work, and broader ranking behavior.

The recommendation requires a separate explicit human authorization before any live rerun. No source request was made for this checkpoint.
