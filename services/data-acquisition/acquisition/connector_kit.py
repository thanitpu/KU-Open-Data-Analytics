"""Reusable, deterministic connector contracts for KU2D Source Labs.

The kit owns execution mechanics and sanitized evidence.  Source adapters only
declare access; source parsers interpret source payloads; domain mappers produce
domain records.  Nothing in this module grants production or scheduling
authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Protocol


CAPABILITY_STATES = {
    "available", "partial", "unverified", "blocked", "unsupported", "not_applicable",
}
SENSITIVE_KEY = re.compile(
    r"(^|_)(api_?key|authorization|cookie|password|secret|session|token|device_?id)(_|$)",
    re.IGNORECASE,
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _walk_safe(value: Any, path: str = "record") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if SENSITIVE_KEY.search(str(key)):
                raise ValueError(f"sensitive field is forbidden in sanitized output: {path}.{key}")
            _walk_safe(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_safe(child, f"{path}[{index}]")


class ErrorClass(str, Enum):
    POLICY = "policy"
    AUTHENTICATION = "authentication"
    QUOTA = "quota"
    TRANSIENT = "transient"
    PARSER = "parser"
    SCHEMA = "schema"
    UNKNOWN = "unknown"


class ConnectorFailure(RuntimeError):
    def __init__(self, message: str, error_class: ErrorClass, *, retryable: bool = False):
        super().__init__(message)
        self.error_class = error_class
        self.retryable = retryable


def classify_error(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, ConnectorFailure):
        category, retryable = exc.error_class.value, exc.retryable
    elif isinstance(exc, (TimeoutError, ConnectionError)):
        category, retryable = ErrorClass.TRANSIENT.value, True
    elif isinstance(exc, (ValueError, TypeError, KeyError)):
        category, retryable = ErrorClass.PARSER.value, False
    else:
        category, retryable = ErrorClass.UNKNOWN.value, False
    return {
        "category": category,
        "retryable": retryable,
        "exception_type": type(exc).__name__,
        "message": str(exc),
    }


@dataclass(frozen=True)
class RequestPlan:
    request_id: str
    capability_id: str
    operation: str
    parameters: dict[str, Any]
    timeout_seconds: int = 20
    max_attempts: int = 1
    quota_cost_per_attempt: int = 0
    credential_environment_key: str | None = None
    pagination: dict[str, Any] = field(default_factory=lambda: {"mode": "none", "page_limit": 1})

    def validate(self) -> "RequestPlan":
        if not self.request_id or not self.capability_id or not self.operation:
            raise ValueError("request_id, capability_id and operation are required")
        if not 1 <= self.timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be between 1 and 120")
        if not 1 <= self.max_attempts <= 3:
            raise ValueError("max_attempts must be between 1 and 3")
        if self.quota_cost_per_attempt < 0:
            raise ValueError("quota cost cannot be negative")
        _walk_safe(self.parameters, "request.parameters")
        return self

    def sanitized(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("credential_environment_key")
        data["credential_required"] = self.credential_environment_key is not None
        return data


@dataclass(frozen=True)
class ResponseEnvelope:
    request_id: str
    status_code: int
    payload: Any
    observed_at: str
    provenance: dict[str, Any]
    response_headers: dict[str, str] = field(default_factory=dict)


class ThinSourceAdapter(Protocol):
    source_id: str
    parser_id: str
    domain_profile_id: str

    def build_request(self, capability_id: str) -> RequestPlan: ...

    def capability_declarations(self) -> list[dict[str, Any]]: ...


class SourceParser(Protocol):
    parser_id: str

    def parse(self, envelope: ResponseEnvelope) -> list[dict[str, Any]]: ...


class DomainMapper(Protocol):
    mapper_id: str

    def map_record(self, source_record: dict[str, Any]) -> dict[str, Any]: ...


class SanitizedLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit(self, event: dict[str, Any]) -> None:
        _walk_safe(event, "log")
        self.events.append(copy.deepcopy(event))


class FixtureReplayTransport:
    """Injectable no-network transport for already-sanitized committed fixtures."""

    def __init__(self, fixtures: Mapping[str, Any], *, observed_at: str = "fixture-replay") -> None:
        self._fixtures = copy.deepcopy(dict(fixtures))
        self._observed_at = observed_at
        self.calls: list[str] = []

    def __call__(self, plan: RequestPlan, credential: str | None) -> ResponseEnvelope:
        if credential is not None:
            raise ConnectorFailure("fixture replay does not accept credentials", ErrorClass.POLICY)
        fixture_id = str(plan.parameters.get("fixture_id") or "")
        if plan.operation != "fixture.replay" or fixture_id not in self._fixtures:
            raise ConnectorFailure("fixture replay request is not available", ErrorClass.POLICY)
        self.calls.append(plan.request_id)
        payload = copy.deepcopy(self._fixtures[fixture_id])
        return ResponseEnvelope(
            request_id=plan.request_id,
            status_code=200,
            payload=payload,
            observed_at=self._observed_at,
            provenance={"transport": "fixture_replay", "fixture_id": fixture_id},
        )


class ConnectorKit:
    """Execute one bounded adapter request and return sanitized deterministic evidence."""

    def __init__(self, *, credentials: Mapping[str, str] | None = None, logger: SanitizedLogger | None = None) -> None:
        self._credentials = dict(credentials or {})
        self.logger = logger or SanitizedLogger()

    def execute(
        self,
        adapter: ThinSourceAdapter,
        parser: SourceParser,
        mapper: DomainMapper,
        capability_id: str,
        transport: Callable[[RequestPlan, str | None], ResponseEnvelope],
    ) -> dict[str, Any]:
        if parser.parser_id != adapter.parser_id:
            raise ConnectorFailure("adapter parser selection does not match", ErrorClass.POLICY)
        plan = adapter.build_request(capability_id).validate()
        declared = {row["capability_id"]: row["state"] for row in adapter.capability_declarations()}
        if declared.get(capability_id) not in {"available", "partial", "unverified"}:
            raise ConnectorFailure("capability is not executable", ErrorClass.POLICY)
        credential = None
        if plan.credential_environment_key:
            credential = self._credentials.get(plan.credential_environment_key)
            if not credential:
                raise ConnectorFailure("required runtime credential is unavailable", ErrorClass.AUTHENTICATION)

        ledger: list[dict[str, Any]] = []
        envelope: ResponseEnvelope | None = None
        failure: dict[str, Any] | None = None
        for attempt in range(1, plan.max_attempts + 1):
            try:
                envelope = transport(plan, credential)
                ledger.append({
                    "request_id": plan.request_id,
                    "attempt": attempt,
                    "status": "completed",
                    "quota_units": plan.quota_cost_per_attempt,
                })
                failure = None
                break
            except Exception as exc:
                failure = classify_error(exc)
                ledger.append({
                    "request_id": plan.request_id,
                    "attempt": attempt,
                    "status": "failed",
                    "quota_units": plan.quota_cost_per_attempt,
                    "error": failure,
                })
                if not failure["retryable"] or attempt == plan.max_attempts:
                    break
        if envelope is None:
            raise ConnectorFailure(
                (failure or {}).get("message", "transport failed"),
                ErrorClass((failure or {}).get("category", "unknown")),
                retryable=bool((failure or {}).get("retryable")),
            )

        try:
            source_records = parser.parse(envelope)
            domain_records = [mapper.map_record(record) for record in source_records]
        except ConnectorFailure:
            raise
        except Exception as exc:
            detail = classify_error(exc)
            raise ConnectorFailure(detail["message"], ErrorClass.PARSER) from exc

        for index, record in enumerate(domain_records):
            _walk_safe(record, f"domain_records[{index}]")
        evidence = {
            "source_id": adapter.source_id,
            "capability_id": capability_id,
            "request_plan": plan.sanitized(),
            "response": {
                "status_code": envelope.status_code,
                "observed_at": envelope.observed_at,
                "provenance": envelope.provenance,
                "payload_sha256": fingerprint(envelope.payload),
            },
            "source_record_count": len(source_records),
            "domain_record_count": len(domain_records),
            "domain_record_sha256": fingerprint(domain_records),
            "request_count": len(ledger),
            "documented_quota_units": sum(row["quota_units"] for row in ledger),
        }
        self.logger.emit({"event": "connector_execution_completed", "evidence": evidence})
        return {
            "source_records": source_records,
            "domain_records": domain_records,
            "evidence": evidence,
            "request_ledger": ledger,
            "boundaries": {
                "production_store": False,
                "production_approved": False,
                "scheduler_action": None,
            },
        }


def validate_domain_capability_profile(profile: dict[str, Any]) -> dict[str, Any]:
    required = {"schema", "profile_id", "version", "domain", "capabilities", "semantic_quality_owner", "boundaries"}
    if set(profile) != required or profile.get("schema") != "ku2d.domain-capability-profile.v1":
        raise ValueError("invalid Domain Capability Profile v1 shape")
    capabilities = profile.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        raise ValueError("capabilities must be a non-empty list")
    identifiers: set[str] = set()
    for row in capabilities:
        if set(row) != {"capability_id", "state", "required_for_mtc", "reason", "evidence_refs"}:
            raise ValueError("invalid capability declaration shape")
        capability_id = row.get("capability_id")
        if not isinstance(capability_id, str) or not capability_id or capability_id in identifiers:
            raise ValueError("capability identifiers must be unique non-empty strings")
        identifiers.add(capability_id)
        if row.get("state") not in CAPABILITY_STATES:
            raise ValueError("invalid capability state")
        if not isinstance(row.get("required_for_mtc"), bool) or not str(row.get("reason") or "").strip():
            raise ValueError("capability requirement and reason are required")
        if not isinstance(row.get("evidence_refs"), list):
            raise ValueError("capability evidence_refs must be a list")
    if profile.get("semantic_quality_owner") != "analysis":
        raise ValueError("semantic quality must remain Analysis-owned")
    boundaries = profile.get("boundaries") or {}
    if boundaries != {"production_approved": False, "scheduler_action": None}:
        raise ValueError("capability profile cannot grant production authority")
    return copy.deepcopy(profile)


def validate_source_manifest(manifest: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema", "manifest_id", "source_id", "provider", "domain_profile_id", "adapter", "parser", "mapper",
        "access_surface", "capabilities", "known_limitations", "fixture_sets", "evidence_refs", "integration_status",
        "boundaries",
    }
    if set(manifest) != required or manifest.get("schema") != "ku2d.source-manifest.v1":
        raise ValueError("invalid Source Manifest v1 shape")
    validate_domain_capability_profile(profile)
    if manifest.get("domain_profile_id") != profile.get("profile_id"):
        raise ValueError("source manifest domain profile mismatch")
    profile_states = {row["capability_id"]: row["state"] for row in profile["capabilities"]}
    manifest_states = {row["capability_id"]: row["state"] for row in manifest.get("capabilities") or []}
    if manifest_states != profile_states:
        raise ValueError("source manifest capability declarations must match the domain profile")
    if not all(str(manifest.get(key) or "").strip() for key in ("adapter", "parser", "mapper", "access_surface")):
        raise ValueError("adapter, parser, mapper and access_surface are required")
    if not manifest.get("fixture_sets") or not manifest.get("known_limitations"):
        raise ValueError("fixture sets and known limitations are required")
    if manifest.get("boundaries") != {
        "provider_requests_performed": 0,
        "documented_quota_units": 0,
        "production_store": False,
        "production_approved": False,
        "scheduler_action": None,
    }:
        raise ValueError("source manifest boundaries are not fail-closed")
    return copy.deepcopy(manifest)


def validate_mtc_assessment(
    assessment: dict[str, Any], manifest: dict[str, Any], profile: dict[str, Any]
) -> dict[str, Any]:
    validate_source_manifest(manifest, profile)
    required = {
        "schema", "assessment_id", "source_manifest_id", "assessed_at", "status", "useful_capabilities",
        "criteria", "record_count", "known_limitations", "closure_status", "boundaries",
    }
    if set(assessment) != required or assessment.get("schema") != "ku2d.minimum-trusted-connection-assessment.v1":
        raise ValueError("invalid MTC Assessment v1 shape")
    if assessment.get("source_manifest_id") != manifest.get("manifest_id"):
        raise ValueError("MTC assessment source manifest mismatch")
    criteria = assessment.get("criteria") or {}
    expected_criteria = {
        "useful_reproducible_capability", "schema_valid_output", "provenance", "failure_classification",
        "sanitized_evidence", "fixture_replay", "known_limitations",
    }
    if set(criteria) != expected_criteria or not all(value is True for value in criteria.values()):
        raise ValueError("all MTC criteria must pass")
    required_capabilities = {
        row["capability_id"] for row in profile["capabilities"] if row["required_for_mtc"]
    }
    if not required_capabilities.issubset(set(assessment.get("useful_capabilities") or [])):
        raise ValueError("required MTC capabilities are unresolved")
    if assessment.get("status") != "passed" or int(assessment.get("record_count", 0)) < 1:
        raise ValueError("MTC assessment must pass with at least one record")
    if assessment.get("boundaries") != {
        "semantic_quality_claimed": False,
        "production_store": False,
        "production_approved": False,
        "scheduler_action": None,
    }:
        raise ValueError("MTC assessment cannot grant semantic or production authority")
    return copy.deepcopy(assessment)
