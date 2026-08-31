"""Deterministic tests for KU2D Core Knowledge Backfill v1."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
if str(ROOT / "acquisition") not in sys.path:
    sys.path.insert(0, str(ROOT / "acquisition"))

from core_knowledge import (
    CANDIDATE_REGISTRY_SCHEMA,
    CORPUS_SCHEMA,
    COVERAGE_STATES,
    GAP_REGISTER_SCHEMA,
    HUMAN_CANDIDATE_PACKET_SCHEMA,
    HUMAN_CONFIRMED_POLICY_SCHEMA,
    ML_MAP_SCHEMA,
    TAXONOMY_SCHEMA,
    materialize_human_confirmed_policy_bundle,
    serialize_core_knowledge,
    taxonomy_index,
    validate_candidate_registry,
    validate_corpus,
    validate_coverage_matrix,
    validate_gap_register,
    validate_human_candidate_packet,
    validate_human_confirmed_policy_registry,
    validate_ml_knowledge_map,
    validate_taxonomy,
)


def load(name: str):
    return json.loads((ROOT / "config" / name).read_text(encoding="utf-8"))


taxonomy = load("core_knowledge_taxonomy.json")
corpus = load("reviewed_learning_corpus.json")
coverage = load("core_coverage_matrix.json")
ml_map = load("ml_knowledge_map.json")
gaps = load("knowledge_gap_register.json")
candidate_registry = load("candidate_learning_evidence_registry.json")
human_candidates = load("human_confirmation_candidate_packet.json")
human_policies = load("human_confirmed_core_semantic_policies.json")

# CK1: every top-level schema is explicit and validates.
assert taxonomy["schema"] == TAXONOMY_SCHEMA
assert corpus["schema"] == CORPUS_SCHEMA
assert coverage["schema"] == "ku2d.core-coverage-matrix.v1"
assert ml_map["schema"] == ML_MAP_SCHEMA
assert gaps["schema"] == GAP_REGISTER_SCHEMA
assert candidate_registry["schema"] == CANDIDATE_REGISTRY_SCHEMA
assert human_candidates["schema"] == HUMAN_CANDIDATE_PACKET_SCHEMA
assert human_policies["schema"] == HUMAN_CONFIRMED_POLICY_SCHEMA
validate_taxonomy(taxonomy)
validate_corpus(corpus, taxonomy)
validate_coverage_matrix(coverage)
validate_ml_knowledge_map(ml_map)
validate_gap_register(gaps)
validate_candidate_registry(candidate_registry)
validate_human_candidate_packet(human_candidates)
validate_human_confirmed_policy_registry(human_policies)

# CK2: taxonomy identifiers are unique and technique/environment remain separate.
index = taxonomy_index(taxonomy)
all_ids = [value["id"] for dimension in taxonomy["dimensions"] for value in dimension["values"]]
assert len(all_ids) == len(set(all_ids))
assert index["acquisition_technique"].isdisjoint(index["execution_environment"])

# CK3: every included episode has strong repository provenance and non-authorizing boundaries.
for episode in corpus["episodes"]:
    assert episode["provenance"]["sanitized"] is True
    assert episode["provenance"]["repository_references"]
    assert episode["authority"]["eligibility"] == "eligible_reviewed_corpus"
    assert episode["ml_projection"]["training_eligible"] is False
    assert set(episode["ml_projection"]["candidate_feature_families"]).isdisjoint(
        episode["ml_projection"]["excluded_leakage_fields"]
    )
    assert episode["ml_projection"]["label_or_decision"]["value"] == episode["knowledge"]["semantic_label"]
    assert episode["boundaries"] == {
        "observation_is_ground_truth": False,
        "production_authorized": False,
        "production_store": False,
        "scheduler_action": None,
        "automatic_ml_export": False,
    }

# CK4: every evidence reference resolves inside the repository or service tree.
reference_groups = [
    *(episode["provenance"]["repository_references"] for episode in corpus["episodes"]),
    *(entry["repository_references"] for entry in corpus["excluded_candidates"]),
    *(item["evidence_references"] for item in coverage["capabilities"]),
    *(task["evidence_sources"] for task in ml_map["tasks"]),
    *(gap["evidence_references"] for gap in gaps["gaps"]),
    *(
        [ref.split("#", 1)[0] for ref in item.get("candidate_evidence_references", [])]
        for item in coverage["capabilities"]
        if item.get("candidate_evidence_references")
    ),
    *(item["evidence_references"] for item in human_candidates["items"]),
    *(item["evidence_references"] for item in human_policies["policies"]),
    [human_policies["source_human_decision_reference"]],
]
for refs in reference_groups:
    for ref in refs:
        service_path = (ROOT / ref).resolve()
        repo_path = (REPO / ref).resolve()
        assert service_path.is_relative_to(REPO) or repo_path.is_relative_to(REPO)
        assert service_path.exists() or repo_path.exists(), ref

# CK5: negative and mixed learning is retained, including access boundaries.
polarities = {episode["polarity"] for episode in corpus["episodes"]}
assert {"positive", "negative", "mixed"}.issubset(polarities)
failure_ids = {episode["knowledge"]["failure_boundary_type_id"] for episode in corpus["episodes"]}
assert {"FB-APPLICATION-SHELL", "FB-TRAFFIC-VERIFICATION", "FB-CLOUD-ACCESS-BLOCKED"}.issubset(failure_ids)

# CK6: only the five explicitly confirmed policies claim Human Review.
human_episodes = [
    episode for episode in corpus["episodes"]
    if episode["authority"]["review_authority_id"] == "RA-HUMAN-CONFIRMED"
]
assert len(human_episodes) == 5
assert all(episode["authority"]["human_reviewed"] is True for episode in human_episodes)
assert all(episode["authority"]["human_decision_record_id"] == "KU2D-H-000001" for episode in human_episodes)
assert all(
    episode["authority"]["human_reviewed"] is False
    for episode in corpus["episodes"] if episode not in human_episodes
)

# CK7: claiming human authority without explicit human review fails closed.
fabricated_human = deepcopy(corpus)
fabricated_human["episodes"][0]["authority"]["review_authority_id"] = "RA-HUMAN-CONFIRMED"
try:
    validate_corpus(fabricated_human, taxonomy)
    raise AssertionError("fabricated human authority validated")
except ValueError:
    pass

# CK8: contradictory active labels for one learning key fail closed.
contradictory = deepcopy(corpus)
duplicate = deepcopy(contradictory["episodes"][0])
duplicate["episode_id"] = "KU2D-CKE-999999"
duplicate["knowledge"]["semantic_label"] = "conflicting-label"
contradictory["episodes"].append(duplicate)
try:
    validate_corpus(contradictory, taxonomy)
    raise AssertionError("contradictory active labels validated")
except ValueError:
    pass

# CK9: invalid taxonomy references fail closed.
invalid_taxonomy_ref = deepcopy(corpus)
invalid_taxonomy_ref["episodes"][0]["knowledge"]["acquisition_technique_id"] = "AT-NOT-DEFINED"
try:
    validate_corpus(invalid_taxonomy_ref, taxonomy)
    raise AssertionError("unknown taxonomy ID validated")
except ValueError:
    pass

# CK10: sensitive material is rejected.
sensitive = deepcopy(corpus)
sensitive["episodes"][0]["provenance"]["cookies"] = "prohibited"
try:
    validate_corpus(sensitive, taxonomy)
    raise AssertionError("sensitive Core Knowledge validated")
except ValueError:
    pass

# CK11: excluded sources remain explicit and are never silently promoted.
excluded = {entry["name"]: entry["eligibility"] for entry in corpus["excluded_candidates"]}
assert excluded["LINE SHOPPING"] == "excluded_candidate_only"
assert excluded["NocNoc"] == "excluded_candidate_only"
assert excluded["TikTok Shop"] == "excluded_candidate_only"
assert excluded["Agoda and Traveloka"] == "excluded_candidate_only"

# CK12: coverage is qualitative, complete for the prompt's minimum capabilities, and gap-aware.
required_capabilities = {
    "Official API", "Sitemap and static discovery", "Canonical detail extraction",
    "Rendered DOM extraction", "Browser acquisition", "Application-bundle discovery",
    "Structured response use", "Bounded pagination", "Execution-environment dependence",
    "Authentication and access-control boundary handling", "Change monitoring",
    "Incremental refresh", "Entity resolution", "Cross-source matching",
    "Temporal observation", "Semantic normalization", "Quality and yield",
    "Provenance and review maturity",
}
assert required_capabilities.issubset({item["capability"] for item in coverage["capabilities"]})
assert {item["state"] for item in coverage["capabilities"]}.issubset(COVERAGE_STATES)
assert all(item["gap"] for item in coverage["capabilities"])

# CK13: the ML map covers the requested tasks but cannot train/export and never claims ready.
assert ml_map["training_or_inference_enabled"] is False
assert ml_map["dataset_export_enabled"] is False
assert len(ml_map["tasks"]) == 8
assert "ready" not in {task["readiness"] for task in ml_map["tasks"]}
assert all(task["leakage_risks"] and task["label_authority"] for task in ml_map["tasks"])
assert all(task["feature_families"] and task["authority_requirement"] for task in ml_map["tasks"])
assert all(task["exclusion_criteria"] for task in ml_map["tasks"])
assert all(set(task["feature_families"]).isdisjoint(task["exclusion_criteria"]) for task in ml_map["tasks"])

# CK14: gaps are ranked by pattern and start no exploration.
assert gaps["exploration_started"] is False
assert [gap["rank"] for gap in gaps["gaps"]] == list(range(1, len(gaps["gaps"]) + 1))
assert all("brand popularity" not in gap["recommended_future_target"].casefold() for gap in gaps["gaps"])

# CK15: serialization is deterministic and non-mutating.
assert serialize_core_knowledge(corpus) == serialize_core_knowledge(deepcopy(corpus))

# CK16: normal runtime has no Core Knowledge import/write integration.
for runtime_folder in ("api", "control_plane", "repository", "service"):
    for runtime_file in (ROOT / runtime_folder).rglob("*.py"):
        runtime_text = runtime_file.read_text(encoding="utf-8")
        assert "core_knowledge" not in runtime_text, runtime_file
        assert "reviewed_learning_corpus" not in runtime_text, runtime_file

# CK17: the corpus is not a training dataset and is separate from coordination state.
assert corpus["ml_training_dataset_exists"] is False
assert corpus["automatic_export"] is False
assert not any("coordination/" in ref for episode in corpus["episodes"] for ref in episode["provenance"]["repository_references"])

# CK18: open Draft PR evidence is retained separately and cannot self-promote.
assert len(candidate_registry["candidates"]) == 11
assert all(candidate["authority"]["candidate_only"] is True for candidate in candidate_registry["candidates"])
assert all(candidate["authority"]["reviewed_corpus_authorized"] is False for candidate in candidate_registry["candidates"])
assert all(candidate["authority"]["promoted_to_reviewed_episode_id"] is None for candidate in candidate_registry["candidates"])
assert all(candidate["provenance"]["artifact_state"] == "open-unmerged-draft-pr" for candidate in candidate_registry["candidates"])
assert {candidate["provenance"]["pr_number"] for candidate in candidate_registry["candidates"]} == {36, 37, 38, 39, 40, 41}

# CK19: candidate feature/label projections remain separate and training-disabled.
for candidate in candidate_registry["candidates"]:
    projection = candidate["ml_projection"]
    assert projection["training_eligible"] is False
    assert set(projection["candidate_feature_families"]).isdisjoint(projection["excluded_leakage_fields"])

# CK20: candidate promotion or Ground Truth claims fail closed.
promoted = deepcopy(candidate_registry)
promoted["candidates"][0]["authority"]["reviewed_corpus_authorized"] = True
try:
    validate_candidate_registry(promoted)
    raise AssertionError("candidate self-promotion validated")
except ValueError:
    pass

# CK21: sensitive candidate material remains rejected.
sensitive_candidate = deepcopy(candidate_registry)
sensitive_candidate["candidates"][0]["provenance"]["cookies"] = "prohibited"
try:
    validate_candidate_registry(sensitive_candidate)
    raise AssertionError("sensitive candidate evidence validated")
except ValueError:
    pass

# CK22: all five candidate questions retain their explicit Human Confirmation disposition.
assert len(human_candidates["items"]) == 5
assert human_candidates["human_confirmation_created"] is True
assert human_candidates["source_human_decision_id"] == "KU2D-H-000001"
assert all(item["review_status"] == "confirmed_by_explicit_human_authority" for item in human_candidates["items"])
assert all(item["human_confirmation_record_id"] and item["final_decision"] for item in human_candidates["items"])

# CK23: a confirmed item without the explicit source Human Decision fails closed.
fabricated_confirmation = deepcopy(human_candidates)
fabricated_confirmation.pop("source_human_decision_id")
try:
    validate_human_candidate_packet(fabricated_confirmation)
    raise AssertionError("fabricated Human Confirmation decision validated")
except ValueError:
    pass

# CK24: candidate evidence is evidence-weighted and never upgrades reviewed coverage.
assert coverage["evidence_weighting"]["open_unmerged_candidate"].endswith("cannot upgrade coverage state")
assert any(item.get("candidate_evidence_references") for item in coverage["capabilities"])
assert next(item for item in coverage["capabilities"] if item["capability"] == "Browser acquisition")["state"] == "partial"

# CK25: the compact policy registry materializes five referentially valid
# Learning -> Human Confirmation -> Ground Truth chains.
policy_bundle = materialize_human_confirmed_policy_bundle(human_policies)
assert len(policy_bundle["learning_records"]) == 5
assert len(policy_bundle["review_records"]) == 0
assert len(policy_bundle["confirmation_records"]) == 5
assert len(policy_bundle["ground_truth_records"]) == 5
assert all(record["status"] == "human_confirmed" for record in policy_bundle["ground_truth_records"])

# CK26: price temporal status is an independent taxonomy axis with the exact
# human-confirmed current, historical, and unresolved states.
assert "price_temporal_status" in index
assert index["price_temporal_status"] == {
    "PTS-CURRENT-ADVERTISED", "PTS-HISTORICAL-OBSERVED", "PTS-TEMPORAL-UNKNOWN",
}
price_policy = next(item for item in human_policies["policies"] if item["policy_id"] == "KU2D-HC-000002")
price_decision = price_policy["final_decision"]
assert price_decision["current_active_official_business_page_without_contrary_history"] == "current_advertised_price"
assert price_decision["current_advertised_price_temporal_reference"] == "observed_at"
assert price_decision["known_historical_evidence"] == "historical_observed_price"
assert price_decision["unresolved_temporality"] == "temporal_status_unknown"
assert price_decision["acquisition_method_alone_determines_temporality"] is False
assert set(price_decision["acquisition_methods_that_do_not_determine_temporality_alone"]) == {
    "official_api", "rendered_dom", "structured_response", "export",
    "snapshot", "archive", "cache", "other_acquisition_method",
}
assert price_decision["temporal_status_separate_from_price_role"] is True
assert price_decision["does_not_imply"] == ["transaction_price", "all_branch_price", "variant_equivalence"]

# CK27: candidate source evidence remains entirely separate and unpromoted.
assert len(candidate_registry["candidates"]) == 11
assert all(item["authority"]["promoted_to_reviewed_episode_id"] is None for item in candidate_registry["candidates"])
assert not any(
    episode["source"]["name"] in {item["source"] for item in candidate_registry["candidates"]}
    for episode in human_episodes
)

# CK28: packet decisions and materialized confirmations agree exactly.
policy_by_id = {item["policy_id"]: item for item in human_policies["policies"]}
confirmation_by_id = {
    item["confirmation_record_id"]: item for item in policy_bundle["confirmation_records"]
}
for item in human_candidates["items"]:
    policy = policy_by_id[item["candidate_id"]]
    assert item["final_decision"] == policy["final_decision"]
    assert confirmation_by_id[item["human_confirmation_record_id"]]["confirmed_decision"] == item["final_decision"]

# CK29: Human Confirmation does not authorize production, scheduling, or ML export.
assert policy_bundle["production_authorized"] is False
assert policy_bundle["ml_dataset_export_enabled"] is False
assert policy_bundle["scheduler_action"] is None
assert all(record["acquisition_outcome"]["production_approved"] is False for record in policy_bundle["learning_records"])
assert all(record["acquisition_outcome"]["production_store"] is False for record in policy_bundle["learning_records"])

# CK30: all eight ML specifications remain non-executing after authority enrichment.
assert len(ml_map["tasks"]) == 8
assert ml_map["training_or_inference_enabled"] is False
assert ml_map["dataset_export_enabled"] is False

print("Core Knowledge deterministic tests passed (CK1-CK30).")
