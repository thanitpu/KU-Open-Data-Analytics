import re
from datetime import date

ALLOWED_BROWSER_OPERATIONS = {
    'reference_year_minus',
    'date_difference',
    'extract_month',
    'extract_day_of_week',
    'log1p',
    'row_sum',
    'group_rare_categories',
}


def _norm(name):
    return re.sub(r'[^a-z0-9]+', '_', str(name or '').strip().lower()).strip('_')


def _is_target(field, target):
    return field.get('role') == 'target' or field.get('analysis_role') == 'target' or (target and field.get('name') == target)


def _selected_for_analysis(field):
    selected = field.get('selected_for_analysis')
    return selected is not False and field.get('analysis_role') != 'context'


def _is_numeric(field):
    return field.get('storage_type') == 'numeric'


def _reference_year(payload):
    raw = str(payload.get('reference_date') or '')
    if len(raw) >= 4 and raw[:4].isdigit():
        return int(raw[:4])
    return date.today().year


def _recommendation(operation, source_fields, output_field, reason, basis, confidence, parameters=None, category='feature_engineering'):
    if operation not in ALLOWED_BROWSER_OPERATIONS:
        raise ValueError(f'Unsupported browser operation: {operation}')
    return {
        'source_fields': list(source_fields),
        'output_field': output_field,
        'operation': operation,
        'parameters': parameters or {},
        'reason': reason,
        'basis': list(basis),
        'confidence': round(float(confidence), 3),
        'category': category,
        'execution': 'browser',
        'requires_user_review': True,
    }


def _domain_hints(fields):
    names = {_norm(f.get('name')) for f in fields}
    joined = ' '.join(names)
    hints = []
    if any(x in joined for x in ['customer', 'purchase', 'spend', 'income', 'mntwine', 'mntmeat']):
        hints.append('customer_analytics')
    if any(x in joined for x in ['product', 'sku', 'order', 'invoice', 'purchase', 'sales']):
        hints.append('retail_commerce')
    if any(x in joined for x in ['sensor', 'temperature', 'humidity', 'pressure']):
        hints.append('sensor_iot')
    return hints or ['general_tabular']


def recommend_features(payload):
    fields = payload.get('fields') or []
    intent = payload.get('analysis_intent') or {}
    target = intent.get('target')
    question = str(intent.get('question_type') or intent.get('analytical_family') or '').lower()
    ref_year = _reference_year(payload)
    ref_date = str(payload.get('reference_date') or f'{ref_year}-12-31')
    candidates = []

    for field in fields:
        name = field.get('name')
        if not name or _is_target(field, target) or not _selected_for_analysis(field):
            continue
        norm = _norm(name)
        profile = field.get('profile') or {}
        distribution = field.get('distribution') or {}
        frequency = field.get('frequency') or {}
        temporal = field.get('temporal') or {}

        birth_year = norm in {'birth_year', 'year_birth', 'yearbirth', 'yob'} or ('birth' in norm and 'year' in norm)
        if birth_year and _is_numeric(field):
            candidates.append(_recommendation(
                'reference_year_minus', [name], 'Age',
                f'{name} appears to represent year of birth; age is usually more directly interpretable for {intent.get("question_type") or "the selected analysis"}.',
                ['field_semantics', 'domain_knowledge', 'analysis_objective'], .96,
                {'reference_year': ref_year}
            ))

        if temporal.get('detected'):
            tenure_semantic = any(token in norm for token in ['customer', 'join', 'joined', 'register', 'signup', 'enroll', 'start', 'acquired'])
            if tenure_semantic:
                output = 'Customer_Tenure_Days' if 'customer' in norm else f'{name}_Tenure_Days'
                candidates.append(_recommendation(
                    'date_difference', [name], output,
                    f'{name} is a temporal field with tenure-like semantics; elapsed time is often more useful than the raw date.',
                    ['field_semantics', 'temporal_profile', 'domain_knowledge'], .9,
                    {'reference_date': ref_date, 'direction': 'reference_minus_source'}
                ))
            if 'time' not in question and temporal.get('unique_timestamps', 0) >= 4:
                candidates.append(_recommendation(
                    'extract_month', [name], f'{name}_Month',
                    f'{name} contains repeated temporal observations; month may capture calendar or seasonal structure.',
                    ['temporal_profile', 'analysis_objective'], .7
                ))
                candidates.append(_recommendation(
                    'extract_day_of_week', [name], f'{name}_DayOfWeek',
                    f'{name} contains repeated temporal observations; day-of-week may capture recurring behavioral patterns.',
                    ['temporal_profile', 'analysis_objective'], .66
                ))

        if _is_numeric(field):
            skew = profile.get('skewness')
            min_value = profile.get('min')
            unique = profile.get('unique', 0)
            if isinstance(skew, (int, float)) and skew >= 1.5 and isinstance(min_value, (int, float)) and min_value >= 0 and unique > 10:
                confidence = min(.95, .72 + min(abs(skew), 5) * .04)
                candidates.append(_recommendation(
                    'log1p', [name], f'{name}_log1p',
                    f'{name} shows substantial positive skew (skewness {skew:.2f}); a log1p feature can reduce scale compression while preserving zero values.',
                    ['distribution_profile', 'analysis_objective'], confidence
                ))

        rare_pct = frequency.get('rare_observation_pct')
        unique = profile.get('unique', 0)
        if isinstance(rare_pct, (int, float)) and rare_pct >= 10 and 6 <= unique <= 100 and not frequency.get('redacted'):
            candidates.append(_recommendation(
                'group_rare_categories', [name], f'{name}_Grouped',
                f'{name} has {rare_pct:.1f}% of observations in rare levels; grouping rare levels can reduce sparse-category noise.',
                ['frequency_profile', 'analysis_objective'], .74,
                {'rare_threshold_pct': 1.0, 'replacement': 'Other'}
            ))

    selected_fields = [f for f in fields if _selected_for_analysis(f) and not _is_target(f, target)]
    spend_fields = [f['name'] for f in selected_fields if _is_numeric(f) and (re.match(r'^mnt', _norm(f.get('name'))) or 'spend' in _norm(f.get('name')))]
    if 2 <= len(spend_fields) <= 12:
        candidates.append(_recommendation(
            'row_sum', spend_fields, 'Total_Spend',
            'Several selected numeric fields appear to represent spending components; an aggregate can capture overall spending intensity while retaining the original components.',
            ['field_semantics', 'domain_knowledge', 'analysis_objective'], .82
        ))

    purchase_fields = [f['name'] for f in selected_fields if _is_numeric(f) and ('purchase' in _norm(f.get('name')) and any(t in _norm(f.get('name')) for t in ['num', 'count', 'purchases']))]
    if 2 <= len(purchase_fields) <= 10:
        candidates.append(_recommendation(
            'row_sum', purchase_fields, 'Total_Purchases',
            'Multiple selected purchase-count fields were detected; their total can summarize overall purchase activity across channels.',
            ['field_semantics', 'domain_knowledge', 'analysis_objective'], .8
        ))

    deduped = {}
    for item in candidates:
        key = (item['operation'], tuple(item['source_fields']), item['output_field'])
        if key not in deduped or item['confidence'] > deduped[key]['confidence']:
            deduped[key] = item
    ordered = sorted(deduped.values(), key=lambda x: (-x['confidence'], x['operation'], x['output_field'] or ''))
    for i, item in enumerate(ordered, 1):
        item['id'] = f'fe_{i:03d}'

    return {
        'schema_version': '1.0',
        'recommender_version': 'rule_based_v1',
        'domain_hints': _domain_hints(fields),
        'recommendations': ordered,
        'warnings': [
            'Recommendations are advisory and must be reviewed before browser execution.',
            'This version uses curated rules only; external Kaggle/knowledge retrieval is not enabled yet.',
        ],
    }
