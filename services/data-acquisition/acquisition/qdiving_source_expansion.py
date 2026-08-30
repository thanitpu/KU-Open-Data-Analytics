from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _number(value: str) -> float | None:
    match = re.search(r"(?<!\d)([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)(?!\d)", value or "")
    if not match:
        return None
    try:
        number = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    return number if 1 <= number <= 1_000_000 else None


def ssi_blog_records(html: str, observed_at: str | None = None, max_items: int = 10) -> list[dict]:
    """Normalize official SSI public article-card metadata, not article authority."""
    if not BeautifulSoup or not html:
        return []
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        parsed = urlparse(urljoin("https://www.divessi.com/en/blog", anchor.get("href") or ""))
        if parsed.hostname not in {"divessi.com", "www.divessi.com"}:
            continue
        if not re.fullmatch(r"/blog/[^/?#]+", parsed.path.rstrip("/")):
            continue
        canonical = parsed._replace(query="", fragment="").geturl()
        if canonical in seen:
            continue
        heading = anchor.find(["h2", "h3", "h4"])
        title = _clean(heading.get_text(" ", strip=True)) if heading else ""
        summary_node = anchor.find("p")
        summary = _clean(summary_node.get_text(" ", strip=True)) if summary_node else ""
        if len(title) < 8:
            continue
        seen.add(canonical)
        records.append({
            "record_type": "DivingContentCandidate",
            "content_id": parsed.path.rstrip("/").split("/")[-1],
            "title": title[:400],
            "summary": summary[:1000] or None,
            "canonical_url": canonical,
            "published_at": None,
            "observed_at": observed_at,
            "source": "SSI Blog",
            "provenance": "official-public-content-index",
            "human_review_required": True,
            "production_approved": False,
        })
        if len(records) >= max(1, min(max_items, 10)):
            break
    return records


def scubadoo_course_records(html: str, observed_at: str | None = None, max_items: int = 10) -> list[dict]:
    """Normalize public dive-service offers; these are never retail products."""
    if not BeautifulSoup or not html:
        return []
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for item in soup.select(".menu-item"):
        title_node = item.select_one(".menu-item-title")
        price_node = item.select_one(".menu-item-price-top, .menu-item-price-bottom")
        description_node = item.select_one(".menu-item-description")
        title = _clean(title_node.get_text(" ", strip=True)) if title_node else ""
        price = _number(price_node.get_text(" ", strip=True)) if price_node else None
        description = _clean(description_node.get_text(" ", strip=True)) if description_node else ""
        if not title or price is None:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
        records.append({
            "record_type": "DiveCourseServiceCandidate",
            "course_service_id": f"scubadookohtao.com:{slug}",
            "course_name": title[:300],
            "location": "Koh Tao, Surat Thani, Thailand",
            "price": price,
            "currency": "THB",
            "package_structure": description[:500] or None,
            "source_url": "https://www.scubadookohtao.com/price-lists",
            "observed_at": observed_at,
            "provenance": "official-public-course-price-list",
            "booking_performed": False,
            "production_approved": False,
        })
        if len(records) >= max(1, min(max_items, 10)):
            break
    return records


def aquamaster_equipment_records(html: str, observed_at: str | None = None, max_items: int = 10) -> list[dict]:
    """Normalize bounded official retail cards without treating display order as demand."""
    if not BeautifulSoup or not html:
        return []
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    soup = BeautifulSoup(html, "html.parser")
    records = []
    seen = set()
    for card in soup.select("article.product"):
        title_link = card.select_one("h4.entry-title a[href]")
        if not title_link:
            continue
        parsed = urlparse(title_link.get("href") or "")
        if parsed.hostname not in {"aquamaster.net", "www.aquamaster.net"} or "/product/" not in parsed.path:
            continue
        canonical = parsed._replace(query="", fragment="").geturl()
        if canonical in seen:
            continue
        title = _clean(title_link.get_text(" ", strip=True))
        amounts = []
        for node in card.select(".price .woocommerce-Price-amount"):
            value = _number(node.get_text(" ", strip=True))
            if value is not None and value not in amounts:
                amounts.append(value)
        if not title or not amounts:
            continue
        seen.add(canonical)
        classes = set(card.get("class") or [])
        categories = sorted(x.removeprefix("product_cat-") for x in classes if x.startswith("product_cat-"))
        records.append({
            "record_type": "DivingEquipmentProductCandidate",
            "product_id": parsed.path.rstrip("/").split("/")[-1],
            "product_name": title[:300],
            "equipment_categories": categories,
            "current_or_range_min_price": min(amounts),
            "range_max_price": max(amounts) if len(amounts) > 1 else None,
            "currency": "THB",
            "canonical_url": canonical,
            "source_surface": "official-sale-catalog",
            "display_position": len(records) + 1,
            "demand_signal": None,
            "observed_at": observed_at,
            "provenance": "official-public-equipment-catalog-card",
            "production_approved": False,
        })
        if len(records) >= max(1, min(max_items, 10)):
            break
    return records
