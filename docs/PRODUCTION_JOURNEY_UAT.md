# KU Open Data Analytics — Production Journey UAT

This checklist validates the integrated six-step production journey on `integration/v62-shell-state` before PR #11 is merged.

## Preconditions

- Frontend is served from the integration branch or an equivalent local static server.
- Backend is API version `0.3.0` and exposes:
  - `GET /health`
  - `GET /capabilities`
  - `POST /analyze`
- `GET /health` returns `status=ok`.
- `GET /capabilities` returns `service.version=0.3.0` and route metadata for regression, binary/multiclass classification, clustering, association, and group comparison.
- Use `sample-data/uat-journey.csv` for route-level UAT. It is synthetic test data, not a benchmark dataset.

## Core journey

| Step | Navigation / action | Expected result |
|---|---|---|
| 1 Start | Import `sample-data/uat-journey.csv` | Dataset context appears; 30 rows and 8 fields are shown; Data Profile unlocks. |
| 2 Data Profile | Open Overview | Field structure, dataset KPIs, numeric exploration, and guidance render from the loaded dataset. |
| 2 Data Profile | Open Fields | Storage and measurement levels are editable; no analysis result is generated here. |
| 2 Data Profile | Open Data Quality | Missing/duplicate/constant checks use the loaded dataset and remain separate from relationship insights. |
| 2 Data Profile | Open Relationships | Scale↔Scale routes to Pearson/Spearman; categorical↔categorical to Chi-square + Cramér’s V; mixed types to group summary + η². |
| 3 Analyze | Continue to Analyze | Five question types are available; analytical family is derived rather than manually selected. |
| 4 Prepare | Continue from a complete Analysis Plan | Preparation Summary uses the actual target/predictors and route-specific preprocessing rules. |
| 5 Setup | Approve preparation | Recommended Setup loads from backend `/capabilities`; Technical Run Spec is collapsed by default. |
| 6 Results | Run Analysis | Only validated/computed payload values appear; answer is shown before technical details. |

## Route UAT

### Regression

1. Question Type: **Predict an outcome**.
2. Target: `spend`.
3. Keep **Use all suitable fields**.
4. Continue through Prepare and Setup.
5. Run Analysis.

Expected:
- Recommended family is Regression.
- Step 4 describes numeric/categorical preprocessing from the validated route.
- Step 5 reports XGBoost policy metadata from `/capabilities`.
- Step 6 includes MAE, RMSE, R², tail evidence, and validated warnings where returned.

### Binary Classification

1. Question Type: **Predict an outcome**.
2. Target: `churn`.
3. Continue through Prepare and Setup.
4. Run Analysis.

Expected:
- Recommended family is Binary Classification.
- Step 4 verifies both classes have at least five observations for the 5-fold validation design.
- Step 5 shows backend model/calibration/threshold policy.
- Step 6 shows classification evidence and a KU-colored confusion matrix when TN/FP/FN/TP are returned.

### Multiclass Classification

1. Question Type: **Predict an outcome**.
2. Target: `segment_label`.
3. Continue through Prepare and Setup.
4. Run Analysis.

Expected:
- Recommended family is Multiclass Classification.
- Step 4 shows three classes and allows Setup because each class has ten observations.
- Step 6 shows macro/weighted F1, balanced accuracy, multiclass ROC-AUC/log-loss evidence, coverage/abstention evidence where returned.

### Explain relationships / drivers

1. Question Type: **Explain relationships / drivers**.
2. Target: `spend` or `churn`.
3. Run the validated route.

Expected:
- Route is derived from target type.
- Step 6 elevates model-derived predictive feature importance as the driver answer.
- A warning states that predictive importance does not establish causal effects.

### Compare Groups

1. Question Type: **Compare groups**.
2. Target: `spend`.
3. In Step 4 choose grouping field `region`.
4. Continue through Setup and Run Analysis.

Expected:
- Step 4 shows complete observations by group and blocks any group with fewer than two complete observations.
- With three regions, backend method is one-way ANOVA.
- Step 6 shows p-value and η² plus a Group Summary table from the validated payload.

Optional two-group check: use a dataset/grouping field with exactly two observed groups; backend method should be Welch t-test and Step 6 should show mean difference/Hedges g when returned.

### Discover Segments

1. Question Type: **Discover segments**.
2. No target is requested.
3. Continue using suitable numeric fields.
4. Run Analysis.

Expected:
- Recommended family is Clustering / Segmentation.
- Step 4 reports median imputation, StandardScaler, PCA, then KMeans.
- Step 6 shows cluster validation evidence and **Segment Profiles** from the validated `findings` payload.

### Association Analysis

1. Question Type: **Discover association rules**.
2. No target is requested.
3. Run Analysis.

Expected:
- Recommended family is Association Analysis.
- Step 4 reports pairwise-complete handling.
- Step 6 shows supported relationship evidence, **Top Supported Associations**, and **Recommended Follow-up** when returned by the backend.

## Preflight guardrails

Use the built-in 9-row demo and choose `Group` as a multiclass prediction target.

Expected:
- Step 3 can still derive Multiclass Classification.
- Step 4 blocks Continue to Setup because the demo has fewer than five observations per class for 5-fold stratified validation.
- The blocker is presented before any API call.

For Compare Groups, a grouping field with any group containing fewer than two complete numeric outcome observations must also block Setup.

## State and regression checks

| Action | Expected result |
|---|---|
| Navigate backward/forward without changing the Analysis Plan | Target, route, predictors, preparation, setup, and validated result remain available as appropriate. |
| Change predictors only | Previous validated result is preserved; Prepare/Setup approval resets. |
| Open Results after predictor change | Result is labeled **Previous validated result** until rerun. |
| Change Question Type or Target | Previous validated result resets. |
| Change a field Measurement Level in Data Profile and return to Analyze | Route/predictors are re-derived from current metadata; downstream approval resets; preserved result is marked stale if it no longer matches. |
| Replace/clear dataset | Stale Analysis Plan and result are cleared. |
| Open an Advanced statistical tool | Advanced panel does not overlap the six-step Analyze page; returning to the journey keeps state coherent. |

## Responsive and accessibility checks

- Desktop: six-step sidebar is visible and no workflow content is covered by sticky elements.
- Tablet/narrow viewport: sidebar is replaced by the horizontal workflow control without overlap or truncation.
- Step 2 tabs can be changed with mouse/touch and with Left/Right/Home/End keyboard keys.
- Active Data Profile tab exposes `aria-selected=true`; inactive tab panels are hidden semantically.
- Current Analysis and load/status regions announce updates through polite live regions.
- Tables and technical payloads scroll horizontally/vertically instead of clipping content on narrow screens.

## Final regression before merge

- Frontend CI: JavaScript syntax, static smoke, and full journey DOM smoke all pass.
- Backend CI: compile and pytest all pass.
- PR remains Draft until manual visual UAT is completed.
- Do not merge or change the Render tracked branch solely to preview this integration without an explicit deployment decision.
