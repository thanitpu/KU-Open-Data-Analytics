from analytics.policies import FAST_POLICY_REGISTRY
from intelligence.fe_recommender import ALLOWED_BROWSER_OPERATIONS


def get_capabilities():
    return {
        'service': {
            'version': '0.5.0',
            'mode': 'fast',
            'source': 'validated_backend',
        },
        'architecture': {
            'deterministic_feature_construction': 'browser when Browser FE Manifest v1 is supplied',
            'model_preprocessing': 'backend validation pipeline',
            'backward_compatibility': 'legacy backend deterministic FE retained only for clients without Browser FE Manifest v1',
        },
        'intelligence': {
            'feature_engineering': {
                'endpoint': '/recommend/feature-engineering',
                'input': 'Profile Manifest v1 aggregated metadata; row-level dataset not required',
                'recommender': 'rule_based_v1',
                'recommendation_execution': 'browser',
                'execution_contract': 'Browser FE Manifest v1 in /analyze options_json',
                'backend_contract_validation': 'lineage + allowed operation + source/output field + basic output type validation',
                'arbitrary_code_returned': False,
                'allowed_browser_operations': sorted(ALLOWED_BROWSER_OPERATIONS),
            },
            'text_analytics': {
                'engine_version': 'ku2a-semantic-engine-v1',
                'routes': ['/text-analytics/semantic-search', '/text-analytics/similar-documents', '/text-analytics/topics'],
                'default_engine': 'lsa-fallback',
                'transformer_enabled_by_api': False,
                'fallback_disclosure': 'LSA/TF-IDF fallback is never represented as transformer output',
            }
        },
        'routes': {
            'clustering': {
                'intent': 'Customer Segmentation', 'target_required': False,
                'policy': FAST_POLICY_REGISTRY['segmentation'],
                'preparation': {
                    'deterministic_features': 'browser-owned when manifest supplied',
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
                    'deterministic_features': 'browser-owned when manifest supplied; legacy R3 expansion only for clients without manifest',
                    'missing_numeric': 'median imputation inside CV', 'missing_categorical': 'most-frequent imputation inside CV',
                    'categorical_encoding': 'OneHotEncoder(handle_unknown=ignore) inside CV',
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
                    'deterministic_features': 'browser-owned when manifest supplied',
                    'missing_numeric': 'median imputation inside CV', 'missing_categorical': 'most-frequent imputation inside CV',
                    'categorical_encoding': 'OneHotEncoder(handle_unknown=ignore) inside CV', 'class_weighting': 'balanced sample weights'
                },
                'validation': 'Nested stratified out-of-fold calibration with 5 outer folds and 3 inner folds',
                'metrics': ['pr_auc', 'roc_auc', 'precision', 'recall', 'f1', 'balanced_accuracy', 'brier', 'log_loss']
            },
            'multiclass-classification': {
                'intent': 'Multiclass Classification', 'target_required': True,
                'policy': FAST_POLICY_REGISTRY['classification_multiclass'],
                'preparation': {
                    'deterministic_features': 'browser-owned when manifest supplied',
                    'missing_numeric': 'median imputation inside CV', 'missing_categorical': 'most-frequent imputation inside CV',
                    'categorical_encoding': 'OneHotEncoder(handle_unknown=ignore) inside CV', 'class_weighting': 'balanced sample weights'
                },
                'validation': '5-fold shuffled StratifiedKFold out-of-fold probabilities',
                'metrics': ['macro_f1', 'weighted_f1', 'balanced_accuracy', 'roc_auc_ovr_macro', 'log_loss', 'coverage', 'abstention_rate']
            },
            'association': {
                'intent': 'Association Analysis', 'target_required': False,
                'policy': {'multiple_testing': 'Benjamini-Hochberg FDR'},
                'preparation': {'deterministic_features': 'browser analytical matrix accepted after manifest validation', 'missing': 'pairwise complete observations', 'structural_fields': 'IDs/constants excluded'},
                'validation': 'FDR-adjusted relationship evidence',
                'metrics': ['tests_run', 'fdr_supported', 'practical_supported', 'redundancy_candidates']
            },
            'group-comparison': {
                'intent': 'Compare Groups', 'target_required': True, 'options_required': ['group'],
                'policy': {'two_groups': 'Welch t-test', 'three_or_more_groups': 'One-way ANOVA'},
                'preparation': {'deterministic_features': 'not used by current route', 'target': 'numeric coercion', 'missing': 'complete-case outcome/group observations'},
                'validation': 'Inferential group comparison selected by observed group count',
                'metrics': ['p_value', 'mean_difference', 'hedges_g', 'eta_squared']
            }
        }
    }
