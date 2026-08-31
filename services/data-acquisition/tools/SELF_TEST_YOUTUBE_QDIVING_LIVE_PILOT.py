"""Deterministic tests for the fail-closed Q-Diving live-pilot preflight."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))

from youtube_qdiving_live_pilot import (  # noqa: E402
    IdentityEvidenceWithheld,
    resolve_exact_reviewed_video_ids,
    validate_pilot_evidence,
)


CASES = json.loads(
    (ROOT / "fixtures" / "youtube_qdiving_live_pilot" / "reviewed_identity_cases.json").read_text(encoding="utf-8")
)
EVIDENCE = json.loads((ROOT / "config" / "youtube_qdiving_live_pilot_v1.json").read_text(encoding="utf-8"))


def withheld(records):
    try:
        resolve_exact_reviewed_video_ids(records)
    except IdentityEvidenceWithheld:
        return True
    return False


# QDP1-QDP5: only exact, canonical, non-sanitized Human-Reviewed identities resolve.
cases = {case["case_id"]: case for case in CASES["cases"]}
assert resolve_exact_reviewed_video_ids(cases["exact-two-real-reviewed"]["records"]) == [
    "VID-REAL001", "VID-REAL002",
]
for case_id in ("no-durable-reviewed-identities", "sanitized-only", "ambiguous-three", "duplicate-identity"):
    assert withheld(cases[case_id]["records"]), case_id

# QDP6-QDP18: durable result is an evidence-before-request exit-2 boundary.
assert validate_pilot_evidence(EVIDENCE) is EVIDENCE
assert EVIDENCE["classification"] == "evidence_withheld"
assert EVIDENCE["exit_classification"] == 2
assert EVIDENCE["technical_completion"] is True
assert EVIDENCE["identity_preflight"]["required_video_count"] == 2
assert EVIDENCE["identity_preflight"]["resolved_video_count"] == 0
assert EVIDENCE["identity_preflight"]["resolved_video_ids"] == []
assert EVIDENCE["credential_boundary"]["status"] == "not_evaluated"
assert EVIDENCE["request_quota_ledger"]["request_count"] == 0
assert EVIDENCE["request_quota_ledger"]["estimated_quota_units"] == 0
assert EVIDENCE["request_quota_ledger"]["comment_threads_page_count"] == 0
assert EVIDENCE["metadata_outcome"]["video_result_count"] == 0
assert EVIDENCE["comments_outcome"]["top_level_comment_count"] == 0
assert EVIDENCE["comments_outcome"]["reply_count"] == 0

# QDP19-QDP25: caption/transcript activity and active-policy mutation remain zero/false.
caption = EVIDENCE["transcript_caption_boundary"]
assert caption["allowed_languages"] == ["th", "en"]
for field in (
    "captions_list_request_count", "captions_download_request_count", "transcript_content_record_count",
    "oauth_flow_count", "audio_video_download_count",
):
    assert caption[field] == 0
policy = json.loads((ROOT / "config" / "youtube_api_policy.json").read_text(encoding="utf-8"))
assert policy["comments_enabled"] is False
assert policy["comment_threads_enabled"] is False

# QDP26-QDP34: Deep Audit and non-production semantics are explicit.
audit = EVIDENCE["deep_audit"]
assert audit["passed"] is False
assert audit["gates"]["exact_reviewed_identity_count"] is False
assert audit["gates"]["request_quota_accounting"] is True
assert audit["gates"]["comment_page_bound_preserved"] is True
assert audit["gates"]["evidence_written_before_live_request"] is True
assert audit["gates"]["transcript_caption_boundary_preserved"] is True
assert EVIDENCE["production_approval_state_mutated"] is False
assert EVIDENCE["knowledge_authority_state_mutated"] is False
assert EVIDENCE["boundaries"]["production_store"] is False
assert EVIDENCE["boundaries"]["scheduler_action"] is None

# QDP35-QDP40: invalid evidence fails closed instead of becoming false-green.
for mutation in (
    lambda row: row["request_quota_ledger"].update(request_count=1),
    lambda row: row["identity_preflight"].update(resolved_video_ids=["VID-REAL001"], resolved_video_count=1),
    lambda row: row["transcript_caption_boundary"].update(captions_download_request_count=1),
    lambda row: row["authority"]["authorized_limits"].update(video_count=3),
    lambda row: row["boundaries"].update(production_store=True),
    lambda row: row.update(exit_classification=0),
):
    broken = copy.deepcopy(EVIDENCE)
    mutation(broken)
    try:
        validate_pilot_evidence(broken)
        raise AssertionError("invalid pilot evidence validated")
    except ValueError:
        pass

print("Q-Diving YouTube live-pilot preflight deterministic tests passed (QDP1-QDP40).")
