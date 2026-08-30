"""Bounded Shopee Thailand Edge-access evidence analysis.

The module accepts a deliberately small browser capture and emits sanitized,
non-production diagnostic evidence. It never stores browser headers, cookies,
tokens, device identifiers, browser profiles, or raw response bodies.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup


SCHEMA = "ku2d.shopee-edge-access-diagnostic.v1"
CLASSIFICATIONS = {
    "edge-public-data-available",
    "edge-rendered-dom-only",
    "edge-traffic-verification",
    "edge-login-required",
    "edge-shell-only",
    "edge-technical-failure",
}
SENSITIVE_QUERY_KEYS = {
    "access_token", "authorization", "cookie", "device_id", "deviceid",
    "fingerprint", "session", "session_id", "sessionid", "signature",
    "sp_atk", "token", "userid", "user_id",
}
STATIC_SUFFIXES = (
    ".avif", ".css", ".gif", ".ico", ".jpeg", ".jpg", ".js", ".png",
    ".svg", ".ttf", ".webp", ".woff", ".woff2",
)
TELEMETRY_MARKERS = (
    "analytics", "beacon", "collect", "crash", "event", "log", "metrics",
    "pixel", "telemetry", "tracking",
)
NAVIGATION_MARKERS = ("/pages/is_short_url", "/universal-link", "/deeplink")
CHALLENGE_MARKERS = (
    "captcha", "verify you are human", "traffic verification",
    "security verification", "robot verification", "ตรวจสอบว่าคุณเป็นมนุษย์",
)
LOGIN_MARKERS = ("login required", "เข้าสู่ระบบ", "ลงชื่อเข้าใช้")
IDENTITY_FIELDS = {"itemid", "item_id", "product_id"}
SIGNAL_FIELDS = {
    "historical_sold", "sold", "sold_count", "sold_display",
    "sold_count_display", "rating", "rating_star", "review_count",
    "rating_count", "rank", "item_rank", "name", "title", "shopid",
    "shop_id", "seller_id",
}
PRODUCT_URL_PATTERNS = (
    re.compile(r"(?:^|/)product/(?P<shop>\d+)/(?P<item>\d+)(?:[/?#]|$)", re.I),
    re.compile(r"-i\.(?P<shop>\d+)\.(?P<item>\d+)(?:[/?#]|$)", re.I),
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_url(value: Any) -> str | None:
    """Return a public URL without fragments, credentials, or sensitive keys."""
    text = str(value or "").strip()
    if not text:
        return None
    parsed = urlsplit(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return parsed.path[:500] if parsed.path.startswith("/") else None
    host = parsed.hostname.casefold()
    if parsed.port:
        host = f"{host}:{parsed.port}"
    safe_query = []
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.casefold()
        if lowered in SENSITIVE_QUERY_KEYS or any(marker in lowered for marker in ("token", "session", "cookie", "auth", "sign", "device")):
            continue
        safe_query.append((key, item[:200]))
    return urlunsplit((parsed.scheme.casefold(), host, parsed.path or "/", urlencode(safe_query), ""))[:1000]


def stable_product_identity(url: Any) -> dict[str, str] | None:
    safe = sanitize_url(url)
    if not safe:
        return None
    parsed = urlsplit(safe)
    if parsed.hostname not in {"shopee.co.th", "www.shopee.co.th"}:
        return None
    for pattern in PRODUCT_URL_PATTERNS:
        match = pattern.search(parsed.path)
        if match:
            shop_id, item_id = match.group("shop"), match.group("item")
            return {
                "platform_product_id": item_id,
                "shop_id": shop_id,
                "identity_key": f"{shop_id}:{item_id}",
            }
    return None


def response_size_bucket(value: Any) -> str:
    try:
        size = max(0, int(value or 0))
    except (TypeError, ValueError):
        return "unknown"
    if size == 0:
        return "zero-or-unknown"
    if size < 10_000:
        return "under-10-kb"
    if size < 100_000:
        return "10-to-100-kb"
    if size < 1_000_000:
        return "100-kb-to-1-mb"
    return "over-1-mb"


def sanitize_console_summary(value: Any) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for item in list(value or [])[:20]:
        if isinstance(item, dict):
            level, message = str(item.get("level") or "error"), str(item.get("message") or "")
        else:
            level, message = "error", str(item)
        message = re.sub(r"https?://[^\s]+", "[public-url-redacted-from-console]", message)
        message = re.sub(
            r"(?i)(token|cookie|authorization|session|device[_-]?id)\s*[:=]\s*\S+",
            r"\1=[redacted]", message,
        )
        output.append({"level": level[:30], "message": " ".join(message.split())[:300]})
    return output


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _product_evidence(document: Any, max_items: int) -> tuple[list[str], list[dict[str, Any]]]:
    fields: set[str] = set()
    samples: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in _walk(document):
        lowered = {str(key).casefold(): value for key, value in row.items()}
        fields.update((set(lowered) & (IDENTITY_FIELDS | SIGNAL_FIELDS)))
        product_id = next((lowered[key] for key in IDENTITY_FIELDS if lowered.get(key) is not None), None)
        signals = sorted(key for key in SIGNAL_FIELDS if lowered.get(key) not in (None, "", [], {}))
        if product_id is None or not signals:
            continue
        identity = str(product_id)
        if identity in seen:
            continue
        samples.append({
            "platform_product_id": identity,
            "shop_id": str(lowered.get("shopid") or lowered.get("shop_id") or "") or None,
            "detected_marketplace_signals": signals,
        })
        seen.add(identity)
        if len(samples) >= max_items:
            break
    return sorted(fields), samples


def classify_network_request(request: dict[str, Any], max_items: int) -> dict[str, Any]:
    safe_url = sanitize_url(request.get("url") or request.get("path"))
    path = urlsplit(safe_url).path.casefold() if safe_url and safe_url.startswith("http") else str(safe_url or "").casefold()
    content_type = str(request.get("content_type") or "").split(";", 1)[0].strip().casefold() or None
    fields, samples = _product_evidence(request.get("response_json"), max_items)
    if any(marker in path for marker in ("/verify/traffic/", "captcha", "challenge")) or int(request.get("status") or 0) in {401, 403, 429}:
        classification = "challenge/access-control"
    elif path.endswith(STATIC_SUFFIXES) or (content_type and any(kind in content_type for kind in ("image/", "font/", "text/css", "javascript"))):
        classification = "static asset"
    elif any(marker in path for marker in TELEMETRY_MARKERS):
        classification = "telemetry/analytics"
    elif any(marker in path for marker in NAVIGATION_MARKERS):
        classification = "navigation-only"
    elif samples:
        classification = "validated-commerce-data"
    elif any(marker in path for marker in ("/api/", "search", "item", "product", "recommend")):
        classification = "commerce-candidate"
    else:
        classification = "navigation-only"
    return {
        "url_or_path": safe_url,
        "method": str(request.get("method") or "GET").upper()[:10],
        "response_status": int(request.get("status") or 0) or None,
        "content_type": content_type,
        "response_size_bucket": response_size_bucket(request.get("response_size")),
        "product_like_fields_detected": fields,
        "validated_product_sample_count": len(samples),
        "validated_product_samples": samples,
        "classification": classification,
    }


def _text(element: Any) -> str | None:
    value = " ".join(element.get_text(" ", strip=True).split())
    return value[:500] or None


def _visible_card_containers(soup: BeautifulSoup) -> list[Any]:
    selectors = (
        "[data-testid='product-card']", "[data-sqe='item']",
        ".shopee-search-item-result__item", ".shop-search-result-view__item",
    )
    found: list[Any] = []
    seen: set[int] = set()
    for selector in selectors:
        for node in soup.select(selector):
            if id(node) not in seen:
                found.append(node)
                seen.add(id(node))
    if found:
        return found
    for anchor in soup.find_all("a", href=True):
        if stable_product_identity(anchor.get("href")):
            node = anchor
            for _ in range(3):
                if getattr(node, "parent", None) is None:
                    break
                node = node.parent
            if id(node) not in seen:
                found.append(node)
                seen.add(id(node))
    return found


def extract_visible_cards(html: str, *, base_url: str, query: str | None, observed_at: str, max_items: int) -> tuple[int, list[dict[str, Any]]]:
    soup = BeautifulSoup(html or "", "html.parser")
    containers = _visible_card_containers(soup)
    output: list[dict[str, Any]] = []
    for order, container in enumerate(containers, start=1):
        anchor = container.find("a", href=True) if getattr(container, "find", None) else None
        if anchor is None and getattr(container, "name", None) == "a":
            anchor = container
        href = anchor.get("href") if anchor else None
        if href and href.startswith("/"):
            parsed = urlsplit(base_url)
            href = urlunsplit((parsed.scheme, parsed.netloc, href, "", ""))
        safe_href = sanitize_url(href)
        identity = stable_product_identity(safe_href)
        text = _text(container) or ""
        price = re.search(r"(?:฿|THB\s*)\s*[\d,.]+", text, re.I)
        sold = re.search(r"(?:ขายแล้ว\s*[\d.,]+\s*(?:พัน|หมื่น|แสน|ล้าน|ชิ้น)?\+?|[\d.,]+\s*(?:k|m|thousand|million)?\+?\s*sold)", text, re.I)
        rating = re.search(r"(?:rating|คะแนน|รีวิว|review)\s*[: ]?\s*[\d.,]+", text, re.I)
        title = None
        if anchor:
            title = anchor.get("title") or anchor.get("aria-label")
            image = anchor.find("img")
            if not title and image:
                title = image.get("alt")
        title = " ".join(str(title or text).split())[:300] or None
        output.append({
            "visible_title": title,
            "visible_price_text": price.group(0) if price else None,
            "visible_sold_count_text": sold.group(0) if sold else None,
            "visible_rating_or_review_text": rating.group(0) if rating else None,
            "product_url": safe_href,
            "stable_product_identity": identity,
            "usable_identity": identity is not None,
            "observed_display_order": order,
            "source_query": query,
            "observed_at": observed_at,
        })
        if len(output) >= max_items:
            break
    return len(containers), output


def _challenge_status(final_url: str | None, title: str | None, html: str) -> dict[str, Any]:
    combined = " ".join((final_url or "", title or "", BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True))).casefold()
    traffic = "/verify/traffic/" in combined or any(marker in combined for marker in CHALLENGE_MARKERS)
    login = any(marker in combined for marker in LOGIN_MARKERS)
    captcha = "captcha" in combined
    return {
        "traffic_verification": traffic,
        "login_required": login,
        "captcha": captcha,
        "access_denied": "access denied" in combined or "ถูกปฏิเสธการเข้าถึง" in combined,
        "stop_boundary_reached": traffic or login or captcha or "access denied" in combined,
    }


def analyze_capture(snapshot: dict[str, Any], *, target_url: str, query: str | None, max_items: int) -> dict[str, Any]:
    """Analyze one page-load-only Edge capture into sanitized evidence."""
    if max_items < 1 or max_items > 10:
        raise ValueError("--max-items must be between 1 and 10.")
    observed_at = str(snapshot.get("observed_at") or utcnow())
    initial_url = sanitize_url(snapshot.get("initial_url") or target_url)
    final_url = sanitize_url(snapshot.get("final_url") or initial_url)
    html = str(snapshot.get("html") or "")
    parsed_html = BeautifulSoup(html, "html.parser")
    parsed_title = parsed_html.title.string if parsed_html.title and parsed_html.title.string else ""
    title = str(snapshot.get("title") or parsed_title).strip()[:300] or None
    challenge = _challenge_status(final_url, title, html)
    visible_count, cards = extract_visible_cards(
        html, base_url=final_url or target_url, query=query,
        observed_at=observed_at, max_items=max_items,
    )
    network = [classify_network_request(row, max_items) for row in list(snapshot.get("network_requests") or [])[:100]]
    remaining_network_samples = max_items
    for row in network:
        bounded_samples = row["validated_product_samples"][:remaining_network_samples]
        row["validated_product_samples"] = bounded_samples
        row["validated_product_sample_count"] = len(bounded_samples)
        remaining_network_samples -= len(bounded_samples)
    validated_network = [row for row in network if row["classification"] == "validated-commerce-data"]
    stable_cards = [row for row in cards if row["usable_identity"]]
    if challenge["traffic_verification"]:
        classification, usable = "edge-traffic-verification", False
    elif challenge["login_required"]:
        classification, usable = "edge-login-required", False
    elif challenge["captcha"] or challenge["access_denied"]:
        classification, usable = "edge-traffic-verification", False
    elif validated_network:
        classification, usable = "edge-public-data-available", True
    elif stable_cards:
        classification, usable = "edge-rendered-dom-only", True
    else:
        classification, usable = "edge-shell-only", False
    result = {
        "schema": SCHEMA,
        "observed_at": observed_at,
        "platform": "shopee-thailand",
        "mode": "bounded-windows-edge-access-diagnostic",
        "classification": classification,
        "initial_url": initial_url,
        "final_url": final_url,
        "page_title": title,
        "source_query": query,
        "max_items": max_items,
        "visible_product_card_count": visible_count,
        "visible_sold_count_text_samples": [row["visible_sold_count_text"] for row in cards if row["visible_sold_count_text"]][:max_items],
        "visible_ranking_context": {
            "context": "observed-display-order-on-single-page-load",
            "source_query": query,
            "observed_orders": [row["observed_display_order"] for row in cards],
            "national_ranking_claimed": False,
        },
        "dom_product_samples": cards,
        "stable_dom_identity_count": len(stable_cards),
        "network_request_metadata": network,
        "validated_network_endpoint_count": len(validated_network),
        "challenge_status": challenge,
        "browser_console_errors_summary": sanitize_console_summary(snapshot.get("console_errors_summary")),
        "technical_completion": True,
        "usable_evidence": usable,
        "failure_reason": None if usable else (
            "traffic-verification-stop-boundary" if classification == "edge-traffic-verification" else
            "login-required-stop-boundary" if classification == "edge-login-required" else
            "no-stable-public-product-identity-or-validated-commerce-response"
        ),
        "production_approved": False,
        "production_store": False,
        "scheduler_action": None,
        "sensitive_browser_state_captured": False,
        "comparison": {
            "plain_http": "reachable application shell; zero usable normalized records",
            "in_app_browser": "traffic verification / Login Required",
            "windows_edge_runner": classification,
            "edge_required": False,
        },
    }
    assert result["classification"] in CLASSIFICATIONS
    return result


def technical_failure_result(*, target_url: str | None, query: str | None, max_items: int, exc: Exception) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "observed_at": utcnow(),
        "platform": "shopee-thailand",
        "mode": "bounded-windows-edge-access-diagnostic",
        "classification": "edge-technical-failure",
        "initial_url": sanitize_url(target_url),
        "final_url": None,
        "page_title": None,
        "source_query": query,
        "max_items": max_items,
        "visible_product_card_count": 0,
        "visible_sold_count_text_samples": [],
        "visible_ranking_context": None,
        "dom_product_samples": [],
        "stable_dom_identity_count": 0,
        "network_request_metadata": [],
        "validated_network_endpoint_count": 0,
        "challenge_status": {
            "traffic_verification": False, "login_required": False,
            "captcha": False, "access_denied": False, "stop_boundary_reached": False,
        },
        "browser_console_errors_summary": [],
        "technical_completion": False,
        "usable_evidence": False,
        "failure_reason": str(exc),
        "technical_failure": {"type": type(exc).__name__, "message": str(exc)},
        "production_approved": False,
        "production_store": False,
        "scheduler_action": None,
        "sensitive_browser_state_captured": False,
        "comparison": {
            "plain_http": "reachable application shell; zero usable normalized records",
            "in_app_browser": "traffic verification / Login Required",
            "windows_edge_runner": "edge-technical-failure",
            "edge_required": False,
        },
    }
