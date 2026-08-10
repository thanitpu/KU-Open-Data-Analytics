# KU Open Data Analytics

**KU Open Data Analytics** is a free, browser-based data analytics and statistics platform intended for education, research, and general-purpose exploratory analysis.

> Working prototype: v0.1

## Project goals

- Make statistical analysis accessible through a clear browser-based workflow.
- Keep user datasets local to the browser whenever practical.
- Help users understand *why* an analysis is appropriate, not only produce output.
- Build statistical functions as independently testable modules.
- Support teaching with assumption checks, interpretation guidance, and transparent calculations.

## Current prototype (v0.1)

- CSV import
- Drag-and-drop CSV
- Paste comma/tab-separated data
- Data preview
- Automatic numeric/categorical type inference
- Dataset overview
- Descriptive statistics
- Histogram
- Basic Analysis Advisor

## Planned roadmap

### v0.2 — Data Workspace
- XLSX import
- Variable View
- Measurement levels: Nominal / Ordinal / Scale
- Variable labels and value labels
- Missing-value definitions and handling
- Data Quality Summary

### v0.3 — Core statistical analysis
- Frequency tables
- Descriptive statistics
- Explore / visualization
- One-sample t-test
- Independent-samples t-test
- Paired-samples t-test
- One-way ANOVA
- Correlation

### Later
- Chi-square
- Non-parametric tests
- Linear and logistic regression
- Reliability analysis
- PCA / factor analysis
- Clustering
- SPC
- Power and sample-size tools

## Architecture direction

```text
src/
├── data/             # import, parsing, variable metadata
├── statistics/       # statistical calculations
├── visualization/    # charts and plots
└── advisor/          # analysis recommendation logic
```

The statistical engine should remain independent from UI code so calculations can be unit-tested against trusted reference implementations.

## Privacy principle

The project is designed around client-side processing where feasible. Dataset contents should not be uploaded to a server unless a future feature explicitly requires it and clearly informs the user.

## Development status

This repository structure is the baseline for moving from a single-file prototype toward a modular application.

## License

MIT License. See `LICENSE`.

## Disclaimer

This project is under active development. Statistical results should be independently validated before use in high-stakes research, clinical, legal, financial, or regulatory decisions.
