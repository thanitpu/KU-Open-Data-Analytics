from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
if str(ACQUISITION) not in sys.path:
    sys.path.insert(0, str(ACQUISITION))

from adapter_registry import AdapterComponents, AdapterRegistry
from source_runner import run_source_from_manifest
from technical_correction_journal import validate_technical_correction_journal
from youtube_qdiving_connector import (
    PublicVideoQDivingMapper,
    YouTubeQDivingAdapter,
    YouTubeQDivingCandidateParser,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def contains_key(value, forbidden_key: str) -> bool:
    if isinstance(value, dict):
        return forbidden_key in value or any(contains_key(child, forbidden_key) for child in value.values())
    if isinstance(value, list):
        return any(contains_key(child, forbidden_key) for child in value)
    return False


registry_document = load(ROOT / "config" / "adapter_registry_v1.json")
run_manifest = load(ROOT / "config" / "run_manifests" / "youtube_qdiving_fixture_v1.json")
source_manifest = load(ROOT / "config" / "source_manifests" / "youtube_qdiving_v1.json")
profile = load(ROOT / "config" / "domain_capability_profiles" / "public_video_q_diving_v1.json")
packet = load(ROOT / "knowledge" / "v1" / "candidate-closure-packets" / "KU2D-YT-QDIVING-CANDIDATES-000001.json")
analysis = load(ROOT / "knowledge" / "v1" / "analysis-intake-manifests" / "KU2D-AI-000001.json")
result = run_source_from_manifest(
    repository_root=ROOT,
    run_manifest=run_manifest,
    implementations={"youtube_qdiving_reference_v1": AdapterComponents(YouTubeQDivingAdapter, YouTubeQDivingCandidateParser, PublicVideoQDivingMapper)},
)

# FC1: ten candidates and exact P50/P51 ordering survive the authoritative path.
packet_ids = [row["video_id"] for row in packet["candidates"]]
analysis_ids = [row["candidate_id"] for row in analysis["records"]]
result_ids = [row["record_id"] for row in result["records"]]
assert packet_ids == analysis_ids == result_ids
assert len(result_ids) == 10

# FC2: provenance and Analysis handoff fields are preserved without semantic claims.
assert all(row["provenance"]["source_packet_id"] == "KU2D-YT-QDIVING-CANDIDATES-000001" for row in result["records"])
assert all(row["provenance"]["query_profile_ids"] for row in result["records"])
assert all(row["channel_identity"]["channel_id"] for row in result["records"])
assert all(all(value is None for value in row["analysis"].values()) for row in result["records"])
assert all(row["acquisition_acceptance"] == "accepted_for_analysis" for row in result["records"])

# FC3: the early gate is entirely technical and all authority remains closed.
assert result["quality_gate"] == {
    "status": "passed",
    "checks": {
        "authority": True, "schema": True, "provenance": True, "timestamps": True,
        "sanitization": True, "exact_technical_duplication": True,
        "evidence_completeness": True,
    },
    "hard_failures": [],
    "metrics": {"record_count": 10, "unique_identity_count": 10, "requested_capability_count": 2, "evidenced_capability_count": 2},
    "semantic_quality_scored": False,
    "final_inclusion_decided": False,
}
assert result["boundaries"] == {"semantic_quality_owner": "analysis", "production_store": False, "production_approved": False, "scheduler_action": None}

# FC4: deterministic replay performs no provider request and consumes no quota.
assert result["transport_mode"] == "fixture_replay"
assert result["request_accounting"]["provider_requests"] == 0
assert result["request_accounting"]["documented_quota_units"] == 0
assert all(row["documented_quota_units"] == 0 for row in result["capability_evidence"].values())
assert not contains_key(result["capability_evidence"], "payload")

# FC5: blocked surfaces and production authority remain unchanged.
states = {row["capability_id"]: row["state"] for row in profile["capabilities"]}
assert states["comments"] == states["captions"] == states["transcripts"] == "blocked"
assert run_manifest["request_policy"]["allow_live_provider"] is False
assert run_manifest["authority_boundaries"]["production_approved"] is False
assert run_manifest["authority_boundaries"]["scheduler_action"] is None

# FC6: the single P53 correction journal remains sanitized and internally exact.
journal = load(ROOT / "knowledge" / "v1" / "correction-journals" / "KU2D-CJ-000003.json")
validate_technical_correction_journal(
    journal, require_closed=True,
)
assert journal["summary"]["event_count"] == 4
assert all(event["related_commit_or_pending_commit"] == "4b15cf2d325a94045c73e2e824a97538c3c84da8" for event in journal["events"])
assert all(event["provider_impact"] == {"provider_reached": False, "request_delta": 0, "quota_delta": 0} for event in journal["events"])

# FC7: the additive versioning suite is part of the full deterministic CI corpus.
runpy.run_path(str(ROOT / "tools" / "SELF_TEST_VERSIONED_ADAPTER_REGISTRY.py"), run_name="__main__")

print("Foundation Consolidation integration checks passed: FC1-FC7")

# P57's bounded TikTok closure is registered without changing the CI workflow.
runpy.run_path(str(ROOT / "tools" / "SELF_TEST_TIKTOK_SOURCE_COMPLETION.py"), run_name="__main__")
