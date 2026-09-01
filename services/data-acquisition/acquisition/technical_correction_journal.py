"""Fail-closed validator for KU2D Technical Correction Journal v1."""
from __future__ import annotations

import copy
import re
from typing import Any


COMMIT = re.compile(r"^(pending_commit|[0-9a-f]{40})$")
REQUIRED_EVENT_FIELDS = {
    "event_id", "observed_at", "phase", "failure_code", "observed_signal",
    "root_cause_layer", "correction", "validation", "outcome", "provider_impact",
    "schema_impact", "quality_impact", "related_commit_or_pending_commit", "learning",
}


def validate_technical_correction_journal(
    journal: dict[str, Any], *, allow_pending_commit: bool = False
) -> dict[str, Any]:
    if journal.get("schema") != "ku2d.technical-correction-journal.v1":
        raise ValueError("invalid technical correction journal schema")
    events = journal.get("events")
    if not isinstance(events, list):
        raise ValueError("technical correction events must be a list")
    event_ids: set[str] = set()
    resolved = unresolved = 0
    for event in events:
        if not isinstance(event, dict) or not REQUIRED_EVENT_FIELDS.issubset(event):
            raise ValueError("P52 correction event fields are incomplete")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or event_id in event_ids:
            raise ValueError("correction event IDs must be unique")
        event_ids.add(event_id)
        link = event.get("related_commit_or_pending_commit")
        if not isinstance(link, str) or not COMMIT.fullmatch(link):
            raise ValueError("correction event commit linkage is invalid")
        if link == "pending_commit" and not allow_pending_commit:
            raise ValueError("pending correction commit must be finalized before PR or closure")
        provider = event.get("provider_impact") or {}
        if provider != {"provider_reached": False, "request_delta": 0, "quota_delta": 0}:
            raise ValueError("P52 correction journal must preserve zero-provider boundaries")
        if event.get("outcome") == "resolved":
            resolved += 1
        elif event.get("outcome") in {"unresolved", "partially_resolved"}:
            unresolved += 1
    summary = journal.get("summary") or {}
    if summary != {
        "event_count": len(events),
        "resolved_count": resolved,
        "unresolved_count": unresolved,
        "correction_cycles_used": len(events),
    }:
        raise ValueError("technical correction summary is inconsistent")
    if journal.get("safety") != {
        "contains_secret": False,
        "contains_raw_payload": False,
        "contains_request_url": False,
        "contains_personal_data": False,
    }:
        raise ValueError("technical correction journal is not sanitized")
    return copy.deepcopy(journal)
