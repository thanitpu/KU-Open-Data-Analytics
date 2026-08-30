"""Deterministic, non-production Human Review staging for Q-Diving YouTube metadata."""
from __future__ import annotations

import copy
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from youtube_source_foundation import load_query_profiles

VIDEO_REVIEW_STATUSES = {"pending", "reviewed"}
RELEVANCE_VALUES = {"core", "adjacent", "irrelevant"}
CONTENT_ROLES = {
    "training", "beginner_experience", "equipment", "destination",
    "operator_information", "safety", "cost", "comparison", "commercial",
}
COMMERCIAL_CONTEXTS = {
    "none", "operator_self_promotion", "affiliate", "sponsorship_disclosed",
    "promotional_offer", "unknown",
}
KNOWLEDGE_USES = {"include", "include_with_context", "exclude"}
SOURCE_CLASSES = {
    "training_authority", "dive_operator", "equipment_manufacturer",
    "independent_instructor", "equipment_reviewer", "travel_dive_creator",
    "community_creator", "other",
}
DOMAIN_FOCUSES = {
    "diving_specialist", "travel_with_diving", "lifestyle_with_diving", "mixed",
}
MONITORING_DECISIONS = {"approve", "watch", "reject"}
EQUIPMENT_VOCABULARY = {
    "mask": ("mask", "หน้ากาก"),
    "fins": ("fins", "fin", "ตีนกบ"),
    "wetsuit": ("wetsuit", "wet suit", "ชุดเวทสูท"),
    "bcd": ("bcd", "buoyancy control device"),
    "regulator": ("regulator", "เรกูเลเตอร์"),
    "dive_computer": ("dive computer", "คอมพิวเตอร์ดำน้ำ"),
    "tank": ("scuba tank", "dive tank", "ถังดำน้ำ"),
    "underwater_camera": ("underwater camera", "กล้องใต้น้ำ"),
    "accessory": ("accessory", "accessories", "อุปกรณ์เสริม"),
    "maintenance": ("maintenance", "service gear", "ดูแลอุปกรณ์", "บำรุงรักษา"),
    "rental": ("rental", "rent gear", "เช่าอุปกรณ์"),
    "purchase": ("purchase", "buy gear", "ซื้ออุปกรณ์"),
    "fitting_sizing": ("fitting", "sizing", "fit test", "เลือกไซซ์", "ขนาด"),
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(*values: Any) -> str:
    return " ".join(str(value or "").casefold() for value in values)


def _contains(text: str, cue: str) -> bool:
    if re.fullmatch(r"[a-z0-9_ -]+", cue):
        return re.search(rf"(?<![a-z0-9]){re.escape(cue)}(?![a-z0-9])", text) is not None
    return cue in text


def _matches(text: str, cues: tuple[str, ...] | list[str]) -> list[str]:
    return [cue for cue in cues if _contains(text, cue)]


@dataclass
class YouTubeVideoReview:
    video_id: str
    review_status: str = "pending"
    relevance: str | None = None
    content_roles: list[str] = field(default_factory=list)
    research_collections: list[str] = field(default_factory=list)
    commercial_context: str | None = None
    knowledge_use: str | None = None
    reviewer_note: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None


@dataclass
class YouTubeChannelReview:
    channel_id: str
    review_status: str = "pending"
    source_class: str | None = None
    domain_focus: str | None = None
    monitoring_decision: str | None = None
    reviewer_note: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None


@dataclass
class YouTubeChannelMonitoringPlan:
    channel_id: str
    uploads_playlist_id: str
    source_class: str
    approved_by: str
    approved_at: str
    cadence: str
    production_enabled: bool = False
    scheduler_action: None = None


@dataclass
class PriceMentionCandidate:
    value: str
    currency: str
    context: str
    source_video_id: str
    observed_at: str
    stated_by_source: bool
    commercial_context: str


@dataclass
class YouTubeKnowledgeDataset:
    dataset_id: str
    domain: str
    source_type: str
    generated_at: str
    query_profile_ids: list[str]
    included_video_ids: list[str]
    included_channel_ids: list[str]
    monitoring_approved_channel_ids: list[str]
    monitoring_watch_channel_ids: list[str]
    research_collections: list[str]
    human_review_summary: dict[str, Any]
    provenance_summary: dict[str, Any]
    data_refresh_due_at: str | None
    production_approved: bool = False


def validate_video_review(review: dict[str, Any]) -> None:
    if review.get("review_status") not in VIDEO_REVIEW_STATUSES:
        raise ValueError("Invalid YouTube video review_status.")
    if review["review_status"] == "pending":
        final_fields = ("relevance", "knowledge_use", "commercial_context", "reviewed_by", "reviewed_at")
        populated = [field_name for field_name in final_fields if review.get(field_name) not in (None, "")]
        if populated:
            raise ValueError(f"Pending video review carries final field(s): {', '.join(populated)}.")
        return
    if review.get("relevance") not in RELEVANCE_VALUES:
        raise ValueError("A reviewed video requires a valid relevance decision.")
    if review.get("knowledge_use") not in KNOWLEDGE_USES:
        raise ValueError("A reviewed video requires a valid knowledge_use decision.")
    if review.get("commercial_context") not in COMMERCIAL_CONTEXTS:
        raise ValueError("A reviewed video requires a valid commercial_context decision.")
    if not set(review.get("content_roles") or []).issubset(CONTENT_ROLES):
        raise ValueError("A video review contains an unsupported content role.")
    if not str(review.get("reviewed_by") or "").strip() or not str(review.get("reviewed_at") or "").strip():
        raise ValueError("A reviewed video requires reviewer provenance.")
    if review.get("relevance") == "irrelevant" and review.get("knowledge_use") != "exclude":
        raise ValueError("An irrelevant video must be excluded from knowledge use.")
    if review.get("knowledge_use") in {"include", "include_with_context"} and review.get("relevance") not in {"core", "adjacent"}:
        raise ValueError("Included video knowledge requires core or adjacent relevance.")


def validate_channel_review(review: dict[str, Any]) -> None:
    if review.get("review_status") not in VIDEO_REVIEW_STATUSES:
        raise ValueError("Invalid YouTube channel review_status.")
    if review["review_status"] == "pending":
        final_fields = ("source_class", "domain_focus", "monitoring_decision", "reviewed_by", "reviewed_at")
        populated = [field_name for field_name in final_fields if review.get(field_name) not in (None, "")]
        if populated:
            raise ValueError(f"Pending channel review carries final field(s): {', '.join(populated)}.")
        return
    if review.get("source_class") not in SOURCE_CLASSES:
        raise ValueError("A reviewed channel requires a valid source_class.")
    if review.get("domain_focus") not in DOMAIN_FOCUSES:
        raise ValueError("A reviewed channel requires a valid domain_focus.")
    if review.get("monitoring_decision") not in MONITORING_DECISIONS:
        raise ValueError("A reviewed channel requires a valid monitoring_decision.")
    if not str(review.get("reviewed_by") or "").strip() or not str(review.get("reviewed_at") or "").strip():
        raise ValueError("A reviewed channel requires reviewer provenance.")


def _indexed_identities(rows: Any, identity_field: str, record_label: str) -> tuple[list[str], dict[str, dict[str, Any]]]:
    if not isinstance(rows, list):
        raise ValueError(f"{record_label} records must be a list.")
    identities: list[str] = []
    indexed: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{record_label} record at index {index} must be an object.")
        identity = row.get(identity_field)
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError(f"{record_label} record at index {index} has an empty {identity_field}.")
        if identity != identity.strip():
            raise ValueError(f"{record_label} identity has surrounding whitespace: {identity!r}.")
        if identity in indexed:
            raise ValueError(f"Duplicate {record_label} identity: {identity}.")
        identities.append(identity)
        indexed[identity] = row
    return identities, indexed


def validate_review_package_integrity(review_package: dict[str, Any]) -> None:
    """Reject malformed or contradictory manual edits before KU2A handoff."""
    if not isinstance(review_package, dict) or review_package.get("schema") != "ku2d.youtube-human-review-package.v1":
        raise ValueError("Expected a YouTube Human Review package.")
    if review_package.get("provider") != "youtube-data-api-v3":
        raise ValueError("Review package provider must be youtube-data-api-v3.")
    if review_package.get("foundation_result_schema") != "ku2d.youtube-source-foundation-result.v1":
        raise ValueError("Review package has an invalid foundation result schema provenance.")
    if review_package.get("domain") != "q_diving" or review_package.get("source_type") != "youtube":
        raise ValueError("Review package must describe the Q-Diving YouTube source contract.")

    candidate_video_ids, candidate_videos = _indexed_identities(
        review_package.get("candidate_videos"), "video_id", "candidate video",
    )
    candidate_channel_ids, candidate_channels = _indexed_identities(
        review_package.get("candidate_channels"), "channel_id", "candidate channel",
    )
    video_review_ids, video_reviews = _indexed_identities(
        review_package.get("video_reviews"), "video_id", "video review",
    )
    channel_review_ids, channel_reviews = _indexed_identities(
        review_package.get("channel_reviews"), "channel_id", "channel review",
    )

    for identity in video_review_ids:
        if identity not in candidate_videos:
            raise ValueError(f"Unknown video review identity: {identity}.")
    for identity in channel_review_ids:
        if identity not in candidate_channels:
            raise ValueError(f"Unknown channel review identity: {identity}.")
    for identity in candidate_video_ids:
        if identity not in video_reviews:
            raise ValueError(f"Candidate video has no review record: {identity}.")
    for identity in candidate_channel_ids:
        if identity not in channel_reviews:
            raise ValueError(f"Candidate channel has no review record: {identity}.")

    for review in review_package["video_reviews"]:
        validate_video_review(review)
    for review in review_package["channel_reviews"]:
        validate_channel_review(review)

    package_profile_ids = review_package.get("query_profile_ids")
    if not isinstance(package_profile_ids, list) or not package_profile_ids:
        raise ValueError("Review package has no query_profile_ids provenance.")
    if any(not isinstance(profile_id, str) or not profile_id.strip() for profile_id in package_profile_ids):
        raise ValueError("Review package contains an empty query_profile_id.")
    if len(package_profile_ids) != len(set(package_profile_ids)):
        raise ValueError("Review package contains duplicate query_profile_ids.")
    profile_rows = review_package.get("query_profile_provenance")
    profile_ids, _ = _indexed_identities(profile_rows, "profile_id", "query-profile provenance")
    profile_id_set = set(profile_ids)
    for row in profile_rows:
        if row.get("domain") != "q_diving":
            raise ValueError(f"Query-profile provenance {row['profile_id']} has an invalid domain.")
        for field_name in ("research_collection", "query_text", "region_code"):
            if not isinstance(row.get(field_name), str) or not row[field_name].strip():
                raise ValueError(f"Query-profile provenance {row['profile_id']} has an empty {field_name}.")
    for profile_id in package_profile_ids:
        if profile_id not in profile_id_set:
            raise ValueError(f"Query profile has no provenance record: {profile_id}.")
    for profile_id in profile_ids:
        if profile_id not in package_profile_ids:
            raise ValueError(f"Unknown query-profile provenance identity: {profile_id}.")

    for review in review_package["video_reviews"]:
        if review.get("review_status") != "reviewed" or review.get("knowledge_use") not in {"include", "include_with_context"}:
            continue
        candidate = candidate_videos[review["video_id"]]
        if not str(candidate.get("channel_id") or "").strip():
            raise ValueError(f"Included candidate video {review['video_id']} has no source channel_id.")
        if not str(candidate.get("refresh_due_at") or "").strip():
            raise ValueError(f"Included candidate video {review['video_id']} has no refresh_due_at.")
        provenance = candidate.get("provenance")
        if not isinstance(provenance, dict) or provenance.get("provider") != "youtube-data-api-v3":
            raise ValueError(f"Included candidate video {review['video_id']} lacks official provider provenance.")
        candidate_profiles = candidate.get("query_profile_ids")
        if not isinstance(candidate_profiles, list) or not candidate_profiles:
            raise ValueError(f"Included candidate video {review['video_id']} has no query-profile provenance path.")
        if any(not isinstance(profile_id, str) or not profile_id.strip() or profile_id not in profile_id_set
               for profile_id in candidate_profiles):
            raise ValueError(f"Included candidate video {review['video_id']} has an unknown query-profile provenance path.")
        if candidate.get("data_status") != "current" or candidate.get("publicly_usable") is not True:
            raise ValueError(f"Included candidate video {review['video_id']} is not from a current, publicly usable foundation record.")


def suggest_relevance(video: dict[str, Any]) -> dict[str, Any]:
    """Return a transparent screening suggestion; never a Human Review decision."""
    text = _text(video.get("title"), video.get("description"))
    collections = set(video.get("research_collections") or [])
    profile_ids = set(video.get("query_profile_ids") or [])
    freedive = _matches(text, ("freediving", "free diving", "freedive", "ฟรีไดฟ์"))
    dive = _matches(text, ("scuba", "diving", "dive", "open water", "ดำน้ำ", "นักดำน้ำ"))
    beginner = _matches(text, ("open water", "beginner", "course", "training", "lesson", "มือใหม่", "คอร์ส", "เรียนดำน้ำ"))
    koh_tao = _matches(text, ("koh tao", "เกาะเต่า"))
    equipment = sorted(
        topic for topic, cues in EQUIPMENT_VOCABULARY.items() if _matches(text, cues)
    )
    koh_tao_query = any("KOH-TAO" in profile_id for profile_id in profile_ids)

    if "diving_equipment" in collections and equipment:
        return {"suggested_relevance": "core", "suggestion_basis": [
            "equipment vocabulary matches the diving_equipment collection",
            f"matched equipment topics: {', '.join(equipment)}",
        ]}
    if "learn_to_dive" in collections and freedive:
        return {"suggested_relevance": "adjacent", "suggestion_basis": [
            "freediving is adjacent to, but not equivalent to, the scuba-beginner collection",
        ]}
    if koh_tao_query and dive and not koh_tao:
        return {"suggested_relevance": "adjacent", "suggestion_basis": [
            "diving content does not match the Koh Tao location constraint",
        ]}
    if "learn_to_dive" in collections and dive and beginner and (not koh_tao_query or koh_tao):
        return {"suggested_relevance": "core", "suggestion_basis": [
            "beginner scuba/course language matches the selected collection",
            *( ["Koh Tao location cue matches the query profile"] if koh_tao_query else [] ),
        ]}
    if dive or equipment:
        return {"suggested_relevance": "adjacent", "suggestion_basis": [
            "meaningful diving relation is present without an exact collection match",
        ]}
    return {"suggested_relevance": "irrelevant", "suggestion_basis": [
        "no meaningful diving relation found in title or description",
    ]}


def suggest_equipment_topics(video: dict[str, Any]) -> dict[str, Any]:
    text = _text(video.get("title"), video.get("description"))
    matches = {
        topic: _matches(text, cues)
        for topic, cues in EQUIPMENT_VOCABULARY.items()
        if _matches(text, cues)
    }
    return {
        "suggested_equipment_topics": sorted(matches),
        "equipment_suggestion_basis": [
            {"topic": topic, "matched_cues": cues} for topic, cues in sorted(matches.items())
        ],
    }


def suggest_commercial_context(video: dict[str, Any]) -> dict[str, Any]:
    """Surface disclosed text cues only; an empty result is unknown, not 'not sponsored'."""
    text = _text(video.get("title"), video.get("description"))
    patterns = {
        "sponsorship_disclosed": ("sponsored", "paid partnership", "#ad", "สนับสนุนโดย"),
        "affiliate": ("affiliate", "affiliate link", "earn a commission", "ลิงก์แนะนำ", "ค่านายหน้า"),
        "promotional_offer": ("promo code", "discount code", "discount", "sale", "buy now", "shop now", "available now", "โปรโมชั่น", "ส่วนลด", "รหัสส่วนลด", "สั่งซื้อ"),
        "operator_self_promotion": ("book with us", "our dive center", "our course", "จองกับเรา", "สมัครเรียนกับเรา"),
    }
    evidence = [
        {"context": context, "matched_cue": cue, "source_field": "title_or_description"}
        for context, cues in patterns.items()
        for cue in _matches(text, cues)
    ]
    priority = ("sponsorship_disclosed", "affiliate", "promotional_offer", "operator_self_promotion")
    suggestion = next((value for value in priority if any(x["context"] == value for x in evidence)), "unknown")
    return {
        "commercial_context_suggestion": suggestion,
        "commercial_context_evidence": evidence,
        "hidden_sponsorship_inferred": False,
    }


def suggest_channel_class(channel: dict[str, Any]) -> dict[str, Any]:
    """Return non-authoritative class/focus hints kept separate from channel review."""
    text = _text(channel.get("channel_title"), channel.get("channel_description"))
    operator = _matches(text, ("dive center", "dive centre", "dive operator", "liveaboard", "book open water", "ศูนย์ดำน้ำ", "โรงเรียนสอนดำน้ำ"))
    travel = _matches(text, ("travel", "traveller", "island life", "lifestyle", "food", "เที่ยว", "ท่องเที่ยว", "ไลฟ์สไตล์"))
    diving = _matches(text, ("scuba", "diving", "dive", "ดำน้ำ"))
    manufacturer = _matches(text, ("manufacturer", "official scuba gear", "dive equipment brand"))
    reviewer = _matches(text, ("gear review", "equipment review", "scuba reviews"))
    instructor = _matches(text, ("independent instructor", "scuba instructor", "ครูสอนดำน้ำ"))
    if operator:
        source_class, focus, basis = "dive_operator", "diving_specialist", operator
    elif manufacturer:
        source_class, focus, basis = "equipment_manufacturer", "diving_specialist", manufacturer
    elif reviewer:
        source_class, focus, basis = "equipment_reviewer", "diving_specialist", reviewer
    elif instructor:
        source_class, focus, basis = "independent_instructor", "diving_specialist", instructor
    elif travel and diving:
        source_class, focus, basis = "travel_dive_creator", "travel_with_diving", travel + diving
    elif diving:
        source_class, focus, basis = "community_creator", "mixed", diving
    else:
        source_class, focus, basis = "other", "mixed", ["no deterministic specialist cue"]
    return {
        "suggested_source_class": source_class,
        "suggested_domain_focus": focus,
        "source_class_suggestion_basis": basis,
        "authoritative": False,
    }


_PRICE_PATTERNS = (
    (re.compile(r"(?<![\w])(?:THB|฿)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.IGNORECASE), "THB"),
    (re.compile(r"(?<![\w])([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*(?:THB|บาท)(?![\w])", re.IGNORECASE), "THB"),
    (re.compile(r"(?<![\w])\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)"), "USD"),
)


def extract_price_mentions(video: dict[str, Any], commercial_suggestion: str) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    for field_name in ("title", "description"):
        value = str(video.get(field_name) or "")
        for pattern, currency in _PRICE_PATTERNS:
            for match in pattern.finditer(value):
                start, end = max(0, match.start() - 35), min(len(value), match.end() + 35)
                candidate = PriceMentionCandidate(
                    value=match.group(1).replace(",", ""), currency=currency,
                    context=value[start:end], source_video_id=str(video.get("video_id") or ""),
                    observed_at=str(video.get("observed_at") or ""), stated_by_source=True,
                    commercial_context=commercial_suggestion,
                )
                mentions.append({
                    **asdict(candidate),
                    "record_type": "PriceMentionCandidate",
                    "current_commerce_price_evidence": False,
                    "product_price_acquisition_record": False,
                })
    return mentions


def _profile_provenance(profile_ids: list[str], profiles: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    rows = profiles if profiles is not None else load_query_profiles()
    by_id = {row.get("profile_id"): row for row in rows}
    result = []
    for profile_id in profile_ids:
        row = by_id.get(profile_id)
        if not row:
            raise ValueError(f"Foundation result references unknown query profile: {profile_id}")
        result.append({
            "profile_id": profile_id,
            "domain": row.get("domain"),
            "research_collection": row.get("research_collection"),
            "query_text": row.get("query_text"),
            "region_code": row.get("region_code"),
            "relevance_language": row.get("relevance_language"),
        })
    return result


def prepare_review_package(
    foundation_result: dict[str, Any], *, profiles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a compact review package without mutating normalized foundation data."""
    source = copy.deepcopy(foundation_result)
    if source.get("schema") != "ku2d.youtube-source-foundation-result.v1":
        raise ValueError("Expected a YouTube source foundation result.")
    if source.get("provider") != "youtube-data-api-v3":
        raise ValueError("Expected official YouTube Data API v3 provenance.")
    profile_ids = list(dict.fromkeys(source.get("query_profile_ids") or []))
    if not profile_ids:
        raise ValueError("Foundation result has no query profile provenance.")

    candidate_videos, video_reviews, price_mentions = [], [], []
    for video in source.get("videos") or []:
        if video.get("transcript_text") is not None:
            raise ValueError("Review staging refuses non-null transcript text.")
        if video.get("data_status") != "current" or not video.get("publicly_usable"):
            continue
        relevance = suggest_relevance(video)
        commercial = suggest_commercial_context(video)
        equipment = suggest_equipment_topics(video)
        candidate_videos.append({
            "video_id": video.get("video_id"),
            "channel_id": video.get("channel_id"),
            "channel_title": video.get("channel_title"),
            "title": video.get("title"),
            "description": video.get("description"),
            "published_at": video.get("published_at"),
            "duration_iso8601": video.get("duration_iso8601"),
            "caption_available": video.get("caption_available"),
            "youtube_paid_product_placement": video.get("paid_product_placement"),
            "video_url": video.get("video_url"),
            "query_profile_ids": list(video.get("query_profile_ids") or []),
            "research_collections": list(video.get("research_collections") or []),
            "observed_at": video.get("observed_at"),
            "refresh_due_at": video.get("refresh_due_at"),
            "data_status": video.get("data_status"),
            "publicly_usable": video.get("publicly_usable"),
            "provenance": copy.deepcopy(video.get("provenance") or {}),
            "review_suggestions": {**relevance, **commercial, **equipment},
        })
        video_reviews.append(asdict(YouTubeVideoReview(
            video_id=str(video.get("video_id") or ""),
            research_collections=list(video.get("research_collections") or []),
        )))
        price_mentions.extend(extract_price_mentions(video, commercial["commercial_context_suggestion"]))

    candidate_channels, channel_reviews = [], []
    for channel in source.get("channels") or []:
        suggestion = suggest_channel_class(channel)
        candidate_channels.append({
            "channel_id": channel.get("channel_id"),
            "channel_title": channel.get("channel_title"),
            "channel_description": channel.get("channel_description"),
            "published_at": channel.get("published_at"),
            "uploads_playlist_id": channel.get("uploads_playlist_id"),
            "channel_url": channel.get("channel_url"),
            "query_profile_ids": list(channel.get("query_profile_ids") or []),
            "observed_at": channel.get("observed_at"),
            "refresh_due_at": channel.get("refresh_due_at"),
            "provenance": copy.deepcopy(channel.get("provenance") or {}),
            "review_suggestions": suggestion,
        })
        channel_reviews.append(asdict(YouTubeChannelReview(channel_id=str(channel.get("channel_id") or ""))))

    return {
        "schema": "ku2d.youtube-human-review-package.v1",
        "domain": "q_diving",
        "source_type": "youtube",
        "provider": "youtube-data-api-v3",
        "generated_at": source.get("observed_at") or _utcnow_iso(),
        "foundation_result_schema": source.get("schema"),
        "query_profile_ids": profile_ids,
        "query_profile_provenance": _profile_provenance(profile_ids, profiles),
        "candidate_videos": candidate_videos,
        "candidate_channels": candidate_channels,
        "video_reviews": video_reviews,
        "channel_reviews": channel_reviews,
        "price_mention_candidates": price_mentions,
        "review_stage": "human-review-pending",
        "production_store": False,
        "production_approved": False,
        "scheduler_action": None,
    }


def create_monitoring_plan(
    channel_review: dict[str, Any], channel_candidate: dict[str, Any], *, cadence: str = "weekly",
) -> dict[str, Any]:
    """Create a non-writing dry plan only after explicit completed channel approval."""
    validate_channel_review(channel_review)
    if channel_review.get("review_status") != "reviewed":
        raise ValueError("Channel Human Review is not complete.")
    if channel_review.get("monitoring_decision") != "approve":
        raise ValueError("Channel Human Review did not approve monitoring.")
    channel_id = str(channel_candidate.get("channel_id") or "").strip()
    uploads_id = str(channel_candidate.get("uploads_playlist_id") or "").strip()
    if not channel_id or channel_id != channel_review.get("channel_id"):
        raise ValueError("Monitoring requires a matching channel_id.")
    if not uploads_id:
        raise ValueError("Monitoring requires an uploads_playlist_id.")
    return asdict(YouTubeChannelMonitoringPlan(
        channel_id=channel_id,
        uploads_playlist_id=uploads_id,
        source_class=str(channel_review["source_class"]),
        approved_by=str(channel_review["reviewed_by"]),
        approved_at=str(channel_review["reviewed_at"]),
        cadence=cadence,
    ))


def create_knowledge_dataset(
    review_package: dict[str, Any], *, dataset_id: str, generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a non-production KU2A handoff from completed Human Review records."""
    validate_review_package_integrity(review_package)
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        raise ValueError("YouTubeKnowledgeDataset requires a non-empty dataset_id.")
    video_reviews = review_package["video_reviews"]
    channel_reviews = review_package["channel_reviews"]

    included_video_reviews = [
        row for row in video_reviews
        if row.get("review_status") == "reviewed" and row.get("knowledge_use") in {"include", "include_with_context"}
    ]
    monitoring_approved_reviews = [
        row for row in channel_reviews
        if row.get("review_status") == "reviewed" and row.get("monitoring_decision") == "approve"
    ]
    monitoring_watch_reviews = [
        row for row in channel_reviews
        if row.get("review_status") == "reviewed" and row.get("monitoring_decision") == "watch"
    ]
    included_video_ids = sorted({str(row["video_id"]) for row in included_video_reviews})
    video_candidates_by_id = {row["video_id"]: row for row in review_package["candidate_videos"]}
    selected_candidates = [video_candidates_by_id[video_id] for video_id in included_video_ids]
    included_channel_ids = sorted({str(row["channel_id"]) for row in selected_candidates})
    monitoring_approved_channel_ids = sorted(str(row["channel_id"]) for row in monitoring_approved_reviews)
    monitoring_watch_channel_ids = sorted(str(row["channel_id"]) for row in monitoring_watch_reviews)
    collections = sorted({
        collection for row in selected_candidates for collection in row.get("research_collections") or []
    })
    selected_channel_candidates = [
        row for row in review_package.get("candidate_channels") or []
        if row.get("channel_id") in included_channel_ids
    ]
    refresh_values = sorted({
        row.get("refresh_due_at")
        for row in selected_candidates + selected_channel_candidates
        if row.get("refresh_due_at")
    })
    summary = {
        "video_candidates": len(video_reviews),
        "video_reviews_completed": sum(row.get("review_status") == "reviewed" for row in video_reviews),
        "videos_included": len(included_video_ids),
        "videos_excluded": sum(row.get("knowledge_use") == "exclude" for row in video_reviews),
        "channel_candidates": len(channel_reviews),
        "channel_reviews_completed": sum(row.get("review_status") == "reviewed" for row in channel_reviews),
        "source_channels_included": len(included_channel_ids),
        "monitoring_channels_approved": len(monitoring_approved_channel_ids),
        "monitoring_channels_watch": len(monitoring_watch_channel_ids),
        "monitoring_channels_rejected": sum(
            row.get("review_status") == "reviewed" and row.get("monitoring_decision") == "reject"
            for row in channel_reviews
        ),
    }
    dataset = YouTubeKnowledgeDataset(
        dataset_id=dataset_id,
        domain="q_diving",
        source_type="youtube",
        generated_at=generated_at or _utcnow_iso(),
        query_profile_ids=list(review_package.get("query_profile_ids") or []),
        included_video_ids=included_video_ids,
        included_channel_ids=included_channel_ids,
        monitoring_approved_channel_ids=monitoring_approved_channel_ids,
        monitoring_watch_channel_ids=monitoring_watch_channel_ids,
        research_collections=collections,
        human_review_summary=summary,
        provenance_summary={
            "provider": review_package.get("provider"),
            "foundation_result_schema": review_package.get("foundation_result_schema"),
            "review_package_schema": review_package.get("schema"),
            "query_profile_provenance": copy.deepcopy(review_package.get("query_profile_provenance") or []),
            "human_review_required": True,
        },
        data_refresh_due_at=refresh_values[0] if refresh_values else None,
        production_approved=False,
    )
    return {"schema": "ku2d.youtube-knowledge-dataset.v1", **asdict(dataset)}
