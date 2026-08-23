# KU Open Data Analytics

KU Open Data Analytics is a browser-first analytical workspace with a validated FastAPI execution backend.

The production experience follows one six-step journey:

1. **Start** — choose or upload a CSV/XLSX dataset.
2. **Data Profile** — review field structure, measurement levels, data quality, and mixed-type relationships.
3. **Analyze** — define the analytical question; KU Open DA derives the analytical family from the question and target.
4. **Prepare** — review route-specific preparation using the actual selected fields.
5. **Setup** — confirm the validated backend run specification and policy metadata.
6. **Results** — read the answer first, then inspect evidence, family-specific findings, warnings, and technical payload.

The browser also retains optional classical statistical tools for focused exploration. They are secondary to the production journey.

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

## Frontend

The static frontend is served from the repository root and is compatible with GitHub Pages.

Data loading, profiling, field metadata review, and browser statistical exploration remain local to the browser. A dataset is sent to the configured analytics API only when the user explicitly runs a validated analysis.

## Backend

The FastAPI service lives under `backend/` and currently reports API version `0.3.0`.

Local run:

    cd backend
    pip install -r requirements.txt
    uvicorn app.api:app --reload

Health check:

    GET /health

Execution capability metadata:

    GET /capabilities

Validated analysis endpoint:

    POST /analyze

`POST /analyze` accepts a CSV upload plus `intent`, optional `target`, `mode=fast`, and optional `options_json`. Compare Groups uses `options_json` to pass the reviewed grouping field.

`GET /capabilities` is the frontend source for Step 5 Recommended Setup. It exposes the validated route policy, preparation behavior, validation design, and returned metrics instead of duplicating those settings in the frontend.

## Render deployment

A `render.yaml` Blueprint is included at the repository root. It deploys the backend from `backend/`, installs `backend/requirements.txt`, starts:

    uvicorn app.api:app --host 0.0.0.0 --port $PORT

and uses `/health` for the service health check.

The backend CORS policy is configured through `CORS_ORIGINS`. The default configuration allows the GitHub Pages origin and localhost development origins.

The frontend default API base is the deployed KU Open Data Analytics Render service. It can be overridden before `src/ai-analytics.js` loads:

    <script>window.KU_ANALYTICS_API_BASE='https://YOUR-SERVICE.onrender.com';</script>

Render Blueprint `autoDeploy` is enabled, but the branch tracked by an existing Render service is controlled by the Render service configuration. Production deployment should therefore remain aligned with the reviewed/merged GitHub branch.

## State and result freshness

The Analysis Plan is authoritative across Steps 3–6. Changing Question Type or Target invalidates the validated result. Predictor changes preserve the previous result for comparison but invalidate downstream preparation/setup approval; Step 6 labels the preserved output as a previous validated result when it no longer matches the Current Analysis. Measurement-level changes are re-derived when returning to Analyze.

## Current analytical boundary

The hosted backend exposes validated **Fast mode**. Deep model/architecture discovery remains in the notebook/research workflow and is not exposed as a public production route yet.
