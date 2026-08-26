from fastapi.testclient import TestClient
from app.api import app
from intelligence.fe_recommender import ALLOWED_BROWSER_OPERATIONS

client = TestClient(app)


def _field(name, storage='numeric', role='predictor', **profile):
    return {
        'name': name,
        'storage_type': storage,
        'measurement_level': 'Scale' if storage == 'numeric' else 'Nominal',
        'role': role,
        'profile': {'n': 100, 'missing_pct': 0, 'unique': 80, **profile},
    }


def test_profile_only_feature_engineering_recommendation():
    payload = {
        'schema_version': '1.0',
        'reference_date': '2026-08-26',
        'analysis_intent': {
            'question_type': 'predict-outcome',
            'target': 'Response',
            'analytical_family': 'Binary Classification',
        },
        'dataset_profile': {'rows': 100, 'fields': 6},
        'fields': [
            _field('Birth_Year', min=1940, max=2000, skewness=-0.2),
            _field('Income', min=0, max=600000, skewness=3.2),
            _field('MntWines', min=0, max=1000, skewness=1.0),
            _field('MntMeatProducts', min=0, max=1200, skewness=1.1),
            _field('Response', storage='text', role='target', unique=2),
            {
                'name': 'Dt_Customer', 'storage_type': 'text', 'measurement_level': 'Nominal', 'role': 'predictor',
                'profile': {'n': 100, 'missing_pct': 0, 'unique': 80},
                'temporal': {'detected': True, 'unique_timestamps': 80, 'granularity': 'daily'},
            },
        ],
    }
    response = client.post('/recommend/feature-engineering', json=payload)
    assert response.status_code == 200
    body = response.json()
    operations = {x['operation'] for x in body['recommendations']}
    outputs = {x['output_field'] for x in body['recommendations']}
    assert 'reference_year_minus' in operations
    assert 'log1p' in operations
    assert 'row_sum' in operations
    assert 'Age' in outputs
    assert 'Income_log1p' in outputs
    assert 'Total_Spend' in outputs
    assert 'Customer_Tenure_Days' in outputs
    assert all(x['operation'] in ALLOWED_BROWSER_OPERATIONS for x in body['recommendations'])
    assert all(x['execution'] == 'browser' for x in body['recommendations'])
    assert body['recommender_version'] == 'rule_based_v1'
    assert 'customer_analytics' in body['domain_hints']


def test_target_is_not_transformed_by_default():
    payload = {
        'analysis_intent': {'question_type': 'predict-outcome', 'target': 'Income'},
        'dataset_profile': {'rows': 100, 'fields': 1},
        'fields': [_field('Income', role='target', min=0, max=600000, skewness=4.0)],
    }
    response = client.post('/recommend/feature-engineering', json=payload)
    assert response.status_code == 200
    assert response.json()['recommendations'] == []
