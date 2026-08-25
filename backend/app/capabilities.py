from analytics.policies import FAST_POLICY_REGISTRY


def get_capabilities():
    return {
        'service': {
            'version': '0.3.0',
            'mode': 'fast',
            'source': 'validated_backend',
        },
        'routes': {
            'clustering': {
                'intent': 'Customer Segmentation', 'target_required': False,
                'policy': FAST_POLICY_REGISTRY['segmentation'],
                'preparation': {
                    'input': 'numeric fields', 'missing_numeric': 'median imputation',
                    'scaling': 'StandardScaler', 'representation': 'PCA retaining 90% variance'
                },
                'validation': 'Silhouette, Calinski-Harabasz, Davies-Bouldin',
                'metrics': ['silhouette', 'calinski_harabasz', 'davies_bouldin', 'pca_variance']
            },
            'regression': {
                'intent': 'Regression', 'target_required': True,
                'policy': FAST_POLICY_REGISTRY['regression'],
                'preparation': {
                    'missing_numeric': 'median imputation', 'missing_categorical': 'most-frequent imputation',
                    'categorical_encoding': 'OneHotEncoder(handle_unknown=ignore)',
                    'target': 'numeric target or recognized ordered text target; missing target rows removed',
                    'recognized_ordinal_targets': [
                        'Low < Medium < High',
                        'Poor < Fair < Good < Very Good < Excellent',
                        'Strongly disagree < Disagree < Neutral < Agree < Strongly agree',
                    ],
                },
                'validation': '5-fold shuffled KFold out-of-fold prediction',
                'metrics': ['mae', 'rmse', 'r2', 'tail_mae', 'tail_bias']
            },
            'binary-classification': {
                'intent': 'Binary Classification', 'target_required': True,
                'policy': FAST_POLICY_REGISTRY['classification_binary'],
                'preparation': {
                    'missing_numeric': 'median imputation', 'missing_categorical': 'most-frequent imputation',
                    'categorical_encoding': 'OneHotEncoder(handle_unknown=ignore)', 'class_weighting': 'balanced sample weights'
                },
                'validation': 'Nested stratified out-of-fold calibration with 5 outer folds and 3 inner folds',
                'metrics': ['pr_auc', 'roc_auc', 'precision', 'recall', 'f1', 'balanced_accuracy', 'brier', 'log_loss']
            },
            'multiclass-classification': {
                'intent': 'Multiclass Classification', 'target_required': True,
                'policy': FAST_POLICY_REGISTRY['classification_multiclass'],
                'preparation': {
                    'missing_numeric': 'median imputation', 'missing_categorical': 'most-frequent imputation',
                    'categorical_encoding': 'OneHotEncoder(handle_unknown=ignore)', 'class_weighting': 'balanced sample weights'
                },
                'validation': '5-fold shuffled StratifiedKFold out-of-fold probabilities',
                'metrics': ['macro_f1', 'weighted_f1', 'balanced_accuracy', 'roc_auc_ovr_macro', 'log_loss', 'coverage', 'abstention_rate']
            },
            'association': {
                'intent': 'Association Analysis', 'target_required': False,
                'policy': {'multiple_testing': 'Benjamini-Hochberg FDR'},
                'preparation': {'missing': 'pairwise complete observations', 'structural_fields': 'IDs/constants excluded'},
                'validation': 'FDR-adjusted relationship evidence',
                'metrics': ['tests_run', 'fdr_supported', 'practical_supported', 'redundancy_candidates']
            },
            'group-comparison': {
                'intent': 'Compare Groups', 'target_required': True, 'options_required': ['group'],
                'policy': {'two_groups': 'Welch t-test', 'three_or_more_groups': 'One-way ANOVA'},
                'preparation': {'target': 'numeric coercion', 'missing': 'complete-case outcome/group observations'},
                'validation': 'Inferential group comparison selected by observed group count',
                'metrics': ['p_value', 'mean_difference', 'hedges_g', 'eta_squared']
            }
        }
    }
