"""Non-production marketplace observations for Commerce Market Observation.

This module is intentionally separate from Retail Product & Price acquisition.
Marketplace counters and ranks are public-surface observations, not transaction
ledger facts and not production approval.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
SOLD_PRECISIONS = {"exact", "rounded", "lower_bound", "unknown"}
TREND_SCORING_VERSION = "commerce-pulse-provisional-v1"
PROVISIONAL_TREND_WEIGHTS = {
    "normalized_sales_velocity": 0.30,
    "rank_strength": 0.25,
    "rank_improvement": 0.15,
    "review_growth": 0.10,
    "repeated_surface_presence": 0.20,
}


def _normalized_text(value: Any, *, casefold: bool = False) -> str:
    normalized = " ".join(str(value or "").strip().split())
    return normalized.casefold() if casefold else normalized


def _normalized_surface(value: Any) -> str:
    surface = _normalized_text(value)
    parsed = urlsplit(surface)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return surface
    host = parsed.hostname.casefold()
    if parsed.port:
        host = f"{host}:{parsed.port}"
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return urlunsplit((parsed.scheme.casefold(), host, parsed.path or "/", query, ""))


def _scope_json(scope_type: str, **context: Any) -> str:
    normalized = {"scope_type": scope_type}
    for key, value in context.items():
        if key == "source_surface":
            normalized[key] = _normalized_surface(value)
        else:
            normalized[key] = _normalized_text(value, casefold=True)
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class CommerceProductObservation:
    platform: str
    platform_product_id: str
    seller_id: str | None
    shop_id: str | None
    title: str | None
    brand: str | None
    category: str | None
    current_price: float | None
    original_price: float | None
    discount_pct: float | None
    rating: float | None
    review_count: int | None
    observed_sold_count: int | None
    sold_count_display: str | None
    sold_count_precision: str
    source_surface: str
    source_rank: int | None
    source_query: str | None
    observed_at: str
    provenance: dict[str, Any]
    publicly_observable: bool
    production_approved: bool = field(default=False, init=False)
    observation_scope: str = field(init=False)

    def __post_init__(self) -> None:
        if self.sold_count_precision not in SOLD_PRECISIONS:
            raise ValueError(f"Unsupported sold-count precision: {self.sold_count_precision}")
        if not self.platform or not self.platform_product_id:
            raise ValueError("Marketplace observations require platform and stable product identity.")
        object.__setattr__(self, "observation_scope", _scope_json(
            "product", source_surface=self.source_surface, source_query=self.source_query,
        ))


@dataclass(frozen=True)
class MarketplaceRankingObservation:
    platform: str
    surface_type: str
    source_surface: str
    category_or_query: str
    sort_mode: str
    product_id: str
    observed_rank: int
    observed_at: str
    provenance: dict[str, Any]
    observation_scope: str = field(init=False)

    def __post_init__(self) -> None:
        required = (self.platform, self.surface_type, self.source_surface,
                    self.category_or_query, self.sort_mode, self.product_id, self.observed_at)
        if not all(str(value).strip() for value in required):
            raise ValueError("Ranking observations require surface, query/category, sort mode, time, and identity.")
        if int(self.observed_rank) < 1:
            raise ValueError("observed_rank must be positive.")
        object.__setattr__(self, "observation_scope", _scope_json(
            "ranking", source_surface=self.source_surface, surface_type=self.surface_type,
            category_or_query=self.category_or_query, sort_mode=self.sort_mode,
        ))


@dataclass(frozen=True)
class SalesCounterObservation:
    platform: str
    product_id: str
    observed_sold_count: int | None
    raw_display: str
    observed_at: str
    precision: str
    source_surface: str
    provenance: dict[str, Any]
    observation_scope: str = field(init=False)

    def __post_init__(self) -> None:
        if self.precision not in SOLD_PRECISIONS:
            raise ValueError(f"Unsupported sold-count precision: {self.precision}")
        if not self.platform or not self.product_id:
            raise ValueError("Sales counters require platform and product_id.")
        if not _normalized_text(self.source_surface):
            raise ValueError("Sales counters require source_surface context.")
        provenance_context = {
            key: self.provenance.get(key)
            for key in ("surface_type", "category_or_query", "sort_mode", "source_query")
            if self.provenance.get(key) is not None
        }
        object.__setattr__(self, "observation_scope", _scope_json(
            "sales-counter", source_surface=self.source_surface, **provenance_context,
        ))


@dataclass(frozen=True)
class SalesVelocityEstimate:
    platform: str
    product_id: str
    prior_observed_at: str
    current_observed_at: str
    prior_sold_count: int | None
    current_sold_count: int | None
    sold_delta: int | None
    elapsed_hours: float
    estimated_units_per_hour: float | None
    confidence: str
    estimate_basis: str
    is_transaction_ledger: bool = field(default=False, init=False)


@dataclass(frozen=True)
class TrendingProductCandidate:
    platform: str
    product_id: str
    cumulative_signal: float | int | None
    raw_velocity_signal: float | None
    normalized_velocity_signal: float
    ranking_signal: float | None
    review_growth_signal: float | None
    trend_score: float
    trend_direction: str
    observed_at: str
    human_review_status: str
    scoring_version: str
    component_values: dict[str, float]
    scoring_weights: dict[str, float]
    weights_authoritative: bool
    raw_signals: dict[str, Any]
    production_approved: bool = field(default=False, init=False)


class CounterDiscontinuityError(ValueError):
    """A counter moved backwards and cannot support an automatic estimate."""


_SOLD_RE = re.compile(
    r"(?P<number>\d+(?:\.\d+)?)\s*"
    r"(?P<suffix>thousand|million|k|m|พัน|หมื่น|แสน|ล้าน)?\s*"
    r"(?P<plus>\+)?",
    re.IGNORECASE,
)
_MULTIPLIERS = {
    "": Decimal(1),
    "k": Decimal(1_000),
    "thousand": Decimal(1_000),
    "m": Decimal(1_000_000),
    "million": Decimal(1_000_000),
    "พัน": Decimal(1_000),
    "หมื่น": Decimal(10_000),
    "แสน": Decimal(100_000),
    "ล้าน": Decimal(1_000_000),
}


def parse_sold_count(display: str | None) -> dict[str, Any]:
    """Parse a public sold-count display while preserving its uncertainty."""
    raw = "" if display is None else str(display).strip()
    text = raw.casefold().replace(",", "").replace("\u00a0", " ")
    match = _SOLD_RE.search(text)
    if not match:
        return {"observed_sold_count": None, "raw_display": raw, "precision": "unknown"}
    number_text = match.group("number")
    suffix = (match.group("suffix") or "").casefold()
    plus = bool(match.group("plus"))
    try:
        number = Decimal(number_text)
        scaled = number * _MULTIPLIERS[suffix]
    except (InvalidOperation, KeyError):
        return {"observed_sold_count": None, "raw_display": raw, "precision": "unknown"}
    if scaled < 0 or scaled != scaled.to_integral_value():
        return {"observed_sold_count": None, "raw_display": raw, "precision": "unknown"}
    precision = "lower_bound" if plus else ("rounded" if suffix else "exact")
    return {"observed_sold_count": int(scaled), "raw_display": raw, "precision": precision}


def _instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Observation timestamps must include a timezone.")
    return parsed.astimezone(timezone.utc)


def estimate_sales_velocity(
    prior: SalesCounterObservation,
    current: SalesCounterObservation,
) -> SalesVelocityEstimate:
    """Estimate counter movement only where two exact observations support it."""
    if prior.platform != current.platform or prior.product_id != current.product_id:
        raise ValueError("Velocity requires the same platform and product_id.")
    earlier, later = _instant(prior.observed_at), _instant(current.observed_at)
    elapsed = (later - earlier).total_seconds() / 3600.0
    if elapsed <= 0:
        raise ValueError("Velocity requires a later current observation.")
    if prior.precision != "exact" or current.precision != "exact":
        return SalesVelocityEstimate(
            platform=prior.platform, product_id=prior.product_id,
            prior_observed_at=prior.observed_at, current_observed_at=current.observed_at,
            prior_sold_count=prior.observed_sold_count, current_sold_count=current.observed_sold_count,
            sold_delta=None, elapsed_hours=round(elapsed, 6), estimated_units_per_hour=None,
            confidence="indeterminate",
            estimate_basis="rounded-or-lower-bound counters cannot support a precise delta",
        )
    if prior.observed_sold_count is None or current.observed_sold_count is None:
        return SalesVelocityEstimate(
            platform=prior.platform, product_id=prior.product_id,
            prior_observed_at=prior.observed_at, current_observed_at=current.observed_at,
            prior_sold_count=prior.observed_sold_count, current_sold_count=current.observed_sold_count,
            sold_delta=None, elapsed_hours=round(elapsed, 6), estimated_units_per_hour=None,
            confidence="indeterminate", estimate_basis="missing sold-counter value",
        )
    delta = current.observed_sold_count - prior.observed_sold_count
    if delta < 0:
        raise CounterDiscontinuityError(
            "Sold counter decreased; possible reset, variant merge, listing change, or unreliable observation."
        )
    return SalesVelocityEstimate(
        platform=prior.platform, product_id=prior.product_id,
        prior_observed_at=prior.observed_at, current_observed_at=current.observed_at,
        prior_sold_count=prior.observed_sold_count, current_sold_count=current.observed_sold_count,
        sold_delta=delta, elapsed_hours=round(elapsed, 6),
        estimated_units_per_hour=round(delta / elapsed, 2), confidence="high",
        estimate_basis="difference between two exact public sold-counter observations",
    )


def build_trending_candidate(
    *, platform: str, product_id: str, observed_at: str,
    cumulative_signal: float | int | None,
    raw_estimated_units_per_hour: float | None,
    normalized_sales_velocity: float,
    rank_strength: float = 0.0, rank_improvement: float = 0.0,
    review_growth: float = 0.0, repeated_surface_presence: float = 0.0,
    weights: dict[str, float] | None = None,
) -> TrendingProductCandidate:
    """Build a review candidate with provisional, transparent scoring inputs."""
    normalized_velocity = float(normalized_sales_velocity)
    if not math.isfinite(normalized_velocity) or not 0.0 <= normalized_velocity <= 1.0:
        raise ValueError("normalized_sales_velocity must be finite and between 0 and 1.")
    raw_velocity = None if raw_estimated_units_per_hour is None else float(raw_estimated_units_per_hour)
    if raw_velocity is not None and (not math.isfinite(raw_velocity) or raw_velocity < 0.0):
        raise ValueError("raw_estimated_units_per_hour must be a non-negative finite value or None.")
    components = {
        "normalized_sales_velocity": normalized_velocity,
        "rank_strength": float(rank_strength),
        "rank_improvement": float(rank_improvement),
        "review_growth": float(review_growth),
        "repeated_surface_presence": float(repeated_surface_presence),
    }
    if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in components.values()):
        raise ValueError("Trend scoring components must be finite and normalized between 0 and 1.")
    selected_weights = dict(weights or PROVISIONAL_TREND_WEIGHTS)
    if (set(selected_weights) != set(components)
            or any(not math.isfinite(value) or value < 0.0 for value in selected_weights.values())
            or sum(selected_weights.values()) <= 0):
        raise ValueError("Trend weights must cover every scoring component.")
    total = sum(selected_weights.values())
    score = sum(components[key] * selected_weights[key] for key in components) / total
    direction = "rising" if score >= 0.65 else ("watch" if score >= 0.35 else "weak-or-insufficient")
    return TrendingProductCandidate(
        platform=platform, product_id=product_id, cumulative_signal=cumulative_signal,
        raw_velocity_signal=raw_velocity, normalized_velocity_signal=normalized_velocity,
        ranking_signal=rank_strength,
        review_growth_signal=review_growth, trend_score=round(score, 4),
        trend_direction=direction, observed_at=observed_at, human_review_status="pending",
        scoring_version=TREND_SCORING_VERSION, component_values=components,
        scoring_weights=selected_weights, weights_authoritative=False,
        raw_signals={"cumulative_sold_count": cumulative_signal,
                     "estimated_units_per_hour": raw_velocity},
    )


def observable_signal_label(signal: str, *, explicit_national_surface: bool = False) -> str:
    labels = {
        "cumulative": "Highest Observable Sold Count",
        "velocity": "Fastest Rising",
        "ranking": "Strongest Marketplace Rank",
        "trend": "Cross-observation Trending",
    }
    if signal not in labels:
        raise ValueError(f"Unsupported marketplace signal: {signal}")
    # A generic surface never earns a national claim. Even an explicit platform
    # national surface must retain its own platform/context provenance elsewhere.
    del explicit_national_surface
    return labels[signal]


def _payload(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        value = asdict(value)
    if not isinstance(value, dict):
        raise TypeError("Commerce observations must be dataclasses or JSON objects.")
    return value


def observation_scope(record_type: str, observation: Any) -> str:
    """Return stable surface identity without hashing volatile observation fields."""
    payload = _payload(observation)
    if all(payload.get(key) is not None for key in (
        "source_surface", "surface_type", "category_or_query", "sort_mode",
    )):
        return _scope_json(
            "ranking", source_surface=payload["source_surface"],
            surface_type=payload["surface_type"],
            category_or_query=payload["category_or_query"], sort_mode=payload["sort_mode"],
        )
    if payload.get("platform_product_id") is not None:
        return _scope_json(
            "product", source_surface=payload.get("source_surface"),
            source_query=payload.get("source_query"),
        )
    if payload.get("raw_display") is not None or payload.get("precision") is not None:
        provenance = payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {}
        context = {
            key: provenance.get(key)
            for key in ("surface_type", "category_or_query", "sort_mode", "source_query")
            if provenance.get(key) is not None
        }
        surface = payload.get("source_surface") or provenance.get("source_surface") or provenance.get("source_url") or provenance.get("surface")
        return _scope_json("sales-counter", source_surface=surface, **context)
    return _scope_json(
        _normalized_text(record_type, casefold=True) or "observation",
        source_surface=payload.get("source_surface"), source_query=payload.get("source_query"),
    )


def default_commerce_observation_path(environ: dict[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    configured = str(env.get("KU2D_COMMERCE_OBSERVATION_DB") or "").strip()
    if not configured:
        raise ValueError("KU2D_COMMERCE_OBSERVATION_DB is required for isolated experimental storage.")
    return Path(configured)


class CommerceObservationStore:
    """Append-only, isolated, non-production store for marketplace experiments."""

    production_store_enabled = False

    def __init__(self, path: str | Path | None = None, *, environ: dict[str, str] | None = None):
        env = os.environ if environ is None else environ
        self.path = Path(path) if path is not None else default_commerce_observation_path(env)
        operations = str(env.get("KU2D_OPERATIONS_DB") or "").strip()
        if operations and self.path.resolve(strict=False) == Path(operations).resolve(strict=False):
            raise ValueError("Commerce observation DB must be separate from the operations DB.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with closing(self.connect()) as connection, connection:
            existing_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(commerce_observation)").fetchall()
            }
            legacy_table = None
            if existing_columns and "observation_scope" not in existing_columns:
                suffix = 1
                legacy_table = "commerce_observation_legacy_v1"
                existing_tables = {
                    row["name"] for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                while legacy_table in existing_tables:
                    suffix += 1
                    legacy_table = f"commerce_observation_legacy_v1_{suffix}"
                connection.execute(f"ALTER TABLE commerce_observation RENAME TO {legacy_table}")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS commerce_observation (
                    observation_id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    observation_scope TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    production_approved INTEGER NOT NULL CHECK(production_approved = 0),
                    UNIQUE(record_type, platform, product_id, observed_at, observation_scope)
                );
                CREATE INDEX IF NOT EXISTS idx_commerce_product_scope_time
                  ON commerce_observation(platform, product_id, observation_scope, observed_at);
                """
            )
            if legacy_table:
                rows = connection.execute(f"SELECT * FROM {legacy_table}").fetchall()
                for row in rows:
                    payload = json.loads(row["payload_json"])
                    scope = observation_scope(row["record_type"], payload)
                    payload["observation_scope"] = scope
                    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    key = "|".join((row["record_type"], row["platform"], row["product_id"], row["observed_at"], scope))
                    migrated_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
                    connection.execute(
                        """INSERT OR IGNORE INTO commerce_observation(
                               observation_id,record_type,platform,product_id,observed_at,
                               observation_scope,payload_json,production_approved)
                           VALUES(?,?,?,?,?,?,?,0)""",
                        (migrated_id, row["record_type"], row["platform"], row["product_id"],
                         row["observed_at"], scope, canonical),
                    )

    def append(self, record_type: str, observation: Any) -> dict[str, Any]:
        payload = dict(_payload(observation))
        platform = str(payload.get("platform") or "").strip()
        product_id = str(payload.get("platform_product_id") or payload.get("product_id") or "").strip()
        observed_at = str(payload.get("observed_at") or "").strip()
        if not platform or not product_id or not observed_at:
            raise ValueError("Stored observations require platform, product identity, and observed_at.")
        if payload.get("production_approved") not in {None, False}:
            raise ValueError("Production-approved commerce observations are not supported.")
        scope = observation_scope(record_type, payload)
        payload["observation_scope"] = scope
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        key = f"{record_type}|{platform}|{product_id}|{observed_at}|{scope}"
        observation_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        with closing(self.connect()) as connection, connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO commerce_observation(
                       observation_id,record_type,platform,product_id,observed_at,
                       observation_scope,payload_json,production_approved)
                   VALUES(?,?,?,?,?,?,?,0)""",
                (observation_id, record_type, platform, product_id, observed_at, scope, canonical),
            )
        return {"observation_id": observation_id, "observation_scope": scope,
                "inserted": cursor.rowcount == 1}

    def observations(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection, connection:
            rows = connection.execute(
                "SELECT * FROM commerce_observation ORDER BY observed_at, observation_id"
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]
