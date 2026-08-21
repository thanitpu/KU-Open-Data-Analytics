import time
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import average_precision_score, roc_auc_score, precision_score, recall_score, f1_score, balanced_accuracy_score, confusion_matrix, brier_score_loss, log_loss
from sklearn.isotonic import IsotonicRegression
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

def _build_binary_parity_features(X):
    Z = X.copy()
    pairs = [
        ("MntMeatProducts", "NumCatalogPurchases"),
        ("MntWines", "NumCatalogPurchases"),
        ("Income", "MntWines"),
        ("MntWines", "MntMeatProducts"),
        ("Income", "MntMeatProducts")
    ]
    for a, b in pairs:
        if a in Z.columns and b in Z.columns:
            Z[f"{a}__x__{b}"] = pd.to_numeric(Z[a], errors="coerce") * pd.to_numeric(Z[b], errors="coerce")
    return Z

def _binary_parity_preprocessor(X):
    num = X.select_dtypes(include=np.number).columns.tolist()
    cat = [c for c in X.columns if c not in num]
    transformers = [("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), num)]
    if cat:
        transformers.append(("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), cat))
    return ColumnTransformer(transformers)

def run_fast_binary_parity(df, target, reference_date="2026-01-01", threshold=.30, outer_folds=5, inner_folds=3):
    t0 = time.perf_counter()
    if target not in df.columns:
        raise ValueError(f"Target '{target}' not found.")
    d = df[df[target].notna()].copy().reset_index(drop=True)
    y_raw = d[target].copy()
    classes = sorted(y_raw.unique().tolist())
    if len(classes) != 2:
        raise ValueError(f"Binary target must contain 2 classes; found {len(classes)}.")
    class_to_int = {classes[0]: 0, classes[1]: 1}
    y = y_raw.map(class_to_int).astype(int)
    exclude = _structural_exclusions(d, target) + [target]
    X = d.drop(columns=list(dict.fromkeys(exclude)), errors="ignore")
    X = _derive_customer_fields(X, reference_date)
    X = _build_binary_parity_features(X)
    base_model = XGBClassifier(n_estimators=500, learning_rate=.03, max_depth=4, subsample=.85, colsample_bytree=.85, objective="binary:logistic", eval_metric="logloss", random_state=42, n_jobs=-1)
    outer_cv = StratifiedKFold(n_splits=outer_folds, shuffle=True, random_state=42)
    oof_uncal = np.zeros(len(y), dtype=float)
    oof_cal = np.zeros(len(y), dtype=float)
    for fold, (tr, va) in enumerate(outer_cv.split(X, y), 1):
        Xtr, Xva = X.iloc[tr], X.iloc[va]
        ytr = y.iloc[tr]
        inner_cv = StratifiedKFold(n_splits=inner_folds, shuffle=True, random_state=100 + fold)
        inner_prob = np.zeros(len(tr), dtype=float)
        for itr, iva in inner_cv.split(Xtr, ytr):
            prep_inner = _binary_parity_preprocessor(Xtr.iloc[itr])
            A = prep_inner.fit_transform(Xtr.iloc[itr]); B = prep_inner.transform(Xtr.iloc[iva])
            model_inner = clone(base_model)
            sw = compute_sample_weight(class_weight="balanced", y=ytr.iloc[itr])
            model_inner.fit(A, ytr.iloc[itr], sample_weight=sw)
            inner_prob[iva] = model_inner.predict_proba(B)[:, 1]
        calibrator = IsotonicRegression(out_of_bounds="clip")
        calibrator.fit(inner_prob.astype(np.float64), ytr.to_numpy(dtype=np.float64))
        prep_outer = _binary_parity_preprocessor(Xtr)
        A = prep_outer.fit_transform(Xtr); B = prep_outer.transform(Xva)
        model_outer = clone(base_model)
        sw = compute_sample_weight(class_weight="balanced", y=ytr)
        model_outer.fit(A, ytr, sample_weight=sw)
        p = model_outer.predict_proba(B)[:, 1].astype(np.float64)
        oof_uncal[va] = p
        oof_cal[va] = calibrator.predict(p)
    oof_cal = np.clip(oof_cal, 0, 1)
    pred = (oof_cal >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    evidence = {
        "pr_auc": float(average_precision_score(y, oof_cal)),
        "roc_auc": float(roc_auc_score(y, oof_cal)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "brier": float(brier_score_loss(y, oof_cal)),
        "log_loss": float(log_loss(y, np.clip(oof_cal, 1e-8, 1-1e-8))),
        "threshold": float(threshold), "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)
    }
    full_cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    full_oof = np.zeros(len(y), dtype=float)
    for tr, va in full_cv.split(X, y):
        prep = _binary_parity_preprocessor(X.iloc[tr]); A = prep.fit_transform(X.iloc[tr]); B = prep.transform(X.iloc[va])
        model = clone(base_model); sw = compute_sample_weight(class_weight="balanced", y=y.iloc[tr])
        model.fit(A, y.iloc[tr], sample_weight=sw)
        full_oof[va] = model.predict_proba(B)[:, 1]
    final_calibrator = IsotonicRegression(out_of_bounds="clip")
    final_calibrator.fit(full_oof.astype(np.float64), y.to_numpy(dtype=np.float64))
    final_preprocessor = _binary_parity_preprocessor(X); Xfull = final_preprocessor.fit_transform(X)
    final_model = clone(base_model); sw = compute_sample_weight(class_weight="balanced", y=y)
    final_model.fit(Xfull, y, sample_weight=sw)
    elapsed = time.perf_counter() - t0
    result = {
        "status": "COMPLETE", "route": "classification", "analysis_type": "binary", "target": target, "mode": "fast",
        "dataset": {"rows": int(len(y)), "columns": int(df.shape[1])},
        "method": {"feature_engineering": "validated_binary_FE", "model": "XGBoost", "calibration": "Isotonic", "threshold_policy": "Balanced_F1", "threshold": float(threshold), "selection_source": "validated_deep_analysis"},
        "evidence": evidence, "warnings": [], "readiness": "FAST_PARITY_VALIDATED", "runtime_seconds": elapsed
    }
    artifacts = {"features": X.columns.tolist(), "excluded": exclude, "class_mapping": class_to_int, "preprocessor": final_preprocessor, "model": final_model, "calibrator": final_calibrator, "oof_uncalibrated_probability": oof_uncal, "oof_calibrated_probability": oof_cal, "oof_prediction": pred}
    return result, artifacts
