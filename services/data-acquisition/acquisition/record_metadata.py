from __future__ import annotations
from urllib.parse import urlparse
from datetime import datetime, timezone
import re

def source_tag(domain="",url="",data_type="",text=""):
    d=(domain or urlparse(url or "").netloc or "").lower()
    t=(text or "").lower()
    dt=(data_type or "").lower()

    if dt in ("business_profile","profile") or any(k in t for k in ["address","ที่อยู่","phone","โทร","opening hours","เวลาเปิด","สาขา","branch","contact","ติดต่อ"]):
        return "About"
    if dt in ("reviews","comments","ratings"):
        return "Reviews"
    if dt in ("promotions","posts") or any(k in t for k in ["promotion","โปรโมชั่น","offer","ส่วนลด","campaign"]):
        return "Marketing"
    if any(k in d for k in ["jobbkk","jobthai","jobsdb","linkedin"]) or any(k in t for k in ["สมัครงาน","ตำแหน่งงาน","job opening","career","vacancy"]):
        return "Employment"
    if "dataforthai" in d or any(k in t for k in ["บริษัท","company limited","registration","ทะเบียน"]):
        return "Corporate"
    if "pantip" in d or any(k in t for k in ["ใกล้บ้าน","ละแวก","แถว","neighborhood","community"]):
        return "Neighborhood"
    if any(k in d for k in ["facebook.com","instagram.com","tiktok.com","x.com","twitter.com"]):
        return "Social"
    if dt in ("menu_offering","offering"):
        return "Offering"
    if dt in ("similar_businesses","similar"):
        return "Competitive"
    return "General"

def normalize_posted_at(value):
    if value is None:return ""
    s=str(value).strip()
    if not s:return ""
    # Preserve source-provided date strings if exact timestamp is unavailable.
    return s

def collected_at():
    return datetime.now(timezone.utc).isoformat()

def enrich_record(record,domain="",data_type=""):
    r=dict(record)
    url=r.get("source_url") or r.get("url") or ""
    text=r.get("text") or r.get("title") or ""
    r["posted_at"]=normalize_posted_at(r.get("posted_at") or r.get("date") or r.get("published_at"))
    r["collected_at"]=r.get("collected_at") or collected_at()
    r["source_tag"]=r.get("source_tag") or source_tag(domain=domain,url=url,data_type=data_type or r.get("data_type",""),text=text)
    return r
