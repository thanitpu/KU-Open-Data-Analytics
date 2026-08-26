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

The Product consumes the same Profile Manifest computation for four additional Data Profile views:

- **Distribution** — distribution shape, skewness, kurtosis, quartiles and local histogram summaries
- **Outliers** — IQR and MAD robust outlier signals by numeric field
- **Categorical** — top-frequency summaries, dominance, rare levels and normalized entropy
- **Temporal** — shown only when a usable temporal field is detected; reports date coverage, granularity and interval regularity

These views are computed in the browser. They do not require the analytics API. `KUProfileInsights.getManifest()` exposes the current aggregate manifest for later intelligence calls without attaching raw rows.

The current Temporal view profiles the **time axis itself**. Numeric trend, seasonality, autocorrelation, lag and rolling-pattern screening remain a later browser-computation extension because those require pairing a time field with one or more measures rather than profiling the date field alone.

## Step 3 profile-aware method selection

Step 3 preserves the question-first flow and derived analytical family, then adds:

- a recommended method
- an **OR — Choose your method(s)** path
- filtering by question type, target kind, usable predictors and Profile Manifest signals
- execution labels distinguishing `Local · Browser` from `KU Validated Engine`

`methodMode` and `selectedMethods` are stored in the authoritative Analysis Plan. Question/target changes reset method selection. Explicit method changes invalidate downstream preparation/setup and prior results. Custom multi-method execution is not yet coordinated end to end; the current slice establishes selection and state only.

## FE recommendation contract

`POST /recommend/feature-engineering`

Input: Profile Manifest v1 plus optional `reference_date`.

The Step 4 request includes the analytical objective and current method selection as well as all field names and their aggregate profiles. Each field is marked as target, selected predictor, or context. Context fields may help domain inference, but the rule-based recommender does not silently derive features from fields excluded from the current analysis.

Output: structured recommendations only. The backend never returns arbitrary JavaScript/Python code. Every recommendation names a browser operation from an allowlist, source fields, derived output field, parameters, reason, evidence basis, confidence, and review requirement.

Initial rule-based operations:

- `reference_year_minus`
- `date_difference`
- `extract_month`
- `extract_day_of_week`
- `log1p`
- `row_sum`
- `group_rare_categories`

## Step 4 Feature Engineering Intelligence review

Step 4 now requests FE recommendations from KU Analytical Intelligence using only the aggregated Profile Manifest. The review panel:

- states that field names and aggregate distribution/frequency summaries are sent while raw rows remain local
- shows the inferred domain hint
- presents each suggested derived feature with source fields, operation, reason, evidence basis and confidence
- defaults recommendations to selected but requires explicit confirmation before Preparation can be approved
- supports select all, clear all, edit and reconfirm
- stores the reviewed recommendation payload and selected recommendation IDs in the Preparation Plan
- handles service errors with Retry or an explicit **Continue without FE recommendations** path
- automatically marks the review complete when no additional derived features are recommended

This slice is **review only**. Selected recommendations are not yet executed and do not yet enter the analytical matrix. Browser FE execution and feature lineage are the next implementation slice.

## UX note — contextual parameter help

Add a small **`?` help control** next to statistical parameters, diagnostics and technical terms so users can click to read a concise explanation without leaving the current step. This should be applied consistently across Data Profile, Analyze, Prepare, Setup and Results where parameters such as skewness, kurtosis, IQR, MAD, entropy, p-value, effect size, calibration and model metrics appear.

The help content should explain, at minimum:

- what the parameter measures
- how to interpret higher/lower or positive/negative values when relevant
- common rule-of-thumb ranges only when statistically defensible
- important cautions or assumptions
- why the parameter matters for the current analytical decision

This is intentionally deferred so contextual help can be designed once and reused consistently across the whole Product rather than added piecemeal.

## Current scope

The foundation now covers Profile Manifest, visible Step 2 profile intelligence, Step 3 method selection, the rule-based FE intelligence contract, and Step 4 FE recommendation review. It does **not** yet:

- execute approved FE in the browser
- add derived fields to the predictor pool / analytical matrix
- coordinate end-to-end execution for arbitrary custom multi-method selections
- perform numeric trend/seasonality/autocorrelation screening in the Temporal view
- add reusable `?` contextual parameter help across analytical screens
- use Kaggle/RAG knowledge
- provide a Knowledge Admin UI

## Next implementation slices

1. Build the trusted browser FE executor + feature lineage; approved derived fields become real predictors and enter the analytical matrix.
2. Move deterministic preparation/FE computation to the browser while keeping backend validation of the manifest/policy boundary.
3. Coordinate execution and combined Results for compatible selected browser/backend methods.
4. Extend Temporal profiling with local trend, seasonality, autocorrelation, lag and rolling-pattern screening where a usable time field and numeric measures coexist.
5. Add a reusable contextual-help component and parameter glossary for the `?` controls across Data Profile / Analyze / Prepare / Setup / Results.
6. Add curated Kaggle knowledge ingestion and hybrid retrieval after the recommendation schema stabilizes.
7. Build internal Knowledge Admin UI only after the knowledge schema and evaluation workflow are stable.

## UAT focus for Step 4 FE review

1. Load a dataset and define a valid analytical question in Step 3.
2. Continue to **Step 4 · Prepare** and confirm the Feature Engineering Recommendations panel appears below Preparation Summary.
3. Confirm the panel explains that only Profile Manifest metadata, field names and aggregate distribution/frequency summaries are sent; raw rows are not sent.
4. When recommendations are returned, review the suggested output feature, source fields, operation, reason, basis and confidence.
5. Before confirming FE choices, **Approve Preparation** remains disabled unless the backend returns no recommendations.
6. Select/clear recommendations and click **Confirm feature choices**; approval becomes available when no other preparation blocker exists.
7. Click **Edit feature choices**; approval becomes blocked again until reconfirmed.
8. Existing group-comparison setup and route-specific preparation blockers must remain authoritative.
9. When the recommendation service is unavailable, Retry and explicit Continue-without-FE paths must work.
10. Remember: approved FE is stored only as a reviewed plan in this slice. Derived columns are not created or sent into ML until the browser FE executor slice.
