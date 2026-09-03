# Statistical validation tests

Each statistical procedure should have:

- a small deterministic input dataset;
- expected statistics to adequate precision;
- edge-case tests;
- missing-data behavior tests;
- comparison against a trusted reference implementation.

Initial targets:
- mean
- sample standard deviation
- quantiles
- t statistics
- F statistics
- p-values
# KU2D intake and Text Analytics

- `ku2d_data_asset_smoke.js` validates single/multi-snapshot Trusted Data Asset contracts, approval, schema, count, identity, provenance, timestamps, and row storage types.
- `ku2d_intake_browser_smoke.js` validates the separate multi-file UI intake and atomic rejection behavior.
- `text_analytics_smoke.js` covers deterministic profile, terms/phrases, supervised sentiment, topics, Topic × Sentiment, retrieval, curation, derived features, and state persistence.
- `text_analytics_browser_smoke.js` covers progressive UI wiring and preservation across journey navigation.
- `backend/tests/test_text_analytics.py` validates the versioned semantic backend and explicit LSA/non-transformer disclosure.
