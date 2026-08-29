from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "acquisition", ROOT / "repository"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import source_explorer as se

fixture = {
    "record_count": 12,
    "unique_sample_record_count": 12,
    "record_types": [{"type": "ProductCandidate", "count": 12}],
    "sample_records": [{"record_type": "ProductCandidate", "product_name": "A", "price": 10}],
    "techniques_available": ["generic_sitemap", "gourmet_rendered_catalog", "gourmet_catalog_network"],
    "techniques_selected": ["generic_sitemap", "gourmet_rendered_catalog", "gourmet_catalog_network"],
    "assigned_techniques": ["gourmet_rendered_catalog", "gourmet_catalog_network"],
    "recommended_techniques": [
        {"technique": "gourmet_rendered_catalog", "tracks": ["product_price"], "score": 100},
        {"technique": "gourmet_catalog_network", "tracks": ["discovery"], "score": 80},
    ],
    "potential_coverage": [],
    "technique_results": [
        {
            "technique": "generic_sitemap",
            "label": "Robots / Sitemap Discovery",
            "record_count": 3,
            "pages_checked": 1,
            "potential": {"discovered_urls": 100},
            "sample_records": [],
        },
        {
            "technique": "gourmet_rendered_catalog",
            "label": "Rendered Product Cards",
            "record_count": 12,
            "pages_checked": 1,
            "potential": {"price_completeness_pct": 100},
            "sample_records": [],
        },
        {
            "technique": "gourmet_catalog_network",
            "label": "GraphQL Network Catalog Discovery",
            "record_count": 1,
            "pages_checked": 1,
            "potential": {"graphql_endpoint": "https://example.invalid/graphql"},
            "sample_records": [],
        },
    ],
}

original = se.explore_with_strategy
se.explore_with_strategy = lambda *args, **kwargs: fixture
try:
    out = se.explore_url("https://example.invalid/", domain="Supermarket", purpose="retail_market_intelligence", max_pages=3)
finally:
    se.explore_with_strategy = original

clues = set(out["pattern_clues"])
assert {"sitemap", "product_cards", "graphql", "graphql_endpoint", "api_candidate"}.issubset(clues), clues

guidance = out["learned_pattern_guidance"]
assert guidance["required_tracks"] == ["product_price", "discovery"]
assert guidance["optional_tracks"] == ["promotion"]
assert set(guidance["tracks"]) == {"product_price", "discovery"}
assert "promotion" in guidance["optional_track_patterns"]
assert set((guidance.get("learned_pattern_library") or {}).get("validated_sources") or []) >= {
    "Lotus's", "Big C", "Makro", "Tops", "Gourmet Market"
}

product_ids = [x["pattern_id"] for x in guidance["tracks"]["product_price"]]
assert "rendered_product_listing" in product_ids

discovery_ids = [x["pattern_id"] for x in guidance["tracks"]["discovery"]]
assert "browser_network_discovery" in discovery_ids

print("Pattern-guided adaptive Explore: PASS")
