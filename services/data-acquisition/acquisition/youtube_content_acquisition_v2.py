"""Offline contracts and normalization for YouTube content acquisition v2.

This module has no transport, credential, OAuth, browser, storage, approval, or
scheduler capability. It validates the planning contract and deterministic
sanitized fixtures only.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from acquisition_learning_record import validate_safe_json_payload


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_SCHEMA = "ku2d.youtube-content-acquisition.v2"
DATASET_SCHEMA = "ku2d.youtube-content-dataset.v2"
AUTHORITATIVE_BRANCH = "codex/ku2d-youtube-content-acquisition-v2"
ALLOWED_LANGUAGES = ["th", "en"]
TRACK_PRECEDENCE = [
    "manual_original", "manual_translated",
    "auto_generated_original", "auto_generated_translated",
]
PATTERN_STEPS = [
    "Channel Discovery", "Playlist/Video Enumeration", "Metadata",
    "Thai/English Transcript/Caption", "Comments/Replies", "Normalize",
    "Provenance", "Quality/Deep Audit", "Dataset Intake",
]
MODULE_REQUIREMENTS = {"required", "optional", "disabled"}
TRANSCRIPT_ABSENCE_STATUSES = {
    "owner_authorized_only", "unavailable", "evidence_withheld",
    "unsupported_language_only", "no_captions", "captions_disabled",
    "partial",
}
COMMENT_ABSENCE_STATUSES = {
    "unavailable", "evidence_withheld", "comments_disabled", "no_comments",
    "quota_boundary", "partial",
}
EXPECTED_BOUNDARIES = {
    "contract_only": True, "executable": False, "live_youtube_request_count": 0,
    "caption_download_count": 0, "comment_live_acquisition_count": 0,
    "oauth_flow_count": 0, "browser_or_edge_request_count": 0,
    "other_language_transcript_text_count": 0, "authority_promotion_count": 0,
    "knowledge_mutation_count": 0, "parked_ref_mutation_count": 0,
    "production_authorized": False, "production_store": False,
    "scheduler_action": None, "analytics_or_ml_implemented": False,
}
OFFICIAL_DOC_PREFIX = "https://developers.google.com/youtube/v3/"
FORBIDDEN_EXECUTABLE_KEYS = {
    "request_command", "dispatch", "workflow_dispatch", "oauth_token",
    "api_key", "cookie", "authorization_header", "scheduler_command",
}


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _list(value: Any, field: str, *, nonempty: bool = True) -> list[Any]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{field} must be a JSON array" + (" with entries" if nonempty else ""))
    return value


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _walk(value: Any) -> None:
    if isinstance(value, dict):
        found = FORBIDDEN_EXECUTABLE_KEYS & set(value)
        if found:
            raise ValueError(f"executable or sensitive fields are forbidden: {sorted(found)}")
        for child in value.values():
            _walk(child)
    elif isinstance(value, list):
        for child in value:
            _walk(child)


def _official_evidence(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        if row.get("evidence_class") != "official_documentation_capability":
            continue
        evidence = _list(row.get("evidence"), "official documentation evidence")
        if any(not str(item).startswith(OFFICIAL_DOC_PREFIX) for item in evidence):
            raise ValueError("official capability cites a non-official documentation URL")


def validate_youtube_content_contract(record: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on scope, authority, module, language, quota, and safety drift."""
    if not isinstance(record, dict) or record.get("schema") != CONTRACT_SCHEMA:
        raise ValueError(f"schema must be {CONTRACT_SCHEMA}")
    _walk(record)
    if record.get("authoritative_branch") != AUTHORITATIVE_BRANCH:
        raise ValueError("authoritative branch drifted")
    if record.get("status") != "offline-contract-ready-not-live-validated-not-authorized":
        raise ValueError("contract cannot claim live validation or authorization")
    prepared = datetime.fromisoformat(str(record.get("prepared_at") or ""))
    if prepared.tzinfo is None:
        raise ValueError("prepared_at must include timezone")
    if set(record.get("evidence_classes") or []) != {
        "merged_repository_observation", "official_documentation_capability",
        "derived_contract", "proposal_not_observed", "unavailable",
    }:
        raise ValueError("evidence classes drifted")

    foundation = _mapping(record.get("existing_foundation"), "existing_foundation")
    if foundation.get("comments_enabled") is not False or foundation.get("arbitrary_transcript_enabled") is not False:
        raise ValueError("the merged v1 safety boundary was weakened")
    if foundation.get("production_scheduling_enabled") is not False:
        raise ValueError("production scheduling was enabled")
    if set(foundation.get("supported_public_methods") or []) != {
        "search.list", "channels.list", "playlists.list", "playlistItems.list", "videos.list",
    }:
        raise ValueError("merged public-method baseline drifted")

    metadata = _list(record.get("metadata_capability_map"), "metadata_capability_map")
    capabilities = {row.get("capability"): row for row in metadata if isinstance(row, dict)}
    required = {
        "channel_identity_metadata_statistics_and_uploads_playlist",
        "playlist_metadata", "playlist_video_enumeration",
        "video_metadata_content_status_statistics_topics_and_live_state",
        "video_category_lookup", "owner_only_video_details",
    }
    if set(capabilities) != required:
        raise ValueError("metadata capability inventory drifted")
    _official_evidence(metadata)
    for name, row in capabilities.items():
        _nonempty(row.get("endpoint"), f"{name}.endpoint")
        _list(row.get("resource_parts"), f"{name}.resource_parts")
        _list(row.get("unavailable_or_not_inferred"), f"{name}.unavailable_or_not_inferred")
        if not isinstance(row.get("estimated_quota_cost"), int) or row["estimated_quota_cost"] < 1:
            raise ValueError(f"{name} quota cost is invalid")
    if capabilities["owner_only_video_details"].get("access_class") != "owner_authorized_only":
        raise ValueError("owner-only video parts were represented as public")

    transcript = _mapping(record.get("transcript_caption_contract"), "transcript_caption_contract")
    if transcript.get("allowed_languages") != ALLOWED_LANGUAGES:
        raise ValueError("transcript language scope must be exactly th/en")
    if transcript.get("retain_other_language_text") is not False:
        raise ValueError("other-language transcript text retention is forbidden")
    if transcript.get("automatic_language_substitution") is not False:
        raise ValueError("automatic transcript language substitution is forbidden")
    if transcript.get("selected_track_output_language_order") != ALLOWED_LANGUAGES:
        raise ValueError("selected transcript language order drifted")
    if transcript.get("same_language_track_precedence") != TRACK_PRECEDENCE:
        raise ValueError("caption-track precedence drifted")
    methods = _list(transcript.get("capability_classes"), "transcript capability classes")
    by_method = {row.get("method"): row for row in methods if isinstance(row, dict)}
    if by_method.get("captions.list", {}).get("access_class") != "owner_authorized_only":
        raise ValueError("captions.list must remain owner-authorized only")
    if by_method.get("captions.download", {}).get("access_class") != "owner_authorized_only":
        raise ValueError("captions.download must remain owner-authorized only")
    if by_method.get("captions.list", {}).get("estimated_quota_cost") != 50:
        raise ValueError("captions.list documented quota cost drifted")
    if by_method.get("captions.download", {}).get("estimated_quota_cost") != 200:
        raise ValueError("captions.download documented quota cost drifted")
    if by_method.get("public_transcript_surface", {}).get("access_class") != "not_approved_unresolved":
        raise ValueError("an unresolved public transcript surface was approved")
    _official_evidence(methods)
    _list(transcript.get("absence_rules"), "transcript absence rules")

    comments = _mapping(record.get("comments_replies_contract"), "comments_replies_contract")
    if comments.get("current_v1_policy_enabled") is not False:
        raise ValueError("comments were enabled in the existing live policy")
    comment_methods = _list(comments.get("methods"), "comment methods")
    if {row.get("endpoint") for row in comment_methods} != {"commentThreads.list", "comments.list"}:
        raise ValueError("comment endpoint inventory drifted")
    if any(row.get("estimated_quota_cost") != 1 for row in comment_methods):
        raise ValueError("comment documented quota costs drifted")
    if any(row.get("max_results_documented") != 100 for row in comment_methods):
        raise ValueError("comment maxResults capability drifted")
    _official_evidence(comment_methods)
    proposal = _mapping(comments.get("future_pilot_default_max_pages"), "future comment page proposal")
    if proposal.get("value_origin") != "proposal_not_observed" or not proposal.get("rationale"):
        raise ValueError("comment page proposal was represented as observed")
    if not isinstance(proposal.get("value"), int) or not 1 <= proposal["value"] <= 2:
        raise ValueError("future comment page proposal must remain bounded")
    if "never population representativeness" not in str(comments.get("ordering_semantics")):
        raise ValueError("comment ordering was conflated with representativeness")
    _list(comments.get("stop_conditions"), "comment stop conditions")
    _list(comments.get("absence_rules"), "comment absence rules")

    boundaries = set(record.get("cross_content_semantic_boundaries") or [])
    for required_rule in (
        "transcript text is not video description", "creator speech is not viewer opinion",
        "comment count is not sentiment", "API or displayed ordering is not representativeness",
        "transcript absence is not content irrelevance",
        "metadata statistics are timestamped observation snapshots, not causal explanations",
        "provenance and authority are separate from interpretation",
    ):
        if required_rule not in boundaries:
            raise ValueError(f"semantic boundary missing: {required_rule}")

    pattern = _mapping(record.get("youtube_acquisition_pattern_v2"), "youtube_acquisition_pattern_v2")
    if pattern.get("steps") != PATTERN_STEPS:
        raise ValueError("YouTube v2 pattern steps drifted")
    if set(pattern.get("module_requirements", {}).values()) - MODULE_REQUIREMENTS:
        raise ValueError("invalid module requirement")
    if pattern.get("module_requirements", {}).get("metadata") != "required":
        raise ValueError("metadata must remain required")
    if set(_mapping(pattern.get("exit_classification"), "exit_classification")) != {"0", "1", "2"}:
        raise ValueError("exit classification must define 0/1/2")
    nonapproved = " ".join(pattern.get("non_approved_methods") or []).lower()
    for term in ("html scraping", "undocumented endpoint", "transcript scraper", "auth or challenge bypass"):
        if term not in nonapproved:
            raise ValueError(f"non-approved method boundary missing: {term}")

    intake = _mapping(record.get("ku2d_to_ku2a_dataset_intake"), "dataset intake")
    if intake.get("schema") != DATASET_SCHEMA or intake.get("storage_neutral") is not True:
        raise ValueError("dataset intake contract drifted")
    if intake.get("entity_order") != ["channel", "playlist", "video", "transcript_segment", "comment", "comment_reply"]:
        raise ValueError("dataset entity inventory drifted")
    for entity, contract in _mapping(intake.get("entities"), "dataset entities").items():
        _list(contract.get("identity_key"), f"{entity}.identity_key")
        _list(contract.get("required_fields"), f"{entity}.required_fields")
    if intake.get("youtube_acquisition_logic_required_by_consumer") is not False or intake.get("production_approved") is not False:
        raise ValueError("dataset consumer or production boundary drifted")
    if _mapping(record.get("boundaries"), "boundaries") != EXPECTED_BOUNDARIES:
        raise ValueError("YouTube v2 safety boundaries drifted")
    readiness = _mapping(record.get("readiness"), "readiness")
    pilot = _mapping(readiness.get("smallest_future_live_pilot"), "future pilot")
    if readiness.get("pilot_execution_authorized") is not False or pilot.get("production_store") is not False or pilot.get("scheduler_action") is not None:
        raise ValueError("future pilot was authorized")
    validate_safe_json_payload(record)
    return deepcopy(record)


def _track_rank(track: dict[str, Any]) -> tuple[int, str]:
    kind = track.get("caption_kind")
    if kind not in TRACK_PRECEDENCE:
        raise ValueError(f"unsupported caption_kind: {kind}")
    return TRACK_PRECEDENCE.index(kind), str(track.get("track_id") or "")


def normalize_transcript_case(case: dict[str, Any], *, acquired_at: str) -> dict[str, Any]:
    """Select Thai/English fixture tracks and normalize segments deterministically."""
    case_id = _nonempty(case.get("case_id"), "caption case_id")
    video_id = _nonempty(case.get("video_id"), f"{case_id}.video_id")
    status = _nonempty(case.get("module_status"), f"{case_id}.module_status")
    tracks = _list(case.get("tracks"), f"{case_id}.tracks", nonempty=False)
    availability = []
    eligible: dict[str, list[dict[str, Any]]] = {language: [] for language in ALLOWED_LANGUAGES}
    for track in tracks:
        track_id = _nonempty(track.get("track_id"), f"{case_id}.track_id")
        language = _nonempty(track.get("language"), f"{track_id}.language").lower()
        segments = _list(track.get("segments"), f"{track_id}.segments", nonempty=False)
        if language not in ALLOWED_LANGUAGES:
            if segments:
                raise ValueError(f"other-language transcript text is forbidden: {language}")
            availability.append({"track_id": track_id, "language": language, "content_retained": False})
            continue
        _track_rank(track)
        if track.get("is_translated") is True and not track.get("translated_from_language"):
            raise ValueError(f"translated track lacks origin language: {track_id}")
        if segments and track.get("content_authorized_for_fixture") is not True:
            raise ValueError(f"track content lacks fixture authorization: {track_id}")
        if segments:
            eligible[language].append(track)

    selected = []
    normalized = []
    timestamp_gap_count = 0
    for language in ALLOWED_LANGUAGES:
        candidates = sorted(eligible[language], key=_track_rank)
        if not candidates:
            continue
        track = candidates[0]
        track_id = track["track_id"]
        selected.append(track_id)
        seen_orders = set()
        previous_start = -1.0
        for index, segment in enumerate(track["segments"]):
            order = segment.get("segment_order")
            if not isinstance(order, int) or order < 0 or order in seen_orders:
                raise ValueError(f"invalid transcript segment order: {track_id}")
            seen_orders.add(order)
            text = _nonempty(segment.get("text"), f"{track_id}.segment.text")
            start = segment.get("start_seconds")
            duration = segment.get("duration_seconds")
            end = segment.get("end_seconds")
            timestamp_complete = all(isinstance(value, (int, float)) and value >= 0 for value in (start, duration, end))
            if timestamp_complete:
                if float(start) < previous_start or abs((float(start) + float(duration)) - float(end)) > 0.01:
                    raise ValueError(f"invalid transcript timestamps: {track_id}")
                previous_start = float(start)
            else:
                timestamp_gap_count += 1
                start = duration = end = None
            normalized.append({
                "video_id": video_id, "track_id": track_id, "segment_order": order,
                "start_seconds": start, "end_seconds": end, "duration_seconds": duration,
                "text": text, "language": language, "caption_kind": track["caption_kind"],
                "is_original_language": bool(track.get("is_original_language")),
                "is_translated": bool(track.get("is_translated")),
                "is_auto_generated": bool(track.get("is_auto_generated")),
                "source_surface": track.get("source_surface"), "acquired_at": acquired_at,
                "provenance": deepcopy(track.get("provenance") or {}),
                "completeness": {"timestamp_complete": timestamp_complete, "source_segment_index": index},
                "module_status": "partial" if status == "partial" else "public_accessible",
                "quality": {"allowed_language": True, "relationship_valid": True},
            })
    if normalized and any(not row["provenance"] for row in normalized):
        raise ValueError(f"transcript segment lacks provenance: {case_id}")
    if not normalized and status not in TRANSCRIPT_ABSENCE_STATUSES and status != "optional":
        raise ValueError(f"caption case has no resolved content or explicit absence status: {case_id}")
    return {
        "case_id": case_id, "video_id": video_id, "module_status": status,
        "selected_track_ids": selected, "segments": normalized,
        "other_language_availability": availability,
        "completeness": {"segment_count": len(normalized), "timestamp_gap_count": timestamp_gap_count,
                         "complete": bool(normalized) and timestamp_gap_count == 0 and status != "partial"},
    }


def normalize_comment_case(case: dict[str, Any], *, acquired_at: str, max_pages: int = 2) -> dict[str, Any]:
    """Normalize sanitized comment threads/replies with bounded coverage evidence."""
    case_id = _nonempty(case.get("case_id"), "comment case_id")
    video_id = _nonempty(case.get("video_id"), f"{case_id}.video_id")
    status = _nonempty(case.get("module_status"), f"{case_id}.module_status")
    page_count = case.get("page_count", 0)
    if not isinstance(page_count, int) or page_count < 0 or page_count > max_pages:
        raise ValueError(f"comment pagination exceeds bounded maximum: {case_id}")
    threads = _list(case.get("threads"), f"{case_id}.threads", nonempty=False)
    if not threads and status not in COMMENT_ABSENCE_STATUSES and status != "optional":
        raise ValueError(f"comment case has no data or explicit absence status: {case_id}")
    comments, replies, seen_comments, seen_replies = [], [], set(), set()
    duplicate_observation_count = 0
    incomplete_thread_count = 0
    for source_order, thread in enumerate(threads):
        thread_id = _nonempty(thread.get("thread_id"), f"{case_id}.thread_id")
        if thread.get("video_id") != video_id:
            raise ValueError(f"thread/video relationship mismatch: {thread_id}")
        top = _mapping(thread.get("top_level_comment"), f"{thread_id}.top_level_comment")
        comment_id = _nonempty(top.get("comment_id"), f"{thread_id}.comment_id")
        if comment_id in seen_comments:
            duplicate_observation_count += 1
            continue
        seen_comments.add(comment_id)
        comments.append(_normalized_comment(top, video_id=video_id, thread_id=thread_id,
                                            parent_comment_id=None, source_order=source_order,
                                            acquired_at=acquired_at, entity="comment"))
        embedded = list(thread.get("embedded_replies") or [])
        fetched = list(thread.get("fetched_replies") or [])
        for reply_order, reply in enumerate(embedded + fetched):
            reply_id = _nonempty(reply.get("comment_id"), f"{thread_id}.reply_id")
            if reply.get("parent_comment_id") != comment_id:
                raise ValueError(f"reply parent relationship mismatch: {reply_id}")
            if reply_id in seen_replies:
                duplicate_observation_count += 1
                continue
            seen_replies.add(reply_id)
            replies.append(_normalized_comment(reply, video_id=video_id, thread_id=thread_id,
                                               parent_comment_id=comment_id, source_order=reply_order,
                                               acquired_at=acquired_at, entity="comment_reply"))
        expected = thread.get("total_reply_count", 0)
        if not isinstance(expected, int) or expected < 0:
            raise ValueError(f"invalid totalReplyCount: {thread_id}")
        actual = len({row.get("comment_id") for row in embedded + fetched})
        if actual < expected or thread.get("next_page_available") is True:
            incomplete_thread_count += 1
    return {
        "case_id": case_id, "video_id": video_id, "module_status": status,
        "comments": comments, "comment_replies": replies,
        "coverage": {"page_count": page_count, "next_page_available": bool(case.get("next_page_available")),
                     "incomplete_thread_count": incomplete_thread_count,
                     "duplicate_observation_count": duplicate_observation_count,
                     "requested_order": case.get("requested_order"),
                     "representative_sample_claimed": False},
    }


def _normalized_comment(source: dict[str, Any], *, video_id: str, thread_id: str,
                        parent_comment_id: str | None, source_order: int,
                        acquired_at: str, entity: str) -> dict[str, Any]:
    provenance = deepcopy(source.get("provenance") or {})
    if not provenance:
        raise ValueError(f"{entity} lacks provenance: {source.get('comment_id')}")
    published = _nonempty(source.get("published_at"), f"{entity}.published_at")
    updated = _nonempty(source.get("updated_at"), f"{entity}.updated_at")
    return {
        "comment_id": source["comment_id"], "thread_id": thread_id, "video_id": video_id,
        "parent_comment_id": parent_comment_id, "text": _nonempty(source.get("text"), f"{entity}.text"),
        "author_channel_id": source.get("author_channel_id"),
        "author_display_name": source.get("author_display_name"),
        "like_count_snapshot": source.get("like_count"), "published_at": published,
        "updated_at": updated, "moderation_or_availability_state": source.get("state", "published"),
        "source_order": source_order, "source_surface": source.get("source_surface"),
        "acquired_at": acquired_at, "provenance": provenance,
        "completeness": {"edited": updated != published, "sampling_may_be_incomplete": bool(source.get("sampling_may_be_incomplete"))},
        "module_status": "public_accessible", "quality": {"relationship_valid": True, "representative_sample_claimed": False},
    }


def build_dataset_intake(fixture: dict[str, Any], *, transcript_results: list[dict[str, Any]],
                         comment_results: list[dict[str, Any]], module_requirements: dict[str, str]) -> dict[str, Any]:
    """Build a storage-neutral offline dataset and classify required-module exits."""
    if set(module_requirements) != {"metadata", "transcript", "comments"} or set(module_requirements.values()) - MODULE_REQUIREMENTS:
        raise ValueError("module requirements must define metadata/transcript/comments")
    if module_requirements["metadata"] != "required":
        raise ValueError("metadata must remain required")
    acquired_at = _nonempty(fixture.get("acquired_at"), "fixture.acquired_at")
    channels = deepcopy(_list(fixture.get("channels"), "fixture.channels"))
    playlists = deepcopy(_list(fixture.get("playlists"), "fixture.playlists"))
    videos = deepcopy(_list(fixture.get("videos"), "fixture.videos"))
    for entity, rows, key in (("channel", channels, "channel_id"), ("playlist", playlists, "playlist_id"), ("video", videos, "video_id")):
        identities = [row.get(key) for row in rows]
        if any(not identity for identity in identities) or len(identities) != len(set(identities)):
            raise ValueError(f"{entity} identities must be non-empty and unique")
        if any(not row.get("provenance") or not row.get("acquired_at") for row in rows):
            raise ValueError(f"{entity} metadata lacks provenance/acquisition time")
    channel_ids = {row["channel_id"] for row in channels}
    video_ids = {row["video_id"] for row in videos}
    if any(row.get("channel_id") not in channel_ids for row in videos):
        raise ValueError("video references an unknown channel")
    if any(row.get("channel_id") not in channel_ids for row in playlists):
        raise ValueError("playlist references an unknown channel")

    segments = [segment for result in transcript_results for segment in result["segments"]]
    comments = [comment for result in comment_results for comment in result["comments"]]
    replies = [reply for result in comment_results for reply in result["comment_replies"]]
    for row in segments + comments + replies:
        if row.get("video_id") not in video_ids:
            raise ValueError("content entity references an unknown video")
    comment_ids = {row["comment_id"] for row in comments}
    if any(row.get("parent_comment_id") not in comment_ids for row in replies):
        raise ValueError("comment reply references an unknown parent")
    identity_sets = [
        [(row["video_id"], row["track_id"], row["segment_order"]) for row in segments],
        [(row["video_id"], row["comment_id"]) for row in comments],
        [(row["video_id"], row["parent_comment_id"], row["comment_id"]) for row in replies],
    ]
    if any(len(values) != len(set(values)) for values in identity_sets):
        raise ValueError("dataset content identities must be unique")

    transcript_by_video = {row["video_id"]: row["module_status"] for row in transcript_results}
    comments_by_video = {row["video_id"]: row["module_status"] for row in comment_results}
    missing_required = []
    if module_requirements["transcript"] == "required":
        missing_required.extend(f"transcript:{video_id}" for video_id in video_ids if transcript_by_video.get(video_id) in TRANSCRIPT_ABSENCE_STATUSES or video_id not in transcript_by_video)
    if module_requirements["comments"] == "required":
        missing_required.extend(f"comments:{video_id}" for video_id in video_ids if comments_by_video.get(video_id) in COMMENT_ABSENCE_STATUSES or video_id not in comments_by_video)
    exit_classification = 2 if missing_required else 0
    result = {
        "schema": DATASET_SCHEMA, "dataset_id": fixture.get("dataset_id"),
        "domain": "q_diving", "source_type": "youtube", "acquired_at": acquired_at,
        "module_requirements": deepcopy(module_requirements),
        "module_status": {"metadata": "public_accessible", "transcript_by_video": transcript_by_video,
                          "comments_by_video": comments_by_video},
        "channels": channels, "playlists": playlists, "videos": videos,
        "transcript_segments": segments, "comments": comments, "comment_replies": replies,
        "quality": {"metadata_identity_complete": True, "provenance_complete": True,
                    "relationships_valid": True, "other_language_transcript_text_count": 0,
                    "representativeness_claim_count": 0},
        "required_module_gaps": sorted(missing_required),
        "technical_completion": True, "approved": exit_classification == 0,
        "exit_classification": exit_classification, "production_approved": False,
        "production_store": False, "scheduler_action": None,
    }
    validate_dataset_intake(result)
    return result


def validate_dataset_intake(dataset: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(dataset, dict) or dataset.get("schema") != DATASET_SCHEMA:
        raise ValueError(f"dataset schema must be {DATASET_SCHEMA}")
    if dataset.get("production_approved") is not False or dataset.get("production_store") is not False or dataset.get("scheduler_action") is not None:
        raise ValueError("dataset intake cannot authorize production or scheduling")
    if dataset.get("quality", {}).get("other_language_transcript_text_count") != 0:
        raise ValueError("dataset contains other-language transcript text")
    if dataset.get("quality", {}).get("representativeness_claim_count") != 0:
        raise ValueError("dataset claims comment representativeness")
    if dataset.get("exit_classification") not in {0, 2} or dataset.get("technical_completion") is not True:
        raise ValueError("offline dataset exit classification is invalid")
    if dataset.get("approved") is not (dataset.get("exit_classification") == 0):
        raise ValueError("dataset approval/exit classification is inconsistent")
    for segment in dataset.get("transcript_segments") or []:
        if segment.get("language") not in ALLOWED_LANGUAGES:
            raise ValueError("dataset transcript language is outside th/en")
    validate_safe_json_payload(dataset)
    return deepcopy(dataset)
