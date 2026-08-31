# KU2D Branch and PR Governance v1

This checkpoint turns the accepted read-only branch inventory into a durable, storage-neutral governance contract. It records evidence and recommended dispositions; it does not delete, close, merge, promote, or mutate any branch or PR.

## Current evidence snapshot

The register was finalized at `2026-08-31T13:08:02+07:00` after fresh remote-ref and GitHub PR checks and creation of Draft PR #47. Unchanged historical branch records retain their earlier per-record observation time; no branch evidence may be newer than the top-level snapshot. The authoritative base is integration squash commit `d497f1b8311e2f7ec410dd1b52735c31befa3d5d`.

| Group | Count | Meaning |
|---|---:|---|
| Remote `codex/*` branches | 25 | Every remote branch present in the refreshed snapshot |
| Active | 1 | `codex/ku2d-branch-governance-v1` only |
| Parked, unreviewed | 8 | Open Draft PRs with unique unmerged work; deletion prohibited |
| Safe-to-delete candidates | 16 | Closed merged PRs with zero-file tree differences against their squash results; advisory only |
| Merged historical / parked reviewed / needs review / superseded | 0 | No current branch requires these dispositions |
| Candidate Learning Evidence records | 11 | Candidate-only projections across six parked branches; none promoted |
| Branch deletions | 0 | Deletion requires a later explicit human-approved action |

The active branch is not a cleanup candidate. Its recorded head is the implementation head used to create Draft PR #47; publishing this registry and later coordination records necessarily advance that same active branch, so exact fresh-head reconciliation applies to every non-active branch while the active record remains explicitly non-deletable. Callers can pass freshly fetched head/PR maps to the pure validator so historical or parked ref drift, missing branches, and PR-state changes fail closed.

## Parked unique work

Candidate projection is not review, merge, promotion, or lossless preservation of the branch tree. All eight branches remain non-deletable.

| Review priority | Branch / PR | Pattern or capability | Durable representation | Required next review |
|---:|---|---|---|---|
| 1 | `overnight-marketplace-source-inventory` / #37 | Marketplace source and access-pattern inventory | Candidate Learning Evidence only (`CLE-000002`, `CLE-000003`) | Review access-pattern claims and bounded Deep Audit priority; do not promote a source |
| 2 | `overnight-ota-source-expansion` / #38 | OTA access-boundary classification | Candidate Learning Evidence only (`CLE-000004`, `CLE-000005`) | Review boundary evidence before technique-transfer conclusions |
| 3 | `overnight-qdiving-source-expansion` / #40 | Content, service-price, and retail-price separation across surfaces | Candidate Learning Evidence only (`CLE-000008`–`000010`) | Review role separation and provenance |
| 4 | `overnight-coffee-source-expansion` / #39 | Official detail pattern and product/menu price roles | Candidate Learning Evidence only (`CLE-000006`, `CLE-000007`) | Review official-detail evidence and distinct price contexts |
| 5 | `overnight-tiktok-shop-commerce-pulse-explore` / #36 | Traffic-verification / required-login stop boundary | Candidate Learning Evidence only (`CLE-000001`) | Review negative boundary evidence without inferring extraction failure |
| 6 | `overnight-cross-domain-source-gap-scan` / #41 | Unresolved-track and source-gap inventory | Candidate Learning Evidence only (`CLE-000011`), not lossless branch preservation | Review gap claims before synthesis |
| 7 | `overnight-acquisition-technique-transfer-matrix` / #42 | Cross-domain technique-transfer synthesis | Nowhere durable outside its Draft PR/branch | Review after #36–#41 |
| 8 | `overnight-exploration-summary` / #43 | Cross-exploration synthesis and sequencing | Nowhere durable outside its Draft PR/branch | Review last, after all dependencies |

The ordering emphasizes reusable patterns, evidence dependencies, and loss risk—not brand popularity. It does not perform the reviews or authorize promotion.

## Advisory cleanup candidates

Each candidate below has a closed merged PR, an identified squash commit, and a refreshed `git diff --name-only <retained-head> <squash>` result of zero files:

- JIB lifecycle and durable validation: `data-acquisition-agent` (#23), `jib-validation-knowledge` (#24).
- Retail policy: `retail-enrichment-policy-fix` (#25).
- YouTube foundation and reviewed pilot learning: `youtube-source-foundation` (#26), `youtube-human-review-equipment` (#27), `youtube-equipment-pilot-learning` (#28).
- Shopee foundation and bounded Edge orchestration: `shopee-commerce-pulse-explore` (#29), `shopee-edge-access-experiment` (#30), `wire-shopee-edge-runner` (#31), `promote-shopee-edge-workflow` (#32).
- Lazada foundation and rendered-DOM review: `lazada-commerce-pulse-explore` (#33), `lazada-browser-access-experiment` (#34), `lazada-rendered-dom-deep-audit` (#35).
- KU2D knowledge foundations: `ku2d-learning-memory-v1` (#44), `ku2d-core-knowledge-backfill-v1` (#45), `ku2d-core-intelligence-v1` (#46).

`SAFE_TO_DELETE_CANDIDATE` is evidence, not permission. A later human-approved cleanup action must re-fetch the branch, re-check PR state and tree equivalence, check external workflow/operator branch-name dependencies, and name every deletion target explicitly. This PR contains no deletion command, bulk cleanup, automatic mutation, or branch action.

## Validator contract

`acquisition/branch_pr_governance.py` is a pure validator. It rejects:

- contradictory open/closed/draft/merged PR states;
- duplicate or missing branch/PR identity;
- a safe-delete advisory without a closed merged PR and exact zero-file tree proof;
- active or parked-unreviewed branches marked deletable;
- parked-unreviewed branches marked reviewed;
- Candidate Learning Evidence represented as integrated, Reviewed Learning Corpus, or Core Knowledge;
- missing provenance, timestamps, unique-work warnings, summary reconciliation, or review priority;
- stale head/PR evidence when fresh expected maps are supplied;
- executable cleanup/deletion fields or any runtime, production, scheduling, live-request, or ML side effect.

The validator performs no filesystem, git, network, database, acquisition, or runtime write. Normal acquisition runtime does not import it.

## Preserved boundaries

This governance layer adds no acquisition source and makes no live request. It does not alter Core Intelligence Quality Foundation, Learning Memory, Reviewed Learning Corpus, Core Knowledge, Candidate Learning Evidence, Human Confirmation, production approval, storage, scheduler, privacy, or ML state. Survey, Google Forms, DoE, bias analysis, SEM, broader Core Intelligence recommendation/ranking, and candidate promotion remain out of scope.
