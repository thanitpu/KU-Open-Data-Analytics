"""Fail-closed validator for KU2D Technical Correction Journal v1."""
from __future__ import annotations

import copy
import re
from datetime import datetime
from typing import Any


JOURNAL_ID = re.compile(r"^KU2D-CJ-[0-9]{6}$")
PROMPT_ID = re.compile(r"^KU2D-P-[0-9]{6}$")
EVENT_ID = re.compile(r"^KU2D-TC-[0-9]{6}$")
COMMIT = re.compile(r"^(pending_commit|[0-9a-f]{40})$")

TOP_LEVEL_FIELDS = {
    "schema", "journal_id", "source_completion_prompt_id", "created_at",
    "closed_at", "events", "summary", "safety",
}
EVENT_REQUIRED_FIELDS = {
    "event_id", "observed_at", "phase", "failure_code", "observed_signal",
    "root_cause_layer", "correction", "validation", "outcome", "provider_impact",
    "learning",
}
EVENT_OPTIONAL_FIELDS = {
    "schema_impact", "quality_impact", "related_commit_or_pending_commit",
    "effort_minutes", "evidence_refs",
}
P52_REQUIRED_EVENT_FIELDS = {
    "schema_impact", "quality_impact", "related_commit_or_pending_commit",
}
EVENT_FIELDS = EVENT_REQUIRED_FIELDS | EVENT_OPTIONAL_FIELDS
PHASES = {
    "protocol_migration", "preflight", "implementation", "test", "ci", "merge",
    "authorization", "dispatch", "acquisition", "artifact", "evidence", "closure",
}
ROOT_CAUSE_LAYERS = {
    "coordination_protocol", "authorization_schema", "workflow", "runtime_code",
    "dependency", "provider_access", "data_quality", "artifact", "ci", "git",
    "environment", "unknown",
}
VALIDATION_RESULTS = {"passed", "failed", "partial", "not_run"}
OUTCOMES = {"resolved", "partially_resolved", "unresolved", "superseded"}


def _exact_fields(value: Any, required: set[str], allowed: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    missing = required - set(value)
    unknown = set(value) - allowed
    if missing or unknown:
        raise ValueError(
            f"{name} fields are invalid; missing={sorted(missing)}, unknown={sorted(unknown)}"
        )
    return value


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _date_time(value: Any, name: str, *, nullable: bool = False) -> datetime | None:
    if value is None and nullable:
        return None
    text = _nonempty(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an RFC 3339 date-time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone offset")
    return parsed


def _string_list(value: Any, name: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{name} must be {'a non-empty' if nonempty else 'an'} array")
    if any(not isinstance(item, str) for item in value) or len(value) != len(set(value)):
        raise ValueError(f"{name} must contain unique strings")
    return value


def _nonnegative_integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def validate_technical_correction_journal(
    journal: dict[str, Any], *, allow_pending_commit: bool = False, require_closed: bool = False
) -> dict[str, Any]:
    journal = _exact_fields(journal, TOP_LEVEL_FIELDS, TOP_LEVEL_FIELDS, "journal")
    if journal["schema"] != "ku2d.technical-correction-journal.v1":
        raise ValueError("invalid technical correction journal schema")
    if not isinstance(journal["journal_id"], str) or not JOURNAL_ID.fullmatch(journal["journal_id"]):
        raise ValueError("journal_id is invalid")
    prompt_id = journal["source_completion_prompt_id"]
    if not isinstance(prompt_id, str) or not PROMPT_ID.fullmatch(prompt_id):
        raise ValueError("source_completion_prompt_id is invalid")
    created_at = _date_time(journal["created_at"], "created_at")
    closed_at = _date_time(journal["closed_at"], "closed_at", nullable=True)
    if require_closed and closed_at is None:
        raise ValueError("closed_at is required for a finalized journal")
    if closed_at is not None and closed_at < created_at:
        raise ValueError("closed_at cannot precede created_at")

    events = journal["events"]
    if not isinstance(events, list):
        raise ValueError("technical correction events must be a list")
    p52_required = P52_REQUIRED_EVENT_FIELDS if prompt_id == "KU2D-P-000052" else set()
    event_ids: set[str] = set()
    resolved = unresolved = 0
    for index, raw_event in enumerate(events):
        event = _exact_fields(
            raw_event, EVENT_REQUIRED_FIELDS | p52_required, EVENT_FIELDS, f"events[{index}]",
        )
        event_id = event["event_id"]
        if not isinstance(event_id, str) or not EVENT_ID.fullmatch(event_id) or event_id in event_ids:
            raise ValueError("correction event IDs must be unique typed identifiers")
        event_ids.add(event_id)
        _date_time(event["observed_at"], f"events[{index}].observed_at")
        if event["phase"] not in PHASES:
            raise ValueError("correction event phase is invalid")
        _nonempty(event["failure_code"], f"events[{index}].failure_code")
        _nonempty(event["observed_signal"], f"events[{index}].observed_signal")
        if event["root_cause_layer"] not in ROOT_CAUSE_LAYERS:
            raise ValueError("correction event root_cause_layer is invalid")

        correction = _exact_fields(
            event["correction"], {"action", "components", "scope_changed"},
            {"action", "components", "scope_changed"}, f"events[{index}].correction",
        )
        _nonempty(correction["action"], f"events[{index}].correction.action")
        _string_list(correction["components"], f"events[{index}].correction.components")
        if correction["scope_changed"] is not False:
            raise ValueError("correction.scope_changed must be false")

        validation = _exact_fields(
            event["validation"], {"checks", "result"}, {"checks", "result"},
            f"events[{index}].validation",
        )
        _string_list(validation["checks"], f"events[{index}].validation.checks", nonempty=True)
        if validation["result"] not in VALIDATION_RESULTS:
            raise ValueError("correction validation result is invalid")
        if event["outcome"] not in OUTCOMES:
            raise ValueError("correction outcome is invalid")

        provider = _exact_fields(
            event["provider_impact"], {"provider_reached", "request_delta", "quota_delta"},
            {"provider_reached", "request_delta", "quota_delta"},
            f"events[{index}].provider_impact",
        )
        if not isinstance(provider["provider_reached"], bool):
            raise ValueError("provider_reached must be boolean")
        _nonnegative_integer(provider["request_delta"], "request_delta")
        _nonnegative_integer(provider["quota_delta"], "quota_delta")

        for field in ("schema_impact", "quality_impact"):
            if field in event:
                _nonempty(event[field], f"events[{index}].{field}")
        if "related_commit_or_pending_commit" in event:
            link = event["related_commit_or_pending_commit"]
            if not isinstance(link, str) or not COMMIT.fullmatch(link):
                raise ValueError("correction event commit linkage is invalid")
            if link == "pending_commit" and not allow_pending_commit:
                raise ValueError("pending correction commit must be finalized before PR or closure")
        if "effort_minutes" in event and event["effort_minutes"] is not None:
            effort = event["effort_minutes"]
            if isinstance(effort, bool) or not isinstance(effort, (int, float)) or effort < 0:
                raise ValueError("effort_minutes must be null or non-negative")

        learning = _exact_fields(
            event["learning"], {"reusable_lesson", "future_prevention", "labels"},
            {"reusable_lesson", "future_prevention", "labels"}, f"events[{index}].learning",
        )
        _nonempty(learning["reusable_lesson"], "reusable_lesson")
        _nonempty(learning["future_prevention"], "future_prevention")
        _string_list(learning["labels"], "learning.labels")
        if "evidence_refs" in event:
            _string_list(event["evidence_refs"], f"events[{index}].evidence_refs")

        if event["outcome"] == "resolved":
            resolved += 1
        elif event["outcome"] in {"unresolved", "partially_resolved"}:
            unresolved += 1

    summary = _exact_fields(
        journal["summary"],
        {"event_count", "resolved_count", "unresolved_count", "correction_cycles_used"},
        {"event_count", "resolved_count", "unresolved_count", "correction_cycles_used"},
        "summary",
    )
    expected_summary = {
        "event_count": len(events),
        "resolved_count": resolved,
        "unresolved_count": unresolved,
        "correction_cycles_used": len(events),
    }
    for field in expected_summary:
        _nonnegative_integer(summary[field], f"summary.{field}")
    if summary != expected_summary:
        raise ValueError("technical correction summary is inconsistent")

    safety = _exact_fields(
        journal["safety"],
        {"contains_secret", "contains_raw_payload", "contains_request_url", "contains_personal_data"},
        {"contains_secret", "contains_raw_payload", "contains_request_url", "contains_personal_data"},
        "safety",
    )
    if safety != {
        "contains_secret": False,
        "contains_raw_payload": False,
        "contains_request_url": False,
        "contains_personal_data": False,
    }:
        raise ValueError("technical correction journal is not sanitized")
    return copy.deepcopy(journal)
