# Automated Analytics Service

Stateless analytics package extracted from the validated notebook pipeline.

## Fast analytical routes

- Binary Classification
- Multiclass Classification
- Regression
- Customer Segmentation
- Exploratory Data Analysis
- Association Analysis

## Run API

Install dependencies:

    pip install -r requirements.txt

Run the service:

    uvicorn app.api:app --reload

Then open /docs for Swagger UI or /health for service health.

## Current boundary

Package v0.1 contains validated Fast execution paths.
Deep model and architecture discovery remains in the research notebook layer.

## Deployment

### Local

    pip install -r requirements.txt
    uvicorn app.api:app --reload

### Docker

    docker build -t analytics-service .
    docker run -p 8000:8000 analytics-service

### API

- `GET /health`
- `POST /analyze`

The `/analyze` endpoint accepts:

- `file`: CSV upload
- `intent`: analytical intent
- `target`: optional target column
- `mode`: currently `fast`

### Supported fast routes

- Binary Classification
- Multiclass Classification
- Regression
- Customer Segmentation
- Exploratory Data Analysis
- Association Analysis

### Current limitation

Deep discovery engines are not yet exposed by the deployment package.
