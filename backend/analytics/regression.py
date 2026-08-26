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
from .shared import _structural_exclusions, _derive_customer_fields, _top_model_importance
from .policies import FAST_POLICY_REGISTRY


_STANDARD_ORDINAL_TARGET_SEQUENCES = [
    ["low", "medium", "high"],
    ["poor", "fair", "good", "very good", "excellent"],
    ["strongly disagree", "disagree", "neutral", "agree", "strongly agree"],
]


def _recognized_ordinal_target(series):
    observed = series.dropna()
    if observed.empty:
        return None, None

    representatives = {}
    normalized = []
    for value in observed:
        label = str(value).strip()
        key = label.casefold()
        representatives.setdefault(key, label)
        normalized.append(key)

    observed_keys = set(normalized)
    for sequence in _STANDARD_ORDINAL_TARGET_SEQUENCES:
        if len(observed_keys) >= 2 and observed_keys.issubset(set(sequence)):
            ordered = [key for key in sequence if key in observed_keys]
            normalized_mapping = {key: idx + 1 for idx, key in enumerate(ordered)}
            encoded = series.map(
                lambda value: np.nan
                if pd.isna(value)
                else normalized_mapping.get(str(value).strip().casefold(), np.nan)
            ).astype(float)
            display_mapping = {
                representatives[key]: normalized_mapping[key] for key in ordered
            }
            return encoded, {
                "type": "ordinal_rank",
                "mapping": display_mapping,
                "order": [representatives[key] for key in ordered],
            }
    return None, None


def _coerce_regression_target(series):
    numeric = pd.to_numeric(series, errors="coerce")
    observed_count = int(series.notna().sum())
    if int(numeric.notna().sum()) == observed_count:
        return numeric, None

    ordinal, encoding = _recognized_ordinal_target(series)
    if ordinal is not None:
        return ordinal, encoding

    return numeric, None


def _build_fast_regression_features(
    df,
    target,
    reference_date="2026-01-01",
    browser_managed=False,
):
    if target not in df.columns:
        raise ValueError(f"Target '{target}' not found.")

    d = df[df[target].notna()].copy().reset_index(drop=True)
    y, target_encoding = _coerce_regression_target(d[target])
    valid = y.notna()
    d = d.loc[valid].reset_index(drop=True)
    y = y.loc[valid].reset_index(drop=True)

    if len(y) < 5:
        raise ValueError("Regression requires at least five numeric or recognized ordinal target observations.")

    exclude = _structural_exclusions(d, target) + [target]
    X = d.drop(columns=list(dict.fromkeys(exclude)), errors="ignore")

    # Backward-compatible clients still receive the validated legacy R3 feature
    # expansion. Once a reviewed browser FE manifest is supplied, deterministic
    # feature construction is browser-owned and the backend must not silently
    # recreate, overwrite or double-transform those fields.
    if not browser_managed:
        X = _derive_customer_fields(X, reference_date)
        pairs = [
            ("MntMeatProducts", "NumCatalogPurchases"),
            ("MntWines", "NumCatalogPurchases"),
            ("Income", "MntWines"),
            ("MntWines", "MntMeatProducts"),
            ("Income", "MntMeatProducts"),
        ]
        for a, b in pairs:
            if a in X.columns and b in X.columns:
                X[f"{a}__x__{b}"] = (
                    pd.to_numeric(X[a], errors="coerce")
                    * pd.to_numeric(X[b], errors="coerce")
                )

        for c in list(X.select_dtypes(include=np.number).columns):
            s = pd.to_numeric(X[c], errors="coerce")
            if s.nunique(dropna=True) > 20 and s.min(skipna=True) >= 0:
                X[f"{c}__log1p"] = np.log1p(s.clip(lower=0))

    return X, y, exclude, target_encoding


def _fast_regression_preprocessor(X):
    num = X.select_dtypes(include=np.number).columns.tolist()
    cat = [c for c in X.columns if c not in num]

    transformers = [
        (
            "num",
            Pipeline([("imputer", SimpleImputer(strategy="median"))]),
            num,
        )
    ]
    if cat:
        transformers.append(
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                cat,
            )
        )

    return ColumnTransformer(transformers)


def run_fast_regression(
    df,
    target,
    reference_date="2026-01-01",
    feature_context=None,
):
    t0 = time.perf_counter()
    policy = FAST_POLICY_REGISTRY["regression"]
    browser_managed = bool((feature_context or {}).get('provided'))
    X, y, excluded, target_encoding = _build_fast_regression_features(
        df, target, reference_date, browser_managed=browser_managed
    )

    model = XGBRegressor(
        n_estimators=500,
        learning_rate=.03,
        max_depth=4,
        subsample=.85,
        colsample_bytree=.85,
        objective="reg:squarederror",
        random_state=42,
        n_jobs=-1,
    )
    pipe = Pipeline(
        [
            ("prep", _fast_regression_preprocessor(X)),
            ("model", model),
        ]
    )

    cv = KFold(n_splits=5, shuffle=True, random_state=42)
    pred = np.asarray(cross_val_predict(pipe, X, y, cv=cv, n_jobs=-1), dtype=float)

    mae = mean_absolute_error(y, pred)
    rmse = mean_squared_error(y, pred) ** .5
    r2 = r2_score(y, pred)

    q90 = np.quantile(y, .90)
    tail = y >= q90
    tail_mae = mean_absolute_error(y[tail], pred[tail])
    tail_bias = float(np.mean(pred[tail] - y[tail]))

    warnings = []
    if target_encoding:
        warnings.append(
            "Ordinal target categories were encoded as ordered ranks. Regression treats the rank codes numerically; differences between adjacent categories should not be interpreted as proven equal intervals."
        )
    if browser_managed:
        warnings.append(
            "Deterministic feature construction was supplied by the reviewed browser preparation contract; backend preprocessing remained inside the validation pipeline."
        )
    if tail_bias < 0:
        warnings.append("Model underpredicts high-target observations.")

    pipe.fit(X, y)
    findings = _top_model_importance(pipe.named_steps["prep"], pipe.named_steps["model"])
    if findings:
        warnings.append(
            "Feature importance is predictive model evidence and does not establish causal drivers."
        )

    result = {
        "status": "COMPLETE",
        "route": "regression",
        "analysis_type": "regression",
        "target": target,
        "mode": "fast",
        "dataset": {
            "rows": int(len(y)),
            "columns": int(df.shape[1]),
        },
        "method": {
            "feature_engineering": "browser_prepared_matrix" if browser_managed else policy["feature_engineering"],
            "model_preprocessing": "CV-safe median imputation + one-hot encoding",
            "model": policy["model"],
            "architecture": policy["architecture"],
            "selection_source": policy["selection_source"],
            "target_encoding": target_encoding,
        },
        "evidence": {
            "mae": float(mae),
            "rmse": float(rmse),
            "r2": float(r2),
            "tail_mae": float(tail_mae),
            "tail_bias": float(tail_bias),
        },
        "findings": findings,
        "warnings": warnings,
        "readiness": "FAST_EXECUTION_READY",
        "runtime_seconds": time.perf_counter() - t0,
    }

    artifacts = {
        "features": X.columns.tolist(),
        "excluded": excluded,
        "pipeline": pipe,
        "oof_predictions": pred,
        "target_values": y,
        "target_encoding": target_encoding,
        "browser_feature_engineering": browser_managed,
    }
    return result, artifacts
