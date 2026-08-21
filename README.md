# KU Open Data Analytics

Free browser-based statistical analysis and learning platform.

The project now contains two complementary analytical layers:

- Browser-based descriptive and classical statistical tools.
- A validated FastAPI analytics backend for Binary Classification, Multiclass Classification, Regression, Customer Segmentation, Exploratory Data Analysis, and Association Analysis.

## Frontend

The static frontend is served from the repository root and is compatible with GitHub Pages.

## Backend

The FastAPI service lives under `backend/`.

Local run:

    cd backend
    pip install -r requirements.txt
    uvicorn app.api:app --reload

Health check:

    GET /health

Validated analysis endpoint:

    POST /analyze

The analysis endpoint accepts a CSV upload plus `intent`, optional `target`, and `mode=fast`.

## Render deployment

A `render.yaml` Blueprint is included at the repository root. It deploys the backend from the `backend` root directory, installs `backend/requirements.txt`, starts `uvicorn app.api:app --host 0.0.0.0 --port $PORT`, and uses `/health` for the service health check.

The backend CORS policy is configured through `CORS_ORIGINS`. The default configuration allows the GitHub Pages origin and localhost development origins.

After Render assigns the public API URL, set the frontend configuration before `src/ai-analytics.js` is loaded:

    <script>window.KU_ANALYTICS_API_BASE='https://YOUR-SERVICE.onrender.com';</script>

The frontend then sends the currently loaded browser dataset to `/analyze` only when the user explicitly runs the Validated Analytics Engine.

## Current analytical boundary

The hosted backend exposes validated Fast mode. Deep model/architecture discovery remains in the research workflow and is not yet exposed as a public web-service route.
