import pandas as pd

from analytics.regression import _build_fast_regression_features, _recognized_ordinal_target


def test_low_medium_high_target_is_rank_encoded():
    target = pd.Series(['Low', 'Medium', 'High', 'Low', 'High'])
    encoded, metadata = _recognized_ordinal_target(target)
    assert encoded.tolist() == [1.0, 2.0, 3.0, 1.0, 3.0]
    assert metadata['order'] == ['Low', 'Medium', 'High']
    assert metadata['mapping'] == {'Low': 1, 'Medium': 2, 'High': 3}


def test_unknown_text_order_is_not_guessed():
    target = pd.Series(['Bronze', 'Silver', 'Gold', 'Bronze', 'Gold'])
    encoded, metadata = _recognized_ordinal_target(target)
    assert encoded is None
    assert metadata is None


def test_regression_feature_builder_accepts_recognized_ordinal_target():
    df = pd.DataFrame({
        'Satisfaction': ['Low', 'Medium', 'High', 'Low', 'Medium', 'High'],
        'Age': [20, 21, 22, 23, 24, 25],
        'Region': ['A', 'A', 'B', 'B', 'C', 'C'],
    })
    X, y, excluded, encoding = _build_fast_regression_features(df, 'Satisfaction')
    assert y.tolist() == [1.0, 2.0, 3.0, 1.0, 2.0, 3.0]
    assert encoding['order'] == ['Low', 'Medium', 'High']
    assert 'Satisfaction' in excluded
    assert list(X.columns) == ['Age', 'Region']
