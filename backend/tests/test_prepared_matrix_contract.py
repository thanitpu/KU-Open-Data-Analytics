import json
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.prepared_matrix import validate_browser_feature_engineering
from analytics.regression import _build_fast_regression_features

client = TestClient(app)


def _browser_manifest(derived_fields=None, lineage=None, applied=None):
    derived_fields = derived_fields or []
    lineage = lineage or []
    if applied is None:
        applied = bool(derived_fields)
    return {
        'schema_version': '1.0',
        'executor_version': '1.0',
        'reviewed': True,
        'review_status': 'ready',
        'applied': applied,
        'derived_fields': derived_fields,
        'lineage': lineage,
    }


def test_browser_manifest_validates_lineage_without_reexecuting_fe():
    df = pd.DataFrame({
        'Year_Birth': [1980, 1990],
        'Age': [46, 36],
        'Target': [10, 20],
    })
    manifest = _browser_manifest(
        ['Age'],
        [{
            'id': 'fe_001',
            'output_field': 'Age',
            'source_fields': ['Year_Birth'],
            'operation': 'reference_year_minus',
            'parameters': {'reference_year': 2026},
            'recommended_by': 'KU Analytical Intelligence',
            'executed_by': 'browser',
            'executor_version': '1.0',
        }],
    )
    context = validate_browser_feature_engineering(
        df, {'browser_feature_engineering': manifest}, target='Target'
    )
    assert context['provided'] is True
    assert context['deterministic_feature_owner'] == 'browser'
    assert context['model_preprocessing_owner'] == 'backend_cv_pipeline'
    assert context['derived_fields'] == ['Age']


def test_invalid_manifest_missing_derived_column_is_rejected():
    df = pd.DataFrame({'Year_Birth': [1980, 1990], 'Target': [10, 20]})
    manifest = _browser_manifest(
        ['Age'],
        [{
            'output_field': 'Age',
            'source_fields': ['Year_Birth'],
            'operation': 'reference_year_minus',
        }],
    )
    with pytest.raises(ValueError, match='missing from analytical matrix'):
        validate_browser_feature_engineering(
            df, {'browser_feature_engineering': manifest}, target='Target'
        )


def test_browser_managed_regression_does_not_recreate_hidden_fe():
    rows = 12
    df = pd.DataFrame({
        'Year_Birth': [1980 + i for i in range(rows)],
        'Age': [46 - i for i in range(rows)],
        'Income': [1000 + i * 500 for i in range(rows)],
        'Income_log1p': [7.0 + i * .1 for i in range(rows)],
        'MntWines': [10 + i for i in range(rows)],
        'MntMeatProducts': [20 + i for i in range(rows)],
        'MntWines__x__MntMeatProducts': [(10 + i) * (20 + i) for i in range(rows)],
        'Target': [100 + i * 3 for i in range(rows)],
    })
    X, _, _, _ = _build_fast_regression_features(
        df, 'Target', browser_managed=True
    )
    assert 'Age' in X.columns
    assert 'Income_log1p' in X.columns
    assert 'MntWines__x__MntMeatProducts' in X.columns
    assert 'Customer_Age' not in X.columns
    assert 'Income_log1p__log1p' not in X.columns
    assert not any(c.endswith('__log1p') and c != 'Income_log1p' for c in X.columns)


def test_legacy_client_retains_backward_compatible_backend_fe():
    df = pd.DataFrame({
        'Year_Birth': [1980 + i for i in range(12)],
        'Income': [1000 + i * 500 for i in range(12)],
        'MntWines': [10 + i for i in range(12)],
        'MntMeatProducts': [20 + i for i in range(12)],
        'Target': [100 + i * 3 for i in range(12)],
    })
    X, _, _, _ = _build_fast_regression_features(
        df, 'Target', browser_managed=False
    )
    assert 'Customer_Age' in X.columns


def test_analyze_accepts_reviewed_empty_manifest_and_reports_ownership():
    csv = 'Group,Score\nA,10\nA,12\nA,11\nB,20\nB,22\nB,21\n'
    options = {
        'group': 'Group',
        'browser_feature_engineering': _browser_manifest([], [], applied=False),
    }
    response = client.post(
        '/analyze',
        files={'file': ('dataset.csv', csv, 'text/csv')},
        data={
            'intent': 'Compare Groups',
            'target': 'Score',
            'mode': 'fast',
            'options_json': json.dumps(options),
        },
    )
    assert response.status_code == 200
    preparation = response.json()['result']['preparation']
    assert preparation['browser_fe_manifest_received'] is True
    assert preparation['browser_fe_applied'] is False
    assert preparation['deterministic_feature_owner'] == 'browser'
    assert preparation['model_preprocessing_owner'] == 'backend_cv_pipeline'
    assert preparation['legacy_backend_feature_engineering'] is False
