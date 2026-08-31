"""Deterministic offline tests for YouTube operational hardening v1."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))

from youtube_operational_hardening import (  # noqa: E402
    CHECKPOINT_SCHEMA, LEDGER_SCHEMA, aggregate_campaign, canonical_watch_url,
    deep_audit_batch, evaluate_batch_scenario, manifest_intent_fingerprint,
    normalize_comment_observations, operational_tier, plan_quota_budget,
    reconcile_quota_ledger, request_key, resume_pending_request_keys,
    validate_batch_manifest, validate_checkpoint, validate_identity_registry,
    validate_ku2a_intake,
)


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def rejects(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


registry_contract = load("config/youtube_reviewed_video_identity_registry.json")
templates = load("config/youtube_batch_manifest_v1.json")["templates"]
policy = load("config/youtube_operational_hardening_v1.json")
p36 = load("config/youtube_p36_consolidation.json")
scenarios = load("fixtures/youtube_operational_hardening/sanitized_batch_scenarios.json")
intake = load("fixtures/youtube_operational_hardening/sanitized_ku2a_intake.json")

# YOH1-YOH10: durable empty registry is honest; synthetic Human Review is validated fail-closed.
assert validate_identity_registry(registry_contract) is registry_contract
assert registry_contract["readiness"]["usable_identity_count"] == 0
assert registry_contract["candidate_audit"]["live_discovery_performed"] is False
assert all(not row["usable_for_live_acquisition"] for row in registry_contract["candidate_only_evidence"])


def reviewed_entry(n: int):
    video_id = f"REALVID000{n}"
    return {
        "registry_entry_id": f"YT-ID-{n}", "video_id": video_id,
        "canonical_watch_url": canonical_watch_url(video_id), "channel_id": "UC-SIM-CHANNEL",
        "title_snapshot": f"Sanitized reviewed title {n}", "status": "active", "superseded_by": None,
        "revocation_reason": None, "privacy_classification": "public_metadata", "sanitized": False,
        "review_linkage": {"review_record_id": f"HUMAN-REVIEW-{n}", "review_status": "reviewed",
                           "knowledge_use": "include", "reviewed_by_actor": "human",
                           "decision_source": "explicit_human_input", "reviewed_by": "fixture-human",
                           "reviewed_at": "2026-09-01T00:00:00Z", "source_candidate_ids": [video_id]},
        "purpose_profile_ids": ["Q-DIVING-TH", "Q-DIVING-EN"],
        "source_evidence_references": [f"offline-fixture:{n}"],
        "source_relationship_evidence": [{"video_id": video_id, "channel_id": "UC-SIM-CHANNEL"}],
        "usable_for_live_acquisition": True,
    }


reviewed_registry = copy.deepcopy(registry_contract)
reviewed_registry["entries"] = [reviewed_entry(1), reviewed_entry(2)]
reviewed_registry["readiness"] = {"usable_identity_count": 2, "required_qdiving_identity_count": 2,
                                  "qdiving_two_video_status": "batch_ready_reviewed_identity"}
assert validate_identity_registry(reviewed_registry) is reviewed_registry
for mutate in (
    lambda r: r["entries"].append(copy.deepcopy(r["entries"][0])),
    lambda r: r["entries"][0].update(video_id="SAN-VID-001"),
    lambda r: r["entries"][0]["review_linkage"].update(reviewed_by_actor="assistant"),
    lambda r: r["entries"][0]["review_linkage"].update(source_candidate_ids=["REALVID0002"]),
    lambda r: r["entries"][0]["source_relationship_evidence"][0].update(channel_id="conflict"),
    lambda r: r["entries"][0].update(status="revoked", revocation_reason="withdrawn"),
):
    bad = copy.deepcopy(reviewed_registry); mutate(bad)
    assert rejects(lambda bad=bad: validate_identity_registry(bad))

# YOH11-YOH23: manifest identity, exact-input, module, bounded page and immutable intent rules.
for template in templates:
    assert validate_batch_manifest(template, registry_contract) is template
    assert template["execution_authorized"] is False
    assert template["identity_registry_entry_ids"] == []
    assert template["request_intent_fingerprint"] == manifest_intent_fingerprint(template)
manifest = copy.deepcopy(templates[0])
manifest["identity_registry_entry_ids"] = ["YT-ID-1", "YT-ID-2"]
manifest["execution_authorized"] = True
manifest["request_intent_fingerprint"] = manifest_intent_fingerprint(manifest)
assert validate_batch_manifest(manifest, reviewed_registry) is manifest
for mutate in (
    lambda m: m.update(search_fallback=True), lambda m: m["allowed_endpoints"].append("search.list"),
    lambda m: m["comment_policy"].update(comment_threads_max_pages_per_video=3),
    lambda m: m["execution_policy"].update(concurrency=2), lambda m: m.update(production_store=True),
    lambda m: m.update(request_intent_fingerprint="stale"),
):
    bad = copy.deepcopy(manifest); mutate(bad)
    assert rejects(lambda bad=bad: validate_batch_manifest(bad, reviewed_registry))

# YOH24-YOH34: official-cost planner and evidence-first quota ledger reconcile.
plan = plan_quota_budget(2)
assert plan["videos_list_requests"] == 1 and plan["max_estimated_quota_units"] == 9
assert plan["unit_cost_value_origin"] == "official_documentation_accessed_2026-09-01"
assert plan["workload_value_origin"] == "proposal_not_observed"
assert rejects(lambda: plan_quota_budget(2, metadata_batch_size=51))
events = []
for method, video_id, page in (("videos.list", "REALVID0001", 0),
                               ("commentThreads.list", "REALVID0001", 0),
                               ("comments.list", "REALVID0001", 0)):
    events.append({"method": method, "video_id": video_id, "request_key": request_key(method, video_id, page_index=page),
                   "unit_cost": 1, "value_origin": "official_documentation_accessed_2026-09-01",
                   "evidence_durable_before_next_request": True})
ledger = {"schema": LEDGER_SCHEMA, "events": events, "consumed_budget": 3, "remaining_budget": 7,
          "request_count": 3, "method_request_counts": {"videos.list": 1, "commentThreads.list": 1,
          "comments.list": 1}, "page_count": 2, "video_count": 1, "stop_reason": "fixture_complete"}
assert reconcile_quota_ledger(ledger, manifest) is ledger
bad_ledger = copy.deepcopy(ledger); bad_ledger["events"][0]["evidence_durable_before_next_request"] = False
assert rejects(lambda: reconcile_quota_ledger(bad_ledger, manifest))

# YOH35-YOH44: durable checkpoint/resume never widens or replays request intent.
planned = [row["request_key"] for row in events]
checkpoint = {"schema": CHECKPOINT_SCHEMA, "run_id": "SIM-RUN-01", "manifest_id": manifest["manifest_id"],
              "request_intent_fingerprint": manifest["request_intent_fingerprint"],
              "expected_video_ids": ["REALVID0001"], "checkpoint_durable": True,
              "video_checkpoints": [{"video_id": "REALVID0001", "status": "in_progress",
                  "comment_threads_pages_durable": 1, "raw_page_token": None,
                  "next_page_token_fingerprint": "a" * 64, "durable_request_keys": planned[:2]}]}
assert validate_checkpoint(checkpoint, manifest) is checkpoint
assert resume_pending_request_keys(checkpoint, manifest, planned) == planned[2:]
bad_checkpoint = copy.deepcopy(checkpoint); bad_checkpoint["video_checkpoints"][0]["raw_page_token"] = "secret"
assert rejects(lambda: validate_checkpoint(bad_checkpoint, manifest))
bad_checkpoint = copy.deepcopy(checkpoint); bad_checkpoint["request_intent_fingerprint"] = "changed"
assert rejects(lambda: validate_checkpoint(bad_checkpoint, manifest))

# YOH45-YOH60: all required deterministic batch scenarios and per-video isolation.
assert len(scenarios["scenarios"]) == 14 and scenarios["live_source_requests"] == 0
scenario_results = {row["scenario_id"]: evaluate_batch_scenario(row) for row in scenarios["scenarios"]}
for row in scenarios["scenarios"]:
    assert scenario_results[row["scenario_id"]]["exit_classification"] == row["expected_exit"]
assert scenario_results["partial-replies-requiring-comments-list"]["comments_list_required"] is True
assert scenario_results["checkpoint-resume"]["resume_skips_durable_requests"] is True
assert scenario_results["page-limit-truncation"]["coverage_truncated"] is True
video_ok = {"video_id": "REALVID0001", "availability": "available", "metadata_identity_complete": True,
            "evidence_durable": True, "quota_integrity": True, "technical_failure": None}
video_missing = {**video_ok, "video_id": "REALVID0002", "availability": "unavailable"}
assert aggregate_campaign([video_ok])["exit_classification"] == 0
assert aggregate_campaign([video_ok, video_missing])["exit_classification"] == 2
video_technical = {**video_ok, "video_id": "REALVID0002", "technical_failure": "writer"}
assert aggregate_campaign([video_ok, video_technical])["exit_classification"] == 1

# YOH61-YOH70: relationship dedupe/edited semantics and source/video/module Deep Audit.
comment_rows = [
    {"video_id": "REALVID0001", "thread_id": "T1", "comment_id": "C1", "parent_comment_id": None,
     "published_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"},
    {"video_id": "REALVID0001", "thread_id": "T1", "comment_id": "C1", "parent_comment_id": None,
     "published_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-02T00:00:00Z"},
]
normalized = normalize_comment_observations(comment_rows, video_id="REALVID0001")
assert len(normalized["comments"]) == 1 and normalized["duplicate_observation_count"] == 1
audit_input = {"source_audit": {"identity_provenance_integrity": True, "quota_ledger_reconciled": True,
               "checkpoint_deterministic": True, "production_approved": False},
               "video_audits": [{"availability": "available", "metadata_identity_complete": True,
                                  "statistics_are_snapshot": True}],
               "module_audits": {"comment_relationship_integrity": True,
                 "pagination_coverage_disclosed": True, "unsupported_language_transcript_text_count": 0,
                 "unauthorized_caption_oauth_count": 0, "representativeness_claim_count": 0}}
audit = deep_audit_batch(audit_input)
assert audit["passed"] is True and audit["hard_failures"] == []
broken_audit = copy.deepcopy(audit_input); broken_audit["module_audits"]["representativeness_claim_count"] = 1
assert deep_audit_batch(broken_audit)["passed"] is False

# YOH71-YOH84: storage-neutral KU2A sample, tiers, drift, gates, and P36 boundary.
assert validate_ku2a_intake(intake) is intake
assert intake["audit"]["analytics_performed"] is False and intake["production_approved"] is False
bad_intake = copy.deepcopy(intake); bad_intake["entities"]["comment_replies"][0]["parent_comment_id"] = "UNKNOWN"
assert rejects(lambda: validate_ku2a_intake(bad_intake))
assert operational_tier(None) == "identity_review_required"
assert operational_tier(reviewed_entry(1)) == "batch_ready_reviewed_identity"
assert operational_tier(reviewed_entry(1), drift=True) == "drift_review_required"
assert operational_tier(None, owner_caption_requested=True) == "owner_authorized_caption_required"
assert operational_tier(None, withheld=True) == "unavailable_or_withheld"
assert len(policy["drift_taxonomy"]) >= 12 and len(policy["human_gate_register"]) >= 8
assert policy["live_source_request_count"] == 0 and policy["production_approved"] is False
assert p36["resolved_reviewed_identity_count"] == 0 and p36["observed_counts"]["requests"] == 0
assert p36["failure_boundaries"] == {"identity_evidence_withheld": True, "credential_failure": False,
    "transport_failure": False, "youtube_access_failure": False, "comment_failure": False}

print("YouTube operational hardening deterministic tests passed (YOH1-YOH84).")
