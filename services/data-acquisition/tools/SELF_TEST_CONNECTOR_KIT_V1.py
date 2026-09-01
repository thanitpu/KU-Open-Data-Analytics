from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
if str(ACQUISITION) not in sys.path:
    sys.path.insert(0, str(ACQUISITION))

from acquisition_analysis_handoff import validate_analysis_intake
from connector_kit import (
    ConnectorFailure,
    ConnectorKit,
    ErrorClass,
    FixtureReplayTransport,
    RequestPlan,
    SanitizedLogger,
    classify_error,
    validate_domain_capability_profile,
    validate_mtc_assessment,
    validate_source_manifest,
)
from youtube_qdiving_connector import (
    PublicVideoQDivingMapper,
    YouTubeQDivingAdapter,
    YouTubeQDivingCandidateParser,
)
from technical_correction_journal import validate_technical_correction_journal


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


packet_path = (
    ROOT / "knowledge" / "v1" / "candidate-closure-packets" /
    "KU2D-YT-QDIVING-CANDIDATES-000001.json"
)
analysis_path = ROOT / "knowledge" / "v1" / "analysis-intake-manifests" / "KU2D-AI-000001.json"
profile_path = ROOT / "config" / "domain_capability_profiles" / "public_video_q_diving_v1.json"
manifest_path = ROOT / "config" / "source_manifests" / "youtube_qdiving_v1.json"
assessment_path = ROOT / "knowledge" / "v1" / "mtc-assessments" / "KU2D-MTC-000001.json"
lifecycle_path = ROOT / "config" / "source_completion_queue_template_v1.json"

packet = load(packet_path)
analysis = validate_analysis_intake(load(analysis_path), packet=packet)
profile = validate_domain_capability_profile(load(profile_path))
manifest = validate_source_manifest(load(manifest_path), profile)
assessment = validate_mtc_assessment(load(assessment_path), manifest, profile)

# CK1: the complete fixture path uses no credential, provider request or quota.
adapter = YouTubeQDivingAdapter()
parser = YouTubeQDivingCandidateParser()
mapper = PublicVideoQDivingMapper()
transport = FixtureReplayTransport(
    {"KU2D-YT-QDIVING-CANDIDATES-000001": packet},
    observed_at="2026-09-01T04:47:45+00:00",
)
kit = ConnectorKit()
video_result = kit.execute(adapter, parser, mapper, "video_metadata", transport)
channel_result = kit.execute(adapter, parser, mapper, "channel_identity", transport)
assert transport.calls == [
    "youtube-qdiving-p50-video_metadata",
    "youtube-qdiving-p50-channel_identity",
]
assert video_result["evidence"]["request_count"] == 1
assert video_result["evidence"]["documented_quota_units"] == 0
assert video_result["boundaries"] == {
    "production_store": False,
    "production_approved": False,
    "scheduler_action": None,
}

# CK2: all ten candidates remain retrievable in P51 order with provenance.
domain_records = video_result["domain_records"]
fixture_ids = [row["video_id"] for row in packet["candidates"]]
analysis_ids = [row["candidate_id"] for row in analysis["records"]]
mapped_ids = [row["record_id"] for row in domain_records]
assert len(domain_records) == assessment["record_count"] == 10
assert fixture_ids == analysis_ids == mapped_ids
assert all(row["channel_identity"]["channel_id"] for row in domain_records)
assert all(row["provenance"]["query_profile_ids"] for row in domain_records)
assert all(row["acquisition_acceptance"] == "accepted_for_analysis" for row in domain_records)
assert all(all(value is None for value in row["analysis"].values()) for row in domain_records)
assert all(row["production_ready"] is False for row in domain_records)
assert channel_result["domain_records"] == domain_records

# CK3: the adapter declares access only; kit evidence is sanitized.
plan = adapter.build_request("video_metadata")
assert plan.operation == "fixture.replay" and plan.credential_environment_key is None
assert plan.pagination == {"mode": "immutable_packet", "page_limit": 1}
assert "credential_environment_key" not in plan.sanitized()
assert "payload" not in video_result["evidence"]["response"]
assert len(video_result["evidence"]["response"]["payload_sha256"]) == 64
assert len(video_result["evidence"]["domain_record_sha256"]) == 64

# CK4: unavailable capabilities and malformed source fixtures fail closed.
try:
    adapter.build_request("comments")
    raise AssertionError("blocked capability was accepted")
except ConnectorFailure as exc:
    assert exc.error_class is ErrorClass.POLICY
bad_packet = copy.deepcopy(packet)
bad_packet["candidate_count"] = 9
bad_transport = FixtureReplayTransport({"KU2D-YT-QDIVING-CANDIDATES-000001": bad_packet})
try:
    kit.execute(adapter, parser, mapper, "video_metadata", bad_transport)
    raise AssertionError("inconsistent fixture was accepted")
except ConnectorFailure as exc:
    assert exc.error_class is ErrorClass.SCHEMA

# CK5: retry/accounting and shared error classification are deterministic.
class TransientThenFixture:
    def __init__(self):
        self.calls = 0
        self.fixture = FixtureReplayTransport({"fixture": packet})

    def __call__(self, request, credential):
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("bounded timeout")
        return self.fixture(request, credential)


class RetryAdapter(YouTubeQDivingAdapter):
    def build_request(self, capability_id):
        return RequestPlan(
            request_id="retry-fixture",
            capability_id=capability_id,
            operation="fixture.replay",
            parameters={"fixture_id": "fixture"},
            max_attempts=2,
            quota_cost_per_attempt=0,
        )


retry_result = ConnectorKit().execute(
    RetryAdapter(), parser, mapper, "video_metadata", TransientThenFixture()
)
assert [row["status"] for row in retry_result["request_ledger"]] == ["failed", "completed"]
assert retry_result["request_ledger"][0]["error"]["category"] == "transient"
assert classify_error(ValueError("bad"))["category"] == "parser"

# CK6: logs reject credential-like fields instead of redacting ambiguously.
logger = SanitizedLogger()
try:
    logger.emit({"api_key": "forbidden"})
    raise AssertionError("sensitive log field was accepted")
except ValueError as exc:
    assert "sensitive field" in str(exc)

# CK7: capability profile supports every contracted state without universals.
states = {row["state"] for row in profile["capabilities"]}
assert states == {"available", "blocked"}
for extra_state in ("partial", "unverified", "unsupported", "not_applicable"):
    changed = copy.deepcopy(profile)
    changed["capabilities"][2]["state"] = extra_state
    validate_domain_capability_profile(changed)
assert {row["capability_id"] for row in profile["capabilities"] if row["required_for_mtc"]} == {
    "video_metadata", "channel_identity",
}
assert not ({"product", "price", "promotion"} & {row["capability_id"] for row in profile["capabilities"]})

# CK8: MTC validators reject unresolved required capabilities and authority drift.
bad_assessment = copy.deepcopy(assessment)
bad_assessment["useful_capabilities"] = ["video_metadata"]
try:
    validate_mtc_assessment(bad_assessment, manifest, profile)
    raise AssertionError("missing MTC capability was accepted")
except ValueError as exc:
    assert "unresolved" in str(exc)
bad_manifest = copy.deepcopy(manifest)
bad_manifest["boundaries"]["production_approved"] = True
try:
    validate_source_manifest(bad_manifest, profile)
    raise AssertionError("production authority drift was accepted")
except ValueError as exc:
    assert "boundaries" in str(exc)

# CK9: schemas and generic lifecycle template are versioned and source-neutral.
schema_files = [
    "domain-capability-profile.schema.json",
    "source-manifest.schema.json",
    "minimum-trusted-connection-assessment.schema.json",
    "source-lab-lifecycle.schema.json",
]
for filename in schema_files:
    document = load(ROOT / "knowledge" / "v1" / filename)
    assert document["$schema"].endswith("2020-12/schema")
    assert document["additionalProperties"] is False
lifecycle = load(lifecycle_path)
assert lifecycle["phases"] == [
    "technique_library_reuse", "explore", "deep_audit",
    "minimum_trusted_connection", "integration", "closure",
]
assert lifecycle["testing"]["level_3"] == ["full_deterministic_corpus_exact_head"]
assert "tiktok" not in json.dumps(lifecycle).lower()
assert lifecycle["boundaries"] == {"production_authorized": False, "scheduler_action": None}

# CK10: reference closure is MTC-only and keeps optional capabilities blocked.
assert assessment["status"] == "passed" and assessment["closure_status"] == "closed_v1"
assert assessment["useful_capabilities"] == ["video_metadata", "channel_identity"]
assert all(assessment["criteria"].values())
assert manifest["integration_status"] == "closed_v1"
assert profile["semantic_quality_owner"] == "analysis"

# CK11: correction journals carry the stronger fields and finalize commit links.
journal = {
    "schema": "ku2d.technical-correction-journal.v1",
    "journal_id": "KU2D-CJ-999999",
    "source_completion_prompt_id": "KU2D-P-000052",
    "created_at": "2026-09-01T00:00:00+00:00",
    "closed_at": "2026-09-01T00:05:00+00:00",
    "events": [{
        "event_id": "KU2D-TC-999999",
        "observed_at": "2026-09-01T00:00:00+00:00",
        "phase": "test",
        "failure_code": "fixture",
        "observed_signal": "fixture",
        "root_cause_layer": "runtime_code",
        "correction": {"action": "fixture", "components": [], "scope_changed": False},
        "validation": {"checks": ["fixture"], "result": "passed"},
        "outcome": "resolved",
        "provider_impact": {"provider_reached": False, "request_delta": 0, "quota_delta": 0},
        "schema_impact": "none",
        "quality_impact": "none",
        "related_commit_or_pending_commit": "0" * 40,
        "learning": {"reusable_lesson": "fixture", "future_prevention": "fixture", "labels": []},
    }],
    "summary": {"event_count": 1, "resolved_count": 1, "unresolved_count": 0, "correction_cycles_used": 1},
    "safety": {"contains_secret": False, "contains_raw_payload": False, "contains_request_url": False, "contains_personal_data": False},
}
validate_technical_correction_journal(journal, require_closed=True)

# CK12: typed journal, Prompt and event identifiers fail closed.
for field, value in (
    ("journal_id", "CJ-999999"),
    ("source_completion_prompt_id", "P-000052"),
):
    invalid = copy.deepcopy(journal)
    invalid[field] = value
    try:
        validate_technical_correction_journal(invalid)
        raise AssertionError(f"invalid {field} was accepted")
    except ValueError:
        pass
invalid_event_id = copy.deepcopy(journal)
invalid_event_id["events"][0]["event_id"] = "TC-999999"
try:
    validate_technical_correction_journal(invalid_event_id)
    raise AssertionError("invalid event_id was accepted")
except ValueError:
    pass

# CK13: lifecycle timestamps require timezone-aware RFC 3339 values and valid order.
for field, value in (
    ("created_at", "not-a-date"),
    ("created_at", "2026-09-01T00:00:00"),
    ("closed_at", "2026-08-31T23:59:59+00:00"),
):
    invalid = copy.deepcopy(journal)
    invalid[field] = value
    try:
        validate_technical_correction_journal(invalid)
        raise AssertionError(f"invalid {field} was accepted")
    except ValueError:
        pass
open_journal = copy.deepcopy(journal)
open_journal["closed_at"] = None
validate_technical_correction_journal(open_journal)
try:
    validate_technical_correction_journal(open_journal, require_closed=True)
    raise AssertionError("open journal was accepted as finalized")
except ValueError:
    pass

# CK14: top-level fields are exact; missing and unknown fields are rejected.
for invalid in (
    {key: value for key, value in journal.items() if key != "journal_id"},
    {**journal, "unexpected": True},
):
    try:
        validate_technical_correction_journal(invalid)
        raise AssertionError("invalid top-level field set was accepted")
    except ValueError:
        pass

# CK15: event fields are exact, including the P52-required impact/link fields.
missing_event_field = copy.deepcopy(journal)
missing_event_field["events"][0].pop("schema_impact")
unknown_event_field = copy.deepcopy(journal)
unknown_event_field["events"][0]["unexpected"] = True
for invalid in (missing_event_field, unknown_event_field):
    try:
        validate_technical_correction_journal(invalid)
        raise AssertionError("invalid event field set was accepted")
    except ValueError:
        pass

# CK16: nested closed objects and event timestamps also reject drift.
unknown_nested = copy.deepcopy(journal)
unknown_nested["events"][0]["correction"]["unexpected"] = True
bad_event_time = copy.deepcopy(journal)
bad_event_time["events"][0]["observed_at"] = "2026-09-01T00:00:00"
for invalid in (unknown_nested, bad_event_time):
    try:
        validate_technical_correction_journal(invalid)
        raise AssertionError("invalid nested correction evidence was accepted")
    except ValueError:
        pass

# CK17: pending links are accepted only while explicitly building the journal.
pending_journal = copy.deepcopy(journal)
pending_journal["events"][0]["related_commit_or_pending_commit"] = "pending_commit"
try:
    validate_technical_correction_journal(pending_journal)
    raise AssertionError("pending correction commits were accepted for closure")
except ValueError as exc:
    assert "finalized" in str(exc)
validate_technical_correction_journal(pending_journal, allow_pending_commit=True)
correction_schema = load(ROOT / "knowledge" / "v1" / "technical-correction-journal.schema.json")
assert "related_commit_or_pending_commit" in correction_schema["properties"]["events"]["items"]["properties"]
assert correction_schema["additionalProperties"] is False
assert correction_schema["properties"]["events"]["items"]["additionalProperties"] is False

# CK18: the durable P52 journal is closed, fully linked, sanitized, and zero-provider.
actual_journal = load(
    ROOT / "knowledge" / "v1" / "correction-journals" / "KU2D-CJ-000002.json"
)
validate_technical_correction_journal(actual_journal, require_closed=True)
assert actual_journal["summary"] == {
    "event_count": 6,
    "resolved_count": 6,
    "unresolved_count": 0,
    "correction_cycles_used": 6,
}
assert all(
    event["related_commit_or_pending_commit"] != "pending_commit"
    and event["provider_impact"] == {
        "provider_reached": False, "request_delta": 0, "quota_delta": 0,
    }
    for event in actual_journal["events"]
)

print("Connector Kit v1 deterministic checks passed: CK1-CK18")
