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
- The production frontend uses the configured analytics API base for both `/capabilities` and `/analyze`; the default is `https://ku-open-data-analytics-api.onrender.com`.
- Backend CORS allows the GitHub Pages origin `https://thanitpu.github.io` and the configured local development origins.
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
| 3 Analyze | Select only a target-required Question Type but do not select a target | Prepare remains locked; sidebar navigation cannot bypass the incomplete Analysis Plan. |
| 4 Prepare | Continue from a complete Analysis Plan | Preparation Summary uses actual target/predictors and shows **Automatically handled** and **Needs review** before field-level detail. |
| 4 Prepare | Resolve any review item and click **Approve Preparation →** | Preparation becomes approved and Setup opens. |
| 5 Setup | Review Recommended Setup | Backend policy comes from `/capabilities`; **Technical Run Specification** is collapsed by default and includes backend API version. |
| 5 Setup | Click **Run recommended analysis →** | The selected validated route executes; no prototype/example result is substituted. |
| 6 Results | Analysis completes | Only validated/computed payload values appear; answer is shown before technical details. |

## Route UAT

### Regression — continuous target

1. Question Type: **Predict an outcome**.
2. Target: `spend`.
3. Keep **Use all suitable fields**.
4. Continue through Prepare and Setup.
5. Run the recommended analysis.

Expected:
- Recommended family is Regression.
- Step 4 describes numeric/categorical preprocessing from the validated route.
- Step 5 reports XGBoost policy metadata from `/capabilities`.
- Step 6 includes MAE, RMSE, R², tail evidence, and validated warnings where returned.

### Regression — recognized ordinal target

Use the built-in 9-row demo.

1. Question Type: **Predict an outcome**.
2. Target: `Satisfaction`.
3. Confirm Data Profile treats `Satisfaction` as Ordinal.
4. Continue to Prepare.

Expected in Step 4:
- Recommended family remains Regression.
- **Automatically handled** includes `Encode ordered categories`.
- The plan shows `Low < Medium < High`.
- **Needs review = 0** and **Approve Preparation →** is enabled.

Expected after a backend run:
- Backend returns `method.target_encoding.type = ordinal_rank`.
- The mapping preserves semantic order, e.g. `Low=1`, `Medium=2`, `High=3`.
- Step 6 answer identifies the result as an **Ordinal rank-coded target**.
- Step 6 shows a **Target Coding** table and a visible warning that rank order is meaningful but equal spacing between adjacent categories is not established.

Recognized production ordinal sequences are intentionally conservative:
- `Low < Medium < High`
- `Poor < Fair < Good < Very Good < Excellent`
- `Strongly disagree < Disagree < Neutral < Agree < Strongly agree`

A subset of one of those sequences is supported when at least two levels are observed. Unknown text ordinal labels must **not** be silently alphabetically encoded; Step 4 must keep the run blocked for review.

### Binary Classification

1. Question Type: **Predict an outcome**.
2. Target: `churn`.
3. Continue through Prepare and Setup.
4. Run the recommended analysis.

Expected:
- Recommended family is Binary Classification.
- Step 4 verifies both classes have at least five observations for the 5-fold validation design.
- Step 5 shows backend model/calibration/threshold policy.
- Step 6 shows classification evidence and a KU-colored confusion matrix when TN/FP/FN/TP are returned.

### Multiclass Classification

1. Question Type: **Predict an outcome**.
2. Target: `segment_label`.
3. Continue through Prepare and Setup.
4. Run the recommended analysis.

Expected:
- Recommended family is Multiclass Classification.
- Step 4 shows three classes and allows approval because each class has ten observations.
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
4. Confirm **Needs review = 0**, click **Approve Preparation →**, then run the recommended analysis.

Expected:
- Step 4 shows complete observations by group and blocks any group with fewer than two complete observations.
- With three regions, backend method is one-way ANOVA.
- Step 6 shows p-value and η² plus a Group Summary table from the validated payload.

Optional two-group check: use a dataset/grouping field with exactly two observed groups; backend method should be Welch t-test and Step 6 should show mean difference/Hedges g when returned.

### Discover Segments

1. Question Type: **Discover segments**.
2. No target is requested.
3. Continue using suitable numeric fields.
4. Run the recommended analysis.

Expected:
- Recommended family is Clustering / Segmentation.
- Step 4 reports median imputation, StandardScaler, PCA, then KMeans.
- Step 6 shows cluster validation evidence and **Segment Profiles** from the validated `findings` payload.

### Association Analysis

1. Question Type: **Discover association rules**.
2. No target is requested.
3. Run the recommended analysis.

Expected:
- Recommended family is Association Analysis.
- Step 4 reports pairwise-complete handling.
- Step 6 shows supported relationship evidence, **Top Supported Associations**, and **Recommended Follow-up** when returned by the backend.

## Preflight guardrails

Use the built-in 9-row demo and choose `Group` as a multiclass prediction target.

Expected:
- Step 3 can still derive Multiclass Classification.
- Step 4 shows the issue under **Needs review** and disables **Approve Preparation →** because the demo has fewer than five observations per class for 5-fold stratified validation.
- The blocker is presented before any API call.

For Compare Groups, a grouping field with any group containing fewer than two complete numeric outcome observations must also block approval.

For Regression, an unrecognized non-numeric ordinal/text target must remain blocked rather than receiving an inferred alphabetical numeric order.

## API and deployment-boundary checks

| Check | Expected result |
|---|---|
| Open Step 5 from GitHub Pages | `/capabilities` is requested from the configured analytics API base, not the GitHub Pages origin. |
| Run a validated analysis | `/analyze` uses the same configured analytics API base as `/capabilities`. |
| Inspect Technical Run Specification | Backend API version is shown after expanding the collapsed details. |
| Send a CORS preflight with Origin `https://thanitpu.github.io` | Backend permits the configured GitHub Pages origin. |
| Override `window.KU_ANALYTICS_API_BASE` before `src/ai-analytics.js` loads | Both Setup capability metadata and analysis execution use that override. |

## State and regression checks

| Action | Expected result |
|---|---|
| Navigate backward/forward without changing the Analysis Plan | Target, route, predictors, preparation, setup, and validated result remain available as appropriate. |
| Select a target-required Question Type without selecting a target | Prepare remains disabled because no executable route has been derived. |
| Change predictors only | Previous validated result is preserved; Prepare/Setup approval resets. |
| Open Results after predictor change | Result is labeled **Previous validated result** until rerun. |
| Change Question Type or Target | Previous validated result resets. |
| Change a field Measurement Level in Data Profile and return to Analyze | Route/predictors are re-derived from current metadata; downstream approval resets; preserved result is marked stale if it no longer matches. |
| Replace/clear dataset | Stale Analysis Plan and result are cleared. |
| Open an Advanced statistical tool on desktop | Advanced panel does not overlap the six-step Analyze page; returning to the journey keeps state coherent. |

## Responsive and accessibility checks

- Desktop (>1050px): six-step sidebar and optional Advanced statistical tools are available; workflow content is not covered by sticky elements.
- Tablet/narrow viewport (≤1050px): the journey becomes a horizontal workflow control and the Advanced statistical tools drawer is hidden to keep the production journey primary.
- Mobile 390px: page-level horizontal overflow must not occur. Wide preview/detail tables scroll inside their own containers rather than widening the document.
- Step 2 tabs can be changed with mouse/touch and with Left/Right/Home/End keyboard keys.
- Active Data Profile tab exposes `aria-selected=true`; inactive tab panels are hidden semantically.
- Current Analysis and load/status regions announce updates through polite live regions.
- Tables and technical payloads scroll horizontally/vertically instead of clipping page content on narrow screens.

## Automated browser visual regression

Frontend CI runs Playwright Chromium against a local static preview of the integration branch at:

- Desktop: 1440 × 900
- Tablet: 900 × 1000
- Mobile: 390 × 844

The browser smoke test validates:

- Start → Data Profile → Analyze → Prepare → Setup → Results in a real browser.
- Sidebar/horizontal journey behavior at the correct responsive breakpoint.
- No page-level horizontal overflow at each captured journey state.
- No browser `pageerror`, application console error, or unexpected HTTP 4xx/5xx from repository assets.
- `/capabilities` and `/analyze` mocks match the production Render API host, so a regression back to the local/GitHub Pages origin fails the browser smoke instead of being hidden by a wildcard mock.
- **Technical Run Specification** is collapsed by default; the browser test expands it and verifies backend version metadata.
- Screenshots for all six journey states at all three viewports are uploaded as the `ku-open-da-visual-uat` GitHub Actions artifact.

Frontend CI also runs a dedicated Ordinal target DOM smoke covering demo `Satisfaction` → Regression → recognized rank coding → Step 4 approval → Step 6 Target Coding/guardrail rendering.

Backend CI covers compile + pytest, including API/CORS contracts, Compare Groups, feature-importance extraction, and recognized/unknown ordinal-target behavior.

## Final regression before merge

- Frontend CI: JavaScript syntax, static smoke, full journey DOM smoke, Ordinal target DOM smoke, and responsive Chromium visual smoke all pass.
- Backend CI: compile and pytest all pass.
- Review the latest `ku-open-da-visual-uat` screenshots for desktop/tablet/mobile before marking PR #11 ready for review.
- PR remains Draft until manual visual/UAT acceptance.
- Do not merge or change the Render tracked branch solely to preview this integration without an explicit deployment decision.
