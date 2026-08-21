import time
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor
from .shared import _structural_exclusions, _derive_customer_fields
from .policies import FAST_POLICY_REGISTRY

def _build_fast_regression_features(df, target, reference_date="2026-01-01"):
    if target not in df.columns:
        raise ValueError(f"Target '{target}' not found.")

    d = df[df[target].notna()].copy().reset_index(drop=True)
    y = pd.to_numeric(d[target], errors="coerce")

    valid = y.notna()
    d = d.loc[valid].reset_index(drop=True)
    y = y.loc[valid].reset_index(drop=True)

    exclude = _structural_exclusions(d, target) + [target]
    X = d.drop(columns=list(dict.fromkeys(exclude)), errors="ignore")
    X = _derive_customer_fields(X, reference_date)

    pairs = [
        ("MntMeatProducts", "NumCatalogPurchases"),
        ("MntWines", "NumCatalogPurchases"),
        ("Income", "MntWines"),
        ("MntWines", "MntMeatProducts"),
        ("Income", "MntMeatProducts")
    ]

    for a, b in pairs:
        if a in X.columns and b in X.columns:
            X[f"{a}__x__{b}"] = (
                pd.to_numeric(X[a], errors="coerce") *
                pd.to_numeric(X[b], errors="coerce")
            )

    for c in list(X.select_dtypes(include=np.number).columns):
        s = pd.to_numeric(X[c], errors="coerce")
        if s.nunique(dropna=True) > 20 and s.min(skipna=True) >= 0:
            X[f"{c}__log1p"] = np.log1p(s.clip(lower=0))

    return X, y, exclude

def _fast_regression_preprocessor(X):
    num = X.select_dtypes(include=np.number).columns.tolist()
    cat = [c for c in X.columns if c not in num]

    transformers = [
        (
            "num",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median"))
            ]),
            num
        )
    ]

    if cat:
        transformers.append((
            "cat",
            Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore"))
            ]),
            cat
        ))

    return ColumnTransformer(transformers)

def run_fast_regression(df, target, reference_date="2026-01-01"):
    t0 = time.perf_counter()
    policy = FAST_POLICY_REGISTRY["regression"]

    X, y, excluded = _build_fast_regression_features(
        df, target, reference_date
    )

    model = XGBRegressor(
        n_estimators=500,
        learning_rate=.03,
        max_depth=4,
        subsample=.85,
        colsample_bytree=.85,
        objective="reg:squarederror",
        random_state=42,
        n_jobs=-1
    )

    pipe = Pipeline([
        ("prep", _fast_regression_preprocessor(X)),
        ("model", model)
    ])

    cv = KFold(n_splits=5, shuffle=True, random_state=42)

    pred = cross_val_predict(
        pipe, X, y,
        cv=cv,
        n_jobs=-1
    )

    pred = np.asarray(pred, dtype=float)

    mae = mean_absolute_error(y, pred)
    rmse = mean_squared_error(y, pred) ** .5
    r2 = r2_score(y, pred)

    q90 = np.quantile(y, .90)
    tail = y >= q90

    tail_mae = mean_absolute_error(
        y[tail], pred[tail]
    )

    tail_bias = float(
        np.mean(pred[tail] - y[tail])
    )

    warnings = []
    if tail_bias < 0:
        warnings.append(
            "Model underpredicts high-target observations."
        )

    pipe.fit(X, y)

    elapsed = time.perf_counter() - t0

    result = {
        "status": "COMPLETE",
        "route": "regression",
        "analysis_type": "regression",
        "target": target,
        "mode": "fast",
        "dataset": {
            "rows": int(len(y)),
            "columns": int(df.shape[1])
        },
        "method": {
            "feature_engineering": policy["feature_engineering"],
            "model": policy["model"],
            "architecture": policy["architecture"],
            "selection_source": policy["selection_source"]
        },
        "evidence": {
            "mae": float(mae),
            "rmse": float(rmse),
            "r2": float(r2),
            "tail_mae": float(tail_mae),
            "tail_bias": float(tail_bias)
        },
        "warnings": warnings,
        "readiness": "FAST_EXECUTION_READY",
        "runtime_seconds": elapsed
    }

    artifacts = {
        "features": X.columns.tolist(),
        "excluded": excluded,
        "pipeline": pipe,
        "oof_predictions": pred,
        "target_values": y
    }

    return result, artifacts
