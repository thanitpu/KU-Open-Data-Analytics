import pandas as pd
from app.orchestrator import execute_analysis

def test_segmentation_smoke():
    df = pd.DataFrame({
        'Income': [20, 22, 21, 80, 85, 82],
        'MntWines': [1, 2, 1, 20, 22, 21],
        'NumStorePurchases': [1, 1, 2, 8, 9, 8],
    })
    result, artifacts = execute_analysis(
        df, intent='Customer Segmentation', mode='fast'
    )
    assert result['status'] == 'COMPLETE'
    assert result['route'] == 'segmentation'
