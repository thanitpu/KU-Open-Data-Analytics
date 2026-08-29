from __future__ import annotations

import json
import re
import time
from urllib.parse import urljoin, urlparse, urlunparse

from supermarket_techniques import BeautifulSoup, GOURMET_HOME, _clean, _dedup, _money_values
from lotus_advanced import get

# Discovery seeds only. Prices are NEVER taken from this list; every observation
# must be materialized from the current official product page at run time.
GOURMET_DETAIL_SEEDS = [
    "https://gourmetmarketthailand.com/en/allowrie_unsalted_butter_10g_pack_8_8850332162158",
    "https://gourmetmarketthailand.com/th/gourmet_fresh_holy_basil_100g_63423",
    "https://gourmetmarketthailand.com/en/doi_chang_roastground_espresso_supreme_250g_8856709000498",
    "https://gourmetmarketthailand.com/en/doi_chang_roast__ground_premium_classic_250g_8856709000467",
    "https://gourmetmarketthailand.com/en/doi_chang_organic_signature_250g_8856709000481",
]


def _canonical(url: str) -> str:
    p = urlparse(url or "")
    path = re.sub(r"^/en(?=/)", "/th", p.path, flags=re.I)
    return urlunparse((p.scheme or "https", p.netloc, path, "", "", ""))


def _identity_from_url(url: str) -> str:
    slug = urlparse(url or "").path.rstrip("/").split("/")[-1]
    m = re.search(r"(?:_|-)(\d{8,14})$", slug)
    if m:
        return m.group(1)
    m = re.search(r"(?:_|-)(\d{4,7})$", slug)
    return m.group(1) if m else ""


def _jsonld_products(html: str) -> list[dict]:
    if not BeautifulSoup or not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tag in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = tag.string or tag.get_text() or ""
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        stack = obj if isinstance(obj, list) else [obj]
        while stack:
            x = stack.pop()
            if isinstance(x, list):
                stack.extend(x)
                continue
            if not isinstance(x, dict):
                continue
            graph = x.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)
            typ = x.get("@type")
            types = {str(v).lower() for v in typ} if isinstance(typ, list) else {str(typ).lower()}
            if "product" in types:
                out.append(x)
    return out


def _brand_value(value) -> str:
    if isinstance(value, dict):
        return _clean(value.get("name") or value.get("brand") or "")
    return _clean(value)


def _offer_price(offers):
    candidates = offers if isinstance(offers, list) else [offers]
    for offer in candidates:
        if not isinstance(offer, dict):
            continue
        for key in ("price", "lowPrice", "salePrice"):
            v = offer.get(key)
            try:
                if v is not None and float(str(v).replace(",", "")) > 0:
                    return float(str(v).replace(",", ""))
            except Exception:
                pass
    return None


def _visible_name(soup, html: str) -> str:
    if soup:
        h = soup.find("h1")
        if h:
            name = _clean(" ".join(h.stripped_strings))
            if name:
                return name
        meta = soup.find("meta", attrs={"property": "og:title"}) or soup.find("meta", attrs={"name": "twitter:title"})
        if meta and meta.get("content"):
            return re.sub(r"\s*[|–-].*$", "", _clean(meta.get("content"))).strip()
    m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.I | re.S)
    return re.sub(r"\s*[|–-].*$", "", _clean(re.sub(r"<[^>]+>", " ", m.group(1)) if m else "")).strip()


def _visible_brand(soup, text: str) -> str:
    if soup:
        for el in soup.find_all(attrs={"itemprop": "brand"}):
            val = _clean(el.get("content") or " ".join(el.stripped_strings))
            if val:
                return val[:120]
    m = re.search(r"(?:Brand|แบรนด์)\s*[:：]?\s*([^\n|]{2,100})", text or "", re.I)
    return _clean(m.group(1))[:120] if m else ""


def _visible_category(soup) -> str:
    if not soup:
        return ""
    labels = []
    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "")
        if re.search(r"/(?:category|categories)/", href, re.I):
            t = _clean(" ".join(a.stripped_strings))
            if t and t not in labels:
                labels.append(t)
    if not labels:
        nav = soup.find(attrs={"aria-label": re.compile("breadcrumb", re.I)})
        if nav:
            labels = [_clean(x) for x in nav.stripped_strings if _clean(x)]
    return " > ".join(labels[-3:])[:240]


def gourmet_detail_record(html: str, url: str) -> dict | None:
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser") if BeautifulSoup else None
    text = _clean(soup.get_text("\n", strip=True) if soup else re.sub(r"<[^>]+>", " ", html))
    identity = _identity_from_url(url)

    for obj in _jsonld_products(html):
        name = _clean(obj.get("name") or "")
        sku = _clean(obj.get("gtin13") or obj.get("gtin12") or obj.get("gtin14") or obj.get("sku") or identity)
        price = _offer_price(obj.get("offers"))
        if name and sku and price is not None:
            category = obj.get("category") or ""
            if isinstance(category, dict):
                category = category.get("name") or ""
            return {
                "record_type": "ProductCandidate", "product_name": name[:300],
                "brand": _brand_value(obj.get("brand"))[:120], "category": _clean(category)[:240],
                "price": price, "regular_price": None, "promo_price": None,
                "currency": "THB", "sku": sku[:100], "source_url": _canonical(url),
                "source_tag": "Product", "provenance": "gourmet-product-detail", "parser_mode": "jsonld-detail",
            }

    name = _visible_name(soup, html)
    vals = _money_values(text)
    price = vals[0] if vals else None
    if not name or not identity or price is None:
        return None
    regular = next((v for v in vals[1:] if v > price), None)
    return {
        "record_type": "ProductCandidate", "product_name": name[:300],
        "brand": _visible_brand(soup, text), "category": _visible_category(soup),
        "price": price, "regular_price": regular,
        "promo_price": price if regular is not None and price < regular else None,
        "currency": "THB", "sku": identity, "source_url": _canonical(url),
        "source_tag": "Product", "provenance": "gourmet-product-detail", "parser_mode": "visible-detail",
    }


def gourmet_detail_links(html: str, base: str) -> list[str]:
    if not BeautifulSoup or not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        u = _canonical(urljoin(base, a.get("href") or ""))
        if "gourmetmarketthailand.com" not in urlparse(u).netloc.lower():
            continue
        if not _identity_from_url(u):
            continue
        if u not in out:
            out.append(u)
    return out


def gourmet_product_detail_catalog(seed=GOURMET_HOME, max_pages=3, source_id=None, progressive=False,
                                   operational_config=None, stable_sample=False):
    cfg = dict(operational_config or {})
    seeds = list(cfg.get("seed_urls") or GOURMET_DETAIL_SEEDS)
    seeds = [_canonical(x) for x in seeds if x]
    queue = list(dict.fromkeys(seeds))
    target = max(5, int(max_pages)) if progressive else max(3, min(5, int(max_pages)))
    run_no = 0
    if progressive and source_id and not stable_sample:
        try:
            from operations_store import states
            run_no = max(0, int((states().get(source_id) or {}).get("total_runs") or 0) - 1)
        except Exception:
            run_no = 0
    if run_no and queue:
        shift = (run_no * target) % len(queue)
        queue = queue[shift:] + queue[:shift]

    rows, checked, diag, seen = [], [], [], set()
    started = time.monotonic()
    budget = 22 if not progressive else max(45, min(120, 20 + target * 10))
    i = 0
    while i < len(queue) and len(rows) < target and time.monotonic() - started < budget:
        u = queue[i]; i += 1
        if u in seen:
            continue
        seen.add(u); checked.append(u)
        r = get(u, timeout=10 if not progressive else 14)
        if not r.get("ok"):
            diag.append({"stage": "gourmet-product-detail", "url": u, "status": "failed", "error": r.get("error")})
            continue
        final = _canonical(r.get("final_url") or u)
        html = r.get("text") or ""
        rec = gourmet_detail_record(html, final)
        if rec:
            rows.append(rec)
            diag.append({"stage": "gourmet-product-detail", "url": final, "status": "materialized",
                         "sku": rec.get("sku"), "price": rec.get("price"), "parser_mode": rec.get("parser_mode")})
        else:
            diag.append({"stage": "gourmet-product-detail", "url": final, "status": "no-product-record", "bytes": r.get("bytes")})
        # Grow only through current official product-detail links. Cached/search prices
        # are never accepted as observations.
        for link in gourmet_detail_links(html, final)[:30]:
            if link not in seen and link not in queue and len(queue) < max(40, target * 8):
                queue.append(link)

    rows = _dedup(rows)
    if stable_sample:
        rows = sorted(rows, key=lambda x: (x.get("sku") or "", x.get("product_name") or ""))
    rows = rows[:target]
    price_pct = round(100 * sum(r.get("price") is not None for r in rows) / len(rows), 1) if rows else 0
    sku_pct = round(100 * sum(bool(r.get("sku")) for r in rows) / len(rows), 1) if rows else 0
    success = round(100 * len(rows) / len(checked), 1) if checked else 0
    op = {
        "seed_urls": seeds, "crawl_mode": "official-detail-seed-to-related-detail",
        "commerce_surface": GOURMET_HOME, "official_domain": "gourmetmarketthailand.com",
    }
    return {
        "rows": rows, "diagnostics": diag, "urls_checked": checked,
        "potential": {
            "product_records": len(rows), "product_detail_urls_tested": len(checked),
            "detail_materialization_success_pct": success,
            "price_completeness_pct": price_pct, "sku_completeness_pct": sku_pct,
            "discovered_detail_urls": len(queue),
            "estimated_extractable_records_high": len(queue) if len(queue) > len(seeds) else None,
            "confidence": "high" if len(rows) >= 5 and price_pct >= 90 and sku_pct >= 90 else "medium" if rows else "low",
            "operational_config": op,
            "data_fields": ["product name", "SKU/GTIN", "brand", "category", "current price", "regular price", "product URL"],
            "basis": "current official Gourmet Market product-detail pages seeded by verified official URLs and expanded only through current official product links",
        },
    }
