"""Non-production marketplace observations for Commerce Market Observation.

This module is intentionally separate from Retail Product & Price acquisition.
Marketplace counters and ranks are public-surface observations, not transaction
ledger facts and not production approval.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


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

    def __post_init__(self) -> None:
        if self.sold_count_precision not in SOLD_PRECISIONS:
            raise ValueError(f"Unsupported sold-count precision: {self.sold_count_precision}")
        if not self.platform or not self.platform_product_id:
            raise ValueError("Marketplace observations require platform and stable product identity.")


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

    def __post_init__(self) -> None:
        required = (self.platform, self.surface_type, self.source_surface,
                    self.category_or_query, self.sort_mode, self.product_id, self.observed_at)
        if not all(str(value).strip() for value in required):
            raise ValueError("Ranking observations require surface, query/category, sort mode, time, and identity.")
        if int(self.observed_rank) < 1:
            raise ValueError("observed_rank must be positive.")


@dataclass(frozen=True)
class SalesCounterObservation:
    platform: str
    product_id: str
    observed_sold_count: int | None
    raw_display: str
    observed_at: str
    precision: str
    provenance: dict[str, Any]

    def __post_init__(self) -> None:
        if self.precision not in SOLD_PRECISIONS:
            raise ValueError(f"Unsupported sold-count precision: {self.precision}")
        if not self.platform or not self.product_id:
            raise ValueError("Sales counters require platform and product_id.")


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
    velocity_signal: float | None
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
    cumulative_signal: float | int | None, velocity_signal: float | None,
    rank_strength: float = 0.0, rank_improvement: float = 0.0,
    review_growth: float = 0.0, repeated_surface_presence: float = 0.0,
    weights: dict[str, float] | None = None,
) -> TrendingProductCandidate:
    """Build a review candidate with provisional, transparent scoring inputs."""
    components = {
        "normalized_sales_velocity": float(velocity_signal or 0.0),
        "rank_strength": float(rank_strength),
        "rank_improvement": float(rank_improvement),
        "review_growth": float(review_growth),
        "repeated_surface_presence": float(repeated_surface_presence),
    }
    if any(value < 0.0 or value > 1.0 for value in components.values()):
        raise ValueError("Trend scoring components must be normalized between 0 and 1.")
    selected_weights = dict(weights or PROVISIONAL_TREND_WEIGHTS)
    if set(selected_weights) != set(components) or sum(selected_weights.values()) <= 0:
        raise ValueError("Trend weights must cover every scoring component.")
    total = sum(selected_weights.values())
    score = sum(components[key] * selected_weights[key] for key in components) / total
    direction = "rising" if score >= 0.65 else ("watch" if score >= 0.35 else "weak-or-insufficient")
    return TrendingProductCandidate(
        platform=platform, product_id=product_id, cumulative_signal=cumulative_signal,
        velocity_signal=velocity_signal, ranking_signal=rank_strength,
        review_growth_signal=review_growth, trend_score=round(score, 4),
        trend_direction=direction, observed_at=observed_at, human_review_status="pending",
        scoring_version=TREND_SCORING_VERSION, component_values=components,
        scoring_weights=selected_weights, weights_authoritative=False,
        raw_signals={"cumulative_sold_count": cumulative_signal,
                     "estimated_units_per_hour": velocity_signal},
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
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS commerce_observation (
                    observation_id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    production_approved INTEGER NOT NULL CHECK(production_approved = 0),
                    UNIQUE(record_type, platform, product_id, observed_at)
                );
                CREATE INDEX IF NOT EXISTS idx_commerce_product_time
                  ON commerce_observation(platform, product_id, observed_at);
                """
            )

    def append(self, record_type: str, observation: Any) -> dict[str, Any]:
        payload = _payload(observation)
        platform = str(payload.get("platform") or "").strip()
        product_id = str(payload.get("platform_product_id") or payload.get("product_id") or "").strip()
        observed_at = str(payload.get("observed_at") or "").strip()
        if not platform or not product_id or not observed_at:
            raise ValueError("Stored observations require platform, product identity, and observed_at.")
        if payload.get("production_approved") not in {None, False}:
            raise ValueError("Production-approved commerce observations are not supported.")
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        key = f"{record_type}|{platform}|{product_id}|{observed_at}"
        observation_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        with closing(self.connect()) as connection, connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO commerce_observation(
                       observation_id,record_type,platform,product_id,observed_at,
                       payload_json,production_approved)
                   VALUES(?,?,?,?,?,?,0)""",
                (observation_id, record_type, platform, product_id, observed_at, canonical),
            )
        return {"observation_id": observation_id, "inserted": cursor.rowcount == 1}

    def observations(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection, connection:
            rows = connection.execute(
                "SELECT * FROM commerce_observation ORDER BY observed_at, observation_id"
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]
