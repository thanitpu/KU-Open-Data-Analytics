"""Deterministic tests for the Acquisition-to-Analysis handoff boundary."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))

from acquisition_analysis_handoff import legacy_candidate_is_readable, validate_analysis_intake

MANIFEST_PATH = ROOT / "knowledge/v1/analysis-intake-manifests/KU2D-AI-000001.json"
PACKET_PATH = ROOT / "knowledge/v1/candidate-closure-packets/KU2D-YT-QDIVING-CANDIDATES-000001.json"
SCHEMA_PATH = ROOT / "knowledge/v1/acquisition-analysis-handoff.schema.json"
POLICY_PATH = ROOT / "knowledge/v1/acquisition-analysis-boundary-policy.json"

manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
packet = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def rejects(record, *, source_packet=packet):
    try:
        validate_analysis_intake(record, packet=source_packet)
    except ValueError:
        return True
    return False


# AAI1-AAI12: exact durable P50 preservation and active contract.
assert validate_analysis_intake(manifest, packet=packet) is manifest
assert manifest["manifest_id"] == "KU2D-AI-000001"
assert manifest["acquisition_acceptance"]["status"] == "accepted_for_analysis"
assert manifest["acquisition_acceptance"]["accepted_record_count"] == 10
assert manifest["analysis_handoff"]["record_count"] == 10
assert manifest["retrieval"] == {
    "record_count": 10, "all_records_indexed": True, "immutable_packet_required": True,
    "provenance_preserved": True, "hidden_record_count_zero": True,
}
assert [row["candidate_id"] for row in manifest["records"]] == [row["video_id"] for row in packet["candidates"]]
assert all(row["acceptance_status"] == "accepted_for_analysis" for row in manifest["records"])
assert all(row["quality"] is None and row["semantic_relevance"] is None for row in manifest["records"])
assert all(row["analytical_rank"] is None and row["analytical_deduplication"] is None for row in manifest["records"])
assert all(row["final_inclusion"] is None and row["production_ready"] is False for row in manifest["records"])
assert manifest["boundaries"]["provider_request_performed"] is False
assert manifest["boundaries"]["documented_quota_units"] == 0

# AAI13-AAI18: packet hashes and policy/schema alignment are explicit.
packet_bytes = PACKET_PATH.read_bytes().replace(b"\r\n", b"\n")
blob_sha = hashlib.sha1(f"blob {len(packet_bytes)}\0".encode("ascii") + packet_bytes).hexdigest()
packet_ref = manifest["source_batch"]["immutable_packet"]
assert blob_sha == packet_ref["git_blob_sha"]
assert hashlib.sha256(packet_bytes).hexdigest() == packet_ref["sha256"]
assert schema["properties"]["schema"]["const"] == manifest["schema"]
assert set(schema["required"]) == set(manifest)
assert policy["handoff_schema"] == manifest["schema"]
assert policy["historical_compatibility"]["legacy_selection_target_is_active_gate"] is False

# AAI19-AAI31: loss, authority drift, semantic claims and provenance drift fail closed.
for mutate in (
    lambda row: row["records"].pop(),
    lambda row: row["records"].append(copy.deepcopy(row["records"][0])),
    lambda row: row["records"][0].update(source_packet_index=1),
    lambda row: row["records"][0].update(quality=1.0),
    lambda row: row["records"][0].update(semantic_relevance=True),
    lambda row: row["records"][0].update(production_ready=True),
    lambda row: row["records"][0].update(record_type="approved_video"),
    lambda row: row["records"][0].update(unreviewed_extra_field=True),
    lambda row: row["records"][0]["provenance"].update(channel_id="OTHER"),
    lambda row: row["acquisition_acceptance"].update(accepted_record_count=2),
    lambda row: row["analysis_handoff"].update(status="approved"),
    lambda row: row["retrieval"].update(hidden_record_count_zero=False),
    lambda row: row["boundaries"].update(provider_request_performed=True),
):
    broken = copy.deepcopy(manifest)
    mutate(broken)
    assert rejects(broken)

# AAI32-AAI35: historical fields are readable evidence only, never current authority.
assert all(legacy_candidate_is_readable(row) for row in packet["candidates"])
legacy_promoted = copy.deepcopy(packet["candidates"][0])
legacy_promoted["usable_for_live_acquisition"] = True
assert legacy_candidate_is_readable(legacy_promoted) is False
assert manifest["governance"]["analysis_selection_is_acquisition_authority"] is False
assert manifest["boundaries"]["production_approved"] is False and manifest["boundaries"]["scheduler_action"] is None

print("Acquisition-to-Analysis handoff deterministic tests passed (AAI1-AAI35).")
