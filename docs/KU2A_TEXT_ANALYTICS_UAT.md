# KU2A Text Analytics concise UAT

## Local CSV path

1. Open `app.html` and choose **Import CSV/XLSX**.
2. Load `tests/fixtures/text-analytics/local-reviews.csv`.
3. Confirm the existing preview, Data Profile, and six-step navigation still work.
4. Open Data Profile → Text Analytics and select `review_text`.
5. Confirm document/language/quality metrics and terms/phrases appear without changing row count.
6. In Analyze choose `sentiment_label`, run the baseline, discover two topics, and run a search.
7. Navigate away and back; confirm selected fields and results remain.
8. In Prepare rename or exclude a topic. In Results export derived CSV and manifest. Confirm the source file itself is unchanged.

## KU2D asset path

1. Choose **Use Data from KU2D** and select `ku2d-approved-snapshot.json` plus `ku2d-draft-snapshot.json` from `tests/fixtures/text-analytics/`.
2. Confirm six rows load and the status says **inspectable only · not production-approved** because one asset is draft.
3. Confirm both `data_asset_id` values, provenance, acquired timestamps, and effective timestamps remain visible in application state/export lineage; acquired and effective timestamps must not be collapsed.
4. Repeat with only the approved snapshot and confirm it reports production-approved input status. This describes the input contract only; it does not authorize KU2A model deployment or KU2B inference.
5. Corrupt `record_count`, duplicate an identity within one snapshot, or change a field type in one of two snapshots. Confirm import is rejected with a readable diagnostic and the previous dataset is not replaced.

## Semantic disclosure

1. Run browser retrieval and confirm it is labelled **browser lexical fallback**, not transformer output.
2. Call the local backend semantic endpoint and confirm its engine metadata says `lsa-fallback`, `semantic: false`, and `fallback: true`.
