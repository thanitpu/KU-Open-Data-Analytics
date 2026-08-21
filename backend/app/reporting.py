LABELS = {
    'feature_engineering': 'Feature engineering', 'selection_source': 'Selection source',
    'pca_dimensions': 'PCA dimensions', 'pca_variance': 'Variance retained',
    'calinski_harabasz': 'Calinski-Harabasz score', 'davies_bouldin': 'Davies-Bouldin score',
    'mae': 'Mean absolute error (MAE)', 'rmse': 'Root mean squared error (RMSE)', 'r2': 'R²',
    'tail_mae': 'High-value MAE', 'tail_bias': 'High-value prediction bias',
    'pr_auc': 'PR-AUC', 'roc_auc': 'ROC-AUC', 'f1': 'F1 score', 'precision': 'Precision',
    'recall': 'Recall', 'balanced_accuracy': 'Balanced accuracy', 'brier': 'Brier score',
    'log_loss': 'Log loss', 'macro_f1': 'Macro F1', 'weighted_f1': 'Weighted F1',
    'roc_auc_ovr_macro': 'Macro ROC-AUC (OvR)', 'coverage': 'Prediction coverage',
    'abstention_rate': 'Abstention rate', 'mean_confidence': 'Mean confidence',
    'mean_margin': 'Mean confidence margin', 'selective_accuracy': 'Selective accuracy',
    'selective_macro_f1': 'Selective macro F1', 'association_pairs': 'Association pairs tested',
    'fdr_supported': 'FDR-supported relationships', 'moderate_plus_pairs': 'Moderate+ relationships',
    'very_strong_numeric_pairs': 'Very strong numeric relationships', 'connected_fields': 'Connected fields',
    'tests_run': 'Tests run', 'practical_supported': 'Practically meaningful relationships',
    'redundancy_candidates': 'Redundancy candidates'
}

def _label(key):
    return LABELS.get(key, str(key).replace('_', ' ').strip().title())

def _fmt(value, key=None):
    if isinstance(value, bool): return 'Yes' if value else 'No'
    if isinstance(value, float):
        if key in {'coverage','abstention_rate','mean_confidence','mean_margin','pca_variance'} and 0 <= value <= 1:
            return f'{value*100:.1f}%'
        return f'{value:.4f}'
    return str(value)

def _finding_cards(findings, route):
    cards = []
    if isinstance(findings, dict):
        for segment, info in findings.items():
            if not isinstance(info, dict): continue
            pct = info.get('size_pct')
            cards.append({
                'title': f'Segment {int(segment)+1}' if str(segment).isdigit() else f'Segment {segment}',
                'subtitle': f'{pct:.1f}% of observations' if isinstance(pct, (int,float)) else None,
                'high': info.get('high', []), 'low': info.get('low', [])
            })
    elif isinstance(findings, list):
        for item in findings[:10]:
            if not isinstance(item, dict):
                cards.append({'title': str(item)}); continue
            cards.append({
                'title': item.get('relationship', 'Finding'),
                'subtitle': item.get('interpretation'),
                'effect': item.get('effect'),
                'q_value': item.get('q_value'),
                'pair_type': item.get('pair_type')
            })
    return cards

def build_executive_report(result):
    route = result.get('route')
    method = result.get('method', {})
    evidence = result.get('evidence', {})
    findings = result.get('findings', [])
    warnings = result.get('warnings', [])

    overview = [
        {'label':'Analysis','value':result.get('analysis_type') or route},
        {'label':'Target','value':result.get('target') or 'Not applicable'},
        {'label':'Status','value':result.get('status')},
        {'label':'Readiness','value':result.get('readiness')}
    ]
    method_rows = [{'label':_label(k),'value':_fmt(v,k)} for k,v in method.items()]
    evidence_rows = [{'label':_label(k),'value':_fmt(v,k),'raw_value':v} for k,v in evidence.items() if not isinstance(v,(dict,list))]
    finding_cards = _finding_cards(findings, route)

    lines = ['ANALYSIS OVERVIEW','-----------------']
    lines += [f"• {x['label']}: {x['value']}" for x in overview]
    lines += ['', 'SELECTED METHOD', '---------------']
    lines += [f"• {x['label']}: {x['value']}" for x in method_rows]
    lines += ['', 'KEY EVIDENCE', '------------']
    lines += [f"• {x['label']}: {x['value']}" for x in evidence_rows]
    if finding_cards:
        lines += ['', 'KEY FINDINGS', '------------']
        for c in finding_cards:
            line = f"• {c['title']}"
            if c.get('subtitle'): line += f" — {c['subtitle']}"
            if c.get('high'): line += f" | Higher: {', '.join(c['high'])}"
            if c.get('low'): line += f" | Lower: {', '.join(c['low'])}"
            lines.append(line)
    if warnings:
        lines += ['', 'WARNINGS / GUARDRAILS', '---------------------']
        lines += [f'• {x}' for x in warnings]

    return {
        'route': route, 'target': result.get('target'),
        'overview': overview, 'method': method_rows, 'evidence': evidence_rows,
        'findings': finding_cards, 'warnings': warnings,
        'text': '\n'.join(lines)
    }
