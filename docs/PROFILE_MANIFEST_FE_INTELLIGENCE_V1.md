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

## Step 2 browser profile views

The live Product now consumes the same Profile Manifest computation for four additional Data Profile views:

- **Distribution** — distribution shape, skewness, kurtosis, quartiles and local histogram summaries
- **Outliers** — IQR and MAD robust outlier signals by numeric field
- **Categorical** — top-frequency summaries, dominance, rare levels and normalized entropy
- **Temporal** — shown only when a usable temporal field is detected; reports date coverage, granularity and interval regularity

These views are computed in the browser. They do not require the analytics API. `KUProfileInsights.getManifest()` exposes the current aggregate manifest for later Step 4 intelligence calls without attaching raw rows.

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

The foundation now covers Phase A/B, a minimal Phase C rule-based recommender, and the visible Step 2 profile-insight slice. It does **not** yet:

- execute FE in the browser
- add derived fields to the predictor pool
- add Step 3 method selection
- call the FE recommender from Step 4
- use Kaggle/RAG knowledge
- provide a Knowledge Admin UI

## Next implementation slices

1. Add Step 3 suitable-method selection while preserving the recommended analytical family.
2. Add Step 4 call to the FE recommender and review UI.
3. Build the trusted browser FE executor + feature lineage; derived fields become real predictors.
4. Move deterministic preparation/FE computation to the browser while keeping backend validation of the manifest/policy boundary.
5. Add curated Kaggle knowledge ingestion and hybrid retrieval after the recommendation schema stabilizes.
6. Build internal Knowledge Admin UI only after the knowledge schema and evaluation workflow are stable.

## UAT focus for the Step 2 slice

1. Load a dataset, then open **Step 2 · Data Profile**.
2. Confirm tabs are ordered as Overview, Fields, Data Quality, Distribution, Outliers, Categorical, Relationships, plus Temporal when a temporal field is detected.
3. Distribution must show field-specific shape metrics and histogram summaries.
4. Outliers must show IQR and MAD signals without describing outliers as automatic errors.
5. Categorical must show frequency structure; identifier/sensitive-like values remain redacted from the manifest.
6. Temporal must appear only for datasets with a detected date/time field and show coverage/granularity/regularity.
7. Key regression checks: Start→Profile→Analyze still works; existing Relationships still works; no page-level horizontal overflow; no raw row array is present in `KUProfileInsights.getManifest()`.
