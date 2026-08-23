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

### Ordinal targets in Regression

Question-first routing treats a target marked **Ordinal** as a Regression target. Numeric ordinal targets run directly. A text ordinal target is executable only when its observed labels match a supported semantic sequence; the backend rank-encodes the observed levels while preserving that order.

Currently recognized sequences are:

- `Low < Medium < High`
- `Poor < Fair < Good < Very Good < Excellent`
- `Strongly disagree < Disagree < Neutral < Agree < Strongly agree`

A subset of one of these sequences is supported when at least two levels are observed. Unknown text ordinal labels are not silently alphabetically encoded; Step 4 keeps them blocked for review instead.

When rank coding is used, Step 6 identifies the target as ordinal rank-coded, shows the category-to-rank mapping, and warns that rank order does not establish equal spacing between adjacent categories.

## Frontend

The static frontend is served from the repository and is compatible with GitHub Pages.

Data loading, profiling, field metadata review, and browser statistical exploration remain local to the browser. A dataset is sent to the configured analytics API only when the user explicitly runs a validated analysis.

The six-step navigation is state-gated. In particular, Prepare does not unlock for a target-required question until an executable route has actually been derived from a selected target.

### Frontend entry architecture

The accepted architecture separates the public site from the analytical workspace:

- `index.html` → Public Landing Page
- `app.html` → Functional KU Open Data Analytics workspace

The Functional migration is now complete: `app.html` is the canonical Product entry and frontend CI sets `KU_APP_ENTRY=app.html`. Static smoke, JSDOM journey smoke, Ordinal target smoke, static preview, and Playwright browser smoke all target that configured Product entry rather than the site root.

Until the explicit Final Landing Integration step, root `index.html` remains a temporary compatibility mirror of `app.html` on the Functional branch. `tests/frontend_entry_guard.js` requires the two files to remain byte-equivalent during this transition, preventing accidental Product-shell divergence. The mirror assertion is intentionally removed/changed only when the approved Public Landing replaces root `index.html`.

Product runtime `src/*.js` must not hard-code `index.html` or root-absolute navigation. Product CSS/JS assets use relative repository paths so `app.html` remains compatible with GitHub Pages project-path hosting.

The architecture/workstream boundaries are recorded in `docs/ADR-frontend-public-landing-app-entry.md`; migration status and Final Integration checks are in `docs/APP_ENTRY_MIGRATION_UAT.md` and `docs/FUNCTIONAL_APP_HANDOFF.md`. Landing-specific HTML/CSS/JS/assets remain outside the Functional Product workstream until the dedicated Final Integration step.

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

`GET /capabilities` is the frontend source for Step 5 Recommended Setup. It exposes the validated route policy, preparation behavior, validation design, returned metrics, service version, and supported ordinal-target sequences instead of duplicating those settings in the frontend.

## Render deployment and API boundary

A `render.yaml` Blueprint is included at the repository root. It deploys the backend from `backend/`, installs `backend/requirements.txt`, starts:

    uvicorn app.api:app --host 0.0.0.0 --port $PORT

and uses `/health` for the service health check.

The frontend default analytics API base is:

    https://ku-open-data-analytics-api.onrender.com

Both Step 5 `/capabilities` and Step 5/6 analysis execution through `/analyze` use the same configurable API base. It can be overridden before `src/ai-analytics.js` loads:

    <script>window.KU_ANALYTICS_API_BASE='https://YOUR-SERVICE.onrender.com';</script>

The backend CORS policy is configured through `CORS_ORIGINS`. The default configuration allows:

- `https://thanitpu.github.io`
- `http://localhost:8000`
- `http://127.0.0.1:8000`

Backend tests include a GitHub Pages CORS preflight contract. Frontend browser smoke mocks `/capabilities` and `/analyze` only on the production Render host so an accidental fallback to the GitHub Pages/local origin is detected rather than hidden by the test harness.

Render Blueprint `autoDeploy` is enabled, but the branch tracked by an existing Render service is controlled by the Render service configuration. Production deployment should therefore remain aligned with the reviewed/merged GitHub branch.

## State and result freshness

The Analysis Plan is authoritative across Steps 3–6. Changing Question Type or Target invalidates the validated result. Predictor changes preserve the previous result for comparison but invalidate downstream preparation/setup approval; Step 6 labels the preserved output as a previous validated result when it no longer matches the Current Analysis.

Storage/measurement metadata for the selected target and predictors is snapshotted with each validated result. A metadata edit immediately invalidates Prepare/Setup approval and preserves the previous result only for comparison. Step 6 marks that result stale even when the derived analytical route stays the same, for example an Ordinal → Scale edit that still routes to Regression.

Each newly loaded browser dataset receives a monotonic dataset revision when the loader replaces the in-memory data array. This means a genuinely new file/dataset clears the Analysis Plan and result even when it happens to have the same row count, column names, storage types, and measurement levels as the prior dataset. Metadata-only edits do not advance the dataset revision.

Dataset replacement/clear therefore resets stale plan/result state reliably. Prepare requires a derived route, Setup requires approved preparation, and Results requires a validated result payload.

## Automated validation

Frontend CI covers JavaScript syntax, the `app.html` entry migration guard, static contracts, full six-step JSDOM flow, a dedicated ordinal-target DOM smoke, same-route metadata freshness, same-schema dataset replacement via revision tracking, and Playwright Chromium visual smoke at desktop, tablet, and mobile viewports. The passing browser run uploads screenshots as the `ku-open-da-visual-uat` artifact.

Backend CI covers compile + pytest, including API version/capabilities, CORS preflight, Compare Groups, segmentation, reporting, predictive feature importance, and recognized/unknown ordinal-target behavior.

## Current analytical boundary

The hosted backend exposes validated **Fast mode**. Deep model/architecture discovery remains in the notebook/research workflow and is not exposed as a public production route yet.
