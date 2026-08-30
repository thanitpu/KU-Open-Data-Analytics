from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "acquisition"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import retail_assigned_acquisition as router

assignments = [
    {
        "technique": "generic_retail_detail_catalog",
        "label": "Canonical Retail Product Detail Catalog",
        "score": 64,
        "evidence": {"tracks": ["product_price"], "track_scores": {"product_price": 64}},
    },
    {
        "technique": "generic_app_bundle",
        "label": "JavaScript / App Bundle Mining",
        "score": 37,
        "evidence": {"tracks": ["discovery"], "track_scores": {"discovery": 37}},
    },
]

product = {
    "record_type": "ProductCandidate",
    "product_name": "Test Model",
    "price": 1990.0,
    "currency": "THB",
    "sku": "SKU-001",
    "source_url": "https://example.test/product/1",
    "provenance": "retail-canonical-product-detail",
}

detail_result = {
    "technique": "generic_retail_detail_catalog",
    "label": "Canonical Retail Product Detail Catalog",
    "status": "completed",
    "record_count": 1,
    "record_types": [{"type": "ProductCandidate", "count": 1}],
    "sample_records": [product],
    "pages_checked": 1,
    "urls_checked": [product["source_url"]],
    "potential": {"price_completeness_pct": 100, "identity_completeness_pct": 100},
    "diagnostics": [],
}

app_result = {
    "technique": "generic_app_bundle",
    "label": "JavaScript / App Bundle Mining",
    "status": "completed",
    "record_count": 2,
    "record_types": [{"type": "EndpointCandidate", "count": 2}],
    "sample_records": [],
    "pages_checked": 3,
    "urls_checked": ["https://example.test/app.js"],
    "potential": {"discovered_urls": 100},
    "diagnostics": [],
}

originals = {
    "assigned_profile": router.assigned_profile,
    "generic_retail_detail_catalog": router.generic_retail_detail_catalog,
    "materialize_for_run": router.materialize_for_run,
    "technique_profile_fingerprint": router.technique_profile_fingerprint,
}
router.assigned_profile = lambda source_id: (assignments, [x["technique"] for x in assignments])
router.generic_retail_detail_catalog = lambda *args, **kwargs: detail_result
router.materialize_for_run = lambda source, techniques, **kwargs: {
    "records": [],
    "benchmark": {"technique_results": [app_result], "techniques_selected": techniques},
    "techniques_used": techniques,
}
router.technique_profile_fingerprint = lambda techniques, rows: "retail-profile-test"
try:
    out = router.assigned_acquisition(
        {"source_id": "SRC-TEST", "url": "https://example.test/", "sector": "IT Retail"},
        max_pages=5,
        stable_sample=True,
    )
finally:
    for name, value in originals.items():
        setattr(router, name, value)

assert out["technique_profile_applied"] is True
assert out["legacy_fallback_used"] is False
assert out["assigned_techniques"] == ["generic_retail_detail_catalog", "generic_app_bundle"]
assert out["technique_profile_fingerprint"] == "retail-profile-test"
assert out["records"] == [product]
assert out["technique_tracks"]["product_price"]["technique"] == "generic_retail_detail_catalog"
assert out["technique_tracks"]["discovery"]["technique"] == "generic_app_bundle"
assert {x["technique"] for x in out["technique_results"]} == {"generic_retail_detail_catalog", "generic_app_bundle"}
assert out["pages_checked"] == 4
assert product["source_url"] in out["urls_checked"]

print("Operational retail assigned acquisition routing: PASS")
