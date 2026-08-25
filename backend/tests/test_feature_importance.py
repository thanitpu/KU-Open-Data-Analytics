import numpy as np
from analytics.shared import _top_model_importance


class DummyPreprocessor:
    def get_feature_names_out(self):
        return np.array(['num__Age', 'cat__Group_B', 'num__Income'])


class DummyModel:
    feature_importances_ = np.array([0.25, 0.60, 0.15])


def test_top_model_importance_uses_transformed_feature_names():
    findings = _top_model_importance(DummyPreprocessor(), DummyModel(), top_n=2)
    assert [x['relationship'] for x in findings] == ['Group_B', 'Age']
    assert findings[0]['importance'] == 0.60
    assert findings[0]['effect'] == 0.60
    assert 'Predictive model importance' in findings[0]['interpretation']
