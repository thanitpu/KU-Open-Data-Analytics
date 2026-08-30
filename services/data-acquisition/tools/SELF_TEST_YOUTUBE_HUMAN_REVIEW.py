"""Deterministic checks for YouTube Human Review, monitoring, and KU2A handoff."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "acquisition", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from youtube_human_review import (
    CONTENT_ROLES,
    EQUIPMENT_VOCABULARY,
    YouTubeChannelReview,
    YouTubeVideoReview,
    create_knowledge_dataset,
    create_monitoring_plan,
    prepare_review_package,
    suggest_channel_class,
    suggest_commercial_context,
    suggest_relevance,
    validate_review_package_integrity,
)
from youtube_source_foundation import load_policy, load_query_profiles
from PREPARE_YOUTUBE_HUMAN_REVIEW import main as prepare_main

FIXTURE = ROOT / "fixtures" / "youtube_human_review" / "sanitized_foundation_result.json"
SCHEMA = ROOT / "config" / "youtube_knowledge_dataset_schema.json"
source = json.loads(FIXTURE.read_text(encoding="utf-8"))
source_before = copy.deepcopy(source)
package = prepare_review_package(source)


def complete_video_review(review_package, video_id, *, relevance="core", knowledge_use="include"):
    review = next(row for row in review_package["video_reviews"] if row["video_id"] == video_id)
    review.update({
        "review_status": "reviewed",
        "relevance": relevance,
        "content_roles": ["training"] if relevance != "irrelevant" else [],
        "commercial_context": "none",
        "knowledge_use": knowledge_use,
        "reviewer_note": "Sanitized deterministic review.",
        "reviewed_by": "ku2d-reviewer",
        "reviewed_at": "2026-08-30T00:00:00Z",
    })
    return review


def complete_channel_review(review_package, channel_id, *, decision, source_class, domain_focus):
    review = next(row for row in review_package["channel_reviews"] if row["channel_id"] == channel_id)
    review.update({
        "review_status": "reviewed",
        "source_class": source_class,
        "domain_focus": domain_focus,
        "monitoring_decision": decision,
        "reviewer_note": "Sanitized deterministic review.",
        "reviewed_by": "ku2d-reviewer",
        "reviewed_at": "2026-08-30T00:00:00Z",
    })
    return review


def assert_handoff_fails(review_package, message_fragment):
    try:
        create_knowledge_dataset(review_package, dataset_id="EXPECTED-FAILURE")
        raise AssertionError(f"Malformed handoff accepted: {message_fragment}")
    except ValueError as exc:
        assert message_fragment in str(exc), (message_fragment, str(exc))

# A/B: reviews are separate, pending, and blank; automation produces suggestions only.
assert source == source_before
assert package["review_stage"] == "human-review-pending"
assert all(row["review_status"] == "pending" for row in package["video_reviews"])
assert all(row["review_status"] == "pending" for row in package["channel_reviews"])
assert all(row["relevance"] is None and row["knowledge_use"] is None for row in package["video_reviews"])
assert all(row["source_class"] is None and row["monitoring_decision"] is None for row in package["channel_reviews"])
assert all("suggested_relevance" in row["review_suggestions"] for row in package["candidate_videos"])
assert "human_review_status" not in json.dumps(package)

by_video = {row["video_id"]: row for row in package["candidate_videos"]}
by_channel = {row["channel_id"]: row for row in package["candidate_channels"]}

# C/D/E: core, adjacent, and irrelevant screening is deterministic and location aware.
assert by_video["SAN-TH-BEGINNER"]["review_suggestions"]["suggested_relevance"] == "core"
assert by_video["SAN-EN-KOH-TAO"]["review_suggestions"]["suggested_relevance"] == "core"
assert by_video["SAN-FREEDIVING"]["review_suggestions"]["suggested_relevance"] == "adjacent"
assert "not equivalent" in " ".join(by_video["SAN-FREEDIVING"]["review_suggestions"]["suggestion_basis"])
assert by_video["SAN-PHUKET-SCUBA"]["review_suggestions"]["suggested_relevance"] == "adjacent"
assert "Koh Tao" in " ".join(by_video["SAN-PHUKET-SCUBA"]["review_suggestions"]["suggestion_basis"])
assert by_video["SAN-NONDIVING"]["review_suggestions"]["suggested_relevance"] == "irrelevant"
assert by_video["SAN-AFFILIATE-GEAR"]["review_suggestions"]["suggested_relevance"] == "core"
assert {"mask", "bcd", "regulator"}.issubset(
    set(by_video["SAN-AFFILIATE-GEAR"]["review_suggestions"]["suggested_equipment_topics"])
)
assert {
    "mask", "fins", "wetsuit", "bcd", "regulator", "dive_computer", "tank",
    "underwater_camera", "accessory", "maintenance", "rental", "purchase", "fitting_sizing",
} == set(EQUIPMENT_VOCABULARY)
assert "equipment" in CONTENT_ROLES

# F: operator/travel class hints remain distinguishable and explicitly non-authoritative.
operator_hint = by_channel["SAN-DIVE-OPERATOR"]["review_suggestions"]
travel_hint = by_channel["SAN-TRAVEL-CREATOR"]["review_suggestions"]
assert operator_hint["suggested_source_class"] == "dive_operator"
assert travel_hint["suggested_source_class"] == "travel_dive_creator"
assert operator_hint["authoritative"] is False and travel_hint["authoritative"] is False
assert suggest_channel_class({"channel_title":"Unclassified", "channel_description":"General videos"})["suggested_source_class"] == "other"

# G: disclosed commercial text creates evidence-bearing hints; no hidden sponsorship is inferred.
commercial = by_video["SAN-AFFILIATE-GEAR"]["review_suggestions"]
assert commercial["commercial_context_suggestion"] == "affiliate"
assert any(row["matched_cue"] == "affiliate" for row in commercial["commercial_context_evidence"])
assert commercial["hidden_sponsorship_inferred"] is False
assert by_video["SAN-AFFILIATE-GEAR"]["youtube_paid_product_placement"] is False
quiet = suggest_commercial_context({"title":"Scuba skills", "description":"Neutral lesson"})
assert quiet["commercial_context_suggestion"] == "unknown"
assert quiet["commercial_context_evidence"] == [] and quiet["hidden_sponsorship_inferred"] is False
product_promotion = suggest_commercial_context({"title":"New dive mask - buy now", "description":"Available now"})
assert product_promotion["commercial_context_suggestion"] == "promotional_offer"
assert product_promotion["commercial_context_evidence"]

# H/I/J/K: monitoring requires completed channel approval and an uploads playlist; it stays dry.
operator_candidate = by_channel["SAN-DIVE-OPERATOR"]
pending_review = next(row for row in package["channel_reviews"] if row["channel_id"] == "SAN-DIVE-OPERATOR")
for invalid_review, invalid_candidate in (
    (pending_review, operator_candidate),
    ({**pending_review, "review_status":"reviewed", "source_class":"dive_operator",
      "domain_focus":"diving_specialist", "monitoring_decision":"watch",
      "reviewed_by":"reviewer", "reviewed_at":"2026-08-30T00:00:00Z"}, operator_candidate),
    ({**pending_review, "review_status":"reviewed", "source_class":"dive_operator",
      "domain_focus":"diving_specialist", "monitoring_decision":"approve",
      "reviewed_by":"reviewer", "reviewed_at":"2026-08-30T00:00:00Z"},
     {**operator_candidate, "uploads_playlist_id":None}),
):
    try:
        create_monitoring_plan(invalid_review, invalid_candidate)
        raise AssertionError("unsafe monitoring plan accepted")
    except ValueError:
        pass
approved_channel_review = {
    **pending_review,
    "review_status": "reviewed",
    "source_class": "dive_operator",
    "domain_focus": "diving_specialist",
    "monitoring_decision": "approve",
    "reviewer_note": "Sanitized fixture approval.",
    "reviewed_by": "ku2d-reviewer",
    "reviewed_at": "2026-08-30T00:00:00Z",
}
plan = create_monitoring_plan(approved_channel_review, operator_candidate, cadence="weekly")
assert plan["uploads_playlist_id"] == "UU-SAN-DIVE-OPERATOR"
assert plan["production_enabled"] is False and plan["scheduler_action"] is None
assert set(plan) == {
    "channel_id", "uploads_playlist_id", "source_class", "approved_by", "approved_at",
    "cadence", "production_enabled", "scheduler_action",
}

# L: textual amounts are context candidates, never Product & Price acquisition evidence.
mentions = package["price_mention_candidates"]
assert len(mentions) == 1 and mentions[0]["value"] == "299" and mentions[0]["currency"] == "USD"
assert mentions[0]["record_type"] == "PriceMentionCandidate"
assert mentions[0]["stated_by_source"] is True
assert mentions[0]["current_commerce_price_evidence"] is False
assert mentions[0]["product_price_acquisition_record"] is False
assert "ProductCandidate" not in json.dumps(mentions) and "PriceObservation" not in json.dumps(mentions)

# M/A: rejecting ongoing monitoring never removes an included video's source channel provenance.
rejected_package = copy.deepcopy(package)
complete_video_review(
    rejected_package, "SAN-FREEDIVING", relevance="adjacent", knowledge_use="include_with_context",
)
rejected_channel_review = complete_channel_review(
    rejected_package,
    "SAN-TRAVEL-CREATOR",
    decision="reject",
    source_class="travel_dive_creator",
    domain_focus="travel_with_diving",
)
rejected_dataset = create_knowledge_dataset(
    rejected_package,
    dataset_id="QDIVING-YOUTUBE-REJECTED-MONITORING",
    generated_at="2026-08-30T01:00:00Z",
)
assert rejected_dataset["included_video_ids"] == ["SAN-FREEDIVING"]
assert rejected_dataset["included_channel_ids"] == ["SAN-TRAVEL-CREATOR"]
assert rejected_dataset["monitoring_approved_channel_ids"] == []
assert rejected_dataset["monitoring_watch_channel_ids"] == []
assert rejected_dataset["human_review_summary"]["source_channels_included"] == 1
assert rejected_dataset["human_review_summary"]["monitoring_channels_rejected"] == 1
try:
    create_monitoring_plan(rejected_channel_review, by_channel["SAN-TRAVEL-CREATOR"])
    raise AssertionError("rejected channel created a monitoring plan")
except ValueError:
    pass

# M/B: approved monitoring is separate, uses uploads, and remains non-production.
reviewed_package = copy.deepcopy(package)
complete_video_review(reviewed_package, "SAN-EN-KOH-TAO", relevance="core", knowledge_use="include")
channel_review = complete_channel_review(
    reviewed_package,
    "SAN-DIVE-OPERATOR",
    decision="approve",
    source_class="dive_operator",
    domain_focus="diving_specialist",
)
dataset = create_knowledge_dataset(
    reviewed_package,
    dataset_id="QDIVING-YOUTUBE-SANITIZED-001",
    generated_at="2026-08-30T01:00:00Z",
)
assert dataset["schema"] == "ku2d.youtube-knowledge-dataset.v1"
assert dataset["domain"] == "q_diving" and dataset["source_type"] == "youtube"
assert dataset["included_video_ids"] == ["SAN-EN-KOH-TAO"]
assert dataset["included_channel_ids"] == ["SAN-DIVE-OPERATOR"]
assert dataset["monitoring_approved_channel_ids"] == ["SAN-DIVE-OPERATOR"]
assert dataset["monitoring_watch_channel_ids"] == []
assert dataset["research_collections"] == ["learn_to_dive"]
assert dataset["human_review_summary"]["video_reviews_completed"] == 1
assert dataset["human_review_summary"]["monitoring_channels_approved"] == 1
assert dataset["provenance_summary"]["provider"] == "youtube-data-api-v3"
assert dataset["provenance_summary"]["human_review_required"] is True
assert dataset["data_refresh_due_at"] == "2026-09-28T09:00:00+00:00"
assert dataset["production_approved"] is False
approved_plan = create_monitoring_plan(channel_review, by_channel["SAN-DIVE-OPERATOR"])
assert approved_plan["production_enabled"] is False and approved_plan["scheduler_action"] is None

# M/C: watch is represented only in its explicit list and cannot create a monitoring plan.
watch_package = copy.deepcopy(package)
complete_video_review(watch_package, "SAN-FREEDIVING", relevance="adjacent", knowledge_use="include_with_context")
watch_review = complete_channel_review(
    watch_package,
    "SAN-TRAVEL-CREATOR",
    decision="watch",
    source_class="travel_dive_creator",
    domain_focus="travel_with_diving",
)
watch_dataset = create_knowledge_dataset(watch_package, dataset_id="QDIVING-YOUTUBE-WATCH")
assert watch_dataset["included_channel_ids"] == ["SAN-TRAVEL-CREATOR"]
assert watch_dataset["monitoring_approved_channel_ids"] == []
assert watch_dataset["monitoring_watch_channel_ids"] == ["SAN-TRAVEL-CREATOR"]
try:
    create_monitoring_plan(watch_review, by_channel["SAN-TRAVEL-CREATOR"])
    raise AssertionError("watch channel created a monitoring plan")
except ValueError:
    pass

# M/D-H: unknown and duplicate candidate/review identities fail before aggregation.
broken = copy.deepcopy(package)
broken["video_reviews"][0]["video_id"] = "UNKNOWN-VIDEO"
assert_handoff_fails(broken, "Unknown video review identity: UNKNOWN-VIDEO")
broken = copy.deepcopy(package)
broken["channel_reviews"][0]["channel_id"] = "UNKNOWN-CHANNEL"
assert_handoff_fails(broken, "Unknown channel review identity: UNKNOWN-CHANNEL")
broken = copy.deepcopy(package)
broken["video_reviews"].append(copy.deepcopy(broken["video_reviews"][0]))
assert_handoff_fails(broken, "Duplicate video review identity")
broken = copy.deepcopy(package)
broken["channel_reviews"].append(copy.deepcopy(broken["channel_reviews"][0]))
assert_handoff_fails(broken, "Duplicate channel review identity")
broken = copy.deepcopy(package)
broken["candidate_videos"].append(copy.deepcopy(broken["candidate_videos"][0]))
assert_handoff_fails(broken, "Duplicate candidate video identity")
broken = copy.deepcopy(package)
broken["candidate_channels"].append(copy.deepcopy(broken["candidate_channels"][0]))
assert_handoff_fails(broken, "Duplicate candidate channel identity")
broken = copy.deepcopy(package)
broken["video_reviews"].pop()
assert_handoff_fails(broken, "Candidate video has no review record")
broken = copy.deepcopy(package)
broken["candidate_channels"][0]["channel_id"] = ""
assert_handoff_fails(broken, "empty channel_id")

# M/I-K: contradictory completed decisions and finalized pending records fail closed.
broken = copy.deepcopy(package)
complete_video_review(broken, "SAN-NONDIVING", relevance="irrelevant", knowledge_use="include")
assert_handoff_fails(broken, "irrelevant video must be excluded")
validate_review_package_integrity(reviewed_package)  # core/include
validate_review_package_integrity(watch_package)  # adjacent/include_with_context
broken = copy.deepcopy(package)
broken["video_reviews"][0]["relevance"] = "core"
assert_handoff_fails(broken, "Pending video review carries final field")
broken = copy.deepcopy(package)
broken["channel_reviews"][0]["monitoring_decision"] = "approve"
assert_handoff_fails(broken, "Pending channel review carries final field")

# M/L-N: included candidate identity and provenance come from the candidate record, not the review.
broken = copy.deepcopy(reviewed_package)
next(row for row in broken["candidate_videos"] if row["video_id"] == "SAN-EN-KOH-TAO")["channel_id"] = None
assert_handoff_fails(broken, "has no source channel_id")
broken = copy.deepcopy(reviewed_package)
next(row for row in broken["candidate_videos"] if row["video_id"] == "SAN-EN-KOH-TAO")["refresh_due_at"] = None
assert_handoff_fails(broken, "has no refresh_due_at")
broken = copy.deepcopy(reviewed_package)
next(row for row in broken["candidate_videos"] if row["video_id"] == "SAN-EN-KOH-TAO")["provenance"] = {}
assert_handoff_fails(broken, "lacks official provider provenance")
broken = copy.deepcopy(reviewed_package)
next(row for row in broken["candidate_videos"] if row["video_id"] == "SAN-EN-KOH-TAO")["provenance"]["provider"] = "untrusted-provider"
assert_handoff_fails(broken, "lacks official provider provenance")
broken = copy.deepcopy(reviewed_package)
next(row for row in broken["candidate_videos"] if row["video_id"] == "SAN-EN-KOH-TAO")["query_profile_ids"] = []
assert_handoff_fails(broken, "has no query-profile provenance path")
broken = copy.deepcopy(reviewed_package)
next(row for row in broken["candidate_videos"] if row["video_id"] == "SAN-EN-KOH-TAO")["publicly_usable"] = False
assert_handoff_fails(broken, "not from a current, publicly usable foundation record")

# The schema makes monitoring separation, identity uniqueness, and provenance constraints explicit.
schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
assert schema["properties"]["production_approved"]["const"] is False
assert set(schema["required"]) == set(dataset)
for field_name in (
    "included_video_ids", "included_channel_ids", "monitoring_approved_channel_ids",
    "monitoring_watch_channel_ids",
):
    assert schema["properties"][field_name]["uniqueItems"] is True
    assert schema["properties"][field_name]["items"]["minLength"] == 1
summary_schema = schema["properties"]["human_review_summary"]
assert {
    "source_channels_included", "monitoring_channels_approved",
    "monitoring_channels_watch", "monitoring_channels_rejected",
}.issubset(summary_schema["required"])
provenance_schema = schema["properties"]["provenance_summary"]
assert provenance_schema["properties"]["provider"]["const"] == "youtube-data-api-v3"
assert provenance_schema["properties"]["human_review_required"]["const"] is True

# N/O: transcript text never enters the review package and comments remain disabled.
assert all(row["transcript_text"] is None for row in source["videos"])
assert "transcript_text" not in json.dumps(package)
policy = load_policy()
assert policy["comments_enabled"] is False and policy["comment_threads_enabled"] is False
assert policy["comment_acquisition_enabled"] is False
assert policy["production_scheduling_enabled"] is False
assert "other" in policy["manual_source_classes"]

# Tool contract is deterministic, compact, and does not leak raw responses or credentials.
secret = "SANITIZED-SECRET-MUST-NOT-LEAK"
tool_source = copy.deepcopy(source)
tool_source["api_key"] = secret
tool_source["raw_api_response"] = {"secret": secret}
with tempfile.TemporaryDirectory() as temp_dir:
    input_path = Path(temp_dir) / "foundation.json"
    output_path = Path(temp_dir) / "review.json"
    input_path.write_text(json.dumps(tool_source), encoding="utf-8")
    assert prepare_main(["--input", str(input_path), "--output", str(output_path)]) == 0
    serialized = output_path.read_text(encoding="utf-8")
    staged = json.loads(serialized)
    assert staged == package
    assert secret not in serialized and "raw_api_response" not in serialized
    assert "thumbnail" not in serialized and "transcript_text" not in serialized

# Equipment Pilot #2 is prepared as exactly two existing profiles, but this test makes no API call.
profile_by_id = {row["profile_id"]: row for row in load_query_profiles()}
equipment_ids = ["QYT-EQUIPMENT-BEGINNER-TH", "QYT-EQUIPMENT-SETUP-EN"]
assert all(profile_id in profile_by_id for profile_id in equipment_ids)
assert all(profile_by_id[profile_id]["research_collection"] == "diving_equipment" for profile_id in equipment_ids)

# Model constructors also preserve pending defaults independent of staging.
assert YouTubeVideoReview("VID").review_status == "pending"
assert YouTubeChannelReview("CHAN").monitoring_decision is None

print("YouTube Human Review and knowledge handoff deterministic contracts: PASS")
