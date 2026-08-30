"""Bounded public TikTok Shop evidence normalization for Commerce Pulse."""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from commerce_market_observation import CommerceProductObservation, parse_sold_count
from shopee_edge_access import sanitize_url


PLATFORM = "tiktok-shop-thailand"
OFFICIAL_HOSTS = {"shop.tiktok.com", "www.shop.tiktok.com", "shop-th.tiktok.com"}
_PRODUCT_PATTERNS = (
    re.compile(r"/(?:[a-z]{2}/)?pdp/(?:[^/?#]+/)?(?P<id>\d{8,})(?:[/?#]|$)", re.I),
    re.compile(r"/(?:view/)?product/(?P<id>\d{8,})(?:[/?#]|$)", re.I),
)
_PRICE_RE = re.compile(r"(?:฿|THB\s*)(?P<amount>\d[\d,]*(?:\.\d+)?)", re.I)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def product_identity(value: Any, *, explicit_id: Any = None, base_url: str = "https://shop.tiktok.com/th/") -> dict[str, Any] | None:
    raw = str(value or "").strip()
    absolute = urljoin(base_url, raw) if raw else None
    safe = sanitize_url(absolute) if absolute else None
    url_id = None
    if safe:
        parsed = urlsplit(safe)
        if (parsed.hostname or "").casefold() not in OFFICIAL_HOSTS:
            return None
        for pattern in _PRODUCT_PATTERNS:
            match = pattern.search(parsed.path)
            if match:
                url_id = match.group("id")
                break
    normalized_explicit = str(explicit_id).strip() if explicit_id is not None else ""
    if url_id and normalized_explicit and url_id != normalized_explicit:
        return None
    product_id = url_id or normalized_explicit or None
    if not product_id or not product_id.isdigit():
        return None
    return {
        "platform_product_id": product_id,
        "canonical_product_url": safe,
        "identity_basis": "canonical-public-product-url" if url_id else "explicit-public-structured-id",
    }


def _first(row: dict[str, Any], *keys: str):
    for key in keys:
        if row.get(key) is not None:
            return row[key]
    return None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None and number.is_integer() else None


def explicit_baht(value: Any) -> float | None:
    match = _PRICE_RE.search(str(value or ""))
    return float(match.group("amount").replace(",", "")) if match else None


def counter_semantics(value: Any) -> dict[str, Any]:
    raw = " ".join(str(value or "").split())[:200] or None
    lowered = str(raw or "").casefold()
    if raw and re.search(r"(?:ขายแล้ว|จำหน่ายไป|\bsold\b)", lowered, re.I):
        parsed = parse_sold_count(raw)
        return {
            "counter_type": "sold", "raw_display": raw,
            "numeric_parse": parsed["observed_sold_count"], "precision": parsed["precision"],
            "semantic_confidence": "explicit-label", "is_transaction_ledger": False,
        }
    if raw and re.search(r"(?:คำสั่งซื้อ|ออเดอร์|\borders?\b)", lowered, re.I):
        parsed = parse_sold_count(raw)
        return {
            "counter_type": "orders", "raw_display": raw,
            "numeric_parse": parsed["observed_sold_count"], "precision": parsed["precision"],
            "semantic_confidence": "explicit-label", "is_transaction_ledger": False,
        }
    return {
        "counter_type": "unknown", "raw_display": raw,
        "numeric_parse": parse_sold_count(raw)["observed_sold_count"] if raw else None,
        "precision": parse_sold_count(raw)["precision"] if raw else "unknown",
        "semantic_confidence": "unlabeled-display" if raw else "not-observed",
        "is_transaction_ledger": False,
    }


def _walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def normalize_row(row: dict[str, Any], *, page_url: str, source_surface: str, query: str | None,
                  observed_at: str, path: str, transport: str) -> dict[str, Any] | None:
    identity = product_identity(
        _first(row, "product_url", "productUrl", "url", "canonical_url"),
        explicit_id=_first(row, "product_id", "productId", "item_id", "itemId"),
        base_url=page_url,
    )
    if not identity:
        return None
    title = " ".join(str(_first(row, "title", "name", "product_name", "productName") or "").split())[:500] or None
    raw_price = _first(row, "display_price", "displayPrice", "price_text", "priceText", "price")
    raw_original = _first(row, "original_price", "originalPrice", "original_price_text")
    current_price = explicit_baht(raw_price)
    original_price = explicit_baht(raw_original)
    raw_counter = _first(row, "sold_display", "soldDisplay", "sold_text", "soldText", "order_display", "orderDisplay", "counter_text")
    counter = counter_semantics(raw_counter)
    rating = _number(_first(row, "rating", "rating_score", "ratingScore"))
    reviews = _integer(_first(row, "review_count", "reviewCount"))
    shop_id = str(_first(row, "shop_id", "shopId") or "").strip() or None
    shop_name = " ".join(str(_first(row, "shop_name", "shopName", "seller_name", "sellerName") or "").split())[:300] or None
    if not any((title, raw_price, raw_counter, rating, reviews, shop_id, shop_name)):
        return None
    observation = CommerceProductObservation(
        platform=PLATFORM, platform_product_id=identity["platform_product_id"],
        seller_id=None, shop_id=shop_id, title=title, brand=None, category=None,
        current_price=current_price, original_price=original_price, discount_pct=None,
        rating=rating, review_count=reviews,
        observed_sold_count=counter["numeric_parse"] if counter["counter_type"] == "sold" else None,
        sold_count_display=counter["raw_display"] if counter["counter_type"] == "sold" else None,
        sold_count_precision=counter["precision"], source_surface=source_surface,
        source_rank=None, source_query=query, observed_at=observed_at,
        provenance={
            "transport": transport, "document_path": path,
            "canonical_product_url": identity["canonical_product_url"],
            "identity_basis": identity["identity_basis"], "shop_name": shop_name,
            "raw_price": raw_price, "raw_original_price": raw_original,
            "price_semantics": "explicit-baht-display" if current_price is not None else (
                "raw-value-scaling-unknown" if raw_price is not None else "not-observed"
            ),
            "marketplace_counter": counter, "rank_claimed": False,
        }, publicly_observable=True,
    )
    return asdict(observation)


def normalize_json(document: Any, *, page_url: str, source_surface: str, query: str | None,
                   observed_at: str, max_items: int) -> list[dict[str, Any]]:
    output, seen = [], set()
    for path, row in _walk(document):
        normalized = normalize_row(
            row, page_url=page_url, source_surface=source_surface, query=query,
            observed_at=observed_at, path=path, transport="public-structured-json",
        )
        if normalized and normalized["platform_product_id"] not in seen:
            output.append(normalized)
            seen.add(normalized["platform_product_id"])
        if len(output) >= max_items:
            break
    return output


def _script_documents(soup: BeautifulSoup):
    for index, script in enumerate(soup.find_all("script")):
        kind = str(script.get("type") or "").casefold()
        script_id = str(script.get("id") or "").casefold()
        if "json" not in kind and script_id not in {"__next_data__", "__nuxt_data__"}:
            continue
        try:
            yield f"html.script[{index}]", json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue


def normalize_html(text: str, *, page_url: str, source_surface: str, query: str | None,
                   observed_at: str, max_items: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(text, "html.parser")
    output, seen = [], set()
    for prefix, document in _script_documents(soup):
        for row in normalize_json(document, page_url=page_url, source_surface=source_surface,
                                  query=query, observed_at=observed_at, max_items=max_items):
            if row["platform_product_id"] not in seen:
                row["provenance"]["document_path"] = prefix + ":" + row["provenance"]["document_path"]
                output.append(row)
                seen.add(row["platform_product_id"])
        if len(output) >= max_items:
            return output[:max_items]
    page_identity = product_identity(page_url)
    if page_identity and page_identity["platform_product_id"] not in seen:
        visible = " ".join(soup.get_text(" ", strip=True).split())
        title = (soup.find("meta", property="og:title") or {}).get("content") or (soup.title.string if soup.title else None)
        price = _PRICE_RE.search(visible)
        sold = re.search(r"(?:ขายแล้ว|จำหน่ายไป|\bsold\b)\s*[\d,.]+\s*(?:k|m|พัน|หมื่น|แสน|ล้าน)?\+?", visible, re.I)
        seller = re.search(r"(?:ขายโดย|sold by)\s+([^|\n]{1,120})", visible, re.I)
        row = normalize_row({
            "product_url": page_url, "title": title,
            "display_price": price.group(0) if price else None,
            "sold_display": sold.group(0) if sold else None,
            "shop_name": seller.group(1).strip() if seller else None,
        }, page_url=page_url, source_surface=source_surface, query=query,
            observed_at=observed_at, path="html.visible-product-detail", transport="public-visible-html")
        if row:
            output.append(row)
    return output[:max_items]
