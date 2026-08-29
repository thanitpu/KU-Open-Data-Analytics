from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode, urljoin

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None

try:
    from lotus_advanced import get
except Exception:  # pragma: no cover
    get = None


BOOKING_ORIGIN = "https://www.booking.com"


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _money(text: str) -> tuple[float | None, str | None]:
    text = _clean(text)
    patterns = [
        (r"(?:THB|฿)\s*([0-9][0-9,]*(?:\.\d{1,2})?)", "THB"),
        (r"([0-9][0-9,]*(?:\.\d{1,2})?)\s*(?:THB|บาท)", "THB"),
        (r"(?:US\$|USD\s*)\s*([0-9][0-9,]*(?:\.\d{1,2})?)", "USD"),
        (r"(?:€|EUR\s*)\s*([0-9][0-9,]*(?:\.\d{1,2})?)", "EUR"),
    ]
    for pat, currency in patterns:
        m = re.search(pat, text, re.I)
        if not m:
            continue
        try:
            v = float(m.group(1).replace(",", ""))
            if v > 0:
                return v, currency
        except Exception:
            pass
    return None, None


def booking_search_url(*, destination: str, check_in: str, check_out: str, adults: int = 2,
                       rooms: int = 1, children: int = 0, currency: str = "THB") -> str:
    params = {
        "ss": destination,
        "checkin": check_in,
        "checkout": check_out,
        "group_adults": max(1, int(adults)),
        "no_rooms": max(1, int(rooms)),
        "group_children": max(0, int(children)),
        "selected_currency": currency.upper(),
        "lang": "en-us",
    }
    return BOOKING_ORIGIN + "/searchresults.html?" + urlencode(params)


def default_query_context(destination: str = "Bangkok", *, days_ahead: int = 30, nights: int = 1,
                          adults: int = 2, rooms: int = 1, children: int = 0,
                          currency: str = "THB", today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    ci = today + timedelta(days=max(1, int(days_ahead)))
    co = ci + timedelta(days=max(1, int(nights)))
    return {
        "destination_or_property": destination,
        "check_in": ci.isoformat(),
        "check_out": co.isoformat(),
        "occupancy": {"adults": max(1, int(adults)), "children": max(0, int(children)), "rooms": max(1, int(rooms))},
        "currency": currency.upper(),
    }


def _first(card, selector: str):
    if not card:
        return None
    try:
        return card.select_one(selector)
    except Exception:
        return None


def _node_text(node) -> str:
    if not node:
        return ""
    try:
        return _clean(" ".join(node.stripped_strings))
    except Exception:
        return _clean(node)


def _property_identity(url: str, name: str) -> str:
    m = re.search(r"/hotel/[^/]+/([^/?#]+)", url or "", re.I)
    if m:
        return m.group(1).lower()
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:160]


def _rating(card) -> tuple[float | None, int | None]:
    node = _first(card, '[data-testid="review-score"]')
    text = _node_text(node)
    score = None; reviews = None
    m = re.search(r"\b([1-9](?:\.\d)?|10(?:\.0)?)\b", text)
    if m:
        try: score = float(m.group(1))
        except Exception: pass
    m = re.search(r"([0-9][0-9,]*)\s+reviews?", text, re.I)
    if m:
        try: reviews = int(m.group(1).replace(",", ""))
        except Exception: pass
    return score, reviews


def _card_records(card, context: dict, source_url: str, observed_at: str) -> list[dict]:
    title_node = _first(card, '[data-testid="title"]')
    link_node = _first(card, '[data-testid="title-link"]') or (title_node.find_parent("a") if title_node else None)
    name = _node_text(title_node)
    href = _clean(link_node.get("href") if link_node and hasattr(link_node, "get") else "")
    property_url = urljoin(BOOKING_ORIGIN, href) if href else ""
    if not name or not property_url:
        return []
    prop_id = _property_identity(property_url, name)
    address = _node_text(_first(card, '[data-testid="address"]'))
    distance = _node_text(_first(card, '[data-testid="distance"]'))
    score, reviews = _rating(card)
    out = [{
        "record_type": "PropertyCandidate",
        "property_id": prop_id,
        "property_name": name[:300],
        "property_url": property_url,
        "address": address[:300] or None,
        "distance_text": distance[:200] or None,
        "review_score": score,
        "review_count": reviews,
        "source_url": source_url,
        "source": "Booking.com",
        "provenance": "booking-public-search-card",
        "observed_at": observed_at,
    }]

    price_node = _first(card, '[data-testid="price-and-discounted-price"]')
    price_text = _node_text(price_node)
    price, detected_currency = _money(price_text)
    # Only a rate query with explicit stay/occupancy/currency context may create a RateObservation.
    required = all(context.get(k) for k in ("check_in", "check_out", "occupancy", "currency"))
    if price is not None and required:
        requested_currency = str(context.get("currency") or "").upper()
        if detected_currency and requested_currency and detected_currency != requested_currency:
            # Preserve evidence as property discovery but do not claim a comparable requested-currency rate.
            return out
        visible = _node_text(card)
        taxes = None
        tax_m = re.search(r"(?:taxes and fees|taxes|fees)[^0-9]{0,20}(?:THB|฿)?\s*([0-9][0-9,]*(?:\.\d+)?)", visible, re.I)
        if tax_m:
            try: taxes = float(tax_m.group(1).replace(",", ""))
            except Exception: taxes = None
        out.append({
            "record_type": "RateObservation",
            "property_id": prop_id,
            "property_name": name[:300],
            "property_url": property_url,
            "price": price,
            "currency": requested_currency or detected_currency,
            "price_text": price_text[:240],
            "taxes_and_fees": taxes,
            "check_in": context.get("check_in"),
            "check_out": context.get("check_out"),
            "occupancy": context.get("occupancy"),
            "destination_or_property": context.get("destination_or_property"),
            "source_url": source_url,
            "source": "Booking.com",
            "provenance": "booking-public-search-rate",
            "observed_at": observed_at,
        })
    return out


def booking_search_records(html: str, context: dict, source_url: str, observed_at: str | None = None) -> dict:
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    if not BeautifulSoup or not html:
        return {"records": [], "diagnostics": {"property_cards": 0, "parser": "unavailable"}}
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select('[data-testid="property-card"]')
    records: list[dict] = []
    for card in cards:
        records.extend(_card_records(card, context, source_url, observed_at))
    properties = [x for x in records if x.get("record_type") == "PropertyCandidate"]
    rates = [x for x in records if x.get("record_type") == "RateObservation"]
    return {
        "records": records,
        "diagnostics": {
            "property_cards": len(cards),
            "property_records": len(properties),
            "rate_records": len(rates),
            "rate_completeness_pct": round(100 * len(rates) / len(properties), 1) if properties else 0,
            "parser": "booking-data-testid-cards",
        },
    }


def booking_public_search(context: dict | None = None, *, destination: str = "Bangkok", timeout: int = 15) -> dict:
    context = dict(context or default_query_context(destination))
    occ = context.get("occupancy") or {}
    url = booking_search_url(
        destination=context.get("destination_or_property") or destination,
        check_in=context.get("check_in"), check_out=context.get("check_out"),
        adults=occ.get("adults", 2), rooms=occ.get("rooms", 1), children=occ.get("children", 0),
        currency=context.get("currency") or "THB",
    )
    if not get:
        return {"ok": False, "error": "HTTP helper unavailable", "source_url": url, "query_context": context, "records": []}
    started = time.monotonic()
    r = get(url, timeout=timeout)
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error"), "source_url": url, "final_url": r.get("final_url"),
                "status": r.get("status"), "query_context": context, "records": [],
                "elapsed_seconds": round(time.monotonic() - started, 3)}
    parsed = booking_search_records(r.get("text") or "", context, r.get("final_url") or url)
    return {
        "ok": True, "source_url": url, "final_url": r.get("final_url") or url, "status": r.get("status"),
        "bytes": r.get("bytes"), "query_context": context, "records": parsed["records"],
        "diagnostics": parsed["diagnostics"], "elapsed_seconds": round(time.monotonic() - started, 3),
        "guardrail": "Public Booking.com search surface only; no login, member-rate use, CAPTCHA solving, or access-control bypass.",
    }


def record_key(record: dict) -> str:
    rt = record.get("record_type")
    if rt == "RateObservation":
        return "|".join(str(record.get(k) or "") for k in ("property_id", "check_in", "check_out", "currency"))
    return str(record.get("property_id") or record.get("property_url") or record.get("property_name") or "")


def audit_booking_runs(first: dict, second: dict, minimum_records: int = 5) -> dict:
    r1 = first.get("records") or []; r2 = second.get("records") or []
    p1 = [x for x in r1 if x.get("record_type") == "PropertyCandidate"]
    rates1 = [x for x in r1 if x.get("record_type") == "RateObservation"]
    keys1 = {record_key(x) for x in p1 if record_key(x)}
    keys2 = {record_key(x) for x in (second.get("records") or []) if x.get("record_type") == "PropertyCandidate" and record_key(x)}
    overlap = len(keys1 & keys2)
    repeat = round(100 * overlap / min(len(keys1), len(keys2)), 1) if keys1 and keys2 else 0
    provenance = round(100 * sum(bool(x.get("provenance")) for x in r1) / len(r1), 1) if r1 else 0
    context_complete = all((first.get("query_context") or {}).get(k) for k in ("check_in", "check_out", "occupancy", "currency"))
    rate_pct = round(100 * len(rates1) / len(p1), 1) if p1 else 0
    gates = {
        "access": bool(first.get("ok") and second.get("ok")),
        "minimum_offer_records": len(p1) >= minimum_records,
        "rate_completeness": rate_pct >= 70,
        "query_context_completeness": context_complete,
        "repeatability": repeat >= 70,
        "provenance": provenance >= 95,
    }
    failures = [k for k, v in gates.items() if not v]
    return {
        "audit_passed": not failures,
        "gate_checks": gates,
        "hard_failures": failures,
        "yield": {"property_records": len(p1), "rate_records": len(rates1)},
        "field_quality": {"rate_completeness_pct": rate_pct, "provenance_pct": provenance,
                          "query_context_complete": context_complete},
        "repeatability": {"property_repeatability_pct": repeat, "first_unique": len(keys1),
                          "second_unique": len(keys2), "overlap": overlap},
        "query_context": first.get("query_context"),
        "technique": "booking_public_search",
        "guardrail": "Pass requires explicit stay dates, occupancy and currency. Public rates only; member/login-only rates are excluded.",
    }
