from app.api import app
from fastapi.testclient import TestClient
from text_analytics.semantic_engine import ENGINE_VERSION, compare_k, discover_topics, evidence_summary, semantic_search, similar_documents


TEXTS = [
    "server lag connection problem",
    "connection disconnect server",
    "gameplay fun with friends",
    "play fun gameplay",
    "patch bug update",
    "update fixed bug",
]


def test_lsa_fallback_is_disclosed():
    result = semantic_search(TEXTS, "server connection", top_n=2, prefer_transformer=False)
    assert result["engine"]["engine_version"] == ENGINE_VERSION
    assert result["engine"]["engine"] == "lsa-fallback"
    assert result["engine"]["semantic"] is False
    assert result["engine"]["fallback"] is True
    assert "not a transformer" in result["engine"]["disclosure"]
    assert len(result["results"]) == 2


def test_semantic_topic_and_similar_contracts():
    assert len(similar_documents(TEXTS, 0, top_n=2, prefer_transformer=False)["results"]) == 2
    topics = discover_topics(TEXTS, k=3, prefer_transformer=False)
    assert topics["k"] == 3
    assert len(topics["assignments"]) == len(TEXTS)
    assert topics["engine"]["engine"] == "lsa-fallback"
    assert len(compare_k(TEXTS, ks=(2, 3), prefer_transformer=False)) == 2
    summary = evidence_summary(topics, ["negative", "negative", "positive", "positive", "negative", "positive"])
    assert summary["summaryVersion"] == "1.0-evidence-rule"
    assert summary["topics"][0]["priorityRank"] == 1


def test_semantic_api_never_enables_transformer():
    client = TestClient(app)
    response = client.post('/text-analytics/semantic-search', json={"texts": TEXTS, "query": "server", "top_n": 2})
    assert response.status_code == 200
    assert response.json()["engine"]["engine"] == "lsa-fallback"
    capabilities = client.get('/capabilities').json()["intelligence"]["text_analytics"]
    assert capabilities["transformer_enabled_by_api"] is False
