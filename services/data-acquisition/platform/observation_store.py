from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_hash(value: str | bytes | None) -> str:
    if value is None:
        value = b""
    if isinstance(value, str):
        value = value.encode("utf-8", errors="replace")
    return hashlib.sha256(value).hexdigest()


class ObservationStore:
    """Append-only evidence store for Explore, Audit and Acquire observations.

    RAW evidence may be compacted later by retention policy, while normalized
    observations remain append-only so price/promotion history is not lost.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    def _init_schema(self) -> None:
        with self.connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS acquisition_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    lifecycle_stage TEXT NOT NULL,
                    technique TEXT,
                    technique_profile_fingerprint TEXT,
                    parser_version TEXT,
                    http_status INTEGER,
                    content_type TEXT,
                    content_hash TEXT NOT NULL,
                    raw_text TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_evidence_source_time
                  ON acquisition_evidence(source_id, observed_at);

                CREATE TABLE IF NOT EXISTS acquisition_observation (
                    observation_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    lifecycle_stage TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    entity_key TEXT,
                    technique TEXT,
                    technique_profile_fingerprint TEXT,
                    validation_status TEXT NOT NULL,
                    rejection_reason TEXT,
                    confidence REAL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_observation_source_time
                  ON acquisition_observation(source_id, observed_at);
                CREATE INDEX IF NOT EXISTS idx_observation_entity_time
                  ON acquisition_observation(source_id, entity_key, observed_at);
                CREATE INDEX IF NOT EXISTS idx_observation_validation
                  ON acquisition_observation(validation_status, record_type);
                """
            )

    @staticmethod
    def _id(*parts: Any) -> str:
        raw = "|".join("" if p is None else str(p) for p in parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def add_evidence(
        self,
        *,
        source_id: str,
        source_url: str,
        lifecycle_stage: str,
        raw: str | bytes | None,
        technique: str | None = None,
        profile_fingerprint: str | None = None,
        parser_version: str | None = None,
        http_status: int | None = None,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        observed_at: str | None = None,
        keep_raw: bool = True,
    ) -> str:
        observed_at = observed_at or utcnow()
        digest = content_hash(raw)
        evidence_id = self._id("evidence", source_id, source_url, observed_at, technique, digest)
        if isinstance(raw, bytes):
            raw_text = raw.decode("utf-8", errors="replace") if keep_raw else None
        else:
            raw_text = raw if keep_raw else None
        with self.connect() as con:
            con.execute(
                """INSERT INTO acquisition_evidence(
                    evidence_id,source_id,source_url,observed_at,lifecycle_stage,
                    technique,technique_profile_fingerprint,parser_version,
                    http_status,content_type,content_hash,raw_text,metadata_json)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    evidence_id, source_id, source_url, observed_at, lifecycle_stage,
                    technique, profile_fingerprint, parser_version, http_status,
                    content_type, digest, raw_text,
                    json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
                ),
            )
        return evidence_id

    def add_observation(
        self,
        *,
        source_id: str,
        source_url: str,
        lifecycle_stage: str,
        record_type: str,
        payload: dict[str, Any],
        validation_status: str,
        entity_key: str | None = None,
        technique: str | None = None,
        profile_fingerprint: str | None = None,
        rejection_reason: str | None = None,
        confidence: float | None = None,
        observed_at: str | None = None,
    ) -> str:
        if validation_status not in {"exploratory", "accepted", "rejected", "trusted"}:
            raise ValueError(f"Unsupported validation_status: {validation_status}")
        if validation_status == "rejected" and not rejection_reason:
            raise ValueError("Rejected observations require rejection_reason")
        observed_at = observed_at or utcnow()
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = content_hash(canonical)
        observation_id = self._id(
            "observation", source_id, source_url, observed_at, record_type,
            entity_key, technique, profile_fingerprint, digest,
        )
        with self.connect() as con:
            con.execute(
                """INSERT INTO acquisition_observation(
                    observation_id,source_id,source_url,observed_at,lifecycle_stage,
                    record_type,entity_key,technique,technique_profile_fingerprint,
                    validation_status,rejection_reason,confidence,payload_json,payload_hash)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    observation_id, source_id, source_url, observed_at, lifecycle_stage,
                    record_type, entity_key, technique, profile_fingerprint,
                    validation_status, rejection_reason, confidence, canonical, digest,
                ),
            )
        return observation_id

    def add_many(self, observations: Iterable[dict[str, Any]]) -> list[str]:
        return [self.add_observation(**item) for item in observations]

    def observations(self, source_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as con:
            if source_id:
                rows = con.execute(
                    "SELECT * FROM acquisition_observation WHERE source_id=? ORDER BY observed_at",
                    (source_id,),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM acquisition_observation ORDER BY observed_at"
                ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            result.append(item)
        return result

    def latest_entity_observations(self, source_id: str) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT o.* FROM acquisition_observation o
                JOIN (
                    SELECT entity_key, MAX(observed_at) AS mx
                    FROM acquisition_observation
                    WHERE source_id=? AND entity_key IS NOT NULL
                    GROUP BY entity_key
                ) x ON o.entity_key=x.entity_key AND o.observed_at=x.mx
                WHERE o.source_id=? ORDER BY o.entity_key""",
                (source_id, source_id),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            result.append(item)
        return result
