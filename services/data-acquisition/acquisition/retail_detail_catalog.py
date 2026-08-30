from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from lotus_advanced import browser_render, get

STATIC_EXTENSIONS = {
    ".css", ".js", ".mjs", ".map", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".pdf", ".zip", ".xml", ".txt", ".mp4", ".webm", ".mp3",
}
NEGATIVE_PATH_TERMS = {
    "account", "login", "logout", "register", "cart", "checkout", "wishlist", "compare", "privacy",
    "terms", "contact", "store-locator", "find-a-store", "blog", "article", "news", "faq", "help",
    "campaign", "promotion", "promotions", "coupon", "catalogue", "category", "search", "brand",
}
PRODUCT_PATH_PATTERNS = [
    re.compile(r"/(?:[a-z]{2}/)?p/(?:bp_)?[a-z0-9_-]+(?:[/?#]|$)", re.I),
    re.compile(r"/web/product/readproduct/\d+/\d+(?:/|$)", re.I),
    re.compile(r"/(?:product|products|product-detail|productdetail|pdp|item|goods|sku)/[^/?#]{2,}", re.I),
]


def _base_domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    parts = host.split(".") if host else []
    if len(parts) < 2:
        return host
    two_label_suffixes = {
        "co.th", "or.th", "ac.th", "go.th", "in.th", "mi.th", "net.th",
        "co.uk", "org.uk", "com.au", "com.sg", "com.my",
    }
    suffix = ".".join(parts[-2:])
    if suffix in two_label_suffixes and len(parts) >= 3:
        return ".".join(parts[-3:])
    return suffix


def _same_site(a: str, b: str) -> bool:
    return bool(_base_domain(a) and _base_domain(a) == _base_domain(b))


def _normalise_url(value: str, base_url: str) -> str:
    raw = unescape(str(value or "").strip()).replace("\\u002F", "/").replace("\\/", "/")
    if not raw or raw.startswith(("javascript:", "mailto:", "tel:", "data:")):
        return ""
    url = urljoin(base_url, raw)
    try:
        p = urlparse(url)
        if p.scheme not in {"http", "https"} or not p.netloc:
            return ""
        # Fragments are not acquisition identity; common tracking query parameters are removed.
        kept = []
        for item in (p.query or "").split("&"):
            if not item:
                continue
            key = item.split("=", 1)[0].lower()
            if key.startswith("utm_") or key in {"gclid", "fbclid", "ref", "source"}:
                continue
            kept.append(item)
        return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path or "/", p.params, "&".join(kept), ""))
    except Exception:
        return ""


def _static_asset(url: str) -> bool:
    path = (urlparse(url).path or "").lower()
    return any(path.endswith(ext) for ext in STATIC_EXTENSIONS)


def product_url_score(url: str, anchor_text: str = "", seed_url: str = "") -> int:
    if not url or _static_asset(url) or (seed_url and not _same_site(url, seed_url)):
        return -1000
    p = urlparse(url)
    path = (p.path or "/").lower()
    text = re.sub(r"\s+", " ", anchor_text or "").strip().lower()
    score = 0
    if re.search(r"/(?:[a-z]{2}/)?p/(?:bp_)?[a-z0-9_-]+", path, re.I):
        score += 85
    if re.search(r"/web/product/readproduct/\d+/\d+", path, re.I):
        score += 85
    if re.search(r"/(?:product|products|product-detail|productdetail|pdp|item|goods|sku)/", path, re.I):
        score += 42
    if any(pat.search(path) for pat in PRODUCT_PATH_PATTERNS):
        score += 28
    if re.search(r"(?:^|[-_/])\d{5,}(?:[-_/]|$)", path):
        score += 16
    if len([x for x in path.split("/") if x]) >= 3:
        score += 6
    if re.search(r"สินค้า|product|รายละเอียด|detail|ซื้อ|shop", text, re.I):
        score += 10
    if any(f"/{term}" in path or f"-{term}" in path for term in NEGATIVE_PATH_TERMS):
        score -= 55
    if path in {"/", "/th", "/en", "/th/", "/en/", "/web/index.php"}:
        score -= 60
    return score


def _candidate_links(html: str, base_url: str) -> list[dict]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, dict] = {}

    def add(value: str, text: str, provenance: str):
        url = _normalise_url(value, base_url)
        if not url or not _same_site(url, base_url):
            return
        score = product_url_score(url, text, base_url)
        if score < 25:
            return
        row = {"url": url, "score": score, "anchor_text": re.sub(r"\s+", " ", text or "").strip()[:240], "provenance": provenance}
        old = found.get(url)
        if old is None or score > old["score"]:
            found[url] = row

    for node in soup.find_all(["a", "button", "div", "article", "li"]):
        text = node.get_text(" ", strip=True)
        for attr in ("href", "data-href", "data-url", "data-link", "data-product-url"):
            value = node.get(attr)
            if value:
                add(value, text, f"dom-{attr}")

    # Modern storefronts frequently serialize relative product routes inside JSON/JS.
    normalised = html.replace("\\u002F", "/").replace("\\/", "/")
    route_re = re.compile(
        r"[\"']((?:https?://[^\"']+|/[^\"']{1,500})(?:/(?:p|product|products|product-detail|productdetail|pdp|item|goods|sku)/|/web/product/readProduct/)[^\"']*)[\"']",
        re.I,
    )
    for match in route_re.finditer(normalised):
        add(match.group(1), "", "embedded-route")

    return sorted(found.values(), key=lambda x: (-x["score"], x["url"]))


def _num(value):
    if isinstance(value, dict):
        value = value.get("value") or value.get("amount") or value.get("price") or value.get("lowPrice")
    if isinstance(value, list) and value:
        value = value[0]
    try:
        text = re.sub(r"[^0-9.]", "", str(value or ""))
        return float(text) if text and re.search(r"\d", text) else None
    except Exception:
        return None


def _first(value):
    if isinstance(value, list):
        return value[0] if value else ""
    return value


def _brand(value) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("title")
    return str(value or "").strip()[:160]


def _image(value) -> str:
    value = _first(value)
    if isinstance(value, dict):
        value = value.get("url") or value.get("contentUrl") or value.get("src")
    return str(value or "").strip()[:1000]


def _offer_values(offers) -> tuple[float | None, float | None, str, str]:
    offer = _first(offers)
    if not isinstance(offer, dict):
        return None, None, "", ""
    price = _num(offer.get("price") or offer.get("lowPrice") or offer.get("salePrice"))
    regular = _num(offer.get("highPrice") or offer.get("regularPrice") or offer.get("originalPrice") or offer.get("listPrice"))
    currency = str(offer.get("priceCurrency") or offer.get("currency") or "THB")[:12]
    availability = str(offer.get("availability") or offer.get("itemCondition") or "")[:160]
    specs = offer.get("priceSpecification")
    for spec in specs if isinstance(specs, list) else ([specs] if isinstance(specs, dict) else []):
        if not isinstance(spec, dict):
            continue
        candidate = _num(spec.get("price"))
        if candidate is None:
            continue
        typ = str(spec.get("@type") or spec.get("name") or "").lower()
        if "list" in typ or "regular" in typ or "original" in typ:
            regular = regular or candidate
        elif price is None:
            price = candidate
    return price, regular, currency, availability


def _jsonld_products(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    objects = []
    for script in soup.find_all("script"):
        if "ld+json" not in str(script.get("type") or "").lower():
            continue
        raw = script.string or script.get_text(" ", strip=True)
        try:
            objects.append(json.loads(raw))
        except Exception:
            continue

    rows = []

    def walk(obj):
        if isinstance(obj, list):
            for item in obj:
                walk(item)
            return
        if not isinstance(obj, dict):
            return
        graph = obj.get("@graph")
        if isinstance(graph, list):
            walk(graph)
        typ = obj.get("@type") or obj.get("type")
        types = {str(x).lower() for x in (typ if isinstance(typ, list) else [typ]) if x}
        if "product" in types:
            name = str(obj.get("name") or obj.get("headline") or "").strip()
            price, regular, currency, availability = _offer_values(obj.get("offers"))
            sku = str(obj.get("sku") or obj.get("productID") or obj.get("productId") or "").strip()
            model = str(obj.get("mpn") or obj.get("model") or "").strip()
            gtin = str(obj.get("gtin13") or obj.get("gtin14") or obj.get("gtin12") or obj.get("gtin") or "").strip()
            source = _normalise_url(str(obj.get("url") or page_url), page_url) or page_url
            if name and price is not None:
                rows.append({
                    "record_type": "ProductCandidate", "product_name": name[:320],
                    "brand": _brand(obj.get("brand")), "category": str(obj.get("category") or "")[:200],
                    "price": price, "regular_price": regular if regular and regular >= price else None,
                    "promo_price": price if regular and regular > price else None, "currency": currency or "THB",
                    "sku": sku[:120], "model": model[:160], "gtin": gtin[:32],
                    "availability": availability, "image_url": _image(obj.get("image")),
                    "color": str(obj.get("color") or "")[:100], "size": str(obj.get("size") or "")[:100],
                    "source_url": source, "source_tag": "Product", "provenance": "retail-product-jsonld",
                })
        for key, value in obj.items():
            if key == "@graph":
                continue
            if isinstance(value, (dict, list)):
                walk(value)

    for obj in objects:
        walk(obj)
    return rows


def _meta_value(soup: BeautifulSoup, *keys: str) -> str:
    wanted = {x.lower() for x in keys}
    for meta in soup.find_all("meta"):
        key = str(meta.get("property") or meta.get("name") or meta.get("itemprop") or "").lower()
        if key in wanted and meta.get("content"):
            return str(meta.get("content")).strip()
    return ""


def _visible_price(text: str) -> float | None:
    patterns = [
        r"฿\s*([0-9][0-9,]*(?:\.\d{1,2})?)",
        r"(?:THB|บาท)\s*([0-9][0-9,]*(?:\.\d{1,2})?)",
        r"([0-9][0-9,]*(?:\.\d{1,2})?)\s*(?:THB|บาท)",
    ]
    for pat in patterns:
        for match in re.finditer(pat, text or "", re.I):
            value = _num(match.group(1))
            if value is not None and value > 0:
                return value
    return None


def _detail_fallback(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    canonical_node = soup.find("link", rel=lambda v: v and "canonical" in str(v).lower())
    canonical = _normalise_url(canonical_node.get("href") if canonical_node else page_url, page_url) or page_url
    name = _meta_value(soup, "og:title", "twitter:title", "product:name")
    if not name:
        heading = soup.find(["h1", "h2"])
        name = heading.get_text(" ", strip=True) if heading else ""
    if not name and soup.title:
        name = soup.title.get_text(" ", strip=True)
    name = re.sub(r"\s+", " ", name or "").strip()

    price = _num(_meta_value(soup, "product:price:amount", "og:price:amount", "price", "sale_price"))
    currency = _meta_value(soup, "product:price:currency", "og:price:currency", "pricecurrency") or "THB"
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    price = price if price is not None else _visible_price(text)

    regular = _num(_meta_value(soup, "product:original_price:amount", "product:regular_price:amount", "list_price"))
    if regular is None:
        crossed = []
        for node in soup.find_all(["del", "s"]):
            value = _visible_price(node.get_text(" ", strip=True)) or _num(node.get_text(" ", strip=True))
            if value:
                crossed.append(value)
        regular = max(crossed) if crossed else None

    sku = _meta_value(soup, "product:retailer_item_id", "sku", "product_id")
    model = ""
    if not sku:
        patterns = [
            r"(?:Product\s*code|รหัสสินค้า|SKU)\s*[:#]?\s*([A-Za-z0-9_-]{4,})",
            r"\(#([A-Za-z0-9_-]{4,})\)",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.I)
            if match:
                sku = match.group(1)
                break
    if not sku:
        match = re.search(r"/p/(?:BP_)?([A-Za-z0-9_-]+)", canonical, re.I)
        if match:
            sku = match.group(1)
    if not sku:
        match = re.search(r"/web/product/readProduct/(\d+)/(\d+)", canonical, re.I)
        if match:
            sku = match.group(1)
            model = match.group(2)

    image = _meta_value(soup, "og:image", "twitter:image", "product:image")
    brand = _meta_value(soup, "product:brand", "brand")
    availability = _meta_value(soup, "product:availability", "availability")
    if not name or price is None or product_url_score(canonical, name, page_url) < 25:
        return []
    return [{
        "record_type": "ProductCandidate", "product_name": name[:320], "brand": brand[:160],
        "price": price, "regular_price": regular if regular and regular >= price else None,
        "promo_price": price if regular and regular > price else None, "currency": currency[:12],
        "sku": str(sku or "")[:120], "model": str(model or "")[:160], "availability": availability[:160],
        "image_url": image[:1000], "source_url": canonical, "source_tag": "Product",
        "provenance": "retail-canonical-product-detail",
    }]


def parse_product_detail(html: str, page_url: str) -> list[dict]:
    rows = _jsonld_products(html, page_url)
    if not rows:
        rows = _detail_fallback(html, page_url)
    # One canonical detail URL may repeat the same product in multiple JSON-LD blocks.
    out = []
    seen = set()
    for row in rows:
        key = (row.get("source_url"), row.get("sku") or row.get("gtin") or row.get("model"), row.get("product_name"), row.get("price"))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def generic_retail_detail_catalog(seed_url: str, max_pages: int = 6, candidate_urls: list[str] | None = None) -> dict:
    """Discover and materialize a bounded sample of canonical retail product details.

    The technique is public-read-only and conservative. It uses official same-site links,
    application routes and rendered DOM links, then accepts a detail page only when an
    attributable product name and currency-bearing price can be tied to a canonical
    product URL. It does not log in, solve challenges, rotate proxies, or bypass controls.
    """
    max_pages = max(1, min(int(max_pages or 6), 10))
    diagnostics = []
    discovery_html = []
    candidates: dict[str, dict] = {}

    def add_candidate(url: str, text: str = "", provenance: str = "upstream"):
        normal = _normalise_url(url, seed_url)
        if not normal or not _same_site(normal, seed_url):
            return
        score = product_url_score(normal, text, seed_url)
        if score < 25:
            return
        old = candidates.get(normal)
        row = {"url": normal, "score": score, "anchor_text": text[:240], "provenance": provenance}
        if old is None or score > old["score"]:
            candidates[normal] = row

    for value in candidate_urls or []:
        add_candidate(value)

    seed = get(seed_url, timeout=15)
    diagnostics.append({"url": seed_url, "phase": "seed-http", "status": seed.get("status"), "ok": seed.get("ok"), "error": seed.get("error")})
    if seed.get("ok"):
        final = seed.get("final_url") or seed_url
        html = seed.get("text") or ""
        discovery_html.append((html, final, "seed-http"))
        if product_url_score(final, "", seed_url) >= 25:
            add_candidate(final, provenance="seed-detail")

    rendered = browser_render(seed_url, timeout=35)
    diagnostics.append({
        "url": seed_url, "phase": "seed-browser", "ok": rendered.get("ok"), "available": rendered.get("available"),
        "dom_bytes": len(rendered.get("html") or ""), "error": rendered.get("error") or rendered.get("stderr"),
    })
    if rendered.get("html"):
        discovery_html.append((rendered.get("html") or "", seed_url, "seed-browser"))
    for value in rendered.get("urls") or []:
        add_candidate(value, provenance="browser-absolute-url")

    for html, base, provenance in discovery_html:
        for row in _candidate_links(html, base):
            add_candidate(row["url"], row.get("anchor_text") or "", f"{provenance}:{row.get('provenance')}")

    ranked = sorted(candidates.values(), key=lambda x: (-x["score"], x["url"]))
    rows = []
    checked = []
    rendered_fallbacks = 0
    for candidate in ranked[:max_pages]:
        url = candidate["url"]
        response = get(url, timeout=15)
        checked.append(url)
        if not response.get("ok"):
            diagnostics.append({"url": url, "phase": "detail-http", "status": response.get("status"), "error": response.get("error"), "candidate_score": candidate["score"]})
            continue
        page_url = response.get("final_url") or url
        parsed = parse_product_detail(response.get("text") or "", page_url)
        if not parsed and rendered_fallbacks < 2:
            rendered_detail = browser_render(page_url, timeout=35)
            rendered_fallbacks += 1
            parsed = parse_product_detail(rendered_detail.get("html") or "", page_url) if rendered_detail.get("html") else []
            diagnostics.append({"url": page_url, "phase": "detail-browser-fallback", "ok": rendered_detail.get("ok"), "records": len(parsed), "error": rendered_detail.get("error") or rendered_detail.get("stderr")})
        diagnostics.append({"url": page_url, "phase": "detail-parse", "status": response.get("status"), "records": len(parsed), "candidate_score": candidate["score"], "candidate_provenance": candidate["provenance"]})
        rows.extend(parsed)

    deduped = []
    seen = set()
    for row in rows:
        key = (row.get("source_url"), row.get("sku") or row.get("gtin") or row.get("model"), row.get("product_name"), row.get("price"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    price_pct = round(100 * sum(x.get("price") is not None for x in deduped) / len(deduped), 1) if deduped else 0.0
    identity_pct = round(100 * sum(bool(x.get("sku") or x.get("gtin") or x.get("model") or product_url_score(x.get("source_url") or "", "", seed_url) >= 25) for x in deduped) / len(deduped), 1) if deduped else 0.0
    confidence = "high" if len(deduped) >= 5 and price_pct >= 90 and identity_pct >= 90 else ("medium" if deduped else "low")
    return {
        "technique": "generic_retail_detail_catalog",
        "label": "Canonical Retail Product Detail Catalog",
        "status": "completed",
        "record_count": len(deduped),
        "record_types": [{"type": "ProductCandidate", "count": len(deduped)}] if deduped else [],
        "sample_records": deduped[:50],
        "pages_checked": len(checked),
        "elapsed_seconds": 0,
        "urls_checked": checked,
        "diagnostics": diagnostics,
        "potential": {
            "discovered_urls": len(ranked), "product_urls_discovered": len(ranked),
            "detail_pages_fetched": len(checked), "price_completeness_pct": price_pct,
            "identity_completeness_pct": identity_pct, "estimated_extractable_records_low": len(deduped),
            "estimated_extractable_records_high": len(ranked) or None, "confidence": confidence,
            "data_fields": ["canonical product URL", "product name", "price", "currency", "SKU/model/GTIN when exposed", "regular/promo price when exposed"],
            "basis": "official same-site product routes plus bounded canonical detail-page parsing",
        },
        "operational_role": "acquisition",
        "note": "Rejects homepage marketing numerals and accepts only product-attributable canonical detail evidence.",
    }
