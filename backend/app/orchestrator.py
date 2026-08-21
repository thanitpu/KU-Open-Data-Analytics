from analytics.segmentation import run_fast_segmentation
from analytics.regression import run_fast_regression
from analytics.classification_binary import run_fast_binary_parity
from analytics.classification_multiclass import run_fast_multiclass_classification
from analytics.exploratory import run_fast_exploratory
from analytics.association import run_fast_association
from analytics.policies import FAST_POLICY_REGISTRY

def execute_analysis(df, intent, target=None, mode='fast', options=None):
    key = str(intent).strip().lower()
    mode = str(mode).strip().lower()

    if mode != 'fast':
        raise NotImplementedError(
            "Package v0.1 exposes validated Fast mode only. "
            "Deep engines remain in the notebook research layer."
        )

    if key in {'customer segmentation', 'segmentation', 'clustering'}:
        return run_fast_segmentation(df)

    if key == 'regression':
        if target is None:
            raise ValueError("Regression requires target.")
        return run_fast_regression(df, target)

    if key in {'binary classification', 'multiclass classification', 'classification'}:
        if target is None:
            raise ValueError("Classification requires target.")

        if key == 'binary classification':
            subtype = 'binary'
        elif key == 'multiclass classification':
            subtype = 'multiclass'
        else:
            n = df[target].nunique(dropna=True)
            subtype = 'binary' if n == 2 else 'multiclass' if n >= 3 else None

        if subtype == 'binary':
            threshold = FAST_POLICY_REGISTRY['classification_binary']['threshold']
            return run_fast_binary_parity(df, target, threshold=threshold)

        if subtype == 'multiclass':
            return run_fast_multiclass_classification(df, target)

        raise ValueError("Unable to resolve classification subtype.")

    if key in {'exploratory data analysis', 'exploratory', 'eda'}:
        return run_fast_exploratory(df)

    if key in {'association analysis', 'association'}:
        return run_fast_association(df)

    raise ValueError(f"Unsupported intent: {intent}")
