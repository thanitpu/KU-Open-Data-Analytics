from __future__ import annotations

import html as html_lib
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None

try:
    from lotus_advanced import get
except Exception:  # pragma: no cover
    get = None

PADI_FEED = "https://blog.padi.com/feed/"
PADI_ALL = "https://blog.padi.com/all-articles/"


def _clean(v) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(str(v or ""))).strip()


def _iso_date(value: str | None) -> str | None:
    v = _clean(value)
    if not v:
        return None
    try:
        return parsedate_to_datetime(v).astimezone(timezone.utc).isoformat()
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%d %B, %Y", "%B %d, %Y"):
        try:
            d = datetime.strptime(v, fmt)
            if not d.tzinfo: d = d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc).isoformat()
        except Exception:
            pass
    return None


def _strip_html(v: str) -> str:
    return _clean(re.sub(r"<[^>]+>", " ", v or ""))


def padi_rss_records(xml_text: str, observed_at: str | None = None) -> list[dict]:
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    records = []
    for item in root.findall(".//item"):
        def txt(tag):
            node = item.find(tag); return _clean(node.text if node is not None else "")
        title = txt("title"); link = txt("link")
        if not title or not link or "blog.padi.com" not in urlparse(link).netloc.lower():
            continue
        pub = _iso_date(txt("pubDate"))
        author = txt("{http://purl.org/dc/elements/1.1/}creator")
        desc = _strip_html(txt("description"))
        categories = [_clean(x.text) for x in item.findall("category") if _clean(x.text)]
        records.append({
            "record_type": "ContentCandidate", "content_id": link.rstrip("/").split("/")[-1],
            "title": title[:400], "canonical_url": link, "published_at": pub,
            "observed_at": observed_at, "author": author[:160] or None,
            "summary": desc[:1000] or None, "topics": categories[:20],
            "source": "PADI Blog", "source_url": PADI_FEED, "provenance": "padi-rss-feed",
        })
    return records


def _html_article_records(html: str, page_url: str, observed_at: str | None = None) -> list[dict]:
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    if not BeautifulSoup or not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    records = []; seen = set()
    candidates = soup.find_all("article")
    if not candidates:
        candidates = soup.select(".post, .article, .card, .story, [class*='article'], [class*='post']")
    for card in candidates:
        link = None
        for a in card.find_all("a", href=True):
            u = urljoin(page_url, a.get("href") or "")
            p = urlparse(u)
            if p.netloc.lower() != "blog.padi.com" or p.path in ("/", "/all-articles/"):
                continue
            if any(x in p.path.lower() for x in ("/category/", "/tag/", "/author/", "/page/")):
                continue
            link = p._replace(query="", fragment="").geturl(); break
        if not link or link in seen: continue
        title_node = card.find(["h1","h2","h3","h4"]) or card.find("a", href=True)
        title = _clean(" ".join(title_node.stripped_strings)) if title_node else ""
        if len(title) < 8: continue
        text = _clean(" ".join(card.stripped_strings))
        date_node = card.find("time")
        published = _iso_date(date_node.get("datetime") if date_node and date_node.get("datetime") else (_clean(" ".join(date_node.stripped_strings)) if date_node else ""))
        if not published:
            m = re.search(r"\b(\d{1,2}\s+[A-Z][a-z]+,?\s+20\d{2}|[A-Z][a-z]+\s+\d{1,2},\s+20\d{2})\b", text)
            published = _iso_date(m.group(1).replace(",", "")) if m else None
        author = None
        m = re.search(r"(?:By|Author)\s+([A-Z][A-Za-z .'-]{2,80})", text)
        if m: author = _clean(m.group(1))
        seen.add(link)
        records.append({
            "record_type":"ContentCandidate","content_id":link.rstrip("/").split("/")[-1],
            "title":title[:400],"canonical_url":link,"published_at":published,"observed_at":observed_at,
            "author":author,"summary":text[:1000],"topics":[],"source":"PADI Blog",
            "source_url":page_url,"provenance":"padi-article-index",
        })
    return records


def padi_content_catalog(max_items: int = 30, timeout: int = 15) -> dict:
    diagnostics=[]; records=[]; started=time.monotonic()
    if not get:
        return {"ok":False,"records":[],"diagnostics":[{"status":"http-helper-unavailable"}]}
    feed=get(PADI_FEED,timeout=timeout)
    if feed.get("ok"):
        records=padi_rss_records(feed.get("text") or "")
        diagnostics.append({"surface":"rss","url":feed.get("final_url") or PADI_FEED,"status":feed.get("status"),"bytes":feed.get("bytes"),"records":len(records)})
    else:
        diagnostics.append({"surface":"rss","url":PADI_FEED,"status":feed.get("status"),"error":feed.get("error")})
    if len(records)<5:
        page=get(PADI_ALL,timeout=timeout)
        if page.get("ok"):
            html_records=_html_article_records(page.get("text") or "",page.get("final_url") or PADI_ALL)
            existing={x.get("canonical_url") for x in records};records.extend(x for x in html_records if x.get("canonical_url") not in existing)
            diagnostics.append({"surface":"article-index","url":page.get("final_url") or PADI_ALL,"status":page.get("status"),"bytes":page.get("bytes"),"records":len(html_records)})
        else:
            diagnostics.append({"surface":"article-index","url":PADI_ALL,"status":page.get("status"),"error":page.get("error")})
    by={}
    for r in records:
        if r.get("canonical_url"):by[r["canonical_url"]]=r
    rows=sorted(by.values(),key=lambda x:(x.get("published_at") or "",x.get("canonical_url") or ""),reverse=True)[:max_items]
    title_pct=round(100*sum(bool(x.get("title")) for x in rows)/len(rows),1) if rows else 0
    time_pct=round(100*sum(bool(x.get("published_at") or x.get("observed_at")) for x in rows)/len(rows),1) if rows else 0
    prov_pct=round(100*sum(bool(x.get("provenance")) for x in rows)/len(rows),1) if rows else 0
    return {"ok":bool(rows),"records":rows,"diagnostics":diagnostics,"metrics":{"content_records":len(rows),"title_or_topic_completeness_pct":title_pct,"published_or_observed_time_pct":time_pct,"provenance_pct":prov_pct},"elapsed_seconds":round(time.monotonic()-started,3),"operational_config":{"rss_url":PADI_FEED,"article_index":PADI_ALL,"official_domain":"blog.padi.com"},"guardrail":"Public PADI Blog feed/index metadata only. No account/profile/private data is collected."}


def audit_padi_runs(first: dict,second: dict,minimum_records: int=5)->dict:
    r1=first.get("records") or [];r2=second.get("records") or []
    k1={x.get("canonical_url") for x in r1 if x.get("canonical_url")};k2={x.get("canonical_url") for x in r2 if x.get("canonical_url")}
    repeat=round(100*len(k1&k2)/min(len(k1),len(k2)),1) if k1 and k2 else 0
    title_pct=round(100*sum(bool(x.get("title") or x.get("topics")) for x in r1)/len(r1),1) if r1 else 0
    time_pct=round(100*sum(bool(x.get("published_at") or x.get("observed_at")) for x in r1)/len(r1),1) if r1 else 0
    prov_pct=round(100*sum(bool(x.get("provenance")) for x in r1)/len(r1),1) if r1 else 0
    semantic_pct=round(100*sum(bool(x.get("title")) and bool(x.get("canonical_url")) and "blog.padi.com" in urlparse(x.get("canonical_url") or "").netloc.lower() for x in r1)/len(r1),1) if r1 else 0
    gates={"access_and_yield":bool(first.get("ok") and second.get("ok")),"minimum_content_records":len(r1)>=minimum_records,"title_or_topic_completeness":title_pct>=90,"published_or_observed_time":time_pct>=80,"semantic_quality":semantic_pct>=85,"repeatability":repeat>=70,"provenance":prov_pct>=95}
    failures=[k for k,v in gates.items() if not v]
    return {"audit_passed":not failures,"gate_checks":gates,"hard_failures":failures,"yield":{"content_records":len(r1)},"field_quality":{"title_or_topic_completeness_pct":title_pct,"published_or_observed_time_pct":time_pct,"semantic_quality_pct":semantic_pct,"provenance_pct":prov_pct},"repeatability":{"content_repeatability_pct":repeat,"first_unique":len(k1),"second_unique":len(k2),"overlap":len(k1&k2)},"technique":"padi_public_feed_index"}
