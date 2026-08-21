import time
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
from .shared import _structural_exclusions, _derive_customer_fields
from .policies import FAST_POLICY_REGISTRY

def run_fast_segmentation(df, reference_date="2026-01-01"):
    t0 = time.perf_counter()
    policy = FAST_POLICY_REGISTRY["segmentation"]

    X = df.copy()
    outcome_like = [
        c for c in X.columns
        if c.lower().startswith("acceptedcmp")
        or c.lower() in {"response","complain"}
    ]
    exclude = _structural_exclusions(X) + outcome_like

    X = X.drop(columns=list(dict.fromkeys(exclude)), errors="ignore")
    X = _derive_customer_fields(X, reference_date)
    X = X.select_dtypes(include=np.number)

    if X.shape[1] < 2:
        raise ValueError("Segmentation requires at least two usable numeric features.")

    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()

    Xi = imputer.fit_transform(X)
    Xs = scaler.fit_transform(Xi)

    pca = PCA(n_components=.90, random_state=42)
    Xp = pca.fit_transform(Xs)

    model = KMeans(
        n_clusters=int(policy["k"]),
        n_init=20,
        random_state=42
    )
    labels = model.fit_predict(Xp)

    counts = pd.Series(labels).value_counts().sort_index()

    evidence = {
        "silhouette": float(silhouette_score(Xp, labels)),
        "calinski_harabasz": float(calinski_harabasz_score(Xp, labels)),
        "davies_bouldin": float(davies_bouldin_score(Xp, labels)),
        "pca_dimensions": int(Xp.shape[1]),
        "pca_variance": float(pca.explained_variance_ratio_.sum())
    }

    profile = X.copy()
    profile["_segment"] = labels
    means = profile.groupby("_segment").mean()
    overall = X.mean()
    sd = X.std().replace(0, np.nan)

    descriptors = {}

    for seg in means.index:
        z = ((means.loc[seg] - overall) / sd).dropna()

        descriptors[str(seg)] = {
            "high": z.sort_values(ascending=False).head(3).index.tolist(),
            "low": z.sort_values().head(3).index.tolist(),
            "size_pct": float(counts.loc[seg] / len(labels) * 100)
        }

    elapsed = time.perf_counter() - t0

    result = {
        "status": "COMPLETE",
        "route": "segmentation",
        "analysis_type": "segmentation",
        "target": None,
        "mode": "fast",
        "dataset": {
            "rows": int(df.shape[0]),
            "columns": int(df.shape[1])
        },
        "method": {
            "representation": f"PCA90_{Xp.shape[1]}D",
            "algorithm": "KMeans",
            "clusters": int(policy["k"]),
            "selection_source": policy["selection_source"]
        },
        "evidence": evidence,
        "findings": descriptors,
        "warnings": [],
        "readiness": "FAST_EXECUTION_READY",
        "runtime_seconds": elapsed
    }

    artifacts = {
        "features": X.columns.tolist(),
        "excluded": list(dict.fromkeys(exclude)),
        "imputer": imputer,
        "scaler": scaler,
        "pca": pca,
        "model": model,
        "labels": labels
    }

    return result, artifacts
