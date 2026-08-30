"""Deep Audit logic for bounded Lazada Thailand rendered-DOM evidence."""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

from commerce_market_observation import CommerceProductObservation, MarketplaceRankingObservation, parse_sold_count
from lazada_browser_access import analyze_capture, stable_product_identity, utcnow
from shopee_edge_access import sanitize_url


SCHEMA = "ku2d.lazada-rendered-dom-deep-audit.v1"
PLATFORM = "lazada-thailand"
_CURRENCY_RE = re.compile(r"(?:฿|THB\s*)(?P<amount>\d[\d,]*(?:\.\d+)?)", re.IGNORECASE)
_RANGE_RE = re.compile(
    r"(?:฿|THB\s*)(?P<minimum>\d[\d,]*(?:\.\d+)?)\s*(?:-|–|—|to|ถึง)\s*"
    r"(?:฿|THB\s*)?(?P<maximum>\d[\d,]*(?:\.\d+)?)",
    re.IGNORECASE,
)


def _normalized(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _amount(value: Any) -> float | None:
    match = _CURRENCY_RE.search(_normalized(value))
    return float(match.group("amount").replace(",", "")) if match else None


def price_evidence(row: dict[str, Any]) -> dict[str, Any]:
    visible = _normalized(row.get("visible_text"))
    current_raw = _normalized(row.get("current_price_text") or row.get("visible_price_text")) or None
    if current_raw is None:
        match = _CURRENCY_RE.search(visible)
        current_raw = match.group(0) if match else None
    original_raw = _normalized(row.get("original_price_text")) or None
    range_raw = _normalized(row.get("variation_price_text")) or None
    range_match = _RANGE_RE.search(range_raw or "")
    return {
        "current_price_raw": current_raw,
        "current_price": _amount(current_raw),
        "current_price_semantics": "explicit-currency-display" if _amount(current_raw) is not None else "not-observed",
        "original_price_raw": original_raw,
        "original_price": _amount(original_raw),
        "original_price_semantics": "explicit-strikethrough-or-labeled-original" if _amount(original_raw) is not None else "not-observed",
        "variation_range_raw": range_raw,
        "variation_min_price": float(range_match.group("minimum").replace(",", "")) if range_match else None,
        "variation_max_price": float(range_match.group("maximum").replace(",", "")) if range_match else None,
        "hidden_numeric_scaling_inferred": False,
    }


def counter_evidence(row: dict[str, Any]) -> dict[str, Any]:
    visible = _normalized(row.get("visible_text"))
    raw = _normalized(row.get("counter_text") or row.get("visible_sold_or_order_text")) or None
    if raw is None:
        match = re.search(
            r"(?:ขายแล้ว\s*[\d.,]+\s*(?:k|m|พัน|หมื่น|แสน|ล้าน|ชิ้น)?\+?|"
            r"[\d.,]+\s*(?:k|m|thousand|million)?\+?\s*sold|"
            r"(?:คำสั่งซื้อ|ออเดอร์|orders?)\s*[: ]?\s*[\d,.]+|"
            r"[\d,.]+\s*orders?|[\d,.]+\s*(?:k|m|พัน|หมื่น|แสน|ล้าน)?\s*ชิ้น)",
            visible, re.IGNORECASE,
        )
        raw = match.group(0) if match else None
    lowered = _normalized(raw).casefold()
    if re.search(r"(?:ขายแล้ว|\bsold\b)", lowered, re.IGNORECASE):
        counter_type, confidence = "sold", "explicit-label"
    elif re.search(r"(?:คำสั่งซื้อ|ออเดอร์|\border(?:s|ed)?\b)", lowered, re.IGNORECASE):
        counter_type, confidence = "orders", "explicit-label"
    elif raw:
        counter_type, confidence = "unknown", "unlabeled-display"
    else:
        counter_type, confidence = "unknown", "not-observed"
    parsed = parse_sold_count(raw)
    return {
        "counter_type": counter_type,
        "raw_display": raw,
        "numeric_parse": parsed["observed_sold_count"],
        "precision": parsed["precision"],
        "semantic_confidence": confidence,
        "observed_sold_count": parsed["observed_sold_count"] if counter_type == "sold" else None,
        "eligible_for_sales_velocity": counter_type == "sold" and parsed["precision"] == "exact",
        "is_transaction_ledger": False,
    }


def rating_review_evidence(row: dict[str, Any]) -> dict[str, Any]:
    visible = _normalized(row.get("visible_text"))
    rating_raw = _normalized(row.get("rating_score_text")) or None
    rating_count_raw = _normalized(row.get("rating_count_text")) or None
    review_raw = _normalized(row.get("review_count_text") or row.get("visible_rating_or_review_text")) or None
    unlabeled = _normalized(row.get("unlabeled_parenthetical_count_text")) or None
    if unlabeled is None:
        match = re.search(r"\([\d,]+\)", visible)
        unlabeled = match.group(0) if match else None

    def labeled_number(value: str | None, labels: tuple[str, ...]) -> float | None:
        if not value or not any(label in value.casefold() for label in labels):
            return None
        match = re.search(r"\d+(?:\.\d+)?", value.replace(",", ""))
        return float(match.group(0)) if match else None

    review_number = labeled_number(review_raw, ("review", "รีวิว"))
    rating_count = labeled_number(rating_count_raw, ("rating", "คะแนน"))
    return {
        "rating_score_raw": rating_raw,
        "rating_score": labeled_number(rating_raw, ("rating", "คะแนน", "ดาว")),
        "rating_count_raw": rating_count_raw,
        "rating_count": int(rating_count) if rating_count is not None else None,
        "review_count_raw": review_raw,
        "review_count": int(review_number) if review_number is not None else None,
        "unlabeled_parenthetical_count_raw": unlabeled,
        "unlabeled_parenthetical_count_classification": "unknown-not-review" if unlabeled else "not-observed",
    }


def _record(
    row: dict[str, Any], *, capture: dict[str, Any], context: dict[str, Any],
    position: int, observed_at: str,
) -> dict[str, Any] | None:
    final_url = sanitize_url(capture.get("final_url") or capture.get("initial_url"))
    identity = stable_product_identity(
        row.get("product_url"), explicit_id=row.get("explicit_product_id"),
        base_url=final_url or "https://www.lazada.co.th/",
    )
    if not identity:
        return None
    price = price_evidence(row)
    counter = counter_evidence(row)
    ratings = rating_review_evidence(row)
    explicit_rank = bool(context.get("sort_semantics_explicit")) and str(context.get("sort_mode") or "").casefold() in {
        "bestseller", "top-sales", "popular-explicit",
    }
    title = _normalized(row.get("visible_title")) or None
    query_category = _normalized(context.get("query_or_category")) or None
    observation = CommerceProductObservation(
        platform=PLATFORM, platform_product_id=identity["platform_product_id"],
        seller_id=str(row.get("seller_id") or "") or None,
        shop_id=str(row.get("shop_id") or "") or None,
        title=title, brand=str(row.get("brand") or "") or None,
        category=str(row.get("category") or "") or None,
        current_price=price["current_price"], original_price=price["original_price"],
        discount_pct=None, rating=ratings["rating_score"], review_count=ratings["review_count"],
        observed_sold_count=counter["observed_sold_count"],
        sold_count_display=counter["raw_display"] if counter["counter_type"] == "sold" else None,
        sold_count_precision=counter["precision"], source_surface=final_url or "",
        source_rank=position if explicit_rank else None, source_query=query_category,
        observed_at=observed_at,
        provenance={
            "surface_type": context.get("surface_type"), "sort_mode": context.get("sort_mode"),
            "observed_display_position": position, "rank_semantics_explicit": explicit_rank,
            "counter_semantics": counter, "price_semantics": price,
        }, publicly_observable=True,
    )
    ranking = None
    if explicit_rank:
        ranking = asdict(MarketplaceRankingObservation(
            platform=PLATFORM, surface_type=str(context["surface_type"]),
            source_surface=final_url or "", category_or_query=query_category or "explicit-surface",
            sort_mode=str(context["sort_mode"]), product_id=identity["platform_product_id"],
            observed_rank=position, observed_at=observed_at,
            provenance={"rendered_dom": True, "national_rank": False},
        ))
    missing = []
    for key, value in {
        "title": title, "current_price": price["current_price"],
        "rating_score": ratings["rating_score"], "review_count": ratings["review_count"],
        "counter_display": counter["raw_display"], "shop_identity": row.get("shop_id") or row.get("seller_id"),
    }.items():
        if value is None:
            missing.append(key)
    return {
        "platform": PLATFORM, "platform_product_id": identity["platform_product_id"],
        "canonical_product_url": identity["product_url"], "identity_basis": identity["identity_basis"],
        "surface_type": context.get("surface_type"), "source_surface": final_url,
        "query_or_category": query_category, "sort_mode": context.get("sort_mode"),
        "observed_display_position": position,
        "marketplace_ranking_observation": ranking,
        "title": title, "price": price, "rating_review": ratings, "counter": counter,
        "shop_id": str(row.get("shop_id") or "") or None,
        "seller_id": str(row.get("seller_id") or "") or None,
        "observed_at": observed_at, "observation_scope": observation.observation_scope,
        "missing_fields": missing, "production_approved": False,
    }


def audit_surface(entry: dict[str, Any], max_items: int = 10) -> dict[str, Any]:
    if max_items < 1 or max_items > 10:
        raise ValueError("Deep Audit max_items must be between 1 and 10.")
    capture = entry.get("capture") or {}
    context = entry.get("context") or {}
    observed_at = str(capture.get("observed_at") or utcnow())
    browser = analyze_capture(
        capture, target_url=str(capture.get("initial_url") or "https://www.lazada.co.th/"),
        query=str(context.get("query_or_category") or "") or None, max_items=max_items,
    )
    records = []
    for position, row in enumerate(list(capture.get("visible_cards") or [])[:max_items], start=1):
        normalized = _record(row, capture=capture, context=context, position=position, observed_at=observed_at)
        if normalized:
            records.append(normalized)
    fields = ("title", "current_price", "rating_score", "review_count", "counter_display", "shop_identity")
    coverage = {
        field: round(100.0 * sum(field not in row["missing_fields"] for row in records) / len(records), 2)
        if records else 0.0
        for field in fields
    }
    sampled_card_count = min(len(list(capture.get("visible_cards") or [])), max_items)
    return {
        "surface_type": context.get("surface_type"),
        "audit_source": context.get("audit_source"),
        "source_surface": sanitize_url(capture.get("final_url") or capture.get("initial_url")),
        "query_or_category": context.get("query_or_category"), "sort_mode": context.get("sort_mode"),
        "sort_semantics_explicit": bool(context.get("sort_semantics_explicit")),
        "technical_completion": browser["technical_completion"],
        "challenge_status": browser["challenge_status"],
        "visible_product_card_count": browser["visible_product_card_count"],
        "retained_product_count": len(records), "records": records,
        "field_coverage_pct": coverage,
        "stable_identity_pct": round(100.0 * len(records) / max(1, sampled_card_count), 2),
        "production_approved": False,
    }


def correlate_search_detail(search: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    same_identity = search["platform_product_id"] == detail["platform_product_id"]
    search_title = _normalized(search.get("title")).casefold()
    detail_title = _normalized(detail.get("title")).casefold()
    title_consistent = bool(search_title and detail_title and (search_title == detail_title or search_title in detail_title or detail_title in search_title))
    search_price = search["price"].get("current_price")
    detail_price = detail["price"].get("current_price")
    minimum = detail["price"].get("variation_min_price")
    maximum = detail["price"].get("variation_max_price")
    price_consistent = search_price is not None and (
        search_price == detail_price or (minimum is not None and maximum is not None and minimum <= search_price <= maximum)
    )
    return {
        "same_item_identity": same_identity,
        "platform_product_id": search["platform_product_id"] if same_identity else None,
        "title_consistent": title_consistent,
        "price_consistent_or_within_detail_range": price_consistent,
        "search_price": search_price, "detail_price": detail_price,
        "detail_variation_range": [minimum, maximum] if minimum is not None and maximum is not None else None,
        "rating_review_comparable": bool(search["rating_review"].get("review_count") is not None and detail["rating_review"].get("review_count") is not None),
        "counter_semantics_match": search["counter"]["counter_type"] == detail["counter"]["counter_type"],
        "shop_identity_match": bool(search.get("shop_id") and search.get("shop_id") == detail.get("shop_id")),
        "variant_equivalence_asserted": False,
    }


def build_audit(entries: list[dict[str, Any]], max_items: int = 10) -> dict[str, Any]:
    surfaces = [audit_surface(entry, max_items=max_items) for entry in entries]
    all_records = [row for surface in surfaces for row in surface["records"]]
    search = next((surface for surface in surfaces if surface["surface_type"] == "keyword-search"), None)
    detail = next((surface for surface in surfaces if surface["surface_type"] == "product-detail"), None)
    correlation = None
    if search and detail:
        detail_by_id = {row["platform_product_id"]: row for row in detail["records"]}
        pair = next(((row, detail_by_id[row["platform_product_id"]]) for row in search["records"] if row["platform_product_id"] in detail_by_id), None)
        if pair:
            correlation = correlate_search_detail(*pair)
    stable_identity = bool(all_records) and all(row["platform_product_id"] for row in all_records)
    explicit_price = bool(all_records) and all(row["price"]["current_price"] is not None for row in all_records)
    no_challenge = all(not surface["challenge_status"]["stop_boundary_reached"] for surface in surfaces)
    timestamped = bool(all_records) and all(row["observed_at"] for row in all_records)
    comparable_surface = bool(search and search["query_or_category"] and search["source_surface"])
    explicit_counter = bool(all_records) and all(row["counter"]["counter_type"] in {"sold", "orders"} for row in all_records)
    sales_velocity_ready = bool(all_records) and all(row["counter"]["eligible_for_sales_velocity"] for row in all_records)
    ready = stable_identity and comparable_surface and timestamped and no_challenge and explicit_counter
    result = {
        "schema": SCHEMA, "audited_at": utcnow(), "platform": PLATFORM,
        "mode": "bounded-rendered-dom-deep-audit", "surfaces": surfaces,
        "product_detail_correlation": correlation,
        "repeatability": {
            "stable_identity_across_observed_surfaces": stable_identity,
            "search_detail_same_item_correlated": bool(correlation and correlation["same_item_identity"]),
            "timestamped_provenance": timestamped, "no_required_authentication_or_challenge": no_challenge,
        },
        "longitudinal_readiness": {
            "ready_for_longitudinal_observation": ready,
            "status": "Ready" if ready and sales_velocity_ready else ("Partial" if stable_identity and no_challenge else "Not ready"),
            "product_identity_price_observation_ready": stable_identity and explicit_price and no_challenge,
            "display_order_observation_ready": comparable_surface and no_challenge,
            "sales_velocity_ready": sales_velocity_ready,
            "blocking_reasons": [
                reason for condition, reason in (
                    (not stable_identity, "stable identity incomplete"),
                    (not comparable_surface, "comparable source surface incomplete"),
                    (not timestamped, "timestamped provenance incomplete"),
                    (not no_challenge, "authentication or challenge boundary reached"),
                    (not explicit_counter, "counter semantics are not explicitly sold or orders"),
                    (not sales_velocity_ready, "no compatible exact sold counter for velocity"),
                ) if condition
            ],
        },
        "pattern_decisions": {
            "product_identity_price": "Approved candidate" if stable_identity and explicit_price and no_challenge else "Needs review",
            "ranking_display_order": "Approved candidate" if any(
                row["marketplace_ranking_observation"] for row in all_records
            ) else ("Needs review" if comparable_surface else "Reject"),
            "sold_order_counter": "Approved candidate" if explicit_counter else "Needs review",
            "longitudinal_observation": "Ready" if ready and sales_velocity_ready else ("Partial" if stable_identity and no_challenge else "Not ready"),
        },
        "technical_completion": all(surface["technical_completion"] for surface in surfaces),
        "production_approved": False, "production_store": False, "scheduler_action": None,
    }
    return result


def technical_failure_result(exc: Exception) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "audited_at": utcnow(), "platform": PLATFORM,
        "mode": "bounded-rendered-dom-deep-audit", "surfaces": [],
        "technical_completion": False, "failure_reason": str(exc),
        "technical_failure": {"type": type(exc).__name__, "message": str(exc)},
        "production_approved": False, "production_store": False, "scheduler_action": None,
    }
