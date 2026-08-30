from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from control_plane.domain_playbooks import playbook, ranked_patterns


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def contains_key(payload: object, key: str) -> bool:
    if isinstance(payload, dict):
        return key in payload or any(contains_key(value, key) for value in payload.values())
    if isinstance(payload, list):
        return any(contains_key(value, key) for value in payload)
    return False


def ranked_pattern(domain: str, pattern_id: str, track: str) -> dict:
    return next(
        pattern
        for pattern in ranked_patterns(domain, clues=[], track=track)
        if pattern["pattern_id"] == pattern_id and pattern["track"] == track
    )


evidence = load_json(REPOSITORY_ROOT / "docs" / "validation" / "jib-retail-validation-2026-08-30.json")
registry = load_json(ROOT / "config" / "retail_domain_validations.json")
core = load_json(ROOT / "config" / "retail_commerce_core_patterns.json")

assert evidence["schema"] == "ku2d.retail-domain-validation.v1"
assert evidence["schema_version"] == 1
assert registry["schema"] == "ku2d.retail-domain-validations.v1"
assert registry["registry_policy"]["validation_records_are_non_authorizing"] is True
assert core["schema"] == "ku2d.retail-commerce-core-patterns.v1"
assert not contains_key(evidence, "validation_scope")
assert not contains_key(registry, "validation_scope")

beauty_registry = registry["domains"]["beauty"]
it_registry = registry["domains"]["it_retail"]
assert beauty_registry["validation_status"] == "inherited-not-yet-domain-validated"
assert beauty_registry["live_validated_sources"] == []
assert it_registry["validation_status"] == "partially-domain-validated"
assert len(it_registry["live_validated_sources"]) == 1
jib = it_registry["live_validated_sources"][0]

# Durable evidence and registry are two views of the same reviewed validation.
provenance = evidence["validation_provenance"]
artifact = provenance["artifact"]
assert evidence["source"]["source_id"] == jib["source_id"] == "SRC-018"
assert evidence["source"]["name"] == jib["source_name"] == "JIB"
assert evidence["source"]["domain"] == jib["domain"] == "IT Retail"
assert evidence["source"]["domain_key"] == "it_retail"
assert provenance["workflow_run_id"] == jib["workflow_provenance"]["workflow_run_id"] == 33302385382
assert provenance["integration_commit"] == jib["workflow_provenance"]["integration_commit"]
assert artifact["id"] == jib["workflow_provenance"]["artifact_id"] == 9729383751
assert artifact["name"] == jib["workflow_provenance"]["artifact_name"]
assert artifact["sha256"] == jib["workflow_provenance"]["artifact_sha256"]
assert evidence["technique_profile_fingerprint"] == jib["technique_profile_fingerprint"] == "cbcfc49db6127e09"

assert evidence["execution"]["environment"] == jib["execution_environment"] == "cloud-hosted-public-read-only"
assert evidence["execution"]["workflow_scope"] == jib["workflow_scope"] == "isolated-staging"
assert evidence["execution"]["approval_scope"] == jib["approval_scope"] == "isolated-staging-db"
assert evidence["result"]["technical_completion"] is True
assert evidence["result"]["isolated_staging_approved"] is True
assert evidence["result"]["production_approved"] == jib["production_approved"] is False
assert evidence["result"]["production_human_approve_performed"] == jib["production_human_approve_performed"] is False
assert evidence["scheduler_evaluation"]["production_scheduling_enabled"] == jib["production_scheduling_enabled"] is False
assert jib["scheduler_evaluation"]["production_scheduling_enabled"] is False

assert evidence["deep_audit"] == jib["deep_audit"] == {
    "passed": True,
    "hard_failures": [],
    "quality_score": 82,
    "quality_label": "strong",
}
assert evidence["quality_metrics"] == jib["metrics"]
assert evidence["quality_metrics"]["product_sample_count"] == 5
assert evidence["quality_metrics"]["product_yield_count"] == 5
for metric in (
    "price_completeness_pct",
    "sellable_product_identity_pct",
    "semantic_quality_pct",
    "product_repeatability_pct",
    "provenance_pct",
    "assigned_technique_execution_pct",
):
    assert evidence["quality_metrics"][metric] == 100.0

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
assert evidence["tracks"]["missing_required"] == []
assert evidence["tracks"]["promotion"] == {"assigned": False, "technique": None}
assert jib["optional_tracks"]["promotion"] == {"assigned": False, "technique": None}

durable_tracks = evidence["tracks"]["validated_techniques"]
registry_tracks = jib["validated_tracks"]
assert set(durable_tracks) == set(registry_tracks) == {"product_price", "discovery"}
for track in durable_tracks:
    assert durable_tracks[track]["technique"] == registry_tracks[track]["technique"]
    assert durable_tracks[track]["label"] == registry_tracks[track]["technique_label"]
    assert durable_tracks[track]["score"] == registry_tracks[track]["score"]
    assert durable_tracks[track]["validated_pattern_ids"] == registry_tracks[track]["validated_pattern_ids"]
assert registry_tracks["product_price"]["technique"] == "generic_retail_detail_catalog"
assert registry_tracks["product_price"]["validated_pattern_ids"] == ["RC-P02"]
assert registry_tracks["discovery"]["technique"] == "generic_app_bundle"
assert registry_tracks["discovery"]["validated_pattern_ids"] == ["RC-P04"]

rc_p04 = next(pattern for pattern in core["core_patterns"] if pattern["pattern_id"] == "RC-P04")
assert "first-party JavaScript/app-bundle route discovery" in rc_p04["methods"]

it_playbook = playbook("IT Retail")
assert it_playbook["learned_pattern_library"]["transfer_status"] == "partially-domain-validated"
assert it_playbook["learned_pattern_library"]["live_validated_sources"] == [
    {
        "source_id": "SRC-018",
        "source_name": "JIB",
        "status": "live-profile-validated",
        "workflow_scope": "isolated-staging",
        "approval_scope": "isolated-staging-db",
        "production_approved": False,
    }
]
assert not contains_key(it_playbook, "validation_scope")

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
        assert domain_evidence[0]["workflow_scope"] == "isolated-staging"
        assert domain_evidence[0]["approval_scope"] == "isolated-staging-db"
        assert domain_evidence[0]["production_approved"] is False
    else:
        assert pattern["transfer_status"] == "cross-domain-candidate"
        assert "JIB" not in pattern["evidence"]["validated_sources"]
        assert domain_evidence == []

rc_p04_playbook_rows = [pattern for pattern in it_playbook["patterns"] if pattern["pattern_id"] == "RC-P04"]
assert len(rc_p04_playbook_rows) == 1
assert rc_p04_playbook_rows[0]["track"] == "discovery"
assert rc_p04_playbook_rows[0]["evidence"]["domain_validated_sources"][0]["technique"] == "generic_app_bundle"

beauty_playbook = playbook("Beauty")
assert beauty_playbook["learned_pattern_library"]["transfer_status"] == "inherited-not-yet-domain-validated"
assert beauty_playbook["learned_pattern_library"]["live_validated_sources"] == []
for pattern in beauty_playbook["patterns"]:
    assert pattern["transfer_status"] == "cross-domain-candidate"
    assert pattern["evidence"]["validated_sources"] == []
    assert pattern["evidence"]["domain_validated_sources"] == []

# Domain-live evidence retains the upstream prior and adds a distinct domain bonus.
for pattern_id, track in (("RC-P02", "product_price"), ("RC-P04", "discovery")):
    it_ranked = ranked_pattern("IT Retail", pattern_id, track)
    beauty_ranked = ranked_pattern("Beauty", pattern_id, track)
    assert it_ranked["base_priority"] == beauty_ranked["base_priority"]
    assert it_ranked["matched_clues"] == beauty_ranked["matched_clues"] == []
    assert it_ranked["learned_score"] > beauty_ranked["learned_score"]
    assert it_ranked["learned_score_components"]["upstream_transfer_prior"] == 4
    assert it_ranked["learned_score_components"]["general_validated_sources"] == 0
    assert it_ranked["learned_score_components"]["domain_live_validation"] == 4
    assert beauty_ranked["learned_score_components"]["upstream_transfer_prior"] == 4
    assert beauty_ranked["learned_score_components"]["domain_live_validation"] == 0

supermarket = playbook("supermarket")
supermarket_sources = set((supermarket.get("learned_pattern_library") or {}).get("validated_sources") or [])
assert supermarket_sources == {"Lotus's", "Big C", "Makro", "Tops", "Gourmet Market"}
assert "JIB" not in supermarket_sources

print("Retail domain validation knowledge: PASS")
