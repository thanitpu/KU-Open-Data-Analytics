"""Sanitized evidence analysis for one Lazada Thailand browser page load.

The analyzer accepts bounded visible-card and public network metadata from a
normal unauthenticated browser context. It never emits headers, cookies,
tokens, device identifiers, profiles, storage state, or raw response bodies.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from commerce_market_observation import parse_sold_count
from shopee_edge_access import response_size_bucket, sanitize_console_summary, sanitize_url


SCHEMA = "ku2d.lazada-browser-access-diagnostic.v1"
CLASSIFICATIONS = {
    "lazada-public-data-available",
    "lazada-rendered-dom-only",
    "lazada-login-required",
    "lazada-traffic-verification",
    "lazada-shell-only",
    "lazada-technical-failure",
}
PLATFORM = "lazada-thailand"
STATIC_SUFFIXES = (
    ".avif", ".css", ".gif", ".ico", ".jpeg", ".jpg", ".js", ".png",
    ".svg", ".ttf", ".webp", ".woff", ".woff2",
)
TELEMETRY_MARKERS = (
    "/analytics", "/beacon", "/collect", "/crash", "/event", "/log",
    "/metrics", "/pixel", "/telemetry", "/tracking",
)
IDENTITY_FIELDS = {"itemid", "item_id", "productid", "product_id", "nid"}
URL_FIELDS = {"producturl", "product_url", "itemurl", "item_url", "url", "link"}
IDENTITY_FIELD_ORDER = ("itemid", "item_id", "productid", "product_id", "nid")
URL_FIELD_ORDER = ("producturl", "product_url", "itemurl", "item_url", "url", "link")
SIGNAL_FIELDS = {
    "name", "title", "productname", "product_name", "priceshow", "price_show",
    "displayprice", "display_price", "price", "ratingscore", "rating_score",
    "rating", "ratingvalue", "reviewcount", "review_count", "ratingcount",
    "rating_count", "solddisplay", "sold_display", "soldcount", "sold_count",
    "orderdisplay", "order_display", "ordercount", "order_count", "orders",
    "rank", "itemrank", "item_rank",
}
_ITEM_URL_RE = re.compile(r"(?:^|[-/])i(?P<item>\d+)(?:[-/.]|$)", re.IGNORECASE)
_CURRENCY_RE = re.compile(r"(?:฿|THB\s*)(?P<amount>\d[\d,]*(?:\.\d+)?)", re.IGNORECASE)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def product_id_from_url(value: Any, base_url: str = "https://www.lazada.co.th/") -> tuple[str | None, str | None]:
    raw = str(value or "").strip()
    if not raw:
        return None, None
    absolute = urljoin(base_url, raw)
    safe = sanitize_url(absolute)
    if not safe:
        return None, None
    parsed = urlsplit(safe)
    if parsed.hostname not in {"lazada.co.th", "www.lazada.co.th"}:
        return None, None
    match = _ITEM_URL_RE.search(parsed.path)
    return (match.group("item"), safe) if match else (None, safe)


def stable_product_identity(
    url: Any, *, explicit_id: Any = None, base_url: str = "https://www.lazada.co.th/",
) -> dict[str, Any] | None:
    url_id, safe_url = product_id_from_url(url, base_url)
    normalized_explicit = str(explicit_id).strip() if explicit_id is not None else ""
    if url_id and normalized_explicit and url_id != normalized_explicit:
        return None
    product_id = url_id or normalized_explicit or None
    if not product_id:
        return None
    return {
        "platform_product_id": product_id,
        "product_url": safe_url,
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
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _explicit_currency(value: Any) -> float | None:
    match = _CURRENCY_RE.search(str(value or ""))
    return float(match.group("amount").replace(",", "")) if match else None


def _counter_semantics(text: Any) -> dict[str, Any]:
    raw = " ".join(str(text or "").split())[:200]
    lowered = raw.casefold()
    if re.search(r"(?:ขายแล้ว|\bsold\b)", lowered, re.IGNORECASE):
        parsed = parse_sold_count(raw)
        return {
            "counter_type": "sold", "raw_display": raw,
            "observed_sold_count": parsed["observed_sold_count"],
            "precision": parsed["precision"], "is_transaction_ledger": False,
        }
    if re.search(r"(?:คำสั่งซื้อ|ออเดอร์|\border(?:s|ed)?\b)", lowered, re.IGNORECASE):
        return {
            "counter_type": "orders", "raw_display": raw,
            "observed_sold_count": None, "precision": "unknown",
            "is_transaction_ledger": False,
        }
    return {
        "counter_type": "unknown", "raw_display": raw or None,
        "observed_sold_count": None, "precision": "unknown",
        "is_transaction_ledger": False,
    }


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _normalized_keys(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key).casefold(): value for key, value in row.items()}


def _structured_product_evidence(document: Any, max_items: int) -> tuple[list[str], list[dict[str, Any]]]:
    fields: set[str] = set()
    samples: list[dict[str, Any]] = []
    seen: set[str] = set()
    for original in _walk(document):
        row = _normalized_keys(original)
        fields.update(set(row) & (IDENTITY_FIELDS | URL_FIELDS | SIGNAL_FIELDS))
        explicit = next((row[key] for key in IDENTITY_FIELD_ORDER if row.get(key) is not None), None)
        candidate_url = next((row[key] for key in URL_FIELD_ORDER if row.get(key) is not None), None)
        identity = stable_product_identity(candidate_url, explicit_id=explicit)
        signals = sorted(key for key in SIGNAL_FIELDS if row.get(key) not in (None, "", [], {}))
        if not identity or not signals or identity["platform_product_id"] in seen:
            continue
        raw_price = _first(row, "priceshow", "price_show", "displayprice", "display_price", "price")
        price = _explicit_currency(raw_price)
        counter_text = _first(row, "solddisplay", "sold_display", "orderdisplay", "order_display")
        counter = _counter_semantics(counter_text)
        samples.append({
            **identity,
            "shop_id": str(_first(row, "shopid", "shop_id") or "") or None,
            "detected_marketplace_signals": signals,
            "visible_or_structured_price": price,
            "raw_price": raw_price,
            "price_semantics": "explicit-currency-display" if price is not None else (
                "raw-structured-value-scaling-unknown" if raw_price is not None else "not-observed"
            ),
            "marketplace_counter": counter,
        })
        seen.add(identity["platform_product_id"])
        if len(samples) >= max_items:
            break
    return sorted(fields), samples


def classify_network_request(request: dict[str, Any], max_items: int) -> dict[str, Any]:
    safe_url = sanitize_url(request.get("url") or request.get("path"))
    parsed = urlsplit(safe_url) if safe_url and safe_url.startswith("http") else None
    path = parsed.path.casefold() if parsed else str(safe_url or "").casefold()
    content_type = str(request.get("content_type") or "").split(";", 1)[0].strip().casefold() or None
    fields, samples = _structured_product_evidence(request.get("response_json"), max_items)
    official_json = bool(
        parsed and parsed.hostname in {"lazada.co.th", "www.lazada.co.th"}
        and content_type and "json" in content_type
    )
    if not official_json:
        samples = []
    status = _integer(request.get("status"))
    if any(marker in path for marker in ("/captcha", "/punish", "/verify", "challenge")) or status in {401, 403, 429}:
        classification = "challenge/access-control"
    elif path.endswith(STATIC_SUFFIXES) or (content_type and any(kind in content_type for kind in ("image/", "font/", "text/css", "javascript"))):
        classification = "static-asset"
    elif "/user/api/" in path or any(marker in path for marker in ("login", "register", "oauth", "password")):
        classification = "account-or-auth-non-commerce"
    elif "/checkout/" in path:
        classification = "checkout-non-observation"
    elif any(marker in path for marker in TELEMETRY_MARKERS):
        classification = "telemetry/analytics"
    elif samples:
        classification = "validated-commerce-data"
    elif any(marker in path for marker in ("/api/", "catalog", "search", "item", "product", "recommend")):
        classification = "commerce-candidate"
    else:
        classification = "navigation-only"
    return {
        "url_or_path": safe_url,
        "method": str(request.get("method") or "GET").upper()[:10],
        "response_status": status,
        "content_type": content_type,
        "response_size_bucket": response_size_bucket(request.get("response_size")),
        "product_like_fields_detected": fields,
        "validated_product_sample_count": len(samples),
        "validated_product_samples": samples,
        "classification": classification,
    }


def _visible_cards_from_html(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html or "", "html.parser")
    selectors = (
        "[data-qa-locator='product-item']", "[data-sqe='item']", ".Bm3ON",
        "[data-testid='product-card']",
    )
    containers: list[Any] = []
    seen_nodes: set[int] = set()
    for selector in selectors:
        for node in soup.select(selector):
            if id(node) not in seen_nodes:
                containers.append(node)
                seen_nodes.add(id(node))
    if not containers:
        for anchor in soup.find_all("a", href=True):
            if product_id_from_url(anchor.get("href"))[0]:
                node = anchor
                for _ in range(3):
                    node = getattr(node, "parent", None) or node
                if id(node) not in seen_nodes:
                    containers.append(node)
                    seen_nodes.add(id(node))
    output = []
    for node in containers:
        anchor = node.find("a", href=True) if getattr(node, "find", None) else None
        if anchor is None and getattr(node, "name", None) == "a":
            anchor = node
        image = anchor.find("img") if anchor else None
        output.append({
            "product_url": anchor.get("href") if anchor else None,
            "explicit_product_id": node.get("data-item-id") or node.get("data-product-id"),
            "visible_title": (anchor.get("title") if anchor else None) or (image.get("alt") if image else None),
            "visible_text": " ".join(node.get_text(" ", strip=True).split())[:1000],
        })
    return output


def _card_record(
    row: dict[str, Any], *, base_url: str, query: str | None, observed_at: str, order: int,
) -> dict[str, Any]:
    identity = stable_product_identity(
        row.get("product_url"), explicit_id=row.get("explicit_product_id"), base_url=base_url,
    )
    text = " ".join(str(row.get("visible_text") or "").split())[:1000]
    price_text = str(row.get("visible_price_text") or "").strip() or None
    if not price_text:
        match = _CURRENCY_RE.search(text)
        price_text = match.group(0) if match else None
    review_text = str(row.get("visible_rating_or_review_text") or "").strip() or None
    if not review_text:
        match = re.search(r"(?:rating|คะแนน|รีวิว|review)\s*[: ]?\s*[\d,.]+", text, re.IGNORECASE)
        review_text = match.group(0) if match else None
    counter_text = str(row.get("visible_sold_or_order_text") or "").strip() or None
    if not counter_text:
        match = re.search(
            r"(?:ขายแล้ว\s*[\d.,]+\s*(?:k|m|พัน|หมื่น|แสน|ล้าน|ชิ้น)?\+?|"
            r"[\d.,]+\s*(?:k|m|thousand|million)?\+?\s*sold|"
            r"(?:คำสั่งซื้อ|ออเดอร์|orders?)\s*[: ]?\s*[\d,.]+|"
            r"[\d,.]+\s*orders?|"
            r"[\d,.]+\s*(?:k|m|พัน|หมื่น|แสน|ล้าน)?\s*ชิ้น)", text, re.IGNORECASE,
        )
        counter_text = match.group(0) if match else None
    title = " ".join(str(row.get("visible_title") or "").split())[:300] or None
    return {
        "visible_title": title,
        "visible_price_text": price_text,
        "normalized_price": _explicit_currency(price_text),
        "price_semantics": "explicit-currency-display" if _explicit_currency(price_text) is not None else "not-observed-or-unvalidated",
        "visible_rating_or_review_text": review_text,
        "visible_sold_or_order_text": counter_text,
        "marketplace_counter": _counter_semantics(counter_text),
        "product_url": identity["product_url"] if identity else sanitize_url(urljoin(base_url, str(row.get("product_url") or ""))),
        "stable_product_identity": identity,
        "usable_identity": identity is not None,
        "observed_display_order": order,
        "source_query": query,
        "observed_at": observed_at,
    }


def _challenge_status(final_url: str | None, title: str | None, visible_text: str) -> dict[str, Any]:
    combined = " ".join((final_url or "", title or "", visible_text or "")).casefold()
    final_route = str(final_url or "").casefold()
    login = "/user/login" in final_route or any(marker in combined for marker in (
        "login required", "please log in to continue", "โปรดเข้าสู่ระบบเพื่อดำเนินการต่อ",
    ))
    captcha = "captcha" in combined
    traffic = any(marker in combined for marker in (
        "/captcha", "/punish", "/verify", "verify you are human", "traffic verification",
        "security verification", "robot verification", "unusual traffic",
    ))
    denied = "access denied" in combined or "ถูกปฏิเสธการเข้าถึง" in combined
    return {
        "traffic_verification": traffic or captcha or denied,
        "login_required": login,
        "captcha": captcha,
        "access_denied": denied,
        "stop_boundary_reached": traffic or captcha or denied or login,
    }


def analyze_capture(snapshot: dict[str, Any], *, target_url: str, query: str | None, max_items: int) -> dict[str, Any]:
    if max_items < 1 or max_items > 10:
        raise ValueError("--max-items must be between 1 and 10.")
    observed_at = str(snapshot.get("observed_at") or utcnow())
    initial_url = sanitize_url(snapshot.get("initial_url") or target_url)
    final_url = sanitize_url(snapshot.get("final_url") or initial_url)
    title = " ".join(str(snapshot.get("title") or "").split())[:300] or None
    html = str(snapshot.get("html") or "")
    visible_rows = list(snapshot.get("visible_cards") or _visible_cards_from_html(html))
    visible_count = _integer(snapshot.get("visible_product_card_count"))
    if visible_count is None:
        visible_count = len(visible_rows)
    visible_text = str(snapshot.get("visible_page_text") or BeautifulSoup(html, "html.parser").get_text(" ", strip=True))[:5000]
    challenge = _challenge_status(final_url, title, visible_text)
    cards = [
        _card_record(row, base_url=final_url or target_url, query=query, observed_at=observed_at, order=index)
        for index, row in enumerate(visible_rows[:max_items], start=1)
    ]
    network = [classify_network_request(row, max_items) for row in list(snapshot.get("network_requests") or [])[:100]]
    remaining = max_items
    for row in network:
        row["validated_product_samples"] = row["validated_product_samples"][:remaining]
        row["validated_product_sample_count"] = len(row["validated_product_samples"])
        remaining -= row["validated_product_sample_count"]
    validated_network = [row for row in network if row["classification"] == "validated-commerce-data"]
    stable_cards = [row for row in cards if row["usable_identity"]]
    if challenge["traffic_verification"]:
        classification, usable = "lazada-traffic-verification", False
    elif challenge["login_required"]:
        classification, usable = "lazada-login-required", False
    elif validated_network:
        classification, usable = "lazada-public-data-available", True
    elif stable_cards:
        classification, usable = "lazada-rendered-dom-only", True
    else:
        classification, usable = "lazada-shell-only", False
    result = {
        "schema": SCHEMA, "observed_at": observed_at, "platform": PLATFORM,
        "mode": "bounded-normal-browser-access-diagnostic", "classification": classification,
        "initial_url": initial_url, "final_url": final_url, "page_title": title,
        "source_query": query, "max_items": max_items,
        "visible_product_card_count": visible_count,
        "dom_product_samples": cards, "stable_dom_identity_count": len(stable_cards),
        "visible_title_samples": [row["visible_title"] for row in cards if row["visible_title"]][:max_items],
        "visible_price_text_samples": [row["visible_price_text"] for row in cards if row["visible_price_text"]][:max_items],
        "visible_rating_or_review_text_samples": [row["visible_rating_or_review_text"] for row in cards if row["visible_rating_or_review_text"]][:max_items],
        "visible_sold_or_order_text_samples": [row["visible_sold_or_order_text"] for row in cards if row["visible_sold_or_order_text"]][:max_items],
        "visible_ranking_context": {
            "context": "observed-display-order-on-single-page-load", "source_query": query,
            "observed_orders": [row["observed_display_order"] for row in cards],
            "national_ranking_claimed": False,
        },
        "network_request_metadata": network,
        "validated_network_endpoint_count": len(validated_network),
        "challenge_status": challenge,
        "browser_console_errors_summary": sanitize_console_summary(snapshot.get("console_errors_summary")),
        "technical_completion": True, "usable_evidence": usable,
        "failure_reason": None if usable else (
            "traffic-verification-stop-boundary" if classification == "lazada-traffic-verification" else
            "login-required-stop-boundary" if classification == "lazada-login-required" else
            "no-stable-public-product-identity-or-validated-commerce-response"
        ),
        "production_approved": False, "production_store": False, "scheduler_action": None,
        "sensitive_browser_state_captured": False,
        "comparison": {
            "plain_http": "reachable application shell; zero usable normalized records",
            "normal_browser": classification, "windows_edge_runner": "not-attempted",
            "edge_required": False,
        },
    }
    assert result["classification"] in CLASSIFICATIONS
    return result


def technical_failure_result(*, target_url: str | None, query: str | None, max_items: int, exc: Exception) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "observed_at": utcnow(), "platform": PLATFORM,
        "mode": "bounded-normal-browser-access-diagnostic",
        "classification": "lazada-technical-failure",
        "initial_url": sanitize_url(target_url), "final_url": None, "page_title": None,
        "source_query": query, "max_items": max_items,
        "visible_product_card_count": 0, "dom_product_samples": [],
        "stable_dom_identity_count": 0, "visible_title_samples": [],
        "visible_price_text_samples": [], "visible_rating_or_review_text_samples": [],
        "visible_sold_or_order_text_samples": [], "visible_ranking_context": None,
        "network_request_metadata": [], "validated_network_endpoint_count": 0,
        "challenge_status": {
            "traffic_verification": False, "login_required": False, "captcha": False,
            "access_denied": False, "stop_boundary_reached": False,
        },
        "browser_console_errors_summary": [], "technical_completion": False,
        "usable_evidence": False, "failure_reason": str(exc),
        "technical_failure": {"type": type(exc).__name__, "message": str(exc)},
        "production_approved": False, "production_store": False, "scheduler_action": None,
        "sensitive_browser_state_captured": False,
        "comparison": {
            "plain_http": "reachable application shell; zero usable normalized records",
            "normal_browser": "lazada-technical-failure", "windows_edge_runner": "not-attempted",
            "edge_required": False,
        },
    }
