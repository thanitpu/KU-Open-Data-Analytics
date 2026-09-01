from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIKTOK = ROOT / "knowledge" / "v1" / "tiktok"
if str(TIKTOK) not in sys.path:
    sys.path.insert(0, str(TIKTOK))

from scope_declaration import FIELDS, SEVEN_FIELDS, validate_scope_declaration


def load(name: str) -> dict:
    return json.loads((TIKTOK / name).read_text(encoding="utf-8"))


def rejected(value: dict, **kwargs) -> None:
    try:
        validate_scope_declaration(value, **kwargs)
    except ValueError:
        return
    raise AssertionError("invalid scope declaration was accepted")


root = load("KU2D-SCOPE-000001.json")
phase = load("KU2D-SCOPE-000001-P01.json")
deep_audit_phase = load("KU2D-SCOPE-000001-P02.json")
adapter_phase = load("KU2D-SCOPE-000001-P03.json")
authority = {"KU2D-H-000023"}
allowed_files = list(root["authorized_files_or_modules"])
schema = json.loads((ROOT / "knowledge" / "v1" / "phase-package-scope-declaration.schema.json").read_text(encoding="utf-8"))
assert schema["additionalProperties"] is False
assert set(schema["required"]) == FIELDS
assert set(schema["properties"]) == FIELDS
assert SEVEN_FIELDS.issubset(root)
assert validate_scope_declaration(
    root, allowed_root_files=allowed_files, allowed_human_authority_ids=authority,
) == root
assert validate_scope_declaration(
    phase, parent=root, allowed_human_authority_ids=authority,
) == phase
assert validate_scope_declaration(
    deep_audit_phase, parent=root, allowed_human_authority_ids=authority,
) == deep_audit_phase
assert validate_scope_declaration(
    adapter_phase, parent=root, allowed_human_authority_ids=authority,
) == adapter_phase

case = copy.deepcopy(root)
del case["capability"]
rejected(case, allowed_root_files=allowed_files, allowed_human_authority_ids=authority)
case = copy.deepcopy(root)
case["unknown"] = True
rejected(case, allowed_root_files=allowed_files, allowed_human_authority_ids=authority)
case = copy.deepcopy(root)
case["authorized_files_or_modules"].append("services/data-acquisition/acquisition/source_runner.py")
rejected(case, allowed_root_files=allowed_files, allowed_human_authority_ids=authority)
case = copy.deepcopy(root)
case["authorized_files_or_modules"].append("unapproved/module.py")
rejected(case, allowed_root_files=allowed_files, allowed_human_authority_ids=authority)
case = copy.deepcopy(root)
case["validation_profile"].remove("exact-head full deterministic corpus")
rejected(case, allowed_root_files=allowed_files, allowed_human_authority_ids=authority)
case = copy.deepcopy(phase)
case["capability"].append("private_account_data")
rejected(case, parent=root, allowed_human_authority_ids=authority)
case = copy.deepcopy(phase)
case["human_authority_id"] = "KU2D-H-999999"
rejected(case, parent=root, allowed_human_authority_ids=authority)

evidence = load("KU2D-TIKTOK-EXPLORE-000001.json")
blocker = load("KU2D-TIKTOK-FOUNDATION-BLOCKER-000001.json")
assert evidence["request_accounting"] == {
    "maximum_authorized": 20, "provider_requests": 5, "quota_delta": 0,
    "retained_records_per_topic": {"diving_lesson": 0, "diving_equipment": 0},
}
assert len(evidence["requests"]) == 5
assert all(row["stable_video_identity_count"] == 0 for row in evidence["requests"])
assert all(row["confirmed_challenge"] is False for row in evidence["requests"])
assert all(row["access_classification"] == "external_blocker_no_compliant_topic_discovery_surface" for row in evidence["topic_results"])
assert blocker["attempted_extension"]["attempt_persisted_in_final_tree"] is False
assert blocker["provider_accounting"] == {"provider_requests": 5, "maximum_authorized": 20, "quota_delta": 0}
assert blocker["boundaries"]["production_approved"] is False
assert blocker["boundaries"]["scheduler_action"] is None

print("TikTok Source Completion checks passed: scope_positive=4 scope_negative=7 requests=5 blockers=2")
