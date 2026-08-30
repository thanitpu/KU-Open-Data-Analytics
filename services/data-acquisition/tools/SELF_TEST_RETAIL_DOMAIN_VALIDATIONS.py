from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from control_plane.domain_playbooks import playbook


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


evidence = load_json(REPOSITORY_ROOT / "docs" / "validation" / "jib-retail-validation-2026-08-30.json")
registry = load_json(ROOT / "config" / "retail_domain_validations.json")

assert evidence["schema"] == "ku2d.retail-domain-validation.v1"
assert evidence["schema_version"] == 1
assert evidence["validation_provenance"]["workflow_run_id"] == 33302385382
assert evidence["validation_provenance"]["integration_commit"] == "79a217292e2dc3a3982a5edf9fdede8377e1eff4"
assert evidence["validation_provenance"]["artifact"]["sha256"] == "d6e5e263d9801add556ef4692b9e84fa837774cf49d8494835a6794f3dfd676b"
assert evidence["source"]["source_id"] == "SRC-018"
assert evidence["source"]["domain_key"] == "it_retail"
assert evidence["execution"]["validation_scope"] == "isolated-staging-db"
assert evidence["result"]["technical_completion"] is True
assert evidence["result"]["isolated_staging_approved"] is True
assert evidence["result"]["production_approved"] is False
assert evidence["result"]["production_human_approve_performed"] is False
assert evidence["technique_profile_fingerprint"] == "cbcfc49db6127e09"
assert evidence["tracks"]["missing_required"] == []
assert evidence["tracks"]["promotion"] == {"assigned": False, "technique": None}
assert set(evidence["domain_gates"]) == {
    "product_catalog_sample",
    "product_price_completeness",
    "product_semantic_quality",
    "sellable_product_identity",
    "product_repeatability",
    "provenance",
    "assigned_technique_execution",
}
assert all(gate["passed"] is True for gate in evidence["domain_gates"].values())
assert evidence["deep_audit"] == {
    "passed": True,
    "hard_failures": [],
    "quality_score": 82,
    "quality_label": "strong",
}
assert evidence["scheduler_evaluation"]["production_scheduling_enabled"] is False

assert registry["schema"] == "ku2d.retail-domain-validations.v1"
assert registry["registry_policy"]["validation_records_are_non_authorizing"] is True
beauty_registry = registry["domains"]["beauty"]
it_registry = registry["domains"]["it_retail"]
assert beauty_registry["validation_status"] == "inherited-not-yet-domain-validated"
assert beauty_registry["live_validated_sources"] == []
assert it_registry["validation_status"] == "partially-domain-validated"
assert len(it_registry["live_validated_sources"]) == 1

jib = it_registry["live_validated_sources"][0]
assert jib["source_id"] == "SRC-018"
assert jib["source_name"] == "JIB"
assert jib["status"] == "live-profile-validated"
assert jib["validation_scope"] == "isolated-staging"
assert jib["production_approved"] is False
assert jib["production_human_approve_performed"] is False
assert jib["production_scheduling_enabled"] is False
assert jib["scheduler_evaluation"]["production_scheduling_enabled"] is False
assert jib["technique_profile_fingerprint"] == "cbcfc49db6127e09"

validated_tracks = jib["validated_tracks"]
assert set(validated_tracks) == {"product_price", "discovery"}
assert validated_tracks["product_price"]["technique"] == "generic_retail_detail_catalog"
assert validated_tracks["product_price"]["validated_pattern_ids"] == ["RC-P02"]
assert validated_tracks["discovery"]["technique"] == "generic_app_bundle"
assert validated_tracks["discovery"]["validated_pattern_ids"] == ["RC-P04"]

it_playbook = playbook("IT Retail")
assert it_playbook["learned_pattern_library"]["transfer_status"] == "partially-domain-validated"
assert it_playbook["learned_pattern_library"]["live_validated_sources"] == [
    {
        "source_id": "SRC-018",
        "source_name": "JIB",
        "status": "live-profile-validated",
        "validation_scope": "isolated-staging",
        "production_approved": False,
    }
]

expected = {
    ("RC-P02", "product_price"): "generic_retail_detail_catalog",
    ("RC-P04", "discovery"): "generic_app_bundle",
}
for pattern in it_playbook["patterns"]:
    key = (pattern["pattern_id"], pattern["track"])
    domain_evidence = pattern["evidence"]["domain_validated_sources"]
    if key in expected:
        assert pattern["transfer_status"] == "domain-live-validated"
        assert pattern["evidence"]["validated_sources"] == ["JIB"]
        assert len(domain_evidence) == 1
        assert domain_evidence[0]["technique"] == expected[key]
        assert domain_evidence[0]["production_approved"] is False
    else:
        assert pattern["transfer_status"] == "cross-domain-candidate"
        assert "JIB" not in pattern["evidence"]["validated_sources"]
        assert domain_evidence == []

beauty_playbook = playbook("Beauty")
assert beauty_playbook["learned_pattern_library"]["transfer_status"] == "inherited-not-yet-domain-validated"
assert beauty_playbook["learned_pattern_library"]["live_validated_sources"] == []
for pattern in beauty_playbook["patterns"]:
    assert pattern["transfer_status"] == "cross-domain-candidate"
    assert pattern["evidence"]["validated_sources"] == []
    assert pattern["evidence"]["domain_validated_sources"] == []

supermarket = playbook("supermarket")
supermarket_sources = set((supermarket.get("learned_pattern_library") or {}).get("validated_sources") or [])
assert supermarket_sources == {"Lotus's", "Big C", "Makro", "Tops", "Gourmet Market"}
assert "JIB" not in supermarket_sources

print("Retail domain validation knowledge: PASS")
