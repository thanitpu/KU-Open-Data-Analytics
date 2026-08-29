from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "supermarket_acquisition_patterns.json"

obj = json.loads(CFG.read_text(encoding="utf-8"))
assert obj["schema"] == "ku2d.supermarket-acquisition-patterns.v1"
assert obj["version"] >= 1

policy = obj["policy"]
assert set(policy["required_tracks"]) == {"product_price", "discovery"}
assert "promotion" in policy["optional_tracks"]

sources = {x["business"]: x for x in obj["validated_sources"]}
assert set(["Lotus's", "Big C", "Makro", "Tops", "Gourmet Market"]).issubset(sources)
assert all(sources[name]["status"] == "approved" for name in ["Lotus's", "Big C", "Makro", "Tops", "Gourmet Market"])

# Every validated source must cover the required tracks.
for name, source in sources.items():
    tracks = source.get("tracks") or {}
    for required in policy["required_tracks"]:
        assert tracks.get(required), f"{name} missing required track {required}"

# Gourmet's validated split-track + Edge profile is a first-class reusable pattern.
gourmet = sources["Gourmet Market"]
assert gourmet["tracks"]["product_price"]["technique"] == "gourmet_rendered_catalog"
assert gourmet["tracks"]["discovery"]["technique"] == "gourmet_catalog_network"
assert gourmet["tracks"]["promotion"] is None
assert gourmet["execution_environment"] == "approved_edge_when_cloud_blocked"
assert gourmet["quality_score"] >= 80

patterns = {x["pattern_id"]: x for x in obj["patterns"]}
expected = {f"SM-P{i:02d}" for i in range(1, 10)}
assert expected.issubset(patterns)

# Evidence from at least two independent retailers is required before calling a
# product-extraction pattern broadly reusable, except API and Edge patterns that
# are intentionally recorded as validated specializations.
assert len(patterns["SM-P02"]["validated_examples"]) >= 2
assert len(patterns["SM-P03"]["validated_examples"]) >= 2
assert len(patterns["SM-P08"]["validated_examples"]) == 5

# Promotion is optional for approval but must remain an explicit pattern.
assert patterns["SM-P07"]["track"] == "promotion"
assert "Promotion is optional" in policy["promotion_rule"]

waterfall = obj["selection_waterfall"]
assert len(waterfall) >= 6
assert any("Deep Audit" in x for x in waterfall)
assert any("Edge" in x for x in waterfall)

print("Supermarket acquisition pattern library: PASS")
