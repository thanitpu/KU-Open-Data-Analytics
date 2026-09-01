from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIKTOK = ROOT / "knowledge" / "v1" / "tiktok"
ACQUISITION = ROOT / "acquisition"
sys.path[:0] = [str(TIKTOK), str(ACQUISITION)]

from scope_declaration import SEVEN_FIELDS, validate_scope_declaration
from technical_correction_journal import validate_technical_correction_journal


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def rejected(value: dict, **kwargs) -> None:
    try:
        validate_scope_declaration(value, **kwargs)
    except ValueError:
        return
    raise AssertionError("invalid P57 scope declaration was accepted")


root = load(TIKTOK / "KU2D-SCOPE-000004.json")
p01 = load(TIKTOK / "KU2D-SCOPE-000004-P01.json")
p02 = load(TIKTOK / "KU2D-SCOPE-000004-P02.json")
assert SEVEN_FIELDS.issubset(root)
assert validate_scope_declaration(root, allowed_root_files=root["authorized_files_or_modules"]) == root
assert validate_scope_declaration(p01, parent=root) == p01
assert validate_scope_declaration(p02, parent=root) == p02

p58_root = load(TIKTOK / "KU2D-SCOPE-000005.json")
p58_p01 = load(TIKTOK / "KU2D-SCOPE-000005-P01.json")
p58_p02 = load(TIKTOK / "KU2D-SCOPE-000005-P02.json")
assert validate_scope_declaration(
    p58_root, allowed_root_files=p58_root["authorized_files_or_modules"],
) == p58_root
assert validate_scope_declaration(p58_p01, parent=p58_root) == p58_p01
assert validate_scope_declaration(p58_p02, parent=p58_root) == p58_p02
case = copy.deepcopy(p02)
case["capability"].append("private_account_data")
rejected(case, parent=root)
case = copy.deepcopy(p01)
case["authorized_files_or_modules"].append("services/data-acquisition/acquisition/source_runner.py")
rejected(case, parent=root)

evidence = load(TIKTOK / "KU2D-TIKTOK-LIVE-EVIDENCE-000002.json")
requests = evidence["requests"]
assert [row["sequence"] for row in requests] == list(range(1, 33))
assert all(row["status"] != "planned" for row in requests)
assert all(set(row) == {"sequence", "timestamp", "strategy", "surface", "topic", "purpose", "status", "records_found", "stable_ids_found", "retained", "failure_class", "quota_delta"} for row in requests)
assert sum(row["retained"] for row in requests) == 0
assert sum(row["quota_delta"] for row in requests) == 0
assert sum(row["failure_class"] == "network_preconnect_failure_provider_not_reached" for row in requests) == 16
assert evidence["request_accounting"] == {
    "historical_requests": 5,
    "new_requests": 27,
    "cumulative_requests": 32,
    "provider_reached_requests": 11,
    "preconnect_failures": 16,
    "quota_delta": 0,
    "remaining_authorized_new_requests": 13,
}
assert evidence["retained_records"] == {"diving_lesson": [], "diving_equipment": []}
assert evidence["minimum_additional_requests_required"]["would_exceed_new_request_limit"] is True
assert evidence["phase_outcome"] == {
    "entered_phases": ["P57-01", "P57-02"],
    "unentered_phases": ["P57-03", "P57-04", "P57-05"],
    "status": "blocked",
    "stop_condition": "more than 40 new outbound requests is required",
    "content_absence_claimed": False,
    "oembed_verification_technique_proven": True,
    "acquisition_technique_frozen": False,
}
assert evidence["boundaries"]["production_approved"] is False
assert evidence["boundaries"]["scheduler_action"] is None

p58_evidence = load(TIKTOK / "KU2D-TIKTOK-EPHEMERAL-BROWSER-EVIDENCE-000003.json")
assert p58_evidence["status"] == "evidence_withheld"
assert p58_evidence["technical_completion"] is True
assert p58_evidence["success"] is False
assert p58_evidence["operation_accounting"] == {
    "provider_reached": 17,
    "provider_limit": 40,
    "preconnect_failures": 2,
    "preconnect_limit": 10,
    "quota_delta": 0,
}
assert p58_evidence["budget_feasibility"] == {
    "provider_reached": 17,
    "provider_limit": 40,
    "provider_remaining": 23,
    "preconnect_failures": 2,
    "preconnect_limit": 10,
    "minimum_provider_operations_for_two_complete_rounds": 24,
    "success_contract_still_feasible": False,
}
assert p58_evidence["phase_outcome"] == {
    "entered_phases": ["P58-01", "P58-02"],
    "unentered_phases": ["P58-03", "P58-04", "P58-05"],
    "status": "blocked",
    "acquisition_technique_frozen": False,
    "adapter_or_registry_artifacts_created": False,
}
assert p58_evidence["final_records"] == {"Diving lesson": [], "Diving equipment": []}
assert all(row["status"] != "started" for row in p58_evidence["operation_ledger"])
assert all(proof["profile_absent_after_teardown"] for proof in p58_evidence["context_destruction_proofs"])
assert all(not proof["cookie_values_persisted"] for proof in p58_evidence["context_destruction_proofs"])
assert p58_evidence["boundaries"]["production_approved"] is False
assert p58_evidence["boundaries"]["scheduler_action"] is None

for absent in (
    ROOT / "acquisition" / "tiktok_diving_connector.py",
    ROOT / "config" / "adapter_registry_v3.json",
    ROOT / "config" / "source_manifests" / "tiktok_diving_v1.json",
    ROOT / "config" / "run_manifests" / "tiktok_diving_fixture_v1.json",
):
    assert not absent.exists(), f"blocked P57 must not create {absent.relative_to(ROOT)}"

baseline_blobs = {
    ".github/workflows/data-acquisition-platform-ci.yml": "481a6f072c541831d562ab5f3dabc6fecd3ce143",
    "services/data-acquisition/acquisition/source_runner.py": "0e0355bbc07bfa3e47d716943f1adf7be5bb388d",
    "services/data-acquisition/acquisition/connector_kit.py": "208c64142c3b62f1c38e475c88061fa1d2338981",
    "services/data-acquisition/acquisition/run_manifest.py": "f1be696ecc799be409569ae872f53dfbe75fb651",
    "services/data-acquisition/acquisition/adapter_registry.py": "e3110ddb36e185f2bff2b30b65087563e043e16a",
    "services/data-acquisition/config/adapter_registry_v1.json": "398dd4daba89d5e6d3e80cb67d52984b114058d3",
    "services/data-acquisition/config/adapter_registry_v2.json": "dfdf74bcf332082d2ab80e58ba6a8cedc80965d8",
}
repository_root = ROOT.parents[1]
for relative, expected_blob in baseline_blobs.items():
    actual = subprocess.run(
        ["git", "hash-object", "--path", relative, relative],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert actual == expected_blob, f"protected blob drifted: {relative}"

journal = load(ROOT / "knowledge" / "v1" / "correction-journals" / "KU2D-CJ-000007.json")
validate_technical_correction_journal(journal, require_closed=True)
links = [event.get("related_commit_or_pending_commit") for event in journal["events"]]
assert all(isinstance(link, str) and re.fullmatch(r"[0-9a-f]{40}", link) for link in links)
assert sum(event["provider_impact"]["request_delta"] for event in journal["events"]) == 27
assert journal["summary"] == {"event_count": 6, "resolved_count": 5, "unresolved_count": 1, "correction_cycles_used": 6}

p58_journal = load(ROOT / "knowledge" / "v1" / "correction-journals" / "KU2D-CJ-000008.json")
validate_technical_correction_journal(p58_journal, require_closed=True)
assert p58_journal["summary"] == {
    "event_count": 10,
    "resolved_count": 9,
    "unresolved_count": 1,
    "correction_cycles_used": 10,
}
assert all(
    isinstance(event["related_commit_or_pending_commit"], str)
    and re.fullmatch(r"[0-9a-f]{40}", event["related_commit_or_pending_commit"])
    for event in p58_journal["events"]
)
assert sum(event["provider_impact"]["request_delta"] for event in p58_journal["events"]) == 19
assert sum(event["provider_impact"]["quota_delta"] for event in p58_journal["events"]) == 0

print("TikTok source completion checks passed: P57 requests=27 corrections=6; P58 provider=17 preconnect=2 corrections=10")
