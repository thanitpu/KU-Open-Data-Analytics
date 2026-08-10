# KU Open Data Analytics v0.5 — Statistical Validation

Reference implementations:
- SciPy for Chi-square
- Statsmodels OLS for Linear Regression

Acceptance tolerance: `1e-3` for displayed numeric outputs.

## Chi-square: Group3 × Satisfaction
- χ² = 0.750000
- df = 2
- p = 0.687289
- Cramér's V = 0.250000
- Minimum expected count = 1.333333
- Expected cells below 5 = 100.0%

## Simple regression: Score ~ Age
- N = 12
- R² = 0.000395
- Adjusted R² = -0.099566
- F = 0.003951
- p(F) = 0.951121
- RMSE = 6.880985
- const: B=85.679612, SE=24.152542, t=3.547437, p=0.005291, 95% CI [31.864395, 139.494828]
- Age: B=-0.066019, SE=1.050359, t=-0.062854, p=0.951121, 95% CI [-2.406365, 2.274326]

## Multiple regression: Score ~ Age + Pre
- N = 12
- R² = 0.396647
- Adjusted R² = 0.262568
- F = 2.958319
- p(F) = 0.102937
- RMSE = 5.635091
- const: B=51.181260, SE=24.342883, t=2.102514, p=0.064853, 95% CI [-3.886167, 106.248687]
- Age: B=-1.417296, SE=1.024121, t=-1.383914, p=0.199738, 95% CI [-3.734019, 0.899428]
- Pre: B=0.934104, SE=0.384215, t=2.431203, p=0.037908, 95% CI [0.064950, 1.803257]

## QA policy
- Chi-square uses complete pairs and warns when expected counts are sparse.
- Regression requires more complete observations than model parameters.
- Zero-variance outcomes and singular predictor matrices are rejected.
- High pairwise predictor correlation produces a collinearity warning.
- Residual plots and Q–Q plots are diagnostic aids, not proof of model adequacy.
