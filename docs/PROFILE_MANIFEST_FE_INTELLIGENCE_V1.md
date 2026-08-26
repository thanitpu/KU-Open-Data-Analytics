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

These views are computed in the browser. They do not require the analytics API. `KUProfileInsights.getManifest()` exposes the current aggregate manifest for later Step 4 intelligence calls without attaching raw rows.

The current Temporal view profiles the **time axis itself**. Numeric trend, seasonality, autocorrelation, lag and rolling-pattern screening remain a later browser-computation extension because those require pairing a time field with one or more measures rather than profiling the date field alone.

## Step 3 profile-aware method selection

Analyze keeps the question-first flow:

1. **What do you want to learn?**
2. **Select the target / outcome** when required.
3. **Recommended analytical family** remains derived automatically.

Within the third panel, the Product now adds a method layer:

- **Recommended method** — the current validated default for the derived route.
- **OR — Choose your method(s)** — exposes only methods compatible with the question type, target type, available predictors and current Profile Manifest.
- Every method is labelled **Local · Browser** or **KU Validated Engine** so execution responsibility is transparent.
- Profile signals can add method-specific cautions, for example recommending robustness review when the target is strongly skewed or has notable outlier signals.

The current method catalog covers:

- XGBoost Regression / Binary / Multiclass on the validated backend
- Linear Regression (OLS) locally in the browser
- Pearson and Spearman correlation as local supporting methods for Explain Drivers
- Validated Group Comparison plus local Welch t-test / One-way ANOVA candidates
- K-means Segmentation on the validated backend
- Mixed-Type Association Screening on the validated backend

Method choice is persisted in the Analysis Plan through `methodMode` and `selectedMethods`. Switching question type or target resets method selection to the recommended mode. Explicit method-selection changes invalidate downstream preparation/setup and the previous result because the planned execution has changed. Metadata-only route re-derivation still preserves the previous validated result for stale-result comparison.

This slice establishes **selection, suitability filtering and state**. Full execution of arbitrary custom multi-method selections is intentionally deferred until Step 4 can validate method-specific preparation and the browser execution coordinator is available.

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

The branch now covers Phase A/B, a minimal Phase C rule-based FE recommender, visible Step 2 profile insights, and Step 3 profile-aware method selection. It does **not** yet:

- execute FE in the browser
- add derived fields to the predictor pool
- call the FE recommender from Step 4
- validate and execute arbitrary custom multi-method selections end-to-end
- perform numeric trend/seasonality/autocorrelation screening in the Temporal view
- add reusable `?` contextual parameter help across analytical screens
- use Kaggle/RAG knowledge
- provide a Knowledge Admin UI

## Next implementation slices

1. Add Step 4 call to the FE recommender and review UI, including method-specific preparation requirements.
2. Build the trusted browser FE executor + feature lineage; derived fields become real predictors.
3. Move deterministic preparation/FE computation to the browser while keeping backend validation of the manifest/policy boundary.
4. Add execution coordination for selected local/backend methods and combined Results when multiple methods are requested.
5. Extend Temporal profiling with local trend, seasonality, autocorrelation, lag and rolling-pattern screening where a usable time field and numeric measures coexist.
6. Add a reusable contextual-help component and parameter glossary for the `?` controls across Data Profile / Analyze / Prepare / Setup / Results.
7. Add curated Kaggle knowledge ingestion and hybrid retrieval after the recommendation schema stabilizes.
8. Build internal Knowledge Admin UI only after the knowledge schema and evaluation workflow are stable.

## UAT focus — Step 2

1. Load a dataset, then open **Step 2 · Data Profile**.
2. Confirm tabs are ordered as Overview, Fields, Data Quality, Distribution, Outliers, Categorical, Relationships, plus Temporal when a temporal field is detected.
3. Distribution must show field-specific shape metrics and histogram summaries.
4. Outliers must show IQR and MAD signals without describing outliers as automatic errors.
5. Categorical must show frequency structure; identifier/sensitive-like values remain redacted from the manifest.
6. Temporal must appear only for datasets with a detected date/time field and show coverage/granularity/regularity.
7. Key regression checks: Start→Profile→Analyze still works; existing Relationships still works; no page-level horizontal overflow; no raw row array is present in `KUProfileInsights.getManifest()`.

## UAT focus — Step 3 method selection

1. Choose **Predict an outcome** with a continuous target. The existing Recommended analytical family must remain visible, followed by **Recommended method**, an **OR** divider, and **Choose your method(s)**.
2. The recommended route should show **XGBoost Regression · KU Validated Engine**. When numeric predictors are available, **Linear Regression (OLS) · Local · Browser** should also be offered.
3. Switch to **Choose methods**. Continue to Prepare must remain disabled until at least one compatible method is selected.
4. For **Explain relationships / drivers** with a continuous target, suitable choices should include XGBoost Regression, OLS, Pearson and Spearman when numeric predictors are available.
5. Binary / multiclass targets must not expose incompatible regression methods.
6. **Compare groups** should expose Validated Group Comparison plus local Welch t-test and One-way ANOVA candidates, with their group-count conditions clearly stated.
7. **Discover segments** should expose K-means Segmentation; **Discover association rules** currently maps to Mixed-Type Association Screening.
8. Changing the question type or target must reset custom method choices to Recommended.
9. Regression checks: Step 1→2→3→4 remains navigable, stale-result behavior after metadata-only changes is preserved, responsive shell behavior remains unchanged, and there is no page-level horizontal overflow.
