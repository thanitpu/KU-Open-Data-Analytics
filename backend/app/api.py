from io import BytesIO
import json
import os
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .orchestrator import execute_analysis
from .reporting import build_executive_report
from .capabilities import get_capabilities
from .schemas import FeatureEngineeringRecommendationRequest, FeatureEngineeringRecommendationResponse, SemanticSearchRequest, SimilarDocumentsRequest, TopicDiscoveryRequest
from intelligence.fe_recommender import recommend_features
from text_analytics.semantic_engine import semantic_search, similar_documents, discover_topics

app = FastAPI(title='Automated Analytics Service', version='0.5.0')

cors_origins = [
    x.strip() for x in os.getenv(
        'CORS_ORIGINS',
        'https://thanitpu.github.io,https://raw.githack.com,http://localhost:8000,http://127.0.0.1:8000'
    ).split(',') if x.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=['GET', 'POST', 'OPTIONS'],
    allow_headers=['*'],
    max_age=3600,
)

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.get('/capabilities')
def capabilities():
    return get_capabilities()

@app.post('/recommend/feature-engineering', response_model=FeatureEngineeringRecommendationResponse)
def recommend_feature_engineering(request: FeatureEngineeringRecommendationRequest):
    try:
        return recommend_features(request.model_dump())
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@app.post('/text-analytics/semantic-search')
def text_semantic_search(request: SemanticSearchRequest):
    try:
        return semantic_search(request.texts, request.query, request.top_n, prefer_transformer=False)
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@app.post('/text-analytics/similar-documents')
def text_similar_documents(request: SimilarDocumentsRequest):
    try:
        return similar_documents(request.texts, request.index, request.top_n, prefer_transformer=False)
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@app.post('/text-analytics/topics')
def text_topics(request: TopicDiscoveryRequest):
    try:
        return discover_topics(request.texts, request.k, prefer_transformer=False)
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))

@app.post('/analyze')
async def analyze(
    file: UploadFile = File(...),
    intent: str = Form(...),
    target: str | None = Form(None),
    mode: str = Form('fast'),
    options_json: str | None = Form(None),
):
    try:
        raw = await file.read()
        df = pd.read_csv(BytesIO(raw))
        options = json.loads(options_json) if options_json else None
        if options is not None and not isinstance(options, dict):
            raise ValueError('options_json must encode a JSON object.')
        result, _ = execute_analysis(
            df=df, intent=intent, target=target, mode=mode, options=options
        )
        return {
            'result': result,
            'report': build_executive_report(result),
        }
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))
