"""Offline deterministic tests for P38 identity discovery and review staging."""
from __future__ import annotations
import copy, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))
from youtube_identity_discovery_review import (build_review_package, quota_plan, retain_candidates,
                                                validate_discovery_evidence)

cases = json.loads((ROOT / "fixtures/youtube_identity_discovery/sanitized_cases.json").read_text(encoding="utf-8"))
evidence = json.loads((ROOT / "config/youtube_qdiving_identity_discovery_v1.json").read_text(encoding="utf-8"))
package = json.loads((ROOT / "fixtures/youtube_identity_discovery/sanitized_human_review_package.json").read_text(encoding="utf-8"))

def rejects(fn):
    try: fn()
    except ValueError: return True
    return False

# YID1-YID10: official-cost bounded planning and current withheld evidence.
plan = quota_plan(2)
assert plan["request_cap"] == 3 and plan["quota_unit_cap"] == 201
assert plan["unit_costs"] == {"search.list": 100, "videos.list": 1}
assert plan["value_origin"] == "official_documentation_accessed_2026-09-01"
assert rejects(lambda: quota_plan(0)) and rejects(lambda: quota_plan(9))
assert validate_discovery_evidence(evidence) is evidence
assert evidence["credential_preflight"] == {"configured": False, "secret_read_or_logged": False}
assert evidence["request_quota_ledger"]["request_count"] == 0
assert evidence["candidate_count"] == 0 and evidence["usable_reviewed_identity_count"] == 0

# YID11-YID24: duplicates, unavailable/private, ambiguity and bounded retention.
result = retain_candidates(cases["search_rows"], cases["metadata_rows"])
assert [row["video_id"] for row in result["retained"]] == cases["expected"]["retained_ids"]
assert result["duplicate_cross_profile_count"] == cases["expected"]["duplicate_cross_profile_count"]
assert sorted(row["reason"] for row in result["excluded"]) == sorted(cases["expected"]["excluded_reasons"])
assert result["retained"][0]["query_profile_ids"] == ["QYT-BEGINNER-EN", "QYT-BEGINNER-KOH-TAO-TH"]
assert all(row["human_review_status"] == "pending" for row in result["retained"])
assert all(row["usable_for_live_acquisition"] is False for row in result["retained"])
assert retain_candidates(cases["zero_result_query"], [], limit=2)["retained"] == []
assert cases["quota_stop"]["planned_quota_units"] > cases["quota_stop"]["available_quota_units"]
assert cases["quota_stop"]["request_must_not_start"] is True
bad = copy.deepcopy(cases["search_rows"]); bad[0]["video_id"] = "bad"
assert rejects(lambda: retain_candidates(bad, cases["metadata_rows"]))

# YID25-YID36: Human Review package is usable for adjudication but has no authority.
staged = build_review_package(result["retained"])
assert staged["selection_target"] == 2 and staged["candidate_count"] == 2
assert staged["suggestions_are_non_authoritative"] is True
assert staged["human_adjudication_required"] is True
assert staged["production_approved"] is False and staged["scheduler_action"] is None
promoted = copy.deepcopy(result["retained"]); promoted[0]["human_review_status"] = "reviewed"
assert rejects(lambda: build_review_package(promoted))
assert package["candidate_count"] == 0 and package["human_adjudication_required"] is True
assert evidence["boundaries"]["comments_acquired"] is False
assert evidence["boundaries"]["captions_called"] is False
assert evidence["boundaries"]["transcript_text_acquired"] is False
assert evidence["boundaries"]["oauth_used"] is False

# YID37-YID45: invalid classification, authority and preflight accounting fail closed.
for mutation in (
    lambda row: row.update(exit_classification=0),
    lambda row: row["request_quota_ledger"].update(request_count=1),
    lambda row: row.update(usable_reviewed_identity_count=1),
    lambda row: row.update(human_review_completed=True),
    lambda row: row["boundaries"].update(comments_acquired=True),
    lambda row: row["boundaries"].update(captions_called=True),
    lambda row: row["boundaries"].update(transcript_text_acquired=True),
    lambda row: row["boundaries"].update(oauth_used=True),
    lambda row: row["boundaries"].update(scheduler_action="run"),
):
    broken = copy.deepcopy(evidence); mutation(broken)
    assert rejects(lambda broken=broken: validate_discovery_evidence(broken))

print("YouTube identity discovery/review deterministic tests passed (YID1-YID45).")
