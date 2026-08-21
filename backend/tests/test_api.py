import io
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
