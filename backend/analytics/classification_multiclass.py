import time
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import f1_score, balanced_accuracy_score, roc_auc_score, log_loss
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier
from .shared import _structural_exclusions, _derive_customer_fields
from .policies import FAST_POLICY_REGISTRY

def _prepare_classification_data(df, target, reference_date="2026-01-01"):
    if target not in df.columns:
        raise ValueError(f"Target '{target}' not found.")
    d = df[df[target].notna()].copy().reset_index(drop=True)
    y = d[target].copy()
    exclude = _structural_exclusions(d, target) + [target]
    X = d.drop(columns=list(dict.fromkeys(exclude)), errors="ignore")
    X = _derive_customer_fields(X, reference_date)
    return X, y.reset_index(drop=True), exclude

def _classification_preprocessor(X):
    num = X.select_dtypes(include=np.number).columns.tolist()
    cat = [c for c in X.columns if c not in num]
    transformers = [("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), num)]
    if cat:
        transformers.append(("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), cat))
    return ColumnTransformer(transformers)

def _build_fast_multiclass_features(X):
    Z = X.copy()
    pairs = [("MntMeatProducts", "NumCatalogPurchases"), ("MntWines", "NumCatalogPurchases"), ("Income", "MntWines"), ("MntWines", "MntMeatProducts"), ("Income", "MntMeatProducts")]
    for a, b in pairs:
        if a in Z.columns and b in Z.columns:
            Z[f"{a}__x__{b}"] = pd.to_numeric(Z[a], errors="coerce") * pd.to_numeric(Z[b], errors="coerce")
    return Z

def run_fast_multiclass_classification(df, target, reference_date="2026-01-01", confidence_min=.60, margin_min=.05):
    t0 = time.perf_counter(); policy = FAST_POLICY_REGISTRY["classification_multiclass"]
    X, y_raw, excluded = _prepare_classification_data(df, target, reference_date)
    classes = sorted(pd.Series(y_raw).dropna().unique().tolist())
    if len(classes) < 3:
        raise ValueError(f"Multiclass classification requires ≥3 classes; found {len(classes)}.")
    class_to_int = {c: i for i, c in enumerate(classes)}; int_to_class = {i: c for c, i in class_to_int.items()}
    y = y_raw.map(class_to_int).astype(int); X = _build_fast_multiclass_features(X)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    base_model = XGBClassifier(n_estimators=400, learning_rate=.03, max_depth=4, subsample=.85, colsample_bytree=.85, objective="multi:softprob", num_class=len(classes), eval_metric="mlogloss", random_state=42, n_jobs=-1)
    oof_prob = np.zeros((len(y), len(classes)), dtype=float)
    for tr, va in cv.split(X, y):
        prep = _classification_preprocessor(X.iloc[tr]); Xtr = prep.fit_transform(X.iloc[tr]); Xva = prep.transform(X.iloc[va])
        model = clone(base_model); sw = compute_sample_weight(class_weight="balanced", y=y.iloc[tr]); model.fit(Xtr, y.iloc[tr], sample_weight=sw)
        prob = np.asarray(model.predict_proba(Xva), dtype=np.float64); prob = np.clip(prob, 1e-12, None); prob /= prob.sum(axis=1, keepdims=True); oof_prob[va] = prob
    pred = np.argmax(oof_prob, axis=1); top_sorted = np.sort(oof_prob, axis=1); confidence = top_sorted[:, -1]; margin = top_sorted[:, -1] - top_sorted[:, -2]
    accepted = (confidence >= confidence_min) & (margin >= margin_min)
    evidence = {
        "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y, pred, average="weighted", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "roc_auc_ovr_macro": float(roc_auc_score(y, oof_prob, multi_class="ovr", average="macro")),
        "log_loss": float(log_loss(y, oof_prob, labels=list(range(len(classes))))),
        "coverage": float(accepted.mean()), "abstention_rate": float(1 - accepted.mean()), "mean_confidence": float(confidence.mean()), "mean_margin": float(margin.mean())
    }
    if accepted.sum() > 0:
        evidence["selective_accuracy"] = float(np.mean(pred[accepted] == y.to_numpy()[accepted]))
        evidence["selective_macro_f1"] = float(f1_score(y.to_numpy()[accepted], pred[accepted], average="macro", zero_division=0))
    else:
        evidence["selective_accuracy"] = None; evidence["selective_macro_f1"] = None
    prep_full = _classification_preprocessor(X); Xfull = prep_full.fit_transform(X); model_full = clone(base_model); sw_full = compute_sample_weight(class_weight="balanced", y=y); model_full.fit(Xfull, y, sample_weight=sw_full)
    elapsed = time.perf_counter() - t0
    result = {
        "status": "COMPLETE", "route": "classification", "analysis_type": "multiclass", "target": target, "mode": "fast",
        "dataset": {"rows": int(len(y)), "columns": int(df.shape[1])},
        "method": {"architecture": policy["architecture"], "model": policy["model"], "calibration": policy["calibration"], "confidence_policy": {"confidence_min": confidence_min, "margin_min": margin_min}, "selection_source": policy["selection_source"]},
        "evidence": evidence, "warnings": [], "readiness": "FAST_EXECUTION_READY", "runtime_seconds": elapsed
    }
    artifacts = {"features": X.columns.tolist(), "excluded": excluded, "class_mapping": class_to_int, "inverse_class_mapping": int_to_class, "preprocessor": prep_full, "model": model_full, "oof_probability": oof_prob, "oof_prediction": pred, "confidence": confidence, "margin": margin, "accepted_mask": accepted}
    return result, artifacts
