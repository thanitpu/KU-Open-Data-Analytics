from analytics.segmentation import run_fast_segmentation
from analytics.regression import run_fast_regression
from analytics.classification_binary import run_fast_binary_parity
from analytics.classification_multiclass import run_fast_multiclass_classification
from analytics.exploratory import run_fast_exploratory
from analytics.association import run_fast_association
from analytics.compare_groups import run_fast_compare_groups
from analytics.policies import FAST_POLICY_REGISTRY
from .prepared_matrix import validate_browser_feature_engineering, preparation_summary


def _finish(output, feature_context):
    result, artifacts = output
    result['preparation'] = preparation_summary(feature_context)
    return result, artifacts


def execute_analysis(df, intent, target=None, mode='fast', options=None):
    key = str(intent).strip().lower()
    mode = str(mode).strip().lower()
    options = options or {}

    if mode != 'fast':
        raise NotImplementedError(
            "Package v0.1 exposes validated Fast mode only. "
            "Deep engines remain in the notebook research layer."
        )

    feature_context = validate_browser_feature_engineering(df, options, target=target)

    if key in {'customer segmentation', 'segmentation', 'clustering'}:
        return _finish(run_fast_segmentation(df, feature_context=feature_context), feature_context)

    if key == 'regression':
        if target is None:
            raise ValueError("Regression requires target.")
        return _finish(run_fast_regression(df, target, feature_context=feature_context), feature_context)

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
            return _finish(
                run_fast_binary_parity(
                    df, target, threshold=threshold, feature_context=feature_context
                ),
                feature_context,
            )

        if subtype == 'multiclass':
            return _finish(
                run_fast_multiclass_classification(
                    df, target, feature_context=feature_context
                ),
                feature_context,
            )

        raise ValueError("Unable to resolve classification subtype.")

    if key in {'compare groups', 'group comparison', 'compare-groups'}:
        if target is None:
            raise ValueError('Compare Groups requires target.')
        group = options.get('group')
        if not group:
            raise ValueError('Compare Groups requires options.group.')
        return _finish(run_fast_compare_groups(df, target, group), feature_context)

    if key in {'exploratory data analysis', 'exploratory', 'eda'}:
        return _finish(run_fast_exploratory(df), feature_context)

    if key in {'association analysis', 'association'}:
        return _finish(run_fast_association(df), feature_context)

    raise ValueError(f"Unsupported intent: {intent}")
