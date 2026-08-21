import time
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, chi2_contingency, kruskal
from statsmodels.stats.multitest import multipletests

def _prepare_unsupervised_fields(df):
    x = df.copy()
    ids = [c for c in x.columns if c.lower() in {"id", "customer_id", "row_id", "index"}]
    constants = [c for c in x.columns if x[c].nunique(dropna=False) <= 1]
    exclude = list(dict.fromkeys(ids + constants)); x = x.drop(columns=exclude, errors="ignore")
    continuous, discrete, binary, categorical, datetime = [], [], [], [], []
    for c in x.columns:
        s = x[c]; n = s.nunique(dropna=True); name = c.lower()
        if s.dtype == "object" and any(k in name for k in ["date", "dt_", "_dt", "time", "timestamp"]):
            dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
            if dt.notna().mean() >= .80:
                datetime.append(c); continue
        if n == 2: binary.append(c)
        elif pd.api.types.is_numeric_dtype(s):
            if n <= 20: discrete.append(c)
            else: continuous.append(c)
        else: categorical.append(c)
    return {"df": x, "excluded": exclude, "continuous": continuous, "discrete": discrete, "binary": binary, "categorical": categorical, "datetime": datetime, "numeric_like": continuous + discrete, "categorical_like": binary + categorical}

def _cramers_v(tab):
    chi2, p, _, _ = chi2_contingency(tab, correction=False); n = tab.values.sum(); r, k = tab.shape
    if n <= 1 or min(r, k) < 2: return np.nan, p
    phi2 = chi2 / n; phi2c = max(0, phi2 - (k - 1) * (r - 1) / (n - 1)); rc = r - (r - 1) ** 2 / (n - 1); kc = k - (k - 1) ** 2 / (n - 1); den = min(rc - 1, kc - 1)
    return (np.sqrt(phi2c / den) if den > 0 else np.nan), p

def _epsilon_sq(groups):
    if len(groups) < 2: return np.nan
    n = sum(len(g) for g in groups); k = len(groups)
    if n <= k: return np.nan
    H = kruskal(*groups).statistic
    return max(0, (H - k + 1) / (n - k))

def _effect_label(v):
    if pd.isna(v): return "unknown"
    if v >= .70: return "very_strong"
    if v >= .50: return "strong"
    if v >= .30: return "moderate"
    if v >= .15: return "weak"
    return "very_weak"

def _compute_fast_associations(df):
    prep = _prepare_unsupervised_fields(df); x = prep["df"]; numeric = prep["numeric_like"]; categorical = prep["categorical_like"]; rows = []
    for i, a in enumerate(numeric):
        for b in numeric[i + 1:]:
            d = x[[a, b]].dropna()
            if len(d) < 10: continue
            rho, p = spearmanr(d[a], d[b]); rows.append({"field_1": a, "field_2": b, "pair_type": "numeric_numeric", "test": "Spearman", "effect": abs(rho), "signed_effect": rho, "direction": 1 if rho > 0 else -1 if rho < 0 else 0, "p_value": p})
    for i, a in enumerate(categorical):
        for b in categorical[i + 1:]:
            tab = pd.crosstab(x[a], x[b])
            if min(tab.shape) < 2: continue
            v, p = _cramers_v(tab); rows.append({"field_1": a, "field_2": b, "pair_type": "categorical_categorical", "test": "ChiSquare+CramersV", "effect": v, "signed_effect": np.nan, "direction": np.nan, "p_value": p})
    for a in categorical:
        for b in numeric:
            d = x[[a, b]].dropna(); groups = [g[b].values for _, g in d.groupby(a, observed=False) if len(g) >= 2]
            if len(groups) < 2: continue
            _, p = kruskal(*groups); eps = _epsilon_sq(groups); rows.append({"field_1": a, "field_2": b, "pair_type": "categorical_numeric", "test": "KruskalWallis+EpsilonSquared", "effect": eps, "signed_effect": np.nan, "direction": np.nan, "p_value": p})
    A = pd.DataFrame(rows)
    if len(A):
        reject, qvals, _, _ = multipletests(A["p_value"].fillna(1), alpha=.05, method="fdr_bh"); A["q_value"] = qvals; A["significant_fdr"] = reject; A["effect_label"] = A["effect"].map(_effect_label); A["evidence_score"] = A["effect"].fillna(0) * np.where(A["significant_fdr"], 1.0, .25); A = A.sort_values(["evidence_score", "effect"], ascending=False).reset_index(drop=True)
    supported = A[A["significant_fdr"] & (A["effect"] >= .15)].copy()
    return prep, A, supported

def run_fast_association(df):
    t0 = time.perf_counter(); prep, A, supported = _compute_fast_associations(df); top_findings = []
    for _, r in supported.head(10).iterrows():
        if r["pair_type"] == "numeric_numeric": interpretation = f"{'positive' if r['signed_effect'] > 0 else 'negative'} association (ρ={r['signed_effect']:.3f})"
        elif r["pair_type"] == "categorical_numeric": interpretation = f"group difference (ε²={r['effect']:.3f})"
        else: interpretation = f"categorical association (Cramér's V={r['effect']:.3f})"
        top_findings.append({"relationship": f"{r['field_1']} ↔ {r['field_2']}", "pair_type": r["pair_type"], "effect": float(r["effect"]), "q_value": float(r["q_value"]), "interpretation": interpretation})
    redundancy = A[(A["pair_type"] == "numeric_numeric") & A["significant_fdr"] & (A["effect"] >= .70)].copy(); recommendations = []
    if len(redundancy): recommendations.append({"analysis": "Redundancy / dimension reduction review", "reason": "Very strong FDR-supported numeric relationships were detected."})
    if len(supported): recommendations.append({"analysis": "Targeted predictive modeling", "reason": "Supported relationships may guide predictor and target selection."})
    elapsed = time.perf_counter() - t0
    result = {"status": "COMPLETE", "route": "association", "analysis_type": "association", "target": None, "mode": "fast", "dataset": {"rows": int(df.shape[0]), "columns": int(df.shape[1])}, "method": {"numeric_numeric": "Spearman", "categorical_categorical": "Chi-square + Cramer's V", "categorical_numeric": "Kruskal-Wallis + epsilon-squared", "multiple_testing": "Benjamini-Hochberg FDR"}, "evidence": {"tests_run": int(len(A)), "fdr_supported": int(A["significant_fdr"].sum()) if len(A) else 0, "practical_supported": int(len(supported)), "redundancy_candidates": int(len(redundancy))}, "findings": top_findings, "warnings": [], "recommendations": recommendations, "readiness": "FAST_EXECUTION_READY", "runtime_seconds": elapsed}
    artifacts = {"associations": A, "supported_associations": supported, "redundancy_candidates": redundancy, "excluded": prep["excluded"]}
    return result, artifacts
