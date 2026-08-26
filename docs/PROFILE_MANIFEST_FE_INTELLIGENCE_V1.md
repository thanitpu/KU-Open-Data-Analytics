# Profile Manifest + Feature Engineering Intelligence v1

## Architecture principle

KU Open DA performs deterministic statistical computation in the browser whenever practical. The backend is reserved for analytical intelligence, validated model policy, model execution/validation, and evidence synthesis.

## Profile Manifest v1

The browser creates an aggregated manifest from the loaded dataset. It contains:

- analysis objective and target metadata
- overall rows, fields, missingness, duplicate count
- field name, role, storage type, measurement level
- numeric distribution summaries, histogram bins, skewness, kurtosis, IQR/MAD outlier signals
- categorical top-frequency summaries, dominance, rare-level concentration, entropy
- temporal detection, date range, interval/granularity summary
- privacy flags

Raw dataset rows are not part of the manifest. High-cardinality identifier-like or sensitive-like categorical fields suppress raw frequency values.

## FE recommendation contract

`POST /recommend/feature-engineering`

Input: Profile Manifest v1 plus optional `reference_date`.

Output: structured recommendations only. The backend never returns arbitrary JavaScript/Python code. Every recommendation names a browser operation from an allowlist, source fields, derived output field, parameters, reason, evidence basis, confidence, and review requirement.

Initial rule-based operations:

- `reference_year_minus`
- `date_difference`
- `extract_month`
- `extract_day_of_week`
- `log1p`
- `row_sum`
- `group_rare_categories`

## Current scope

This first slice establishes Phase A/B and a minimal Phase C rule-based recommender. It does **not** yet:

- change the Step 2 visible tabs
- execute FE in the browser
- add derived fields to the predictor pool
- use Kaggle/RAG knowledge
- provide a Knowledge Admin UI

## Next implementation slices

1. Wire Profile Manifest generation into the live Product state and add Distribution / Outliers / Categorical / Temporal views to Step 2.
2. Add Step 3 suitable-method selection while preserving the recommended family.
3. Add Step 4 call to the FE recommender and review UI.
4. Build the trusted browser FE executor + feature lineage; derived fields become real predictors.
5. Add curated Kaggle knowledge ingestion and hybrid retrieval after the recommendation schema stabilizes.
6. Build internal Knowledge Admin UI only after the knowledge schema and evaluation workflow are stable.

## UAT focus for this slice

This slice is intentionally non-visible in the Product UI. Regression checks are automated: existing Product journey must remain unchanged; frontend Profile Manifest smoke and backend FE recommendation tests must pass before any UI wiring begins.
