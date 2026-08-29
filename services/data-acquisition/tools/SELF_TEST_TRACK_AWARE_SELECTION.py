from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "acquisition"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from track_selection import select_track_profile

# Watsons-like case: huge homepage text yield with prices but no attributable SKU/detail URL.
watsons = [
    {
        "technique": "basic_crawler", "label": "Basic HTML Crawler", "status": "completed",
        "record_count": 312,
        "record_types": [{"type": "ProductCandidate", "count": 291}, {"type": "PromotionCandidate", "count": 21}],
        "sample_records": [
            {"record_type": "ProductCandidate", "product_name": "ส่งฟรี! เมื่อชอป", "price": 499, "sku": "", "source_url": "https://example.test/th", "source_tag": "Marketing", "provenance": "text-pattern"},
            {"record_type": "ProductCandidate", "product_name": "Serum", "price": 30, "sku": "", "source_url": "https://example.test/th", "source_tag": "Marketing", "provenance": "text-pattern"},
        ],
        "potential": {"confidence": "medium"}, "elapsed_seconds": 1,
    },
    {
        "technique": "generic_browser_network", "label": "Browser Network / API Discovery", "status": "completed",
        "record_count": 0, "record_types": [], "sample_records": [],
        "potential": {"discovered_urls": 17, "api_candidates": 0, "confidence": "medium"}, "elapsed_seconds": 1,
    },
]
profile, tracks, meta = select_track_profile(watsons, ["product_price", "discovery"], ["promotion"], {"price_completeness_pct": 80})
assert "product_price" not in tracks
assert meta["required_track_gaps"]["product_price"]["status"] == "required-track-gap"
assert tracks["discovery"]["technique"] == "generic_browser_network"
assert all("product_price" not in x["tracks"] for x in profile)

# JIB-like case: many promotion listing URLs must not qualify as Product & Price.
jib = [
    {
        "technique": "generic_browser_rendered", "label": "Browser-rendered DOM", "status": "completed",
        "record_count": 122,
        "record_types": [{"type": "DocumentCandidate", "count": 1}, {"type": "PromotionListingItemCandidate", "count": 121}],
        "sample_records": [{"record_type": "PromotionListingItemCandidate", "promotion_title": "Sale", "source_url": "https://example.test/sale/1", "provenance": "listing-card"}],
        "potential": {"discovered_urls": 1326, "confidence": "medium"}, "elapsed_seconds": 1,
    },
    {
        "technique": "generic_browser_network", "label": "Browser Network / API Discovery", "status": "completed",
        "record_count": 12, "record_types": [{"type": "EndpointCandidate", "count": 12}],
        "sample_records": [{"record_type": "EndpointCandidate", "source_url": "https://example.test/api/catalog"}],
        "potential": {"discovered_urls": 274, "api_candidates": 130, "confidence": "medium"}, "elapsed_seconds": 1,
    },
]
profile2, tracks2, meta2 = select_track_profile(jib, ["product_price", "discovery"], ["promotion"], {"price_completeness_pct": 85, "model_or_sku_completeness_pct": 90})
assert "product_price" not in tracks2
assert "promotion" not in tracks2  # listing candidates are not yet promotion facts
assert tracks2["discovery"]["technique"] == "generic_browser_network"
assert "product_price" in meta2["required_track_gaps"]

# A canonical detail technique with identity + prices must qualify.
detail = {
    "technique": "generic_api_probe", "label": "Discovered JSON/API Probe", "status": "completed",
    "record_count": 10, "record_types": [{"type": "ProductCandidate", "count": 10}],
    "sample_records": [
        {"record_type": "ProductCandidate", "product_name": f"Model {i}", "price": 1000+i, "sku": f"SKU-{i}", "source_url": f"https://example.test/product/{i}", "provenance": "official-json-api"}
        for i in range(10)
    ],
    "potential": {"confidence": "high", "reported_total": 100}, "elapsed_seconds": 1,
}
profile3, tracks3, meta3 = select_track_profile(jib + [detail], ["product_price", "discovery"], ["promotion"], {"price_completeness_pct": 85, "model_or_sku_completeness_pct": 90})
assert tracks3["product_price"]["technique"] == "generic_api_probe"
assert tracks3["product_price"]["price_completeness_pct"] == 100.0
assert tracks3["product_price"]["identity_completeness_pct"] == 100.0
assert "product_price" not in meta3["required_track_gaps"]

print("Track-aware retail technique selection: PASS")
