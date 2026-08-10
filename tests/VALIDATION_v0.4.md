# KU Open Data Analytics v0.4 — Extended Statistical Validation

Reference implementation: SciPy. Acceptance tolerance: 1e-3 unless noted.

## New v0.4 quantities
- One-sample mean difference: 4.166667; 95% CI [-0.002666, 8.335999]; Cohen's d = 0.634963
- Welch mean difference: -7.666667; 95% CI [-14.690540, -0.642793]; Hedges' g = -1.297845
- Paired mean difference: 3.916667; 95% CI [3.344620, 4.488713]; Cohen's dz = 4.350225
- ANOVA eta² = 0.374032; omega² = 0.219651
- Brown–Forsythe F = 0.267123; p = 0.771441
- Pearson r = -0.019872; Fisher 95% CI [-0.587078, 0.560421]

## Tukey HSD / Tukey–Kramer pairwise results
- A-B: diff=-7.750000, 95% CI [-19.081630, 3.581630], p_adj=0.191431
- A-C: diff=-8.500000, 95% CI [-19.831630, 2.831630], p_adj=0.145973
- B-C: diff=-0.750000, 95% CI [-12.081630, 10.581630], p_adj=0.981389

## QA policy
- Numeric statistics, effect sizes, CI bounds and p-values should agree within 1e-3.
- Plot rendering is visually inspected; plots are diagnostic aids, not formal normality tests.
- Brown–Forsythe is used as a variance-homogeneity diagnostic.
- Tukey–Kramer is appropriate for all pairwise comparisons after classical one-way ANOVA, including unequal group sizes.
