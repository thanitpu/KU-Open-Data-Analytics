from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class LifecycleDecision:
    action: str
    reason: str
    requires_human_approval: bool = False


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def decide_next_action(
    *,
    quality_profile: dict[str, Any] | None,
    run_state: dict[str, Any] | None,
    current_profile_fingerprint: str | None,
    audited_profile_fingerprint: str | None,
    now: datetime | None = None,
    deep_audit_days: int = 30,
    repeated_failure_threshold: int = 3,
) -> LifecycleDecision:
    """Pure policy function used by scheduler/monitoring orchestration.

    It never auto-approves a materially changed technique profile.
    """
    now = now or datetime.now(timezone.utc)
    q = quality_profile or {}
    state = run_state or {}

    if current_profile_fingerprint and audited_profile_fingerprint and current_profile_fingerprint != audited_profile_fingerprint:
        return LifecycleDecision(
            "deep-audit",
            "Technique profile changed since the approved audit.",
            requires_human_approval=True,
        )

    if not q.get("audit_passed"):
        return LifecycleDecision("deep-audit", "Source has not passed Deep Audit.")

    if not q.get("approved_for_store"):
        return LifecycleDecision(
            "await-human-approval",
            "Deep Audit passed but repository acquisition is not yet approved.",
            requires_human_approval=True,
        )

    consecutive_failures = int(state.get("consecutive_failures") or 0)
    if consecutive_failures >= repeated_failure_threshold:
        return LifecycleDecision(
            "re-explore",
            f"Acquisition failed {consecutive_failures} consecutive times.",
        )

    last_audit = _parse_ts(q.get("last_audit_at"))
    if not last_audit or now - last_audit >= timedelta(days=max(1, deep_audit_days)):
        return LifecycleDecision("deep-audit", "Periodic Deep Audit is due.")

    return LifecycleDecision("scheduled-acquire", "Approved profile is current and healthy.")


def drift_detected(metrics: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if metrics.get("materialized_records") is not None and int(metrics.get("materialized_records") or 0) <= 0:
        reasons.append("zero-materialized-records")
    if metrics.get("price_completeness_pct") is not None and float(metrics["price_completeness_pct"]) < 80:
        reasons.append("price-completeness-below-80")
    if metrics.get("semantic_quality_pct") is not None and float(metrics["semantic_quality_pct"]) < 80:
        reasons.append("semantic-quality-below-80")
    if metrics.get("repeatability_pct") is not None and float(metrics["repeatability_pct"]) < 70:
        reasons.append("repeatability-below-70")
    if metrics.get("provenance_pct") is not None and float(metrics["provenance_pct"]) < 95:
        reasons.append("provenance-below-95")
    if int(metrics.get("blocked_or_rate_limited_events") or 0) >= 3:
        reasons.append("repeated-access-blocks")
    if metrics.get("schema_changed"):
        reasons.append("schema-changed")
    return bool(reasons), reasons
