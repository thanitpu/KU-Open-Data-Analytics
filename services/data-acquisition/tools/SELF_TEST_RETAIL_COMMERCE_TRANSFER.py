from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from control_plane.domain_playbooks import playbook, recommended_sequence

core = json.loads((ROOT / "config" / "retail_commerce_core_patterns.json").read_text(encoding="utf-8"))
assert core["schema"] == "ku2d.retail-commerce-core-patterns.v1"
assert len((core.get("derived_from") or {}).get("validated_sources") or []) == 5
assert {x["pattern_id"] for x in core["core_patterns"]} == {f"RC-P{i:02d}" for i in range(1, 8)}

beauty = playbook("Beauty")
assert beauty["required_business_tracks"] == ["product_price", "discovery"]
assert beauty["optional_business_tracks"] == ["promotion"]
assert set(beauty["variant_dimensions"]) >= {"shade", "color", "size", "volume"}
assert beauty["quality_gates"]["variant_identity_when_present_pct"] == 90
assert beauty["learned_pattern_library"]["transfer_status"] == "inherited-not-yet-domain-validated"

beauty_seq = recommended_sequence("beauty retail", clues=["product_cards", "sitemap", "promotion"])
assert set(beauty_seq["tracks"]) == {"product_price", "discovery"}
assert set(beauty_seq["optional_track_patterns"]) == {"promotion"}
assert beauty_seq["tracks"]["product_price"][0]["pattern_id"] in {"RC-P01", "RC-P02", "RC-P03"}
assert any(x["pattern_id"] == "RC-P05" for x in beauty_seq["optional_track_patterns"]["promotion"])

it = playbook("IT Retail")
assert it["required_business_tracks"] == ["product_price", "discovery"]
assert set(it["variant_dimensions"]) >= {"capacity", "memory", "storage", "configuration"}
assert it["quality_gates"]["model_or_sku_completeness_pct"] == 90

it_seq = recommended_sequence("electronics retail", clues=["json_api", "product_endpoint", "reported_total"])
assert set(it_seq["tracks"]) == {"product_price", "discovery"}
assert it_seq["tracks"]["product_price"][0]["pattern_id"] == "RC-P01"
assert any(x.get("action") == "prefer_edge_runner" for x in it_seq["environment_rules"])

# Cross-domain transfer remains a candidate prior unless a pattern/track pair has
# explicit domain evidence. Beauty has no live domain validation yet.
for pattern in beauty["patterns"]:
    assert pattern["transfer_status"] == "cross-domain-candidate"
    assert pattern["evidence"]["validated_sources"] == []
    assert pattern["evidence"]["domain_validated_sources"] == []
    assert len(pattern["evidence"]["upstream_validated_sources"]) == 5

# JIB validates only canonical-detail Product & Price and app-bundle Discovery.
it_validated = {
    ("RC-P02", "product_price"): "generic_retail_detail_catalog",
    ("RC-P04", "discovery"): "generic_app_bundle",
}
for pattern in it["patterns"]:
    key = (pattern["pattern_id"], pattern["track"])
    assert len(pattern["evidence"]["upstream_validated_sources"]) == 5
    if key in it_validated:
        assert pattern["transfer_status"] == "domain-live-validated"
        assert pattern["evidence"]["validated_sources"] == ["JIB"]
        assert pattern["evidence"]["domain_validated_sources"][0]["technique"] == it_validated[key]
    else:
        assert pattern["transfer_status"] == "cross-domain-candidate"
        assert pattern["evidence"]["validated_sources"] == []
        assert pattern["evidence"]["domain_validated_sources"] == []

print("Retail commerce cross-domain transfer: PASS")
