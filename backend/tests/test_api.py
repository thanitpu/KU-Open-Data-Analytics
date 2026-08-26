import io
import json
import pandas as pd
from fastapi.testclient import TestClient
from app.api import app

client = TestClient(app)


def _csv_file(df):
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return ('dataset.csv', buf.getvalue().encode('utf-8'), 'text/csv')


def test_health():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'


def test_github_pages_cors_preflight():
    r = client.options(
        '/capabilities',
        headers={
            'Origin': 'https://thanitpu.github.io',
            'Access-Control-Request-Method': 'GET',
        },
    )
    assert r.status_code == 200
    assert r.headers['access-control-allow-origin'] == 'https://thanitpu.github.io'
    assert 'GET' in r.headers['access-control-allow-methods']


def test_capabilities():
    r = client.get('/capabilities')
    assert r.status_code == 200
    payload = r.json()
    assert payload['service']['version'] == '0.5.0'
    assert payload['service']['mode'] == 'fast'
    assert payload['routes']['regression']['policy']['model'] == 'XGBoost'
    assert payload['routes']['group-comparison']['intent'] == 'Compare Groups'
    assert payload['intelligence']['feature_engineering']['endpoint'] == '/recommend/feature-engineering'
    assert payload['intelligence']['feature_engineering']['recommendation_execution'] == 'browser'
    assert payload['intelligence']['feature_engineering']['execution_contract'] == 'Browser FE Manifest v1 in /analyze options_json'
    assert payload['architecture']['model_preprocessing'] == 'backend validation pipeline'


def test_segmentation_endpoint():
    df = pd.DataFrame({
        'Income':[20,22,21,80,85,82],
        'MntWines':[1,2,1,20,22,21],
        'NumStorePurchases':[1,1,2,8,9,8],
    })
    r = client.post(
        '/analyze',
        files={'file': _csv_file(df)},
        data={'intent':'Customer Segmentation','mode':'fast'}
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload['result']['route'] == 'segmentation'
    assert payload['result']['status'] == 'COMPLETE'
    assert payload['result']['preparation']['legacy_backend_feature_engineering'] is True


def test_compare_groups_endpoint():
    df = pd.DataFrame({'Group':['A','A','A','B','B','B'],'Score':[1,2,3,7,8,9]})
    r = client.post(
        '/analyze',
        files={'file': _csv_file(df)},
        data={'intent':'Compare Groups','target':'Score','mode':'fast','options_json':json.dumps({'group':'Group'})}
    )
    assert r.status_code == 200
    payload = r.json()['result']
    assert payload['route'] == 'compare_groups'
    assert payload['method']['test'] == 'Welch t-test'
    assert payload['method']['grouping_field'] == 'Group'
    assert payload['evidence']['groups'] == 2
