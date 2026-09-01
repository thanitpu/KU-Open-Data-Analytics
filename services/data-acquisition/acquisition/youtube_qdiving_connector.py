"""YouTube Q-Diving reference adapter/parser/mapper for Connector Kit v1."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from connector_kit import ConnectorFailure, ErrorClass, RequestPlan, ResponseEnvelope


ROOT = Path(__file__).resolve().parents[1]
PACKET_PATH = (
    ROOT / "knowledge" / "v1" / "candidate-closure-packets" /
    "KU2D-YT-QDIVING-CANDIDATES-000001.json"
)


class YouTubeQDivingAdapter:
    """Declare fixture access; execution mechanics remain in ConnectorKit."""

    source_id = "youtube-data-api-v3-q-diving"
    parser_id = "youtube-qdiving-sanitized-candidate-parser.v1"
    domain_profile_id = "public-video-q-diving.v1"
    mapper_id = "public-video-q-diving-mapper.v1"

    def capability_declarations(self) -> list[dict[str, str]]:
        return [
            {"capability_id": "video_metadata", "state": "available"},
            {"capability_id": "channel_identity", "state": "available"},
            {"capability_id": "comments", "state": "blocked"},
            {"capability_id": "captions", "state": "blocked"},
            {"capability_id": "transcripts", "state": "blocked"},
        ]

    def build_request(self, capability_id: str) -> RequestPlan:
        if capability_id not in {"video_metadata", "channel_identity"}:
            raise ConnectorFailure("capability is outside the YouTube v1 MTC fixture", ErrorClass.POLICY)
        return RequestPlan(
            request_id=f"youtube-qdiving-p50-{capability_id}",
            capability_id=capability_id,
            operation="fixture.replay",
            parameters={"fixture_id": "KU2D-YT-QDIVING-CANDIDATES-000001"},
            timeout_seconds=5,
            max_attempts=1,
            quota_cost_per_attempt=0,
            credential_environment_key=None,
            pagination={"mode": "immutable_packet", "page_limit": 1},
        )


class YouTubeQDivingCandidateParser:
    """Parse the sanitized P50 closure packet into source-specific records."""

    parser_id = YouTubeQDivingAdapter.parser_id

    def parse(self, envelope: ResponseEnvelope) -> list[dict[str, Any]]:
        payload = envelope.payload
        if not isinstance(payload, dict) or payload.get("schema") != "ku2d.youtube-qdiving-human-review-package.v1":
            raise ConnectorFailure("unexpected YouTube candidate fixture schema", ErrorClass.SCHEMA)
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or payload.get("candidate_count") != len(candidates):
            raise ConnectorFailure("YouTube candidate count is inconsistent", ErrorClass.SCHEMA)
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                raise ConnectorFailure("YouTube candidate must be an object", ErrorClass.PARSER)
            video_id = str(candidate.get("video_id") or "").strip()
            channel_id = str(candidate.get("channel_id") or "").strip()
            if not video_id or not channel_id or video_id in seen:
                raise ConnectorFailure("YouTube candidate identity is missing or duplicated", ErrorClass.PARSER)
            seen.add(video_id)
            output.append({
                "source_record_type": "youtube_qdiving_public_video_candidate.v1",
                "source_packet_index": index,
                **candidate,
                "fixture_provenance": envelope.provenance,
            })
        return output


class PublicVideoQDivingMapper:
    """Map source records while leaving semantic decisions to Analysis."""

    mapper_id = YouTubeQDivingAdapter.mapper_id

    def map_record(self, source_record: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": "ku2d.public-video-q-diving-record.v1",
            "record_id": source_record["video_id"],
            "video_metadata": {
                "canonical_watch_url": source_record["canonical_watch_url"],
                "title": source_record.get("title"),
                "published_at": source_record.get("published_at"),
                "default_language": source_record.get("default_language"),
                "default_audio_language": source_record.get("default_audio_language"),
                "public_availability_state": source_record.get("public_availability_state"),
            },
            "channel_identity": {
                "channel_id": source_record["channel_id"],
                "channel_title": source_record.get("channel_title"),
            },
            "provenance": {
                "source_packet_id": "KU2D-YT-QDIVING-CANDIDATES-000001",
                "source_packet_index": source_record["source_packet_index"],
                "query_profile_ids": list(source_record.get("query_profile_ids") or []),
                "profile_query_provenance": list(source_record.get("profile_query_provenance") or []),
                "observed_at": source_record.get("observed_at"),
                "fixture": source_record["fixture_provenance"],
            },
            "analysis": {
                "semantic_relevance": None,
                "quality": None,
                "analytical_rank": None,
                "analytical_deduplication": None,
                "final_inclusion": None,
            },
            "acquisition_acceptance": "accepted_for_analysis",
            "production_ready": False,
        }
