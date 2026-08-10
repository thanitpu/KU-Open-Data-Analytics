# Architecture Notes

KU Open Data Analytics will evolve from the v0.1 single-file prototype toward four separable layers:

1. **Data Engine** — import, parsing, type inference, metadata, missing data.
2. **Statistical Engine** — pure statistical functions with no UI dependency.
3. **Visualization Engine** — plots and statistical graphics.
4. **Interpretation & Learning Engine** — assumptions, analysis recommendations, explanations.

## Design rule

Statistical calculations must be deterministic, independently testable, and separated from presentation code.

## Validation rule

Every statistical procedure added to the application should include reference test cases whose results are compared with a trusted implementation such as R, SciPy/statsmodels, or another established statistical package.
