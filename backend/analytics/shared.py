from dataclasses import dataclass
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd

def _structural_exclusions(df, target=None):
    ids = [c for c in df.columns if c.lower() in {"id","customer_id","row_id","index"}]
    constants = [
        c for c in df.columns
        if c != target and df[c].nunique(dropna=False) <= 1
    ]
    return list(dict.fromkeys(ids + constants))

def _derive_customer_fields(X, reference_date="2026-01-01"):
    Z = X.copy()

    if "Year_Birth" in Z.columns:
        Z["Customer_Age"] = (
            pd.Timestamp(reference_date).year -
            pd.to_numeric(Z["Year_Birth"], errors="coerce")
        )
        Z = Z.drop(columns="Year_Birth")

    if "Dt_Customer" in Z.columns:
        dt = pd.to_datetime(Z["Dt_Customer"], errors="coerce", dayfirst=True)
        Z["Customer_Tenure_Days"] = (
            pd.Timestamp(reference_date) - dt
        ).dt.days
        Z = Z.drop(columns="Dt_Customer")

    return Z

def _top_model_importance(preprocessor, model, top_n=10):
    values = getattr(model, 'feature_importances_', None)
    if values is None:
        return []
    try:
        names = preprocessor.get_feature_names_out().tolist()
    except Exception:
        names = [f'feature_{i+1}' for i in range(len(values))]
    values = np.asarray(values, dtype=float)
    if len(names) != len(values):
        names = [f'feature_{i+1}' for i in range(len(values))]
    order = np.argsort(values)[::-1]
    findings = []
    for idx in order[:top_n]:
        score = float(values[idx])
        if not np.isfinite(score) or score <= 0:
            continue
        name = str(names[idx])
        if '__' in name:
            name = name.split('__', 1)[1]
        findings.append({
            'relationship': name,
            'interpretation': f'Predictive model importance = {score:.4f}',
            'effect': score,
            'importance': score,
        })
    return findings
