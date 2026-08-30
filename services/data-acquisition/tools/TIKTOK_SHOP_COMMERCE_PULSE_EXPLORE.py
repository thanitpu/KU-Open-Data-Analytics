"""Bounded non-production TikTok Shop Thailand public-surface explorer."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
if str(ACQUISITION) not in sys.path:
    sys.path.insert(0, str(ACQUISITION))

from tiktok_shop_commerce_pulse import OFFICIAL_HOSTS, normalize_html, normalize_json, utcnow


SCHEMA = "ku2d.tiktok-shop-commerce-pulse-explore.v1"
MAX_BODY_BYTES = 2_000_000
EXIT_EVIDENCE_OBTAINED = 0
EXIT_TECHNICAL_FAILURE = 1
EXIT_EVIDENCE_WITHHELD = 2


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Bounded TikTok Shop Commerce Pulse exploration")
    value.add_argument("--url")
    value.add_argument("--query")
    value.add_argument("--max-items", type=int, default=10)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--no-production-store", action="store_true")
    return value


def validate_options(args: argparse.Namespace) -> tuple[str, str, str | None]:
    if not args.no_production_store:
        raise ValueError("--no-production-store is required.")
    if args.max_items < 1 or args.max_items > 10:
        raise ValueError("--max-items must be between 1 and 10.")
    if bool(args.url) == bool(args.query):
        raise ValueError("Provide exactly one of --url or --query.")
    query = args.query.strip() if args.query else None
    url = args.url.strip() if args.url else f"https://shop.tiktok.com/th/k/{quote(query or '')}"
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in OFFICIAL_HOSTS:
        raise ValueError("Only official public HTTPS TikTok Shop customer surfaces are allowed.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in URLs are prohibited.")
    surface = "keyword-search" if query else ("product-detail" if "/pdp/" in parsed.path or "/product/" in parsed.path else "explicit-public-url")
    return url, surface, query


def public_http_fetch(url: str, timeout: int = 20) -> dict:
    request = Request(url, headers={
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.5",
        "User-Agent": "KU2D-Public-Surface-Research/1.0 (+non-production; no-auth)",
    }, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(MAX_BODY_BYTES + 1)
            return {"status": int(response.status), "effective_url": response.geturl(),
                    "content_type": response.headers.get("Content-Type"),
                    "body": body[:MAX_BODY_BYTES], "truncated": len(body) > MAX_BODY_BYTES}
    except HTTPError as exc:
        body = exc.read(MAX_BODY_BYTES + 1)
        return {"status": int(exc.code), "effective_url": exc.geturl(),
                "content_type": exc.headers.get("Content-Type") if exc.headers else None,
                "body": body[:MAX_BODY_BYTES], "truncated": len(body) > MAX_BODY_BYTES}
    except URLError as exc:
        raise RuntimeError(f"Public HTTP transport failed: {exc.reason}") from exc


def challenge_status(text: str, status: int, effective_url: str) -> tuple[bool, str | None]:
    lowered = (text + " " + effective_url).casefold()
    if status in {401, 403, 429}:
        return True, f"http-{status}-access-control-or-rate-limit"
    markers = ("captcha", "verify you are human", "security verification", "unusual traffic",
               "login required", "เข้าสู่ระบบเพื่อดำเนินการต่อ")
    if any(marker in lowered for marker in markers):
        return True, "challenge-or-required-login-marker"
    return False, None


def base_result(url=None, surface=None, query=None, max_items=10) -> dict:
    return {
        "schema": SCHEMA, "observed_at": utcnow(), "platform": "tiktok-shop-thailand",
        "mode": "bounded-public-surface-explore", "target_url": url,
        "source_surface": surface, "source_query": query, "max_items": max_items,
        "request_count": 0, "access_status": "not-attempted", "challenge_detected": False,
        "challenge_reason": None, "sample_normalized_records": [], "usable_evidence": False,
        "technical_completion": False, "browser_required": None, "edge_required": False,
        "official_api_classification": "seller-creator-or-partner-authorized-not-national-public-feed",
        "failure_reason": None, "production_approved": False, "production_store": False,
        "scheduler_action": None,
    }


def explore(args: argparse.Namespace, *, fetcher=public_http_fetch) -> dict:
    url, surface, query = validate_options(args)
    result = base_result(url, surface, query, args.max_items)
    fetched = fetcher(url)
    result["request_count"] = 1
    status = int(fetched.get("status") or 0)
    body = fetched.get("body") or b""
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
    effective_url = str(fetched.get("effective_url") or url)
    challenged, reason = challenge_status(text, status, effective_url)
    result.update({
        "target_url": effective_url, "http_status": status,
        "content_type": fetched.get("content_type"), "response_bytes": len(body),
        "response_truncated": bool(fetched.get("truncated")),
        "access_status": "challenge-or-blocked" if challenged else ("reachable" if 200 <= status < 400 else "http-error"),
        "challenge_detected": challenged, "challenge_reason": reason,
    })
    if not challenged:
        content_type = str(fetched.get("content_type") or "").casefold()
        if "json" in content_type:
            result["sample_normalized_records"] = normalize_json(
                json.loads(text), page_url=effective_url, source_surface=surface, query=query,
                observed_at=result["observed_at"], max_items=args.max_items)
        elif "html" in content_type or text.lstrip().startswith("<"):
            result["sample_normalized_records"] = normalize_html(
                text, page_url=effective_url, source_surface=surface, query=query,
                observed_at=result["observed_at"], max_items=args.max_items)
    result["usable_evidence"] = bool(result["sample_normalized_records"])
    result["technical_completion"] = True
    result["browser_required"] = False if result["usable_evidence"] else (not challenged and status == 200)
    if challenged:
        result["failure_reason"] = "public-access-boundary-reached-no-circumvention-attempted"
    elif not result["usable_evidence"]:
        result["failure_reason"] = "reachable-page-without-stable-public-product-signal-evidence"
    return result


def main(argv=None, *, fetcher=public_http_fetch) -> int:
    args = parser().parse_args(argv)
    result = base_result(args.url, None, args.query, args.max_items)
    code = EXIT_TECHNICAL_FAILURE
    try:
        result = explore(args, fetcher=fetcher)
        code = EXIT_EVIDENCE_OBTAINED if result["usable_evidence"] else EXIT_EVIDENCE_WITHHELD
    except Exception as exc:
        result["failure_reason"] = str(exc)
        result["technical_failure"] = {"type": type(exc).__name__, "message": str(exc)}
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"TikTok Shop evidence writing failed: {exc}", file=sys.stderr)
        return EXIT_TECHNICAL_FAILURE
    print(json.dumps({
        "schema": result["schema"], "exit_classification": code,
        "technical_completion": result["technical_completion"],
        "usable_evidence": result["usable_evidence"], "access_status": result["access_status"],
        "record_count": len(result["sample_normalized_records"]),
        "request_count": result["request_count"], "production_store": result["production_store"],
        "scheduler_action": result["scheduler_action"], "output": str(args.output),
    }, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
