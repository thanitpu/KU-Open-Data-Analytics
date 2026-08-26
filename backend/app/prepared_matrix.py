import pandas as pd

ALLOWED_BROWSER_FE_OPERATIONS = {
    'reference_year_minus',
    'date_difference',
    'extract_month',
    'extract_day_of_week',
    'log1p',
    'row_sum',
    'group_rare_categories',
    'product',
}

_NUMERIC_OUTPUT_OPERATIONS = {
    'reference_year_minus',
    'date_difference',
    'extract_month',
    'extract_day_of_week',
    'log1p',
    'row_sum',
    'product',
}


def _unique_strings(values, label):
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f'{label} must be a list.')
    result = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'{label} must contain non-empty strings.')
        value = value.strip()
        if value in result:
            raise ValueError(f'{label} contains duplicate value: {value}.')
        result.append(value)
    return result


def validate_browser_feature_engineering(df, options=None, target=None):
    """Validate the browser-prepared analytical matrix contract.

    This is structural/semantic validation, not re-execution of browser FE. The
    backend deliberately avoids recomputing deterministic FE row-by-row; it
    verifies lineage, allowed operations, source/output columns and basic output
    type expectations before model execution.
    """
    options = options or {}
    manifest = options.get('browser_feature_engineering')
    if manifest is None:
        return {
            'provided': False,
            'applied': False,
            'contract': None,
            'deterministic_feature_owner': 'backend_legacy_compatibility',
            'model_preprocessing_owner': 'backend_cv_pipeline',
            'legacy_backend_feature_engineering': True,
            'derived_fields': [],
            'lineage': [],
        }
    if not isinstance(manifest, dict):
        raise ValueError('options.browser_feature_engineering must be an object.')
    if str(manifest.get('schema_version') or '') != '1.0':
        raise ValueError('Unsupported browser feature engineering schema_version; expected 1.0.')

    derived = _unique_strings(manifest.get('derived_fields'), 'browser_feature_engineering.derived_fields')
    lineage = manifest.get('lineage') or []
    if not isinstance(lineage, list):
        raise ValueError('browser_feature_engineering.lineage must be a list.')
    applied = bool(manifest.get('applied'))
    if applied != bool(derived):
        raise ValueError('browser_feature_engineering.applied must match whether derived_fields are present.')
    if len(lineage) != len(derived):
        raise ValueError('browser_feature_engineering.lineage must contain one entry per derived field.')

    lineage_outputs = []
    normalized_lineage = []
    for index, item in enumerate(lineage, 1):
        if not isinstance(item, dict):
            raise ValueError(f'Feature lineage entry {index} must be an object.')
        output = str(item.get('output_field') or '').strip()
        if not output:
            raise ValueError(f'Feature lineage entry {index} is missing output_field.')
        if output in lineage_outputs:
            raise ValueError(f'Duplicate feature lineage output_field: {output}.')
        lineage_outputs.append(output)
        operation = str(item.get('operation') or '').strip()
        if operation not in ALLOWED_BROWSER_FE_OPERATIONS:
            raise ValueError(f'Unsupported browser FE operation in lineage: {operation}.')
        sources = _unique_strings(item.get('source_fields'), f'lineage[{index}].source_fields')
        if not sources:
            raise ValueError(f'Feature lineage entry {index} must have at least one source field.')
        if output == target:
            raise ValueError('Browser feature engineering may not overwrite the analysis target.')
        missing_sources = [name for name in sources if name not in df.columns]
        if missing_sources:
            raise ValueError(f'Feature lineage source field(s) missing from analytical matrix: {", ".join(missing_sources)}.')
        if output not in df.columns:
            raise ValueError(f'Derived field declared by browser lineage is missing from analytical matrix: {output}.')
        if operation in _NUMERIC_OUTPUT_OPERATIONS and len(df):
            numeric = pd.to_numeric(df[output], errors='coerce')
            if int(numeric.notna().sum()) == 0:
                raise ValueError(f'Derived field {output} must contain numeric values for operation {operation}.')
        normalized_lineage.append({
            'id': item.get('id'),
            'output_field': output,
            'source_fields': sources,
            'operation': operation,
            'parameters': item.get('parameters') if isinstance(item.get('parameters'), dict) else {},
            'reason': item.get('reason'),
            'basis': item.get('basis') if isinstance(item.get('basis'), list) else [],
            'confidence': item.get('confidence'),
            'recommended_by': item.get('recommended_by') or 'KU Analytical Intelligence',
            'executed_by': item.get('executed_by') or 'browser',
            'executor_version': item.get('executor_version') or manifest.get('executor_version'),
        })

    if set(lineage_outputs) != set(derived):
        raise ValueError('browser_feature_engineering.derived_fields must match lineage output_field values.')

    return {
        'provided': True,
        'applied': applied,
        'contract': 'browser_feature_engineering_v1',
        'schema_version': '1.0',
        'executor_version': manifest.get('executor_version'),
        'reviewed': bool(manifest.get('reviewed', True)),
        'review_status': manifest.get('review_status'),
        'deterministic_feature_owner': 'browser',
        'model_preprocessing_owner': 'backend_cv_pipeline',
        'legacy_backend_feature_engineering': False,
        'derived_fields': derived,
        'lineage': normalized_lineage,
    }


def preparation_summary(context):
    return {
        'contract': context.get('contract'),
        'browser_fe_manifest_received': bool(context.get('provided')),
        'browser_fe_applied': bool(context.get('applied')),
        'derived_fields': list(context.get('derived_fields') or []),
        'feature_lineage': list(context.get('lineage') or []),
        'deterministic_feature_owner': context.get('deterministic_feature_owner'),
        'model_preprocessing_owner': context.get('model_preprocessing_owner'),
        'legacy_backend_feature_engineering': bool(context.get('legacy_backend_feature_engineering')),
    }
