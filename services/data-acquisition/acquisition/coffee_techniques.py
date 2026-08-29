from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None

try:
    from lotus_advanced import get
except Exception:  # pragma: no cover
    get = None

PUNTHAI_ORIGIN = "https://www.punthaicoffee.com"
PUNTHAI_MENU_SEEDS = [
    PUNTHAI_ORIGIN + "/en/product/coffee/hot-espresso",
    PUNTHAI_ORIGIN + "/en/product/coffee/espresso",
    PUNTHAI_ORIGIN + "/en/product/coffee/iced-americano",
    PUNTHAI_ORIGIN + "/en/product/coffee/hot-americano",
    PUNTHAI_ORIGIN + "/en/product/coffee/hot-latte",
    PUNTHAI_ORIGIN + "/en/product/coffee/hot-thairicano",
]


def _clean(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _baht_price(text: str) -> float | None:
    for pat in (
        r"(?:Price|ราคา)\s*[:：]?\s*([0-9][0-9,.]*)\s*(?:Baht|บาท)",
        r"(?:฿|THB)\s*([0-9][0-9,.]*)",
        r"([0-9][0-9,.]*)\s*(?:Baht|บาท)",
    ):
        m = re.search(pat, text or "", re.I)
        if not m:
            continue
        try:
            n = float(m.group(1).replace(",", ""))
            if 10 <= n <= 10000:
                return n
        except Exception:
            pass
    return None


def _size(text: str) -> str | None:
    m = re.search(r"(?:Size|ขนาด)\s*[:：]?\s*([0-9]+(?:\.\d+)?)\s*(Oz\.?|ml\.?|มล\.?)", text or "", re.I)
    return (_clean(m.group(1)) + " " + _clean(m.group(2))) if m else None


def _jsonld_menu(html: str) -> dict | None:
    if not BeautifulSoup or not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = tag.string or tag.get_text() or ""
        try: obj = json.loads(raw)
        except Exception: continue
        stack = obj if isinstance(obj, list) else [obj]
        while stack:
            x = stack.pop()
            if isinstance(x, list): stack.extend(x); continue
            if not isinstance(x, dict): continue
            if isinstance(x.get("@graph"), list): stack.extend(x["@graph"])
            typ = x.get("@type")
            types = {str(t).lower() for t in typ} if isinstance(typ, list) else {str(typ).lower()}
            if types & {"product", "menuitem"}:
                return x
    return None


def punthai_menu_record(html: str, url: str, observed_at: str | None = None) -> dict | None:
    if not html:
        return None
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    soup = BeautifulSoup(html, "html.parser") if BeautifulSoup else None
    text = _clean(soup.get_text("\n", strip=True) if soup else re.sub(r"<[^>]+>", " ", html))
    obj = _jsonld_menu(html) or {}
    name = _clean(obj.get("name"))
    if not name and soup:
        h = soup.find("h1")
        if h: name = _clean(" ".join(h.stripped_strings))
    if not name and soup:
        meta = soup.find("meta", attrs={"property": "og:title"})
        if meta: name = re.sub(r"\s*[|–-].*$", "", _clean(meta.get("content"))).strip()
    price = None
    offers = obj.get("offers") if isinstance(obj, dict) else None
    for offer in (offers if isinstance(offers, list) else [offers]):
        if not isinstance(offer, dict): continue
        try:
            v = float(str(offer.get("price") or "").replace(",", ""))
            if v > 0: price = v; break
        except Exception: pass
    price = price if price is not None else _baht_price(text)
    if not name or price is None:
        return None
    category = _clean(obj.get("category")) if isinstance(obj, dict) else ""
    if not category:
        # The detail page places the category/ingredient line near the item title.
        m = re.search(re.escape(name) + r"\s+([^\n]{2,120}?)\s+(?:Price|ราคา)", text, re.I)
        category = _clean(m.group(1)) if m else ""
    return {
        "record_type": "MenuItemCandidate",
        "menu_item_id": urlparse(url).path.rstrip("/").split("/")[-1].lower(),
        "menu_item_name": name[:240],
        "category": category[:180] or None,
        "price": price,
        "currency": "THB",
        "size": _size(text),
        "source_url": url,
        "source": "PunThai Coffee",
        "provenance": "punthai-official-menu-detail",
        "observed_at": observed_at,
    }


def punthai_detail_links(html: str, base_url: str) -> list[str]:
    if not BeautifulSoup or not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        u = urljoin(base_url, a.get("href") or "")
        p = urlparse(u)
        if p.netloc.lower().removeprefix("www.") != "punthaicoffee.com":
            continue
        if "/product/" not in p.path.lower():
            continue
        u = p._replace(query="", fragment="").geturl()
        if u not in out: out.append(u)
    return out


def punthai_menu_catalog(*, seed_urls: list[str] | None = None, max_items: int = 12, timeout: int = 12) -> dict:
    seeds = list(seed_urls or PUNTHAI_MENU_SEEDS)
    queue = list(dict.fromkeys(seeds)); seen = set(); rows = []; diagnostics = []
    started = time.monotonic(); budget = max(40, min(150, max_items * 12))
    while queue and len(rows) < max_items and time.monotonic() - started < budget:
        u = queue.pop(0)
        if u in seen: continue
        seen.add(u)
        if not get:
            diagnostics.append({"url": u, "status": "http-helper-unavailable"}); break
        r = get(u, timeout=timeout)
        if not r.get("ok"):
            diagnostics.append({"url": u, "status": "failed", "http_status": r.get("status"), "error": r.get("error")})
            continue
        final = r.get("final_url") or u; html = r.get("text") or ""
        rec = punthai_menu_record(html, final)
        if rec:
            rows.append(rec)
            diagnostics.append({"url": final, "status": "materialized", "name": rec.get("menu_item_name"), "price": rec.get("price")})
        else:
            diagnostics.append({"url": final, "status": "no-menu-record", "bytes": r.get("bytes")})
        for link in punthai_detail_links(html, final)[:25]:
            if link not in seen and link not in queue and len(queue) < 80:
                queue.append(link)
    # Stable deterministic identity ordering for repeat audit.
    by_id = {}
    for r in rows:
        by_id[r["menu_item_id"]] = r
    rows = sorted(by_id.values(), key=lambda x: x["menu_item_id"])[:max_items]
    return {
        "ok": bool(rows), "records": rows, "diagnostics": diagnostics,
        "metrics": {
            "menu_records": len(rows), "price_completeness_pct": 100.0 if rows else 0.0,
            "provenance_pct": 100.0 if rows else 0.0, "urls_tested": len(seen),
        },
        "operational_config": {"seed_urls": seeds, "max_items": max_items, "official_domain": "punthaicoffee.com"},
        "guardrail": "Current official PunThai public menu detail pages only; no delivery-platform prices or cached search prices are stored.",
    }


def audit_punthai_runs(first: dict, second: dict, minimum_records: int = 5) -> dict:
    r1 = first.get("records") or []; r2 = second.get("records") or []
    k1 = {str(x.get("menu_item_id") or "") for x in r1 if x.get("menu_item_id")}
    k2 = {str(x.get("menu_item_id") or "") for x in r2 if x.get("menu_item_id")}
    repeat = round(100 * len(k1 & k2) / min(len(k1), len(k2)), 1) if k1 and k2 else 0.0
    price_pct = round(100 * sum(x.get("price") is not None for x in r1) / len(r1), 1) if r1 else 0.0
    provenance_pct = round(100 * sum(bool(x.get("provenance")) for x in r1) / len(r1), 1) if r1 else 0.0
    gates = {
        "access_and_yield": bool(first.get("ok") and second.get("ok")),
        "minimum_menu_records": len(r1) >= minimum_records,
        "price_completeness": price_pct >= 70,
        "semantic_quality": all(bool(x.get("menu_item_name")) and 10 <= float(x.get("price") or 0) <= 10000 for x in r1),
        "repeatability": repeat >= 70,
        "provenance": provenance_pct >= 95,
    }
    failures = [k for k, v in gates.items() if not v]
    return {
        "audit_passed": not failures, "gate_checks": gates, "hard_failures": failures,
        "yield": {"menu_records": len(r1)},
        "field_quality": {"price_completeness_pct": price_pct, "provenance_pct": provenance_pct},
        "repeatability": {"menu_repeatability_pct": repeat, "first_unique": len(k1), "second_unique": len(k2), "overlap": len(k1 & k2)},
        "technique": "punthai_official_menu_detail",
    }
