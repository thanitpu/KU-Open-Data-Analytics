# KU Open Data Analytics v0.3 — Statistical Validation Pack

Use `validation_dataset_v0.3.csv` as the input dataset.

All expected values below were computed with SciPy and should match KU Open Data Analytics within normal floating-point rounding tolerance.

## 1. One-sample t-test
- Variable: `Score`
- Test value: `80`
- N: 12
- Mean: 84.166667
- SD: 6.562058
- t: 2.199578
- df: 11
- p (two-sided): 0.050123

## 2. Welch independent-samples t-test
- Outcome: `Score`
- Group: `Group2`
- Group A: N=6, Mean=80.333333, SD=5.715476
- Group B: N=6, Mean=88.000000, SD=5.176872
- Welch t: -2.435260
- df: 9.903611
- p (two-sided): 0.035352

## 3. Paired-samples t-test
- Variable 1: `Post`
- Variable 2: `Pre`
- Complete pairs: 12
- Mean difference (Post - Pre): 3.916667
- SD difference: 0.900337
- t: 15.069620
- df: 11
- p (two-sided): 0.000000

## 4. One-way ANOVA
- Outcome: `Score`
- Group: `Group3`
- F: 2.688870
- df between: 2
- df within: 9
- p: 0.121474
- eta squared: 0.374032

## 5. Pearson correlation
- X: `Score`
- Y: `Age`
- N: 12
- r: -0.019872
- p (two-sided): 0.951121

## 6. Spearman correlation
- X: `Score`
- Y: `Age`
- N: 12
- rho: -0.067258
- p (two-sided): 0.835478

## Acceptance tolerance

For v0.3 manual QA, accept a result when:
- reported N/df exactly match;
- means and SDs differ by no more than `1e-3`;
- t/F/r/rho/eta² differ by no more than `1e-3`;
- p-values differ by no more than `1e-3`.

If a procedure fails these tolerances, do not merge until the calculation is reviewed.
