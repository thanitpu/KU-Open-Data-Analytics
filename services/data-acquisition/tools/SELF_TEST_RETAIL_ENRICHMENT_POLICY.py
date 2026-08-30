from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "acquisition", ROOT / "repository"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import source_explorer as se
import LIVE_JIB_RETAIL_LIFECYCLE as live_jib
import LIVE_RETAIL_TRANSFER_EXPLORE as live_transfer


DISCOVERY_RESULT = {
    "technique": "generic_app_bundle",
    "label": "JavaScript / App Bundle Mining",
    "status": "completed",
    "record_count": 1,
    "record_types": [{"type": "EndpointCandidate", "count": 1}],
    "sample_records": [
        {
            "record_type": "EndpointCandidate",
            "source_url": "https://official-retailer.co.th/assets/app.js",
        }
    ],
    "pages_checked": 1,
    "elapsed_seconds": 0.1,
    "operational_role": "discovery",
    "potential": {"discovered_urls": 100, "confidence": "high"},
    "diagnostics": [],
}

PRODUCT_RESULT = {
    "technique": "generic_retail_detail_catalog",
    "label": "Canonical Retail Product Detail Catalog",
    "status": "completed",
    "record_count": 10,
    "record_types": [{"type": "ProductCandidate", "count": 10}],
    "sample_records": [
        {
            "record_type": "ProductCandidate",
            "product_name": "Validated retail product",
            "price": 990.0,
            "currency": "THB",
            "sku": "SKU-001",
            "source_url": "https://official-retailer.co.th/product/SKU-001",
            "provenance": "official-product-detail",
        }
    ],
    "pages_checked": 4,
    "elapsed_seconds": 0.1,
    "potential": {
        "discovered_urls": 1003,
        "product_urls_discovered": 1003,
        "price_completeness_pct": 100.0,
        "identity_completeness_pct": 100.0,
        "confidence": "high",
    },
    "diagnostics": [],
}


def bench(*results):
    rows = copy.deepcopy(list(results))
    return {
        "record_count": sum(int(row.get("record_count") or 0) for row in rows),
        "unique_sample_record_count": sum(len(row.get("sample_records") or []) for row in rows),
        "record_types": [],
        "sample_records": [],
        "techniques_available": [row["technique"] for row in rows],
        "techniques_selected": [row["technique"] for row in rows],
        "assigned_techniques": [],
        "recommended_techniques": [],
        "potential_coverage": [],
        "technique_results": rows,
    }


def run(domain, *, base_results=(DISCOVERY_RESULT,), techniques=None, url="https://official-retailer.co.th/"):
    calls = []
    original_strategy = se.explore_with_strategy
    original_detail = se.generic_retail_detail_catalog

    def fake_detail(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return copy.deepcopy(PRODUCT_RESULT)

    se.explore_with_strategy = lambda *args, **kwargs: bench(*base_results)
    se.generic_retail_detail_catalog = fake_detail
    try:
        result = se.explore_url(
            url,
            domain=domain,
            purpose="retail_market_intelligence",
            max_pages=3,
            techniques=techniques,
        )
    finally:
        se.explore_with_strategy = original_strategy
        se.generic_retail_detail_catalog = original_detail
    return result, calls


# A. Domain validation maturity is knowledge, not an execution gate.
it_result, it_calls = run("IT Retail")
assert it_result["learned_pattern_guidance"]["learned_pattern_library"]["transfer_status"] == "partially-domain-validated"
assert len(it_calls) == 1, it_result["track_selection"]
assert "product_price" in it_result["track_recommendations"]
assert "generic_retail_detail_catalog" in it_result["assigned_techniques"]
assert it_result["track_selection"]["canonical_detail_enrichment_attempted"] is True
assert it_result["track_selection"]["canonical_detail_enrichment_basis"] == [
    "retail-core-pattern-RC-P02",
    "domain-live-validated-technique",
]
assert it_result["track_selection"]["canonical_detail_enrichment"]["record_count"] == 10
assert it_result["track_selection"]["canonical_detail_enrichment"]["discovered_product_url_count"] == 1003

transfer_compact = live_transfer.compact(it_result)["canonical_detail_enrichment"]
jib_compact = live_jib.compact_enrichment_decision(it_result["track_selection"])
for compact in (transfer_compact, jib_compact):
    assert compact == {
        "eligible": True,
        "attempted": True,
        "basis": ["retail-core-pattern-RC-P02", "domain-live-validated-technique"],
        "skip_reason": None,
        "record_count": 10,
        "discovered_product_url_count": 1003,
    }

# B. The inherited Beauty prior remains eligible.
beauty_result, beauty_calls = run("Beauty")
assert beauty_result["learned_pattern_guidance"]["learned_pattern_library"]["transfer_status"] == "inherited-not-yet-domain-validated"
assert len(beauty_calls) == 1
assert beauty_result["track_selection"]["canonical_detail_enrichment_eligible"] is True
assert beauty_result["track_selection"]["canonical_detail_enrichment_attempted"] is True

# C. Do not enrich when Product & Price already passes attribution gates.
closed_result, closed_calls = run("IT Retail", base_results=(DISCOVERY_RESULT, PRODUCT_RESULT))
assert closed_calls == []
assert closed_result["track_selection"]["canonical_detail_enrichment_attempted"] is False
assert closed_result["track_selection"]["canonical_detail_enrichment_skip_reason"] == "product-price-already-resolved"

# D. Respect an explicit technique allow-list.
excluded_result, excluded_calls = run("IT Retail", techniques=["generic_app_bundle"])
assert excluded_calls == []
assert excluded_result["track_selection"]["canonical_detail_enrichment_eligible"] is False
assert excluded_result["track_selection"]["canonical_detail_enrichment_skip_reason"] == "technique-explicitly-excluded"

# E. Do not apply retail-detail policy to arbitrary domain playbooks.
general_result, general_calls = run("General")
assert general_calls == []
assert general_result["track_selection"]["canonical_detail_enrichment_eligible"] is False
assert general_result["track_selection"]["canonical_detail_enrichment_skip_reason"] == "retail-product-price-policy-not-applicable"

# F. Never turn example/test fixtures into live detail requests.
example_result, example_calls = run("IT Retail", url="https://example.invalid/")
assert example_calls == []
assert example_result["track_selection"]["canonical_detail_enrichment_eligible"] is False
assert example_result["track_selection"]["canonical_detail_enrichment_skip_reason"] == "example-or-test-url"

# G. Only Product & Price evidence can establish a domain-live detail prior.
discovery_only = {
    "required_tracks": ["product_price", "discovery"],
    "learned_pattern_library": {"schema": "ku2d.retail-commerce-core-patterns.v1"},
    "tracks": {
        "product_price": [],
        "discovery": [
            {
                "pattern_id": "RC-P04",
                "track": "discovery",
                "evidence": {
                    "domain_validated_sources": [{"technique": "generic_app_bundle"}]
                },
            }
        ],
    },
}
discovery_decision = se.canonical_detail_enrichment_policy(
    "https://official-retailer.co.th/",
    discovery_only,
    {"product_price": {"status": "required-track-gap"}},
    None,
)
assert discovery_decision["canonical_detail_enrichment_eligible"] is False
assert "domain-live-validated-technique" not in discovery_decision["canonical_detail_enrichment_basis"]

product_live = copy.deepcopy(discovery_only)
product_live["tracks"]["product_price"] = [
    {
        "pattern_id": "CUSTOM-PRODUCT-DETAIL",
        "track": "product_price",
        "evidence": {
            "domain_validated_sources": [
                {"technique": "generic_retail_detail_catalog"}
            ]
        },
    }
]
product_decision = se.canonical_detail_enrichment_policy(
    "https://official-retailer.co.th/",
    product_live,
    {"product_price": {"status": "required-track-gap"}},
    None,
)
assert product_decision["canonical_detail_enrichment_eligible"] is True
assert "domain-live-validated-technique" in product_decision["canonical_detail_enrichment_basis"]

print("Retail canonical-detail enrichment policy: PASS")
