# KU Open Data Analytics

KU Open Data Analytics combines a public university-facing Landing Page with a browser-first analytical workspace backed by validated FastAPI execution.

The canonical repository is `thanitpu/KU2A-Analytics`. **KU Open Data Analytics** remains the user-facing product name; the repository rename does not rename the product or its existing Render API service. Repository-cutover and cross-repository handoff rules are recorded in `docs/KU2A_REPOSITORY_RENAME_CUTOVER.md`.

The Product experience follows one six-step journey:

1. **Start** — choose or upload a CSV/XLSX dataset, or inspect one or more compatible KU2D trusted JSON assets.
2. **Data Profile** — review field structure, measurement levels, data quality, and mixed-type relationships.
3. **Analyze** — define the analytical question; KU Open DA derives the analytical family from the question and target.
4. **Prepare** — review route-specific preparation using the actual selected fields.
5. **Setup** — confirm the validated backend run specification and policy metadata.
6. **Results** — read the answer first, then inspect evidence, family-specific findings, warnings, and technical payload.

The browser also retains optional classical statistical tools for focused exploration. They are secondary to the production journey.

## KU2D intake and text analytics

The Product provides a separate **Use Data from KU2D** path for `trusted-data-asset-v1` JSON. It validates contract version, approval status, compatible schemas, counts, identities, provenance, and acquisition/effective timestamps. Draft assets can be inspected, but remain explicitly non-production-approved. Multi-snapshot rows retain `data_asset_id` lineage and keep acquisition time separate from effective time.

Text Analytics is progressively disclosed across the existing journey: text profile and terms/phrases in Data Profile; supervised baseline sentiment, topic discovery, Topic × Sentiment, and disclosed retrieval in Analyze; human topic curation in Prepare; configuration disclosure in Setup; and evidence/derived-feature exports in Results. Browser retrieval is labelled as lexical fallback. Backend semantic routes use a versioned engine and identify LSA fallback as non-transformer output.

KU2D continues to own discovery, audit, approval, acquisition, monitoring, provenance, and repository storage. KU2A does not import credentials, crawlers, production scheduling, or KU2B operational inference. See `docs/KU2A_TEXT_ANALYTICS_MIGRATION_REGISTER.md` and `docs/KU2A_TEXT_ANALYTICS_UAT.md`.

## Validated analytical routes

FastAPI currently exposes validated Fast mode for:

- Binary Classification
- Multiclass Classification
- Regression
- Customer Segmentation / Clustering
- Association Analysis
- Compare Groups — Welch t-test for two observed groups and one-way ANOVA for three or more groups
- Exploratory Data Analysis through the backend orchestrator

Supervised model results can include model-derived predictive feature importance. These importance values are predictive evidence and must not be interpreted as causal effects.

### Ordinal targets in Regression

Question-first routing treats a target marked **Ordinal** as a Regression target. Numeric ordinal targets run directly. A text ordinal target is executable only when its observed labels match a supported semantic sequence; the backend rank-encodes the observed levels while preserving that order.

Currently recognized sequences are:

- `Low < Medium < High`
- `Poor < Fair < Good < Very Good < Excellent`
- `Strongly disagree < Disagree < Neutral < Agree < Strongly agree`

A subset of one of these sequences is supported when at least two levels are observed. Unknown text ordinal labels are not silently alphabetically encoded; Step 4 keeps them blocked for review instead.

When rank coding is used, Step 6 identifies the target as ordinal rank-coded, shows the category-to-rank mapping, and warns that rank order does not establish equal spacing between adjacent categories.

## Frontend

The static frontend is compatible with repository-path GitHub Pages hosting.

### Final entry architecture

- `index.html` → Public Landing Page
- `app.html` → Functional KU Open Data Analytics workspace

The Public Landing owns only `src/landing*` and `assets/landing/*`; it does not import Product analytical JS/CSS and does not call FastAPI. Its primary **Start analyzing** CTA uses the relative target `app.html`.

The Product entry remains `app.html`. Data loading, profiling, field metadata review, and browser statistical exploration stay local to the browser. A dataset is sent to the configured analytics API only when the user explicitly runs a validated analysis.

The Product header includes a persistent text-size control with `A`, `A+`, and `A++`. `A+` is the default comfortable size. The selected size is stored in browser local storage and is applied to dense analytical copy and controls without changing the Landing design.

Product runtime code must not hard-code `index.html` or root-absolute redirects. Product and Landing local assets use relative repository paths so both entries remain compatible with GitHub Pages project-path hosting.

`tests/frontend_entry_guard.js` enforces Public/Product separation. `tests/landing_smoke.js` validates the Public layer. Functional JSDOM and browser tests continue to target `app.html`. `tests/public_product_visual_smoke.js` verifies the real browser contract `index.html → app.html` at desktop, tablet, and mobile sizes. `tests/ui_preferences_smoke.js` validates the text-size control and preference persistence.

Architecture/workstream boundaries are recorded in `docs/ADR-frontend-public-landing-app-entry.md`; handoff and migration history are in `docs/LANDING_INTEGRATION_HANDOFF.md`, `docs/FUNCTIONAL_APP_HANDOFF.md`, and `docs/APP_ENTRY_MIGRATION_UAT.md`.

## Backend

The FastAPI service lives under `backend/` and currently reports API version `0.3.0`.

Local run from the repository root:

    pip install -r backend/requirements.txt
    uvicorn app.api:app --app-dir backend --host 127.0.0.1 --port 8001

Health check:

    GET /health

Execution capability metadata:

    GET /capabilities

Validated analysis endpoint:

    POST /analyze

`POST /analyze` accepts a CSV upload plus `intent`, optional `target`, `mode=fast`, and optional `options_json`. Compare Groups uses `options_json` to pass the reviewed grouping field.

`GET /capabilities` is the frontend source for Step 5 Recommended Setup. It exposes the validated route policy, preparation behavior, validation design, returned metrics, service version, and supported ordinal-target sequences instead of duplicating those settings in the frontend.

## Render deployment and API boundary

A `render.yaml` Blueprint is included at the repository root. It deploys the backend from `backend/`, installs `backend/requirements.txt`, starts:

    uvicorn app.api:app --host 0.0.0.0 --port $PORT

and uses `/health` for the service health check.

The Product resolves its analytics API base by environment:

- when opened from `localhost` or `127.0.0.1` → `http://127.0.0.1:8001` for Manual UAT/local development;
- on GitHub Pages/other non-local origins → `https://ku-open-data-analytics-api.onrender.com`;
- an explicit `window.KU_ANALYTICS_API_BASE` set before `src/ai-analytics.js` loads overrides either default.

Both Step 5 `/capabilities` and Step 5/6 analysis execution through `/analyze` use the same resolved API base.

The backend CORS policy is configured through `CORS_ORIGINS`. The default configuration allows:

- `https://thanitpu.github.io`
- `http://localhost:8000`
- `http://127.0.0.1:8000`

For Manual Combined UAT on Windows, `tools/start-manual-uat.bat` checks/install backend dependencies if needed, starts the local FastAPI on port `8001`, starts the Public/Product web server on port `8000`, and opens the Public Landing. This lets the branch backend be tested before any Render deployment.

Backend tests include a GitHub Pages CORS preflight contract. Frontend browser smoke explicitly overrides the API base to the mocked production Render host so CI remains deterministic and does not depend on a live local or deployed backend.

Render Blueprint `autoDeploy` is enabled, but the branch tracked by an existing Render service is controlled by the Render service configuration. Production deployment should therefore remain aligned with the reviewed/merged GitHub branch.

## State and result freshness

The Analysis Plan is authoritative across Steps 3–6. Changing Question Type or Target invalidates the validated result. Predictor changes preserve the previous result for comparison but invalidate downstream preparation/setup approval; Step 6 labels the preserved output as a previous validated result when it no longer matches the Current Analysis.

Storage/measurement metadata for the selected target and predictors is snapshotted with each validated result. A metadata edit immediately invalidates Prepare/Setup approval and preserves the previous result only for comparison. Step 6 marks that result stale even when the derived analytical route stays the same, for example an Ordinal → Scale edit that still routes to Regression.

Each newly loaded browser dataset receives a monotonic dataset revision when the loader replaces the in-memory data array. A genuinely new file/dataset therefore clears the Analysis Plan and result even when it has the same row count, schema, storage types, and measurement levels as the prior dataset. Metadata-only edits do not advance the dataset revision.

Dataset replacement/clear resets stale plan/result state reliably. Prepare requires a derived route, Setup requires approved preparation, and Results requires a validated result payload.

## Automated validation

Frontend CI covers JavaScript syntax, Public/Product entry separation, Landing static contracts, text-size preference persistence, CSV/XLSX loading, the full six-step JSDOM flow, Ordinal-target/state freshness, browser-level Landing → Product navigation, and responsive Chromium visual smoke at desktop, tablet, and mobile viewports. Passing browser runs upload screenshots as the `ku-open-da-visual-uat` artifact.

Backend CI covers compile + pytest, including API version/capabilities, CORS preflight, Compare Groups, segmentation, reporting, predictive feature importance, and recognized/unknown ordinal-target behavior.

## Current analytical boundary

The hosted backend exposes validated **Fast mode**. Deep model/architecture discovery remains in the notebook/research workflow and is not exposed as a public production route yet.
