import time
import numpy as np
import pandas as pd
from scipy.stats import ttest_ind, f_oneway


def _clean_groups(df, target, group):
    if target not in df.columns:
        raise ValueError(f"Target '{target}' not found.")
    if group not in df.columns:
        raise ValueError(f"Grouping field '{group}' not found.")
    d = df[[target, group]].copy()
    d[target] = pd.to_numeric(d[target], errors='coerce')
    d = d.dropna(subset=[target, group])
    if d.empty:
        raise ValueError('No complete numeric outcome/group observations are available.')
    entries = [(str(name), g[target].to_numpy(dtype=float)) for name, g in d.groupby(group, observed=False)]
    entries = [(name, values) for name, values in entries if len(values) > 0]
    if len(entries) < 2:
        raise ValueError('Compare Groups requires at least two observed groups.')
    return d, entries


def _hedges_g(a, b):
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return np.nan
    s1, s2 = np.std(a, ddof=1), np.std(b, ddof=1)
    pooled = np.sqrt(((n1 - 1) * s1 ** 2 + (n2 - 1) * s2 ** 2) / (n1 + n2 - 2))
    if not np.isfinite(pooled) or pooled == 0:
        return np.nan
    d = (np.mean(a) - np.mean(b)) / pooled
    correction = 1 - 3 / (4 * (n1 + n2) - 9)
    return float(correction * d)


def _eta_squared(groups):
    all_values = np.concatenate(groups)
    grand = float(np.mean(all_values))
    ss_between = sum(len(g) * (float(np.mean(g)) - grand) ** 2 for g in groups)
    ss_total = float(np.sum((all_values - grand) ** 2))
    return float(ss_between / ss_total) if ss_total > 0 else np.nan


def run_fast_compare_groups(df, target, group):
    t0 = time.perf_counter()
    d, entries = _clean_groups(df, target, group)
    warnings = []
    summaries = [
        {'group': name, 'n': int(len(values)), 'mean': float(np.mean(values)), 'sd': float(np.std(values, ddof=1)) if len(values) > 1 else None}
        for name, values in entries
    ]
    if any(x['n'] < 2 for x in summaries):
        warnings.append('At least one group has fewer than two observations; inferential evidence may be unstable.')

    if len(entries) == 2:
        (name_a, a), (name_b, b) = entries
        if len(a) < 2 or len(b) < 2:
            raise ValueError('Welch t-test requires at least two observations in each group.')
        test = ttest_ind(a, b, equal_var=False, nan_policy='omit')
        v1, v2 = np.var(a, ddof=1) / len(a), np.var(b, ddof=1) / len(b)
        df_welch = (v1 + v2) ** 2 / ((v1 ** 2) / (len(a) - 1) + (v2 ** 2) / (len(b) - 1)) if (v1 + v2) > 0 else np.nan
        diff = float(np.mean(a) - np.mean(b))
        g = _hedges_g(a, b)
        evidence = {
            't': float(test.statistic), 'df': float(df_welch), 'p_value': float(test.pvalue),
            'mean_difference': diff, 'hedges_g': g, 'groups': 2, 'n_total': int(len(d))
        }
        findings = [{
            'relationship': f'{name_a} vs {name_b}',
            'interpretation': f'Mean difference = {diff:.3f}; Hedges g = {g:.3f}' if np.isfinite(g) else f'Mean difference = {diff:.3f}',
            'effect': float(abs(g)) if np.isfinite(g) else None
        }]
        method = {'test': 'Welch t-test', 'grouping_field': group, 'missing_policy': 'complete-case'}
        analysis_type = 'two_group_comparison'
    else:
        arrays = [values for _, values in entries]
        if any(len(a) < 2 for a in arrays):
            raise ValueError('One-way ANOVA requires at least two observations in each observed group.')
        test = f_oneway(*arrays)
        eta = _eta_squared(arrays)
        evidence = {
            'f': float(test.statistic), 'df_between': int(len(arrays) - 1), 'df_within': int(len(d) - len(arrays)),
            'p_value': float(test.pvalue), 'eta_squared': eta, 'groups': int(len(arrays)), 'n_total': int(len(d))
        }
        findings = [{
            'relationship': f'{x["group"]} group mean',
            'interpretation': f'N={x["n"]}, mean={x["mean"]:.3f}' + (f', SD={x["sd"]:.3f}' if x['sd'] is not None else '')
        } for x in summaries[:20]]
        method = {'test': 'One-way ANOVA', 'grouping_field': group, 'missing_policy': 'complete-case'}
        analysis_type = 'multi_group_comparison'

    result = {
        'status': 'COMPLETE', 'route': 'compare_groups', 'analysis_type': analysis_type,
        'target': target, 'mode': 'fast', 'dataset': {'rows': int(len(d)), 'columns': int(df.shape[1])},
        'method': method, 'evidence': evidence, 'findings': findings, 'group_summaries': summaries,
        'warnings': warnings, 'readiness': 'FAST_EXECUTION_READY', 'runtime_seconds': time.perf_counter() - t0
    }
    return result, {'group_summaries': summaries}
