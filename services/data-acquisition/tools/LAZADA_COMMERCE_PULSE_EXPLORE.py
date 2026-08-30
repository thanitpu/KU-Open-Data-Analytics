"""Bounded, non-production Lazada Thailand public-surface explorer.

Exit 0 means stable product identity plus public marketplace-signal evidence was
normalized. Exit 2 means the bounded probe completed but evidence was blocked
or insufficient. Exit 1 means a technical/runtime/evidence-writing failure.
Evidence is attempted before every exit; authentication and challenge bypass
are outside this tool's contract.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
if str(ACQUISITION) not in sys.path:
    sys.path.insert(0, str(ACQUISITION))

from commerce_market_observation import CommerceProductObservation, parse_sold_count


EXIT_EVIDENCE_OBTAINED = 0
EXIT_TECHNICAL_FAILURE = 1
EXIT_EVIDENCE_WITHHELD = 2
SCHEMA = "ku2d.lazada-commerce-pulse-explore.v1"
REGISTRY_PATH = ROOT / "config" / "lazada_commerce_pulse_sources.json"
MAX_BODY_BYTES = 2_000_000
PLATFORM = "lazada-thailand"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Bounded Lazada Commerce Pulse public-surface exploration")
    target = value.add_mutually_exclusive_group(required=True)
    target.add_argument("--url")
    target.add_argument("--query")
    target.add_argument("--category")
    value.add_argument("--max-items", type=int, default=10)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--no-production-store", action="store_true")
    return value


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def target_url(args: argparse.Namespace, registry: dict[str, Any]) -> tuple[str, str, str | None]:
    if args.url:
        return args.url.strip(), "explicit-public-url", None
    query = args.query.strip() if args.query else None
    surface = "keyword-search"
    if args.category:
        category = args.category.strip().casefold()
        seeds = {row["category_id"].casefold(): row for row in registry["pilot_seed_registry"]["categories"]}
        if category not in seeds:
            raise ValueError(f"Unknown category seed: {args.category}")
        query = seeds[category]["thai_queries"][0]
        surface = "category-seed-search"
    return f"https://www.lazada.co.th/catalog/?q={quote_plus(query or '')}", surface, query


def validate_options(args: argparse.Namespace, registry: dict[str, Any]) -> tuple[str, str, str | None]:
    if not args.no_production_store:
        raise ValueError("--no-production-store is required.")
    maximum = int(registry["pilot_limits"]["max_items"])
    if args.max_items < 1 or args.max_items > maximum:
        raise ValueError(f"--max-items must be between 1 and {maximum}.")
    url, surface, query = target_url(args, registry)
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in {"lazada.co.th", "www.lazada.co.th"}:
        raise ValueError("Only public HTTPS Lazada Thailand customer surfaces are allowed.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in URLs are prohibited.")
    return url, surface, query


def public_http_fetch(url: str, timeout: int = 20) -> dict[str, Any]:
    request = Request(url, headers={
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.5",
        "User-Agent": "KU2D-Public-Surface-Research/1.0 (+non-production; no-auth)",
    }, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(MAX_BODY_BYTES + 1)
            return {
                "status": int(response.status), "effective_url": response.geturl(),
                "content_type": response.headers.get("Content-Type"),
                "body": body[:MAX_BODY_BYTES], "truncated": len(body) > MAX_BODY_BYTES,
            }
    except HTTPError as exc:
        body = exc.read(MAX_BODY_BYTES + 1)
        return {
            "status": int(exc.code), "effective_url": exc.geturl(),
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "body": body[:MAX_BODY_BYTES], "truncated": len(body) > MAX_BODY_BYTES,
        }
    except URLError as exc:
        raise RuntimeError(f"Public HTTP transport failed: {exc.reason}") from exc


def _challenge(text: str, status: int, effective_url: str = "") -> tuple[bool, str | None]:
    lowered = text.casefold()
    route = str(effective_url).casefold()
    if any(marker in route for marker in ("/captcha", "/punish", "/verify", "sec.lazada")):
        return True, "redirected-to-lazada-access-challenge"
    if status in {401, 403, 429}:
        return True, f"http-{status}-access-control-or-rate-limit"
    markers = (
        "verify you are human", "captcha verification", "captcha challenge", "robot verification", "security verification",
        "login required", "unusual traffic", "ตรวจสอบว่าคุณเป็นมนุษย์", "ยืนยันตัวตน",
    )
    if any(marker in lowered for marker in markers):
        return True, "challenge-marker-in-response"
    return False, None


_ITEM_URL_RE = re.compile(r"(?:^|[-/])i(?P<item>\d+)(?:[-/.]|$)", re.IGNORECASE)
_CURRENCY_RE = re.compile(r"(?:฿|THB\s*)(?P<amount>\d[\d,]*(?:\.\d+)?)", re.IGNORECASE)
_ENDPOINT_RE = re.compile(r"(?:https://www\.lazada\.co\.th)?(/[A-Za-z0-9_?=&%./-]*(?:api|catalog|products)[A-Za-z0-9_?=&%./-]*)", re.IGNORECASE)


def product_id_from_url(value: Any, base_url: str = "https://www.lazada.co.th/") -> tuple[str | None, str | None]:
    raw = str(value or "").strip()
    if not raw:
        return None, None
    absolute = urljoin(base_url, raw)
    parsed = urlparse(absolute)
    if (parsed.hostname or "").casefold() not in {"lazada.co.th", "www.lazada.co.th"}:
        return None, None
    match = _ITEM_URL_RE.search(parsed.path)
    return (match.group("item"), absolute) if match else (None, absolute)


def _walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _first(row: dict[str, Any], *keys: str):
    for key in keys:
        if row.get(key) is not None:
            return row[key]
    return None


def _integer(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _explicit_currency(value: Any) -> float | None:
    match = _CURRENCY_RE.search(str(value or ""))
    return float(match.group("amount").replace(",", "")) if match else None


def _counter(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    sold = _first(row, "soldDisplay", "sold_display", "soldCountDisplay", "sold_count_display", "sold", "soldCount", "sold_count")
    orders = _first(row, "orderDisplay", "order_display", "orders", "orderCount", "order_count")
    if sold is not None:
        parsed = parse_sold_count(str(sold))
        return parsed, {
            "counter_type": "sold", "raw_display": str(sold), "meaning": "public-display-not-transaction-ledger",
            "precision": parsed["precision"], "parsed_value": parsed["observed_sold_count"],
        }
    if orders is not None:
        return {"observed_sold_count": None, "raw_display": "", "precision": "unknown"}, {
            "counter_type": "orders", "raw_display": str(orders),
            "meaning": "orders-not-assumed-sold-or-fulfilled", "precision": "unknown", "parsed_value": None,
        }
    return {"observed_sold_count": None, "raw_display": "", "precision": "unknown"}, {
        "counter_type": "unknown", "raw_display": None, "meaning": "no-public-counter-observed",
        "precision": "unknown", "parsed_value": None,
    }


def _identity(row: dict[str, Any], base_url: str) -> tuple[str | None, str | None, str]:
    candidate_url = _first(row, "productUrl", "product_url", "itemUrl", "item_url", "url", "link")
    url_id, canonical_url = product_id_from_url(candidate_url, base_url)
    explicit = _first(row, "itemId", "item_id", "productId", "product_id", "nid")
    explicit_id = str(explicit).strip() if explicit is not None else ""
    if url_id and explicit_id and url_id != explicit_id:
        return None, canonical_url, "contradictory-url-and-structured-id"
    if url_id:
        return url_id, canonical_url, "canonical-public-product-url"
    if explicit_id:
        return explicit_id, canonical_url, "explicit-public-structured-id"
    return None, canonical_url, "missing"


def _observation_from_row(
    row: dict[str, Any], *, path: str, url: str, surface: str, query: str | None,
    observed_at: str, transport: str,
) -> dict[str, Any] | None:
    product_id, canonical_url, identity_basis = _identity(row, url)
    if not product_id:
        return None
    title = _first(row, "name", "title", "productName", "product_name")
    raw_price = _first(row, "priceShow", "price_show", "displayPrice", "display_price", "price")
    raw_original = _first(row, "originalPriceShow", "original_price_show", "originalPrice", "original_price")
    current_price = _explicit_currency(raw_price)
    original_price = _explicit_currency(raw_original)
    rating = _first(row, "ratingScore", "rating_score", "rating", "ratingValue")
    reviews = _first(row, "reviewCount", "review_count", "ratingCount", "rating_count")
    raw_rank = _integer(_first(row, "rank", "itemRank", "item_rank"))
    sort_mode = _first(row, "sortMode", "sort_mode", "selectedSort", "selected_sort")
    rank = raw_rank if raw_rank is not None and str(sort_mode or "").strip() else None
    parsed_counter, counter_semantics = _counter(row)
    if all(value is None for value in (title, raw_price, rating, reviews, rank)) and counter_semantics["counter_type"] == "unknown":
        return None
    price_semantics = "explicit-currency-display" if current_price is not None else (
        "raw-structured-value-scaling-unknown" if raw_price is not None else "not-observed"
    )
    observation = CommerceProductObservation(
        platform=PLATFORM, platform_product_id=product_id,
        seller_id=str(_first(row, "sellerId", "seller_id") or "") or None,
        shop_id=str(_first(row, "shopId", "shop_id") or "") or None,
        title=str(title or "").strip() or None,
        brand=str(_first(row, "brandName", "brand_name", "brand") or "").strip() or None,
        category=str(_first(row, "categoryName", "category_name", "category") or "").strip() or None,
        current_price=current_price, original_price=original_price,
        discount_pct=_number(_first(row, "discountPct", "discount_pct")),
        rating=_number(rating), review_count=_integer(reviews),
        observed_sold_count=parsed_counter["observed_sold_count"],
        sold_count_display=str(counter_semantics["raw_display"]) if counter_semantics["counter_type"] == "sold" else None,
        sold_count_precision=parsed_counter["precision"], source_surface=url,
        source_rank=rank, source_query=query, observed_at=observed_at,
        provenance={
            "source_url": url, "surface_type": surface, "transport": transport, "document_path": path,
            "identity_basis": identity_basis, "canonical_product_url": canonical_url,
            "marketplace_counter": counter_semantics, "counter_is_transaction_ledger": False,
            "raw_price": raw_price, "raw_original_price": raw_original,
            "price_semantics": price_semantics, "price_scaling_validated": current_price is not None,
            "rank_context": {
                "surface": surface, "query": query, "sort_mode": sort_mode,
                "rank": rank, "raw_rank_without_complete_context": raw_rank if rank is None else None,
                "national_rank": False,
            },
        }, publicly_observable=True,
    )
    return asdict(observation)


def normalize_public_json(
    document: Any, *, url: str, surface: str, query: str | None, observed_at: str, max_items: int,
) -> list[dict[str, Any]]:
    output, seen = [], set()
    for path, row in _walk(document):
        normalized = _observation_from_row(
            row, path=path, url=url, surface=surface, query=query,
            observed_at=observed_at, transport="public-http-structured-json",
        )
        if not normalized or normalized["platform_product_id"] in seen:
            continue
        output.append(normalized)
        seen.add(normalized["platform_product_id"])
        if len(output) >= max_items:
            break
    return output


def _script_documents(soup: BeautifulSoup) -> list[tuple[str, Any]]:
    documents = []
    for index, script in enumerate(soup.find_all("script")):
        script_type = str(script.get("type") or "").casefold()
        script_id = str(script.get("id") or "").casefold()
        if "json" not in script_type and script_id not in {"__next_data__", "__nuxt_data__"}:
            continue
        try:
            documents.append((f"html.script[{index}]", json.loads(script.string or script.get_text())))
        except (json.JSONDecodeError, TypeError):
            continue
    return documents


def normalize_public_html(
    text: str, *, url: str, surface: str, query: str | None, observed_at: str, max_items: int,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(text, "html.parser")
    output, seen = [], set()
    for path, document in _script_documents(soup):
        for row in normalize_public_json(
            document, url=url, surface=surface, query=query, observed_at=observed_at,
            max_items=max_items - len(output),
        ):
            if row["platform_product_id"] not in seen:
                output.append(row)
                seen.add(row["platform_product_id"])
        if len(output) >= max_items:
            return output
    for index, anchor in enumerate(soup.find_all("a", href=True)):
        product_id, canonical = product_id_from_url(anchor.get("href"), url)
        if not product_id or product_id in seen:
            continue
        container = anchor
        for _ in range(3):
            container = container.parent or container
        visible = " ".join(container.get_text(" ", strip=True).split())
        title = anchor.get("title") or (anchor.find("img") or {}).get("alt") or " ".join(anchor.get_text(" ", strip=True).split())
        price_match = _CURRENCY_RE.search(visible)
        sold_match = re.search(r"(?:ขายแล้ว|sold)\s*([\d,.]+\s*(?:k|m|พัน|หมื่น|แสน|ล้าน)?\+?)", visible, re.IGNORECASE)
        row = {"productUrl": canonical, "title": title or None}
        if price_match:
            row["priceShow"] = price_match.group(0)
        if sold_match:
            row["soldDisplay"] = sold_match.group(1)
        normalized = _observation_from_row(
            row, path=f"html.anchor[{index}]", url=url, surface=surface, query=query,
            observed_at=observed_at, transport="public-http-visible-html",
        )
        if normalized:
            output.append(normalized)
            seen.add(product_id)
        if len(output) >= max_items:
            break
    return output


def _discover_endpoints(text: str) -> list[dict[str, Any]]:
    values = dict.fromkeys(match.group(1) for match in _ENDPOINT_RE.finditer(text))
    output = []
    for value in list(values)[:20]:
        lowered = value.casefold()
        if "/user/api/" in lowered or any(word in lowered for word in ("login", "register", "password", "oauth")):
            relevance = "account-or-auth-non-commerce"
        elif "/checkout/" in lowered:
            relevance = "checkout-non-observation"
        elif lowered.endswith("sw.js"):
            relevance = "service-worker-non-commerce"
        elif "com.lazada.android" in lowered:
            relevance = "app-navigation-non-commerce"
        elif "/helpcenter/" in lowered:
            relevance = "informational-non-commerce"
        else:
            relevance = "unvalidated-candidate"
        output.append({
            "url_or_path": value[:500], "commerce_relevance": relevance,
            "validated_public_product_data": False,
        })
    return output


def _base_result(*, url: str | None, surface: str | None, query: str | None, max_items: int) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "observed_at": utcnow(), "platform": PLATFORM,
        "mode": "non-production-discovery-diagnostic", "target_url": url,
        "source_surface": surface, "source_query": query, "max_items": max_items,
        "attempted_techniques": ["plain-public-http-static-or-structured"],
        "transport_outcomes": {
            "plain_public_http": {"attempted": False, "status": "not-attempted"},
            "browser_context": {"attempted": False, "status": "not-required-or-tested"},
            "windows_edge_runner": {"attempted": False, "status": "not-required-or-tested"},
        },
        "access_status": "not-attempted", "challenge_detected": False, "challenge_reason": None,
        "discovered_public_endpoints": [], "sample_normalized_records": [],
        "usable_evidence": False, "confidence": "none", "technical_completion": False,
        "failure_reason": None, "production_approved": False, "production_store": False,
        "scheduler_action": None,
    }


def explore(args: argparse.Namespace, *, fetcher=public_http_fetch, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = registry or load_registry()
    url, surface, query = validate_options(args, registry)
    result = _base_result(url=url, surface=surface, query=query, max_items=args.max_items)
    fetched = fetcher(url)
    status = int(fetched.get("status") or 0)
    body = fetched.get("body") or b""
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
    effective_url = fetched.get("effective_url") or url
    challenged, reason = _challenge(text, status, effective_url)
    result["transport_outcomes"]["plain_public_http"] = {
        "attempted": True, "status": status, "effective_url": effective_url,
        "content_type": fetched.get("content_type"), "response_bytes": len(body),
        "response_truncated": bool(fetched.get("truncated")),
    }
    result["access_status"] = "challenge-or-blocked" if challenged else ("reachable" if 200 <= status < 400 else "http-error")
    result["challenge_detected"], result["challenge_reason"] = challenged, reason
    result["discovered_public_endpoints"] = _discover_endpoints(text)
    if not challenged:
        content_type = str(fetched.get("content_type") or "").casefold()
        if "json" in content_type:
            try:
                result["sample_normalized_records"] = normalize_public_json(
                    json.loads(text), url=url, surface=surface, query=query,
                    observed_at=result["observed_at"], max_items=args.max_items,
                )
            except json.JSONDecodeError:
                result["failure_reason"] = "response-claimed-json-but-was-invalid"
        elif "html" in content_type or text.lstrip().startswith("<"):
            result["sample_normalized_records"] = normalize_public_html(
                text, url=url, surface=surface, query=query,
                observed_at=result["observed_at"], max_items=args.max_items,
            )
    result["usable_evidence"] = bool(result["sample_normalized_records"])
    result["technical_completion"] = True
    if result["usable_evidence"]:
        result["confidence"] = "exploratory"
    elif not result["failure_reason"]:
        if challenged:
            result["failure_reason"] = "public-surface-access-challenged-no-circumvention-attempted"
        elif status == 200:
            result["failure_reason"] = "reachable-application-shell-or-page-without-stable-product-signal-evidence"
        else:
            result["failure_reason"] = f"http-{status}-without-stable-product-signal-evidence"
    return result


def _write_evidence(output: Path, result: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv=None, *, fetcher=public_http_fetch) -> int:
    args = parser().parse_args(argv)
    result = _base_result(url=args.url, surface=None, query=args.query or args.category, max_items=args.max_items)
    exit_code = EXIT_TECHNICAL_FAILURE
    try:
        result = explore(args, fetcher=fetcher)
        exit_code = EXIT_EVIDENCE_OBTAINED if result["usable_evidence"] else EXIT_EVIDENCE_WITHHELD
    except Exception as exc:
        result["technical_completion"] = False
        result["failure_reason"] = str(exc)
        result["technical_failure"] = {"type": type(exc).__name__, "message": str(exc)}
    try:
        _write_evidence(args.output, result)
    except Exception as exc:
        print(f"Lazada Commerce Pulse evidence writing failed: {exc}", file=sys.stderr)
        return EXIT_TECHNICAL_FAILURE
    print(json.dumps({
        "schema": result["schema"], "technical_completion": result["technical_completion"],
        "usable_evidence": result["usable_evidence"], "access_status": result["access_status"],
        "challenge_detected": result["challenge_detected"],
        "sample_record_count": len(result["sample_normalized_records"]),
        "production_store": result["production_store"], "output": str(args.output),
        "exit_classification": exit_code,
    }, ensure_ascii=False, sort_keys=True))
    if exit_code != EXIT_EVIDENCE_OBTAINED:
        print(f"Lazada Commerce Pulse evidence withheld: {result.get('failure_reason')}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
