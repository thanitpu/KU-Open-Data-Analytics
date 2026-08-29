#!/usr/bin/env python3
"""
KU Text Analytics Lab — Steam Thai Review Crawler POC

Uses Steam's documented public user-review endpoint:
GET https://store.steampowered.com/appreviews/<appid>?json=1

Privacy design:
- does NOT store author SteamID
- does NOT store profile information
- stores only review-level fields useful for text analytics
- redacts obvious email/phone patterns from review text
"""

from __future__ import annotations
import argparse, csv, json, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://store.steampowered.com/appreviews/{appid}"

DEFAULT_APPS = {
    "730": "Counter-Strike 2",
    "570": "Dota 2",
    "578080": "PUBG: BATTLEGROUNDS",
    "271590": "Grand Theft Auto V",
}

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?:\+?66|0)[\s-]?\d(?:[\s-]?\d){7,9}")

def redact_pii(text: str) -> str:
    text = EMAIL_RE.sub("<EMAIL>", text or "")
    text = PHONE_RE.sub("<PHONE>", text)
    return text.strip()

def api_url(appid: str, cursor: str, language: str, page_size: int) -> str:
    qs = urlencode({
        "json": 1,
        "filter": "recent",
        "language": language,
        "review_type": "all",
        "purchase_type": "all",
        "num_per_page": min(100, max(1, page_size)),
        "cursor": cursor,
        "filter_offtopic_activity": 1,
    })
    return f"{BASE.format(appid=appid)}?{qs}"

def fetch_json(url: str, timeout: int = 30) -> dict:
    req = Request(url, headers={
        "User-Agent": "KU-Text-Analytics-Lab/0.2 educational-research-poc"
    })
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def iso_time(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except Exception:
        return ""

def crawl_app(appid: str, app_name: str, max_reviews: int, language: str,
              delay: float, page_size: int) -> list[dict]:
    rows, cursor, seen = [], "*", set()
    while len(rows) < max_reviews:
        payload = fetch_json(api_url(appid, cursor, language, page_size))
        if payload.get("success") != 1:
            raise RuntimeError(f"Steam returned success={payload.get('success')} for app {appid}")
        reviews = payload.get("reviews") or []
        if not reviews:
            break

        for rv in reviews:
            rid = str(rv.get("recommendationid") or "")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            text = redact_pii(rv.get("review") or "")
            if not text:
                continue
            positive = bool(rv.get("voted_up"))
            rows.append({
                "review_id": f"steam:{appid}:{rid}",
                "review_text": text,
                "sentiment_label": "positive" if positive else "negative",
                "sentiment_confidence": "1.0",
                "rating": "",
                "category": "gaming",
                "date": iso_time(rv.get("timestamp_created")),
                "language": rv.get("language") or language,
                "source": "steam_user_reviews",
                "source_url": f"https://store.steampowered.com/app/{appid}/",
                "app_id": appid,
                "app_name": app_name,
                "votes_helpful": rv.get("votes_up", 0),
                "playtime_at_review_minutes": (rv.get("author") or {}).get("playtime_at_review", ""),
                "steam_purchase": rv.get("steam_purchase", ""),
                "received_for_free": rv.get("received_for_free", ""),
            })
            if len(rows) >= max_reviews:
                break

        next_cursor = payload.get("cursor")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        if len(rows) < max_reviews:
            time.sleep(max(0.5, delay))
    return rows

def write_csv(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "review_id","review_text","sentiment_label","sentiment_confidence",
        "rating","category","date","language","source","source_url",
        "app_id","app_name","votes_helpful","playtime_at_review_minutes",
        "steam_purchase","received_for_free"
    ]
    with output.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def main():
    ap = argparse.ArgumentParser(description="Collect Thai Steam reviews for KU Text Analytics Lab.")
    ap.add_argument("--appid", action="append",
                    help="Steam app id. Repeat for multiple apps. Default: 730, 570, 578080.")
    ap.add_argument("--max-per-app", type=int, default=500,
                    help="Maximum reviews per app (default 500).")
    ap.add_argument("--language", default="thai",
                    help="Steam review language code (default thai).")
    ap.add_argument("--delay", type=float, default=1.5,
                    help="Seconds between API requests (default 1.5).")
    ap.add_argument("--page-size", type=int, default=100,
                    help="Reviews per request, maximum 100.")
    ap.add_argument("--output", default="fixtures/steam_thai_reviews.csv")
    args = ap.parse_args()

    appids = args.appid or ["730", "570", "578080"]
    all_rows = []
    print("KU Text Analytics Lab — Steam Thai Review Crawler")
    print("Privacy: author SteamID/profile data are not stored.")
    for appid in appids:
        name = DEFAULT_APPS.get(appid, f"Steam App {appid}")
        print(f"\nCollecting {name} ({appid}) ...")
        rows = crawl_app(appid, name, args.max_per_app, args.language,
                         args.delay, args.page_size)
        print(f"  collected: {len(rows):,}")
        all_rows.extend(rows)

    out = Path(args.output)
    write_csv(all_rows, out)
    pos = sum(r["sentiment_label"] == "positive" for r in all_rows)
    neg = sum(r["sentiment_label"] == "negative" for r in all_rows)
    print(f"\nSaved: {out}")
    print(f"Rows: {len(all_rows):,} | positive: {pos:,} | negative: {neg:,}")
    print("[Steam crawler completed]")

if __name__ == "__main__":
    main()
