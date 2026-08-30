"""Bounded, non-production Shopee Thailand public-surface explorer.

The tool records diagnostic evidence before returning. Exit 0 means usable
identity + marketplace-signal evidence was normalized; exit 2 means the probe
completed but evidence was insufficient/blocked; exit 1 is a technical or
evidence-writing failure. It never authenticates, solves challenges, or stores
production state.
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
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
if str(ACQUISITION) not in sys.path:
    sys.path.insert(0, str(ACQUISITION))

from commerce_market_observation import CommerceProductObservation, parse_sold_count


EXIT_EVIDENCE_OBTAINED = 0
EXIT_TECHNICAL_FAILURE = 1
EXIT_EVIDENCE_WITHHELD = 2
SCHEMA = "ku2d.shopee-commerce-pulse-explore.v1"
REGISTRY_PATH = ROOT / "config" / "shopee_commerce_pulse_sources.json"
MAX_BODY_BYTES = 2_000_000


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Bounded Shopee Commerce Pulse public-surface exploration")
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
        url = args.url.strip()
        return url, "explicit-public-url", None
    if args.query:
        return f"https://shopee.co.th/search?keyword={quote_plus(args.query.strip())}", "keyword-search", args.query.strip()
    category = args.category.strip().casefold()
    seeds = {row["category_id"].casefold(): row for row in registry["pilot_seed_registry"]["categories"]}
    if category not in seeds:
        raise ValueError(f"Unknown category seed: {args.category}")
    seed = seeds[category]
    query = seed["thai_queries"][0]
    return f"https://shopee.co.th/search?keyword={quote_plus(query)}", "category-seed-search", query


def validate_options(args: argparse.Namespace, registry: dict[str, Any]) -> tuple[str, str, str | None]:
    if not args.no_production_store:
        raise ValueError("--no-production-store is required.")
    maximum = int(registry["pilot_limits"]["max_items"])
    if args.max_items < 1 or args.max_items > maximum:
        raise ValueError(f"--max-items must be between 1 and {maximum}.")
    url, surface, query = target_url(args, registry)
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in {"shopee.co.th", "www.shopee.co.th"}:
        raise ValueError("Only public HTTPS Shopee Thailand customer surfaces are allowed.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in URLs are prohibited.")
    return url, surface, query


def public_http_fetch(url: str, timeout: int = 20) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.5",
            "User-Agent": "KU2D-Public-Surface-Research/1.0 (+non-production; no-auth)",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(MAX_BODY_BYTES + 1)
            truncated = len(body) > MAX_BODY_BYTES
            return {
                "status": int(response.status),
                "effective_url": response.geturl(),
                "content_type": response.headers.get("Content-Type"),
                "body": body[:MAX_BODY_BYTES],
                "truncated": truncated,
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
    challenge_markers = (
        "verify you are human", "captcha verification", "captcha challenge",
        "robot verification", "security verification", "login required",
        "ตรวจสอบว่าคุณเป็นมนุษย์", "ยืนยันตัวตน",
    )
    if "/verify/traffic/" in str(effective_url).casefold():
        return True, "redirected-to-shopee-traffic-verification"
    detected = status in {401, 403, 429} or any(marker in lowered for marker in challenge_markers)
    if status in {401, 403, 429}:
        return True, f"http-{status}-access-control-or-rate-limit"
    if detected:
        return True, "challenge-marker-in-response"
    return False, None


_ENDPOINT_RE = re.compile(r"(?:https://shopee\.co\.th)?(/api/v\d+/[A-Za-z0-9_?=&%./-]+)", re.IGNORECASE)
_FIELD_NAMES = (
    "itemid", "item_id", "product_id", "shopid", "shop_id", "seller_id",
    "historical_sold", "sold", "sold_count", "sold_display", "price",
    "price_before_discount", "rating", "review_count", "catid", "category",
)


def _discover_endpoints(text: str) -> list[dict[str, Any]]:
    endpoints = []
    for value in dict.fromkeys(match.group(1) for match in _ENDPOINT_RE.finditer(text)):
        navigation_only = "/pages/is_short_url" in value
        endpoints.append({
            "url_or_path": value[:500],
            "commerce_relevance": "navigation-only" if navigation_only else "unvalidated-candidate",
            "validated_public_product_data": False,
        })
    return endpoints[:20]


def _detected_fields(text: str) -> list[str]:
    found = []
    for name in _FIELD_NAMES:
        if re.search(rf'["\']{re.escape(name)}["\']\s*:', text, re.IGNORECASE):
            found.append(name)
    return sorted(set(found))


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
            return row.get(key)
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


def normalize_public_json(
    document: Any, *, url: str, surface: str, query: str | None,
    observed_at: str, max_items: int,
) -> list[dict[str, Any]]:
    """Conservatively normalize product-like public JSON objects.

    Numeric API price scaling is not guessed; the raw value and uncertainty are
    retained in provenance. A record requires a stable item identity plus at
    least one marketplace signal (sold display/count, rank, rating, or reviews).
    """
    output, seen = [], set()
    for path, row in _walk(document):
        product_id = _first(row, "itemid", "item_id", "product_id")
        if product_id is None or str(product_id) in seen:
            continue
        sold_display = _first(row, "sold_display", "sold_count_display")
        sold_raw = _first(row, "historical_sold", "sold_count", "sold")
        parsed = parse_sold_count(str(sold_display)) if sold_display is not None else {
            "observed_sold_count": _integer(sold_raw),
            "raw_display": str(sold_raw) if sold_raw is not None else "",
            "precision": "unknown" if sold_raw is not None else "unknown",
        }
        rating_value = _first(row, "rating", "rating_star")
        if isinstance(rating_value, dict):
            rating_value = _first(rating_value, "rating_star", "value")
        reviews = _first(row, "review_count", "rating_count")
        if isinstance(reviews, list):
            reviews = sum(_integer(value) or 0 for value in reviews)
        source_rank = _integer(_first(row, "rank", "item_rank"))
        if all(value is None for value in (sold_raw, sold_display, rating_value, reviews, source_rank)):
            continue
        current_price = _number(_first(row, "price", "current_price"))
        original_price = _number(_first(row, "price_before_discount", "original_price"))
        observation = CommerceProductObservation(
            platform="shopee-thailand", platform_product_id=str(product_id),
            seller_id=str(_first(row, "seller_id") or "") or None,
            shop_id=str(_first(row, "shopid", "shop_id") or "") or None,
            title=str(_first(row, "name", "title") or "") or None,
            brand=str(_first(row, "brand") or "") or None,
            category=str(_first(row, "category", "catid") or "") or None,
            current_price=current_price, original_price=original_price,
            discount_pct=_number(_first(row, "discount_pct")),
            rating=_number(rating_value), review_count=_integer(reviews),
            observed_sold_count=parsed["observed_sold_count"],
            sold_count_display=str(sold_display) if sold_display is not None else None,
            sold_count_precision=parsed["precision"], source_surface=surface,
            source_rank=source_rank, source_query=query, observed_at=observed_at,
            provenance={
                "source_url": url, "transport": "public-http-json", "json_path": path,
                "price_scale": "unknown-do-not-use-as-currency-until-validated",
                "sold_counter_is_transaction_ledger": False,
            },
            publicly_observable=True,
        )
        output.append(asdict(observation))
        seen.add(str(product_id))
        if len(output) >= max_items:
            break
    return output


def _base_result(*, url: str | None, surface: str | None, query: str | None, max_items: int) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "observed_at": utcnow(), "platform": "shopee-thailand",
        "mode": "non-production-discovery-diagnostic", "target_url": url,
        "source_surface": surface, "source_query": query, "max_items": max_items,
        "attempted_techniques": ["public-http-static-or-json"],
        "transport_outcomes": {
            "normal_local_http": {"attempted": False, "status": "not-attempted"},
            "browser_context": {"attempted": False, "status": "not-attempted"},
            "windows_edge_runner": {"attempted": False, "status": "not-required-or-tested"},
            "github_hosted_runner": {"attempted": False, "status": "not-tested-by-local-tool"},
        },
        "access_status": "not-attempted", "challenge_detected": False,
        "challenge_reason": None, "discovered_public_endpoints": [], "detected_fields": [],
        "sample_normalized_records": [], "usable_evidence": False, "confidence": "none",
        "technical_completion": False, "failure_reason": None,
        "production_approved": False, "production_store": False, "scheduler_action": None,
    }


def explore(args: argparse.Namespace, *, fetcher=public_http_fetch, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = registry or load_registry()
    url, surface, query = validate_options(args, registry)
    result = _base_result(url=url, surface=surface, query=query, max_items=args.max_items)
    fetched = fetcher(url)
    status = int(fetched.get("status") or 0)
    body = fetched.get("body") or b""
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
    challenged, challenge_reason = _challenge(text, status, fetched.get("effective_url") or url)
    result["transport_outcomes"]["normal_local_http"] = {
        "attempted": True, "status": status, "effective_url": fetched.get("effective_url") or url,
        "content_type": fetched.get("content_type"), "response_bytes": len(body),
        "response_truncated": bool(fetched.get("truncated")),
    }
    result["access_status"] = "challenge-or-blocked" if challenged else ("reachable" if 200 <= status < 400 else "http-error")
    result["challenge_detected"] = challenged
    result["challenge_reason"] = challenge_reason
    result["discovered_public_endpoints"] = _discover_endpoints(text)
    result["detected_fields"] = _detected_fields(text)
    content_type = str(fetched.get("content_type") or "").casefold()
    document = None
    if "json" in content_type:
        try:
            document = json.loads(text)
        except json.JSONDecodeError:
            result["failure_reason"] = "response-claimed-json-but-was-invalid"
    if document is not None and not challenged:
        result["sample_normalized_records"] = normalize_public_json(
            document, url=url, surface=surface, query=query,
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
            result["failure_reason"] = "reachable-application-shell-or-page-without-usable-product-signal-evidence"
        else:
            result["failure_reason"] = f"http-{status}-without-usable-product-signal-evidence"
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
        print(f"Shopee Commerce Pulse evidence writing failed: {exc}", file=sys.stderr)
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
        print(f"Shopee Commerce Pulse evidence withheld: {result.get('failure_reason')}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
