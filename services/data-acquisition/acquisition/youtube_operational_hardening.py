"""Offline YouTube reviewed-identity and batch-readiness contracts.

The module is intentionally transport-free.  It validates durable Human Review
identity, immutable exact-input manifests, quota/checkpoint reconciliation,
sanitized simulations, Deep Audit, and KU2D-to-KU2A packaging without reading
credentials or making a source request.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from typing import Any


REGISTRY_SCHEMA = "ku2d.reviewed-youtube-video-identity-registry.v1"
MANIFEST_SCHEMA = "ku2d.youtube-batch-manifest.v1"
CHECKPOINT_SCHEMA = "ku2d.youtube-batch-checkpoint.v1"
LEDGER_SCHEMA = "ku2d.youtube-quota-ledger.v1"
DATASET_SCHEMA = "ku2d.youtube-batch-dataset-intake.v1"
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
ALLOWED_ENDPOINTS = ("videos.list", "commentThreads.list", "comments.list")
OFFICIAL_UNIT_COSTS = {endpoint: 1 for endpoint in ALLOWED_ENDPOINTS}
REGISTRY_STATUSES = {"active", "superseded", "revoked"}
MODULE_REQUIREMENTS = {"required", "optional", "disabled"}


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field} must be a non-empty trimmed string")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def canonical_watch_url(video_id: str) -> str:
    if not isinstance(video_id, str) or VIDEO_ID_RE.fullmatch(video_id) is None:
        raise ValueError("video_id must be a canonical 11-character YouTube identity")
    return f"https://www.youtube.com/watch?v={video_id}"


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_identity_registry(registry: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(registry, dict) or registry.get("schema") != REGISTRY_SCHEMA:
        raise ValueError(f"identity registry schema must be {REGISTRY_SCHEMA}")
    if registry.get("production_approved") is not False or registry.get("scheduler_action") is not None:
        raise ValueError("identity registry must remain non-production and unscheduled")
    entries = _list(registry.get("entries"), "entries")
    candidates = _list(registry.get("candidate_only_evidence"), "candidate_only_evidence")
    seen: dict[str, str] = {}
    registry_entry_ids: set[str] = set()
    review_ids: set[str] = set()
    for index, entry in enumerate(entries):
        row = _mapping(entry, f"entries[{index}]")
        registry_entry_id = _nonempty(row.get("registry_entry_id"), f"entries[{index}].registry_entry_id")
        if registry_entry_id in registry_entry_ids:
            raise ValueError(f"duplicate registry_entry_id: {registry_entry_id}")
        registry_entry_ids.add(registry_entry_id)
        video_id = _nonempty(row.get("video_id"), f"entries[{index}].video_id")
        if VIDEO_ID_RE.fullmatch(video_id) is None or video_id.upper().startswith("SAN"):
            raise ValueError("reviewed registry contains a malformed or sanitized-placeholder video_id")
        if video_id in seen:
            raise ValueError(f"duplicate reviewed video_id: {video_id}")
        seen[video_id] = _nonempty(row.get("channel_id"), f"entries[{index}].channel_id")
        if row.get("canonical_watch_url") != canonical_watch_url(video_id):
            raise ValueError("canonical watch URL does not derive from video_id")
        if row.get("status") not in REGISTRY_STATUSES:
            raise ValueError("reviewed identity status is invalid")
        if row.get("privacy_classification") != "public_metadata":
            raise ValueError("reviewed identity privacy classification is not public_metadata")
        if row.get("sanitized") is not False:
            raise ValueError("reviewed identity cannot be sanitized")
        review = _mapping(row.get("review_linkage"), f"entries[{index}].review_linkage")
        review_id = _nonempty(review.get("review_record_id"), "review_record_id")
        if review_id in review_ids:
            raise ValueError("one Human Review record cannot authorize multiple registry entries ambiguously")
        review_ids.add(review_id)
        if review.get("review_status") != "reviewed" or review.get("knowledge_use") not in {"include", "include_with_context"}:
            raise ValueError("registry identity lacks an inclusion Human Review decision")
        if review.get("reviewed_by_actor") != "human" or review.get("decision_source") != "explicit_human_input":
            raise ValueError("registry identity carries assistant-generated or missing human authority")
        _nonempty(review.get("reviewed_by"), "reviewed_by")
        _nonempty(review.get("reviewed_at"), "reviewed_at")
        source_ids = _list(review.get("source_candidate_ids"), "source_candidate_ids")
        if source_ids != [video_id]:
            raise ValueError("registry identity has ambiguous source linkage")
        purposes = _list(row.get("purpose_profile_ids"), "purpose_profile_ids")
        if not purposes or any(not isinstance(item, str) or not item.strip() for item in purposes):
            raise ValueError("registry identity requires purpose/profile linkage")
        evidence_refs = _list(row.get("source_evidence_references"), "source_evidence_references")
        if not evidence_refs:
            raise ValueError("registry identity requires source evidence references")
        relationships = _list(row.get("source_relationship_evidence"), "source_relationship_evidence")
        if not relationships:
            raise ValueError("registry identity requires video/channel relationship evidence")
        for relation in relationships:
            relation = _mapping(relation, "source_relationship_evidence item")
            if relation.get("video_id") != video_id or relation.get("channel_id") != row["channel_id"]:
                raise ValueError("conflicting channel/video relationship evidence")
        status = row["status"]
        if status == "active":
            if row.get("superseded_by") is not None or row.get("revocation_reason") is not None:
                raise ValueError("active identity carries supersession/revocation state")
            expected_usable = True
        elif status == "superseded":
            _nonempty(row.get("superseded_by"), "superseded_by")
            expected_usable = False
        else:
            _nonempty(row.get("revocation_reason"), "revocation_reason")
            expected_usable = False
        if row.get("usable_for_live_acquisition") is not expected_usable:
            raise ValueError("usable_for_live_acquisition conflicts with review/status authority")

    candidate_ids: set[str] = set()
    for index, candidate in enumerate(candidates):
        row = _mapping(candidate, f"candidate_only_evidence[{index}]")
        candidate_id = _nonempty(row.get("candidate_identity"), "candidate_identity")
        if candidate_id in candidate_ids:
            raise ValueError("duplicate candidate-only identity")
        candidate_ids.add(candidate_id)
        if row.get("evidence_class") not in {"sanitized_fixture", "historical_candidate_only"}:
            raise ValueError("candidate-only evidence class is invalid")
        if row.get("review_status") != "not_human_reviewed" or row.get("usable_for_live_acquisition") is not False:
            raise ValueError("candidate-only evidence cannot be promoted into reviewed live input")
        if row.get("privacy_safe") is not True:
            raise ValueError("candidate-only evidence must be privacy safe")
    readiness = _mapping(registry.get("readiness"), "readiness")
    usable_count = sum(entry.get("usable_for_live_acquisition") is True for entry in entries)
    if readiness.get("usable_identity_count") != usable_count:
        raise ValueError("registry readiness usable count is inconsistent")
    if readiness.get("qdiving_two_video_status") != (
        "batch_ready_reviewed_identity" if usable_count == 2 else "identity_review_required"
    ):
        raise ValueError("registry readiness tier is inconsistent")
    return registry


def manifest_intent_fingerprint(manifest: dict[str, Any]) -> str:
    immutable = {
        "manifest_id": manifest.get("manifest_id"),
        "identity_registry_id": manifest.get("identity_registry_id"),
        "identity_registry_entry_ids": manifest.get("identity_registry_entry_ids"),
        "modules": manifest.get("modules"),
        "allowed_endpoints": manifest.get("allowed_endpoints"),
        "language_scope": manifest.get("language_scope"),
        "comment_policy": manifest.get("comment_policy"),
        "request_budget": manifest.get("request_budget"),
        "execution_policy": manifest.get("execution_policy"),
    }
    return _fingerprint(immutable)


def validate_batch_manifest(manifest: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    validate_identity_registry(registry)
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError(f"batch manifest schema must be {MANIFEST_SCHEMA}")
    if manifest.get("mode") != "exact-input-only" or manifest.get("search_fallback") is not False:
        raise ValueError("batch manifest must be exact-input-only with no search fallback")
    endpoints = manifest.get("allowed_endpoints")
    if endpoints != list(ALLOWED_ENDPOINTS) or "search.list" in endpoints:
        raise ValueError("batch manifest endpoint allowlist changed")
    if manifest.get("automatic_endpoint_switching") is not False:
        raise ValueError("batch manifest cannot switch endpoints automatically")
    if manifest.get("language_scope") != ["th", "en"]:
        raise ValueError("batch manifest language scope must be [th, en]")
    modules = _mapping(manifest.get("modules"), "modules")
    if modules.get("metadata") != "required" or any(value not in MODULE_REQUIREMENTS for value in modules.values()):
        raise ValueError("batch manifest module requirements are invalid")
    refs = _list(manifest.get("identity_registry_entry_ids"), "identity_registry_entry_ids")
    if len(refs) != len(set(refs)):
        raise ValueError("batch manifest contains duplicate identity references")
    registry_by_id = {entry["registry_entry_id"]: entry for entry in registry["entries"]}
    for ref in refs:
        entry = registry_by_id.get(ref)
        if entry is None or entry.get("usable_for_live_acquisition") is not True:
            raise ValueError("batch manifest references an absent, revoked, superseded, or unreviewed identity")
    if manifest.get("execution_authorized") is True and not refs:
        raise ValueError("an executable batch cannot have zero reviewed identity references")
    comment_policy = _mapping(manifest.get("comment_policy"), "comment_policy")
    page_cap = _nonnegative_int(comment_policy.get("comment_threads_max_pages_per_video"), "comment page cap")
    if page_cap > 2:
        raise ValueError("commentThreads page cap exceeds the reviewed bounded contract")
    if comment_policy.get("comments_list_when_embedded_incomplete_only") is not True:
        raise ValueError("comments.list may run only for incomplete embedded replies")
    if comment_policy.get("ordering_is_acquisition_context_only") is not True:
        raise ValueError("comment ordering semantic boundary is missing")
    budget = _mapping(manifest.get("request_budget"), "request_budget")
    _nonnegative_int(budget.get("max_total_requests"), "max_total_requests")
    _nonnegative_int(budget.get("max_estimated_quota_units"), "max_estimated_quota_units")
    if budget.get("value_origin") not in {"official_documentation", "proposal_not_observed", "mixed"}:
        raise ValueError("request budget value origin is invalid")
    execution = _mapping(manifest.get("execution_policy"), "execution_policy")
    if execution.get("evidence_before_next_request") is not True or execution.get("concurrency") != 1:
        raise ValueError("batch execution must be serialized and evidence-first")
    if execution.get("checkpoint_resume") is not True or execution.get("idempotent_request_keys") is not True:
        raise ValueError("batch execution lacks checkpoint/idempotency guarantees")
    if manifest.get("production_store") is not False or manifest.get("production_approved") is not False:
        raise ValueError("batch manifest must remain non-production")
    if manifest.get("scheduler_action") is not None:
        raise ValueError("batch manifest must not schedule acquisition")
    if manifest.get("request_intent_fingerprint") != manifest_intent_fingerprint(manifest):
        raise ValueError("batch manifest immutable request-intent fingerprint is stale")
    return manifest


def plan_quota_budget(
    video_count: int, *, metadata_batch_size: int = 50, comment_pages_per_video: int = 2,
    reply_requests_per_video: int = 2,
) -> dict[str, Any]:
    for value, field in ((video_count, "video_count"), (metadata_batch_size, "metadata_batch_size"),
                         (comment_pages_per_video, "comment_pages_per_video"),
                         (reply_requests_per_video, "reply_requests_per_video")):
        _nonnegative_int(value, field)
    if metadata_batch_size < 1 or metadata_batch_size > 50:
        raise ValueError("metadata_batch_size must be between 1 and the merged policy cap 50")
    if comment_pages_per_video > 2:
        raise ValueError("comment page plan exceeds the bounded page cap")
    metadata_requests = math.ceil(video_count / metadata_batch_size) if video_count else 0
    thread_requests = video_count * comment_pages_per_video
    reply_requests = video_count * reply_requests_per_video
    total = metadata_requests + thread_requests + reply_requests
    return {
        "video_count": video_count,
        "videos_list_requests": metadata_requests,
        "comment_threads_list_requests": thread_requests,
        "comments_list_requests": reply_requests,
        "max_total_requests": total,
        "max_estimated_quota_units": total,
        "unit_costs": deepcopy(OFFICIAL_UNIT_COSTS),
        "unit_cost_value_origin": "official_documentation_accessed_2026-09-01",
        "workload_value_origin": "proposal_not_observed",
        "guaranteed_duration_or_yield": False,
    }


def reconcile_quota_ledger(ledger: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(ledger, dict) or ledger.get("schema") != LEDGER_SCHEMA:
        raise ValueError(f"quota ledger schema must be {LEDGER_SCHEMA}")
    events = _list(ledger.get("events"), "quota ledger events")
    request_keys: set[str] = set()
    consumed = 0
    method_counts = {endpoint: 0 for endpoint in ALLOWED_ENDPOINTS}
    page_count = 0
    video_ids: set[str] = set()
    for index, event in enumerate(events):
        row = _mapping(event, f"events[{index}]")
        endpoint = row.get("method")
        if endpoint not in ALLOWED_ENDPOINTS:
            raise ValueError("quota ledger contains an unauthorized endpoint")
        request_key = _nonempty(row.get("request_key"), "request_key")
        if request_key in request_keys:
            raise ValueError("quota ledger contains a duplicate logical request")
        request_keys.add(request_key)
        if row.get("unit_cost") != OFFICIAL_UNIT_COSTS[endpoint]:
            raise ValueError("quota ledger unit cost differs from documented contract")
        if row.get("value_origin") != "official_documentation_accessed_2026-09-01":
            raise ValueError("quota ledger event lacks current documentation provenance")
        consumed += row["unit_cost"]
        method_counts[endpoint] += 1
        page_count += int(endpoint in {"commentThreads.list", "comments.list"})
        video_id = row.get("video_id")
        if video_id is not None:
            if not isinstance(video_id, str) or VIDEO_ID_RE.fullmatch(video_id) is None:
                raise ValueError("quota ledger contains an invalid video identity")
            video_ids.add(video_id)
        if row.get("evidence_durable_before_next_request") is not True:
            raise ValueError("quota event was not durably evidenced before the next request")
    budget = manifest["request_budget"]
    if consumed != ledger.get("consumed_budget") or len(events) != ledger.get("request_count"):
        raise ValueError("quota ledger totals do not reconcile")
    if ledger.get("remaining_budget") != budget["max_estimated_quota_units"] - consumed:
        raise ValueError("quota ledger remaining budget does not reconcile")
    if consumed > budget["max_estimated_quota_units"]:
        raise ValueError("quota ledger exceeded manifest budget")
    if ledger.get("method_request_counts") != method_counts:
        raise ValueError("quota ledger method counts do not reconcile")
    if ledger.get("page_count") != page_count or ledger.get("video_count") != len(video_ids):
        raise ValueError("quota ledger page/video counts do not reconcile")
    return ledger


def request_key(method: str, video_id: str, *, page_index: int = 0, parent_comment_id: str | None = None) -> str:
    if method not in ALLOWED_ENDPOINTS or VIDEO_ID_RE.fullmatch(video_id or "") is None:
        raise ValueError("request key intent is invalid")
    if page_index < 0:
        raise ValueError("page_index cannot be negative")
    return _fingerprint({"method": method, "video_id": video_id, "page_index": page_index,
                         "parent_comment_id": parent_comment_id})


def validate_checkpoint(checkpoint: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(checkpoint, dict) or checkpoint.get("schema") != CHECKPOINT_SCHEMA:
        raise ValueError(f"checkpoint schema must be {CHECKPOINT_SCHEMA}")
    _nonempty(checkpoint.get("run_id"), "run_id")
    if checkpoint.get("manifest_id") != manifest.get("manifest_id"):
        raise ValueError("checkpoint manifest identity changed")
    if checkpoint.get("request_intent_fingerprint") != manifest.get("request_intent_fingerprint"):
        raise ValueError("checkpoint request intent is inconsistent")
    states = _list(checkpoint.get("video_checkpoints"), "video_checkpoints")
    expected_ids = set(checkpoint.get("expected_video_ids") or [])
    if expected_ids != {row.get("video_id") for row in states}:
        raise ValueError("checkpoint video scope changed")
    durable_keys: set[str] = set()
    page_cap = manifest["comment_policy"]["comment_threads_max_pages_per_video"]
    for state in states:
        state = _mapping(state, "video checkpoint")
        video_id = state.get("video_id")
        if VIDEO_ID_RE.fullmatch(video_id or "") is None:
            raise ValueError("checkpoint contains an invalid video identity")
        if state.get("status") not in {"pending", "in_progress", "complete", "withheld", "technical_failure"}:
            raise ValueError("checkpoint video status is invalid")
        if _nonnegative_int(state.get("comment_threads_pages_durable"), "durable page count") > page_cap:
            raise ValueError("checkpoint exceeds the immutable page cap")
        if state.get("raw_page_token") is not None:
            raise ValueError("checkpoint must not persist raw page tokens")
        token_fingerprint = state.get("next_page_token_fingerprint")
        if token_fingerprint is not None and (not isinstance(token_fingerprint, str) or len(token_fingerprint) != 64):
            raise ValueError("checkpoint page-token fingerprint is invalid")
        for key in _list(state.get("durable_request_keys"), "durable_request_keys"):
            if key in durable_keys:
                raise ValueError("checkpoint repeats a durable logical request")
            durable_keys.add(key)
    if checkpoint.get("checkpoint_durable") is not True:
        raise ValueError("checkpoint is not durable")
    return checkpoint


def resume_pending_request_keys(checkpoint: dict[str, Any], manifest: dict[str, Any], planned_keys: list[str]) -> list[str]:
    validate_checkpoint(checkpoint, manifest)
    if len(planned_keys) != len(set(planned_keys)):
        raise ValueError("planned request intent contains duplicate logical requests")
    durable = {
        key for state in checkpoint["video_checkpoints"] for key in state["durable_request_keys"]
    }
    if not durable.issubset(set(planned_keys)):
        raise ValueError("checkpoint contains a request outside immutable intent")
    return [key for key in planned_keys if key not in durable]


def normalize_comment_observations(rows: list[dict[str, Any]], *, video_id: str) -> dict[str, Any]:
    comments: dict[str, dict[str, Any]] = {}
    duplicates = 0
    edited = 0
    for index, row in enumerate(_list(rows, "comment observations")):
        item = _mapping(row, f"comment observation {index}")
        if item.get("video_id") != video_id:
            raise ValueError("comment/video relationship mismatch")
        comment_id = _nonempty(item.get("comment_id"), "comment_id")
        parent_id = item.get("parent_comment_id")
        if parent_id is not None and (not isinstance(parent_id, str) or not parent_id.strip()):
            raise ValueError("reply parent identity is invalid")
        existing = comments.get(comment_id)
        if existing is not None:
            if existing.get("parent_comment_id") != parent_id or existing.get("thread_id") != item.get("thread_id"):
                raise ValueError("duplicate comment has conflicting relationships")
            duplicates += 1
            if str(item.get("updated_at") or "") > str(existing.get("updated_at") or ""):
                comments[comment_id] = deepcopy(item)
            continue
        if item.get("updated_at") != item.get("published_at"):
            edited += 1
        comments[comment_id] = deepcopy(item)
    return {"comments": list(comments.values()), "duplicate_observation_count": duplicates,
            "edited_comment_count": edited}


def evaluate_batch_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    scenario_id = _nonempty(scenario.get("scenario_id"), "scenario_id")
    flags = set(_list(scenario.get("flags"), "flags"))
    technical = {"corrupt_checkpoint", "relationship_mismatch", "evidence_writer_failure"}
    withheld = {"one_video_unavailable", "identity_revoked_after_manifest_creation"}
    if flags & technical:
        exit_code, classification = 1, "technical_failure"
    elif flags & withheld:
        exit_code, classification = 2, "evidence_withheld"
    else:
        exit_code, classification = 0, "approved_offline_simulation"
    comment_status = "public_accessible"
    for flag, status in (
        ("comments_disabled", "comments_disabled"), ("no_comments", "no_comments"),
        ("page_limit_truncation", "partial"), ("quota_boundary_before_next_page", "quota_boundary"),
        ("mixed_optional_module_outcomes", "mixed_optional"),
    ):
        if flag in flags:
            comment_status = status
    return {
        "scenario_id": scenario_id,
        "exit_classification": exit_code,
        "classification": classification,
        "metadata_required_resolved": not bool(flags & (technical | withheld)),
        "comment_status": comment_status,
        "comments_list_required": "partial_replies_requiring_comments_list" in flags,
        "coverage_truncated": bool(flags & {"page_limit_truncation", "quota_boundary_before_next_page"}),
        "resume_skips_durable_requests": "checkpoint_resume" in flags,
        "duplicate_suppression_required": "duplicate_pages_comments" in flags,
        "edited_timestamp_preservation_required": "edited_comment" in flags,
        "per_video_isolation_preserved": "one_video_unavailable" in flags,
    }


def aggregate_campaign(video_results: list[dict[str, Any]], *, metadata_required: bool = True) -> dict[str, Any]:
    """Aggregate independently durable per-video outcomes into 0/2/1 semantics."""
    rows = _list(video_results, "video_results")
    identities: set[str] = set()
    technical: list[str] = []
    withheld: list[str] = []
    for index, row in enumerate(rows):
        item = _mapping(row, f"video_results[{index}]")
        video_id = _nonempty(item.get("video_id"), "video_id")
        if VIDEO_ID_RE.fullmatch(video_id) is None or video_id in identities:
            raise ValueError("campaign contains malformed or duplicate video identity")
        identities.add(video_id)
        if item.get("evidence_durable") is not True or item.get("quota_integrity") is not True:
            technical.append(video_id)
            continue
        if item.get("technical_failure") is not None:
            technical.append(video_id)
            continue
        if item.get("availability") != "available" or (
            metadata_required and item.get("metadata_identity_complete") is not True
        ):
            withheld.append(video_id)
    exit_code = 1 if technical else 2 if withheld else 0
    return {
        "exit_classification": exit_code,
        "classification": {0: "approved_offline_simulation", 1: "technical_failure", 2: "evidence_withheld"}[exit_code],
        "video_count": len(rows),
        "technical_failure_video_ids": technical,
        "withheld_video_ids": withheld,
        "per_video_isolation_preserved": True,
    }


def deep_audit_batch(result: dict[str, Any]) -> dict[str, Any]:
    source = _mapping(result.get("source_audit"), "source_audit")
    videos = _list(result.get("video_audits"), "video_audits")
    modules = _mapping(result.get("module_audits"), "module_audits")
    gates = {
        "identity_provenance_integrity": source.get("identity_provenance_integrity") is True,
        "quota_ledger_reconciled": source.get("quota_ledger_reconciled") is True,
        "checkpoint_deterministic": source.get("checkpoint_deterministic") is True,
        "production_approved_false": source.get("production_approved") is False,
        "available_video_metadata_complete": all(
            video.get("metadata_identity_complete") is True
            for video in videos if video.get("availability") == "available"
        ),
        "snapshot_semantics": all(video.get("statistics_are_snapshot") is True for video in videos),
        "comment_relationship_integrity": modules.get("comment_relationship_integrity") is True,
        "pagination_coverage_disclosed": modules.get("pagination_coverage_disclosed") is True,
        "unsupported_language_transcript_text_zero": modules.get("unsupported_language_transcript_text_count") == 0,
        "unauthorized_caption_oauth_zero": modules.get("unauthorized_caption_oauth_count") == 0,
        "representativeness_claims_zero": modules.get("representativeness_claim_count") == 0,
    }
    return {"passed": all(gates.values()), "gates": gates,
            "hard_failures": [name for name, passed in gates.items() if not passed]}


def validate_ku2a_intake(package: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(package, dict) or package.get("schema") != DATASET_SCHEMA:
        raise ValueError(f"dataset package schema must be {DATASET_SCHEMA}")
    if package.get("storage_neutral") is not True or package.get("production_approved") is not False:
        raise ValueError("dataset package must be storage-neutral and non-production")
    entities = _mapping(package.get("entities"), "entities")
    channels = {row["channel_id"] for row in _list(entities.get("channels"), "channels")}
    videos = {row["video_id"]: row for row in _list(entities.get("videos"), "videos")}
    comments = {row["comment_id"]: row for row in _list(entities.get("comments"), "comments")}
    replies = _list(entities.get("comment_replies"), "comment_replies")
    if len(videos) != len(entities["videos"]) or len(comments) != len(entities["comments"]):
        raise ValueError("dataset package contains duplicate entity identity")
    for video in videos.values():
        if video.get("channel_id") not in channels:
            raise ValueError("video references an unknown channel")
    for comment in comments.values():
        if comment.get("video_id") not in videos or comment.get("parent_comment_id") is not None:
            raise ValueError("top-level comment relationship is invalid")
    reply_ids: set[str] = set()
    for reply in replies:
        if reply.get("comment_id") in reply_ids:
            raise ValueError("duplicate reply identity")
        reply_ids.add(reply.get("comment_id"))
        parent = comments.get(reply.get("parent_comment_id"))
        if parent is None or reply.get("video_id") != parent.get("video_id"):
            raise ValueError("reply relationship is invalid")
    serialized = json.dumps(package, ensure_ascii=False).casefold()
    for prohibited in ("sentiment_score", "embedding", "topic_model", "semantic_search_result"):
        if prohibited in serialized:
            raise ValueError("dataset package contains prohibited analytics output")
    if package.get("scheduler_action") is not None:
        raise ValueError("dataset package must not schedule work")
    return package


def operational_tier(entry: dict[str, Any] | None, *, drift: bool = False,
                     owner_caption_requested: bool = False, withheld: bool = False) -> str:
    if drift:
        return "drift_review_required"
    if owner_caption_requested:
        return "owner_authorized_caption_required"
    if withheld:
        return "unavailable_or_withheld"
    if entry is None or entry.get("usable_for_live_acquisition") is not True:
        return "identity_review_required"
    if entry.get("status") != "active":
        return "drift_review_required"
    return "batch_ready_reviewed_identity"
