"""Deterministic offline tests for YouTube Content Acquisition Pattern v2."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))

from youtube_content_acquisition_v2 import (  # noqa: E402
    ALLOWED_LANGUAGES,
    EXPECTED_BOUNDARIES,
    PATTERN_STEPS,
    TRACK_PRECEDENCE,
    build_dataset_intake,
    normalize_comment_case,
    normalize_transcript_case,
    validate_dataset_intake,
    validate_youtube_content_contract,
)


CONTRACT_PATH = ROOT / "config" / "youtube_content_acquisition_v2.json"
FIXTURE_PATH = ROOT / "fixtures" / "youtube_content_v2" / "sanitized_content_bundle.json"
SCHEMA_PATH = ROOT / "config" / "youtube_content_dataset_schema_v2.json"
contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
v1_policy = json.loads((ROOT / "config" / "youtube_api_policy.json").read_text(encoding="utf-8"))
acquired_at = fixture["acquired_at"]


def rejects_contract(mutator, message: str) -> None:
    changed = deepcopy(contract)
    mutator(changed)
    try:
        validate_youtube_content_contract(changed)
        raise AssertionError(message)
    except ValueError:
        pass


def rejects_transcript(case: dict, message: str) -> None:
    try:
        normalize_transcript_case(case, acquired_at=acquired_at)
        raise AssertionError(message)
    except ValueError:
        pass


def rejects_comments(case: dict, message: str) -> None:
    try:
        normalize_comment_case(case, acquired_at=acquired_at)
        raise AssertionError(message)
    except ValueError:
        pass


# YT2-1..YT2-10: the contract is detached, non-executable, and preserves v1 safety.
validated = validate_youtube_content_contract(contract)
assert validated == contract and validated is not contract
assert contract["schema"] == "ku2d.youtube-content-acquisition.v2"
assert contract["status"] == "offline-contract-ready-not-live-validated-not-authorized"
assert contract["boundaries"] == EXPECTED_BOUNDARIES
assert contract["boundaries"]["live_youtube_request_count"] == 0
assert contract["boundaries"]["caption_download_count"] == 0
assert contract["boundaries"]["comment_live_acquisition_count"] == 0
assert contract["boundaries"]["oauth_flow_count"] == 0
assert v1_policy["comments_enabled"] is False and v1_policy["comment_acquisition_enabled"] is False
assert v1_policy["arbitrary_transcript_acquisition_enabled"] is False and v1_policy["production_scheduling_enabled"] is False

# YT2-11..YT2-24: metadata capability and field absence remain explicit.
metadata = {row["capability"]: row for row in contract["metadata_capability_map"]}
assert len(metadata) == 6
assert metadata["channel_identity_metadata_statistics_and_uploads_playlist"]["endpoint"] == "channels.list"
assert "uploads_playlist_id" in metadata["channel_identity_metadata_statistics_and_uploads_playlist"]["normalized_fields"]
assert "generic_updated_at" in metadata["channel_identity_metadata_statistics_and_uploads_playlist"]["unavailable_or_not_inferred"]
assert metadata["playlist_video_enumeration"]["endpoint"] == "playlistItems.list"
assert "displayed_position_as_importance" in metadata["playlist_video_enumeration"]["unavailable_or_not_inferred"]
video_capability = metadata["video_metadata_content_status_statistics_topics_and_live_state"]
assert video_capability["endpoint"] == "videos.list"
assert {"statistics", "topicDetails", "liveStreamingDetails"} <= set(video_capability["resource_parts"])
assert {"default_language", "default_audio_language", "duration", "caption_available"} <= set(video_capability["normalized_fields"])
assert "generic_updated_at" in video_capability["unavailable_or_not_inferred"]
assert "statistics_as_causal_explanation" in video_capability["unavailable_or_not_inferred"]
assert metadata["video_category_lookup"]["endpoint"] == "videoCategories.list"
assert metadata["owner_only_video_details"]["access_class"] == "owner_authorized_only"
assert all(str(url).startswith("https://developers.google.com/youtube/v3/") for row in metadata.values() for url in row["evidence"] if row["evidence_class"] == "official_documentation_capability")

# YT2-25..YT2-39: language, authorization, precedence, and method classes are exact.
transcript = contract["transcript_caption_contract"]
assert transcript["allowed_languages"] == ALLOWED_LANGUAGES == ["th", "en"]
assert transcript["retain_other_language_text"] is False
assert transcript["retain_other_language_availability_metadata"] is True
assert transcript["automatic_language_substitution"] is False
assert transcript["same_language_track_precedence"] == TRACK_PRECEDENCE
assert transcript["selected_track_output_language_order"] == ["th", "en"]
methods = {row["method"]: row for row in transcript["capability_classes"]}
assert methods["videos.list contentDetails.caption"]["content_available"] is False
assert methods["captions.list"]["access_class"] == "owner_authorized_only"
assert methods["captions.list"]["estimated_quota_cost"] == 50
assert methods["captions.download"]["access_class"] == "owner_authorized_only"
assert methods["captions.download"]["estimated_quota_cost"] == 200
assert methods["public_transcript_surface"]["access_class"] == "not_approved_unresolved"
assert "no_captions is not extraction_failure" in transcript["absence_rules"]
assert "unsupported_language_only is not extraction_failure" in transcript["absence_rules"]
assert "owner_authorization_required is not public extraction_failure" in transcript["absence_rules"]

# YT2-40..YT2-60: every caption case normalizes deterministically without language leakage.
caption_results = {row["case_id"]: normalize_transcript_case(row, acquired_at=acquired_at) for row in fixture["caption_cases"]}
manual_th = caption_results["manual-th-with-auto-and-unsupported-availability"]
assert manual_th["selected_track_ids"] == ["TR-TH-MANUAL"]
assert len(manual_th["segments"]) == 2
assert {row["language"] for row in manual_th["segments"]} == {"th"}
assert manual_th["other_language_availability"] == [{"track_id":"TR-JA-AVAILABLE","language":"ja","content_retained":False}]
assert all(row["caption_kind"] == "manual_original" for row in manual_th["segments"])
both = caption_results["manual-en-plus-explicit-th-translation"]
assert both["selected_track_ids"] == ["TR-TH-TRANSLATED", "TR-EN-MANUAL"]
assert [row["language"] for row in both["segments"]] == ["th", "en"]
assert both["segments"][0]["is_translated"] is True
assert both["segments"][1]["is_original_language"] is True
assert caption_results["auto-generated-th"]["segments"][0]["caption_kind"] == "auto_generated_original"
assert caption_results["auto-generated-en"]["segments"][0]["is_auto_generated"] is True
unsupported = caption_results["unsupported-language-only"]
assert unsupported["segments"] == [] and unsupported["module_status"] == "unsupported_language_only"
assert unsupported["other_language_availability"][0]["language"] == "ja"
assert caption_results["no-captions"]["module_status"] == "no_captions"
assert caption_results["captions-disabled"]["module_status"] == "captions_disabled"
assert caption_results["private-deleted-unavailable-video"]["module_status"] == "unavailable"
partial = caption_results["partial-transcript-with-timestamp-gap"]
assert partial["module_status"] == "partial" and partial["completeness"]["complete"] is False
assert partial["completeness"]["timestamp_gap_count"] == 1
assert partial["segments"][1]["start_seconds"] is None
assert caption_results["owner-authorization-required"]["segments"] == []
assert all(row["language"] in ALLOWED_LANGUAGES for result in caption_results.values() for row in result["segments"])

# YT2-61..YT2-75: comments preserve relationships, coverage, edit time, and non-representativeness.
comment_results = {row["case_id"]: normalize_comment_case(row, acquired_at=acquired_at) for row in fixture["comment_cases"]}
published = comment_results["published-threads-replies-pagination-and-edit"]
assert len(published["comments"]) == 2
assert len(published["comment_replies"]) == 2
assert published["coverage"]["duplicate_observation_count"] == 1
assert published["coverage"]["incomplete_thread_count"] == 0
assert published["coverage"]["page_count"] == 2
assert published["coverage"]["representative_sample_claimed"] is False
assert published["comments"][0]["completeness"]["edited"] is True
assert published["comments"][0]["published_at"] != published["comments"][0]["updated_at"]
assert all(row["parent_comment_id"] == "COMMENT-1" for row in published["comment_replies"])
assert all(row["quality"]["representative_sample_claimed"] is False for row in published["comments"] + published["comment_replies"])
assert comment_results["comments-disabled"]["module_status"] == "comments_disabled"
assert comment_results["no-comments"]["module_status"] == "no_comments"
assert comment_results["partial-replies"]["coverage"]["incomplete_thread_count"] == 1
assert comment_results["partial-replies"]["coverage"]["next_page_available"] is True
assert comment_results["deleted-or-moderated-observation"]["comments"][0]["moderation_or_availability_state"] == "deleted_or_unavailable"
assert comment_results["video-unavailable-comments"]["module_status"] == "unavailable"
assert comment_results["quota-boundary"]["module_status"] == "quota_boundary"
assert contract["comments_replies_contract"]["current_v1_policy_enabled"] is False

# YT2-76..YT2-88: configurable modules and storage-neutral KU2A intake fail closed.
dataset = build_dataset_intake(
    fixture,
    transcript_results=[caption_results["manual-th-with-auto-and-unsupported-availability"], both],
    comment_results=[published, comment_results["comments-disabled"]],
    module_requirements={"metadata":"required", "transcript":"optional", "comments":"optional"},
)
assert dataset["schema"] == "ku2d.youtube-content-dataset.v2"
assert dataset["exit_classification"] == 0 and dataset["approved"] is True
assert dataset["technical_completion"] is True
assert dataset["required_module_gaps"] == []
assert len(dataset["channels"]) == 2 and len(dataset["videos"]) == 2
assert len(dataset["transcript_segments"]) == 4
assert len(dataset["comments"]) == 2 and len(dataset["comment_replies"]) == 2
assert dataset["quality"]["other_language_transcript_text_count"] == 0
assert dataset["quality"]["representativeness_claim_count"] == 0
assert dataset["production_approved"] is False
assert dataset["production_store"] is False and dataset["scheduler_action"] is None
assert validate_dataset_intake(dataset) == dataset
required_comments = build_dataset_intake(
    fixture,
    transcript_results=[manual_th, both],
    comment_results=[published, comment_results["comments-disabled"]],
    module_requirements={"metadata":"required", "transcript":"required", "comments":"required"},
)
assert required_comments["exit_classification"] == 2 and required_comments["approved"] is False
assert required_comments["required_module_gaps"] == ["comments:VID-EN"]
partial_required = build_dataset_intake(
    fixture,
    transcript_results=[{**manual_th, "module_status":"partial"}, both],
    comment_results=[published, comment_results["comments-disabled"]],
    module_requirements={"metadata":"required", "transcript":"required", "comments":"optional"},
)
assert partial_required["required_module_gaps"] == ["transcript:VID-TH"]

# YT2-89..YT2-101: pattern, semantic, audit, readiness, and schema contracts are explicit.
pattern = contract["youtube_acquisition_pattern_v2"]
assert pattern["steps"] == PATTERN_STEPS
assert pattern["module_requirements"] == {"metadata":"required","transcript":"optional","comments":"optional"}
assert set(pattern["exit_classification"]) == {"0", "1", "2"}
assert "third-party arbitrary transcript scraper" in pattern["non_approved_methods"]
assert "browser or Edge fallback" in pattern["non_approved_methods"]
semantics = set(contract["cross_content_semantic_boundaries"])
assert "creator speech is not viewer opinion" in semantics
assert "comment count is not sentiment" in semantics
assert "API or displayed ordering is not representativeness" in semantics
assert contract["deep_audit"]["transcript"]["unsupported_language_text_count"] == 0
assert contract["deep_audit"]["comments"]["representativeness_claim_count"] == 0
assert contract["ku2d_to_ku2a_dataset_intake"]["youtube_acquisition_logic_required_by_consumer"] is False
assert contract["ku2d_to_ku2a_dataset_intake"]["production_approved"] is False
assert contract["readiness"]["pilot_execution_authorized"] is False
assert contract["readiness"]["smallest_future_live_pilot"]["source"] == "Q-Diving reviewed YouTube candidates"

# YT2-102..YT2-119: false-green contract and normalization mutations are rejected.
rejects_contract(lambda row: row["transcript_caption_contract"].update(allowed_languages=["th","en","ja"]), "broadened transcript languages validated")
rejects_contract(lambda row: row["transcript_caption_contract"].update(retain_other_language_text=True), "other-language retention validated")
rejects_contract(lambda row: row["transcript_caption_contract"].update(automatic_language_substitution=True), "automatic language substitution validated")
rejects_contract(lambda row: row["transcript_caption_contract"]["capability_classes"][1].update(access_class="public_api_key_read"), "captions.list public access validated")
rejects_contract(lambda row: row["comments_replies_contract"].update(current_v1_policy_enabled=True), "comments live policy enablement validated")
rejects_contract(lambda row: row["comments_replies_contract"]["future_pilot_default_max_pages"].update(value_origin="observed"), "page proposal represented as observed validated")
rejects_contract(lambda row: row["youtube_acquisition_pattern_v2"]["module_requirements"].update(metadata="optional"), "optional metadata validated")
rejects_contract(lambda row: row["boundaries"].update(live_youtube_request_count=1), "live request validated")
rejects_contract(lambda row: row.update(api_key="secret"), "credential-bearing contract validated")

other_text = deepcopy(next(row for row in fixture["caption_cases"] if row["case_id"] == "unsupported-language-only"))
other_text["tracks"][0]["content_authorized_for_fixture"] = True
other_text["tracks"][0]["segments"] = [{"segment_order":0,"start_seconds":0,"duration_seconds":1,"end_seconds":1,"text":"forbidden"}]
rejects_transcript(other_text, "other-language text normalized")
translated = deepcopy(next(row for row in fixture["caption_cases"] if row["case_id"] == "manual-en-plus-explicit-th-translation"))
translated["tracks"][2].pop("translated_from_language")
rejects_transcript(translated, "translation without origin normalized")
unauthorized = deepcopy(next(row for row in fixture["caption_cases"] if row["case_id"] == "auto-generated-en"))
unauthorized["tracks"][0]["content_authorized_for_fixture"] = False
rejects_transcript(unauthorized, "unauthorized fixture content normalized")
bad_time = deepcopy(next(row for row in fixture["caption_cases"] if row["case_id"] == "auto-generated-en"))
bad_time["tracks"][0]["segments"][0]["end_seconds"] = 9
rejects_transcript(bad_time, "invalid transcript timestamps normalized")
over_pages = deepcopy(next(row for row in fixture["comment_cases"] if row["case_id"] == "published-threads-replies-pagination-and-edit"))
over_pages["page_count"] = 3
rejects_comments(over_pages, "unbounded comment pagination normalized")
wrong_video = deepcopy(next(row for row in fixture["comment_cases"] if row["case_id"] == "published-threads-replies-pagination-and-edit"))
wrong_video["threads"][0]["video_id"] = "OTHER"
rejects_comments(wrong_video, "thread/video mismatch normalized")
wrong_parent = deepcopy(next(row for row in fixture["comment_cases"] if row["case_id"] == "published-threads-replies-pagination-and-edit"))
wrong_parent["threads"][0]["embedded_replies"][0]["parent_comment_id"] = "OTHER"
rejects_comments(wrong_parent, "reply/parent mismatch normalized")
no_provenance = deepcopy(next(row for row in fixture["comment_cases"] if row["case_id"] == "published-threads-replies-pagination-and-edit"))
no_provenance["threads"][0]["top_level_comment"]["provenance"] = {}
rejects_comments(no_provenance, "comment without provenance normalized")

# YT2-120..YT2-128: dataset and JSON Schema pin safety and language invariants.
unsafe_dataset = deepcopy(dataset); unsafe_dataset["production_approved"] = True
try:
    validate_dataset_intake(unsafe_dataset)
    raise AssertionError("production dataset validated")
except ValueError:
    pass
unsafe_dataset = deepcopy(dataset); unsafe_dataset["quality"]["representativeness_claim_count"] = 1
try:
    validate_dataset_intake(unsafe_dataset)
    raise AssertionError("representativeness claim validated")
except ValueError:
    pass
unsafe_dataset = deepcopy(dataset); unsafe_dataset["transcript_segments"][0]["language"] = "ja"
try:
    validate_dataset_intake(unsafe_dataset)
    raise AssertionError("other-language dataset text validated")
except ValueError:
    pass
assert schema["properties"]["production_approved"]["const"] is False
assert schema["properties"]["production_store"]["const"] is False
assert schema["properties"]["scheduler_action"]["type"] == "null"
assert schema["$defs"]["transcript_segment"]["properties"]["language"]["enum"] == ["th", "en"]
assert set(schema["required"]) == set(dataset)
assert fixture["boundaries"]["live_request_count"] == 0 and fixture["boundaries"]["other_language_transcript_text_count"] == 0

print("YouTube Content Acquisition v2 deterministic tests passed (YT2-1..YT2-132).")
