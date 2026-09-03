"""Versioned semantic retrieval and topic discovery for KU2A.

The lightweight LSA path is deterministic and is always identified as a
non-transformer fallback. Transformer loading is opt-in to the Python API and
is not enabled by the public FastAPI routes in this release.
"""

from __future__ import annotations

import re
from typing import Iterable

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize

ENGINE_VERSION = "ku2a-semantic-engine-v1"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
THAI_STOP = {"และ", "หรือ", "ที่", "ใน", "ของ", "เป็น", "ก็", "มี", "ได้", "ให้", "กับ", "จาก", "มาก", "ครับ", "ค่ะ", "นะ", "แต่", "แล้ว", "เรา", "ผม", "ฉัน", "มัน", "ไม่"}
ENGLISH_STOP = {"the", "a", "an", "and", "or", "is", "are", "was", "were", "to", "of", "in", "for", "on", "with", "this", "that", "it", "very"}


def _safe_texts(texts: Iterable[object]) -> list[str]:
    return [str(value or "").strip() for value in texts]


def _embed_sentence_transformers(texts: list[str]):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME)
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(embeddings, dtype=float), {
        "engine_version": ENGINE_VERSION,
        "engine": "sentence-transformers",
        "model": MODEL_NAME,
        "semantic": True,
        "fallback": False,
    }


def _embed_lsa(texts: list[str], dimension: int = 128):
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True)
    matrix = vectorizer.fit_transform(texts)
    maximum = min(matrix.shape[0] - 1, matrix.shape[1] - 1, dimension)
    if maximum >= 1:
        reduced = TruncatedSVD(n_components=maximum, random_state=42).fit_transform(matrix)
        vectors = normalize(reduced)
        model = f"char-tfidf+truncated-svd-{maximum}"
    else:
        vectors = normalize(matrix).toarray()
        model = "char-tfidf"
    return np.asarray(vectors, dtype=float), {
        "engine_version": ENGINE_VERSION,
        "engine": "lsa-fallback",
        "model": model,
        "semantic": False,
        "fallback": True,
        "disclosure": "LSA/TF-IDF fallback; not a transformer result.",
    }


def embeddings(texts: Iterable[object], prefer_transformer: bool = False):
    cleaned = _safe_texts(texts)
    if not cleaned or not any(cleaned):
        raise ValueError("At least one non-empty document is required.")
    if prefer_transformer:
        try:
            return _embed_sentence_transformers(cleaned)
        except Exception as error:  # transformer dependency/model is optional
            vectors, metadata = _embed_lsa(cleaned)
            metadata["fallback_reason"] = f"{type(error).__name__}: {error}"
            return vectors, metadata
    return _embed_lsa(cleaned)


def semantic_search(texts, query, top_n: int = 10, prefer_transformer: bool = False):
    cleaned = _safe_texts(texts)
    query = str(query or "").strip()
    if not query:
        raise ValueError("Query is required.")
    vectors, metadata = embeddings(cleaned + [query], prefer_transformer)
    scores = np.dot(vectors[:-1], vectors[-1])
    indices = np.argsort(scores)[::-1][: max(1, min(int(top_n), len(cleaned)))]
    return {"engine": metadata, "query": query, "results": [{"index": int(index), "text": cleaned[int(index)], "similarity": float(scores[int(index)])} for index in indices]}


def similar_documents(texts, index: int, top_n: int = 5, prefer_transformer: bool = False):
    cleaned = _safe_texts(texts)
    index = int(index)
    if index < 0 or index >= len(cleaned):
        raise ValueError("Document index is out of range.")
    vectors, metadata = embeddings(cleaned, prefer_transformer)
    scores = np.dot(vectors, vectors[index])
    indices = [int(item) for item in np.argsort(scores)[::-1] if int(item) != index][: max(1, int(top_n))]
    return {"engine": metadata, "source": {"index": index, "text": cleaned[index]}, "results": [{"index": item, "text": cleaned[item], "similarity": float(scores[item])} for item in indices]}


def _word_tokens(value: str):
    tokens = re.findall(r"[\u0E00-\u0E7F]{2,}|[A-Za-z]{2,}", value.lower())
    return [token for token in tokens if token not in THAI_STOP and token not in ENGLISH_STOP]


def _topic_terms(texts: list[str], labels, topic_count: int, top_n: int = 8):
    combined = [" ".join(texts[index] for index, label in enumerate(labels) if label == topic) for topic in range(topic_count)]
    vectorizer = TfidfVectorizer(tokenizer=_word_tokens, token_pattern=None, lowercase=False, min_df=1)
    matrix = vectorizer.fit_transform(combined)
    terms = np.array(vectorizer.get_feature_names_out())
    return [[{"term": terms[index], "score": float(matrix[topic, index])} for index in np.asarray(matrix[topic].todense()).ravel().argsort()[::-1][:top_n] if matrix[topic, index] > 0] for topic in range(topic_count)]


def discover_topics(texts, k: int = 5, prefer_transformer: bool = False, random_state: int = 42):
    cleaned = _safe_texts(texts)
    nonempty = [index for index, value in enumerate(cleaned) if value]
    if len(nonempty) < 2:
        raise ValueError("At least two non-empty documents are required.")
    topic_count = max(2, min(int(k), len(nonempty)))
    vectors, metadata = embeddings([cleaned[index] for index in nonempty], prefer_transformer)
    model = KMeans(n_clusters=topic_count, random_state=random_state, n_init=10)
    labels = model.fit_predict(vectors)
    centers = normalize(model.cluster_centers_)
    similarities = np.sum(vectors * centers[labels], axis=1)
    silhouette = None
    if len(set(labels)) > 1 and len(labels) > topic_count:
        silhouette = float(silhouette_score(vectors, labels, metric="cosine"))
    term_lists = _topic_terms([cleaned[index] for index in nonempty], labels, topic_count)
    topics = []
    for topic in range(topic_count):
        members = np.where(labels == topic)[0]
        ranked = members[np.argsort(similarities[members])[::-1]]
        representatives = [{"index": nonempty[int(item)], "text": cleaned[nonempty[int(item)]], "similarity": float(similarities[item])} for item in ranked[:5]]
        label = " · ".join(item["term"] for item in term_lists[topic][:3]) or f"Topic {topic + 1}"
        topics.append({"id": topic, "label": label, "size": int(len(members)), "share": float(len(members) / len(nonempty)), "terms": term_lists[topic], "representatives": representatives})
    assignments = [None] * len(cleaned)
    for local_index, label in enumerate(labels):
        assignments[nonempty[local_index]] = int(label)
    return {"engine": metadata, "k": topic_count, "documents": len(nonempty), "topics": topics, "assignments": assignments, "quality": {"silhouette_cosine": silhouette, "mean_compactness": float(np.mean(similarities))}}


def compare_k(texts, ks=(3, 5, 7, 10), prefer_transformer: bool = False):
    rows = []
    for k in ks:
        if int(k) >= len(texts):
            continue
        try:
            result = discover_topics(texts, int(k), prefer_transformer)
            rows.append({"k": int(k), **result["quality"], "engine": result["engine"]})
        except Exception as error:
            rows.append({"k": int(k), "error": str(error)})
    return rows


def topic_priority(topic_result, sentiment_labels):
    labels = [str(value or "").lower() for value in sentiment_labels]
    rows = []
    for topic in topic_result.get("topics", []):
        indices = [index for index, assignment in enumerate(topic_result.get("assignments", [])) if assignment == topic["id"]]
        counts = {"positive": 0, "negative": 0, "neutral": 0, "unknown": 0}
        for index in indices:
            label = labels[index] if index < len(labels) else ""
            counts[label if label in counts else "unknown"] += 1
        known = counts["positive"] + counts["negative"] + counts["neutral"]
        negative_share = counts["negative"] / known if known else 0.0
        prevalence = topic.get("share", 0.0)
        rows.append({"topicId": topic["id"], "topicLabel": topic["label"], "size": topic["size"], "prevalence": prevalence, "negativeShare": negative_share, "priorityScore": prevalence * negative_share, "counts": counts})
    rows.sort(key=lambda row: row["priorityScore"], reverse=True)
    for rank, row in enumerate(rows, 1):
        row["priorityRank"] = rank
    return rows


def evidence_summary(topic_result, sentiment_labels, max_topics: int = 5):
    priority = topic_priority(topic_result, sentiment_labels)
    topics = {topic["id"]: topic for topic in topic_result.get("topics", [])}
    return {
        "summaryVersion": "1.0-evidence-rule",
        "method": "Rule-based synthesis from topic prevalence, sentiment composition, and representative documents",
        "topics": [{**row, "representatives": topics.get(row["topicId"], {}).get("representatives", [])[:3]} for row in priority[:max_topics]],
    }
