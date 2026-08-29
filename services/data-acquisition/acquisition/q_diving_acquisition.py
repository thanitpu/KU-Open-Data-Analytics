from __future__ import annotations
import re,json,html as htmllib
from urllib.request import Request,urlopen
from urllib.parse import urljoin,urlparse
from datetime import datetime,timezone
from diving_text_analytics import analyze

UA="Mozilla/5.0 (compatible; KU2D-Q-Diving/1.0; research prototype)"

def clean(x):return re.sub(r"\s+"," ",htmllib.unescape(str(x or ""))).strip()

def fetch(url,timeout=18):
    req=Request(url,headers={"User-Agent":UA,"Accept-Language":"th,en;q=0.8"})
    with urlopen(req,timeout=timeout) as r:
        raw=r.read(3_000_000)
        enc=r.headers.get_content_charset() or "utf-8"
        return {"url":r.geturl(),"status":getattr(r,"status",200),"html":raw.decode(enc,"replace")}

def _meta(doc,key):
    pats=[
      rf'<meta[^>]+(?:property|name)=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)',
      rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(key)}["\']'
    ]
    for p in pats:
        m=re.search(p,doc,re.I)
        if m:return clean(m.group(1))
    return ""

def parse_html(doc,url):
    title=_meta(doc,"og:title")
    if not title:
        m=re.search(r"<title[^>]*>(.*?)</title>",doc,re.I|re.S);title=clean(re.sub("<[^>]+>"," ",m.group(1))) if m else ""
    desc=_meta(doc,"og:description") or _meta(doc,"description")
    pub=_meta(doc,"article:published_time")
    # remove scripts/styles/nav-like noise; retain article text.
    x=re.sub(r"<(script|style|svg|noscript)[^>]*>.*?</\1>"," ",doc,flags=re.I|re.S)
    x=re.sub(r"<br\s*/?>|</p>|</li>|</h[1-6]>","\n",x,flags=re.I)
    text=clean(re.sub(r"<[^>]+>"," ",x))
    canonical=""
    m=re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',doc,re.I)
    if m:canonical=urljoin(url,m.group(1))
    return {"title":title,"description":desc,"published_at":pub,"text":text[:200000],
            "canonical_url":canonical or url}

def source_type_for(url):
    host=urlparse(url).netloc.lower()
    if "pantip.com" in host:return "pantip"
    if "padi.com" in host:return "padi"
    if "divessi.com" in host:return "ssi"
    if "youtube.com" in host or "youtu.be" in host:return "youtube"
    return "web"

def content_type_for(source_type,url):
    if source_type=="pantip":return "discussion"
    if source_type in ("padi","ssi"):return "article"
    if source_type=="youtube":return "video"
    return "article"

def acquire_url(url):
    src=source_type_for(url)
    # YouTube public HTML is useful for metadata but transcript/comments are deliberately not scraped here.
    r=fetch(url);p=parse_html(r["html"],r["url"]);analytics=analyze(p["text"])
    return {"ok":True,"source_type":src,"content_type":content_type_for(src,url),
      "title":p["title"],"source_url":p["canonical_url"],"published_at":p["published_at"],
      "description":p["description"],"raw_text":p["text"],"analytics":analytics,
      "diagnostics":{"http_status":r["status"],"fetched_url":r["url"],
        "youtube_transcript_status":"not-acquired-from-public-html" if src=="youtube" else None,
        "youtube_comments_status":"requires-authorized/API-or-user-supplied-data" if src=="youtube" else None}}

def import_transcript(title,url,transcript,channel="",published_at="",source_type="youtube"):
    return {"ok":True,"source_type":source_type,"content_type":"transcript","title":title,
      "source_url":url,"published_at":published_at,"channel":channel,"raw_text":transcript,
      "analytics":analyze(transcript),"diagnostics":{"mode":"user-supplied-transcript"}}
