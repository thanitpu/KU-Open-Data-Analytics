import time
import numpy as np
import pandas as pd
from .association import _prepare_unsupervised_fields, _compute_fast_associations

def run_fast_exploratory(df):
    t0 = time.perf_counter()

    prep, A, supported = (
        _compute_fast_associations(df)
    )

    x = prep["df"]
    profile_rows = []

    for c in x.columns:
        s = x[c]
        role = (
            "numeric"
            if pd.api.types.is_numeric_dtype(s)
            else "categorical"
        )
        profile_rows.append({
            "field": c,
            "dtype": str(s.dtype),
            "role": role,
            "missing_pct": float(s.isna().mean() * 100),
            "n_unique": int(s.nunique(dropna=True)),
            "unique_ratio": float(s.nunique(dropna=True) / len(x))
        })

    field_profile = pd.DataFrame(profile_rows)
    conn_rows = []
    fields = sorted(set(supported["field_1"]) | set(supported["field_2"]))

    for c in fields:
        e = supported[(supported["field_1"] == c) | (supported["field_2"] == c)]
        conn_rows.append({
            "field": c,
            "connections": len(e),
            "mean_effect": float(e["effect"].mean()) if len(e) else 0,
            "max_effect": float(e["effect"].max()) if len(e) else 0
        })

    connectivity = pd.DataFrame(conn_rows)
    if len(connectivity):
        connectivity = connectivity.sort_values(
            ["connections", "max_effect"], ascending=False
        ).reset_index(drop=True)

    top_findings = []
    for _, r in supported.head(8).iterrows():
        if r["pair_type"] == "numeric_numeric":
            direction = "positive" if r["signed_effect"] > 0 else "negative"
            interpretation = f"{direction} monotonic association (ρ={r['signed_effect']:.3f})"
        elif r["pair_type"] == "categorical_numeric":
            interpretation = f"group-related numeric difference (ε²={r['effect']:.3f})"
        else:
            interpretation = f"categorical association (Cramér's V={r['effect']:.3f})"

        top_findings.append({
            "relationship": f"{r['field_1']} ↔ {r['field_2']}",
            "pair_type": r["pair_type"],
            "effect": float(r["effect"]),
            "interpretation": interpretation
        })

    very_strong_numeric = A[(A["pair_type"] == "numeric_numeric") & (A["effect"] >= .70)]
    recommendations = []

    if len(very_strong_numeric):
        recommendations.append({
            "analysis": "Dimension reduction / composite features",
            "reason": "Several numeric variables show very strong shared structure."
        })

    if len(connectivity) and (connectivity.iloc[0]["connections"] >= 5):
        recommendations.append({
            "analysis": "Customer segmentation",
            "reason": "Multiple fields show substantial multivariate connectivity."
        })

    recommendations.append({
        "analysis": "Association analysis",
        "reason": "Formal FDR-controlled association evidence is available."
    })

    elapsed = time.perf_counter() - t0
    result = {
        "status": "COMPLETE",
        "route": "exploratory",
        "analysis_type": "exploratory",
        "target": None,
        "mode": "fast",
        "dataset": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "method": {
            "association_screen": "mixed-type fast association scan",
            "multiple_testing": "Benjamini-Hochberg FDR"
        },
        "evidence": {
            "usable_fields": int(len(prep["df"].columns)),
            "association_pairs": int(len(A)),
            "fdr_supported": int(A["significant_fdr"].sum()) if len(A) else 0,
            "moderate_plus_pairs": int((A["effect"] >= .30).sum()) if len(A) else 0,
            "very_strong_numeric_pairs": int(len(very_strong_numeric)),
            "connected_fields": int(len(connectivity))
        },
        "findings": top_findings,
        "warnings": [],
        "recommendations": recommendations,
        "readiness": "FAST_EXECUTION_READY",
        "runtime_seconds": elapsed
    }

    artifacts = {
        "field_profile": field_profile,
        "associations": A,
        "supported_associations": supported,
        "connectivity": connectivity,
        "excluded": prep["excluded"]
    }

    return result, artifacts
