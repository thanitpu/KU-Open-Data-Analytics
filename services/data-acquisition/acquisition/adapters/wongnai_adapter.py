from __future__ import annotations
from urllib.request import Request,urlopen
from urllib.parse import urlparse
from html.parser import HTMLParser
import json,re,hashlib,sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
PROVIDERS=HERE.parent/"providers"
sys.path.insert(0,str(PROVIDERS))
from serper_provider import search as serper_search

UA="Mozilla/5.0 KU-Open-DA-Wongnai-Quick/2.3"

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.text=[];self.links=[];self.scripts=[];self._script=False;self._buf=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="a" and a.get("href"):self.links.append((a.get("href"),a.get("title",""),a.get("aria-label","")))
        if tag=="script":self._script=True;self._buf=[]
    def handle_data(self,data):
        x=" ".join(data.split())
        if x:self.text.append(x)
        if self._script:self._buf.append(data)
    def handle_endtag(self,tag):
        if tag=="script" and self._script:
            self.scripts.append("".join(self._buf));self._script=False;self._buf=[]

def _fetch(url,timeout=20):
    req=Request(url,headers={"User-Agent":UA,"Accept-Language":"th-TH,th;q=0.9,en;q=0.8"})
    with urlopen(req,timeout=timeout) as r:
        return r.geturl(),r.read(2_500_000).decode("utf-8","ignore")

def _dedupe(records,limit):
    out=[];seen=set()
    for r in records:
        text=(r.get("text") or r.get("title") or "").strip()
        key=hashlib.sha1((r.get("url","")+"|"+text).encode("utf-8","ignore")).hexdigest()
        if key in seen:continue
        seen.add(key);r["record_id"]=key[:12];out.append(r)
        if len(out)>=limit:break
    return out

def _direct_extract(url,data_type,limit):
    final,body=_fetch(url)
    p=Page();p.feed(body)
    text=" ".join(p.text)
    records=[]
    if data_type=="reviews":
        # Extract sufficiently long text fragments with review/rating language.
        chunks=re.split(r'(?<=[.!?。])\s+|\n+',text)
        for c in chunks:
            low=c.lower()
            if len(c)>=35 and any(k in low for k in ["รีวิว","review","บริการ","อาหาร","กาแฟ","อร่อย","คะแนน"]):
                records.append({"text":c[:1200],"url":final,"source":"wongnai","data_type":"reviews","method":"direct-html"})
    elif data_type=="promotions":
        for c in re.split(r'(?<=[.!?。])\s+|\n+',text):
            low=c.lower()
            if len(c)>=25 and any(k in low for k in ["โปรโมชั่น","promotion","โปรโม","ส่วนลด","deal","offer"]):
                records.append({"text":c[:1200],"url":final,"source":"wongnai","data_type":"promotions","method":"direct-html"})
    elif data_type=="similar_businesses":
        for href,title,aria in p.links:
            label=" ".join(x for x in [title,aria] if x).strip()
            if "/restaurants/" in href and href not in final:
                records.append({"title":label or href,"url":href if href.startswith("http") else "https://www.wongnai.com"+href,
                                "source":"wongnai","data_type":"similar_businesses","method":"direct-link"})
    return _dedupe(records,limit)

def _search_fallback(business_name,data_type,limit):
    suffix={
        "reviews":"รีวิว ร้านอาหาร ความคิดเห็น rating",
        "promotions":"โปรโมชั่น ส่วนลด เมนูใหม่ promotion",
        "similar_businesses":"ร้านคล้าย ร้านแนะนำ ใกล้เคียง"
    }.get(data_type,data_type)
    q=f"site:wongnai.com {business_name} {suffix}"
    r=serper_search(q,num=max(10,limit))
    rows=[]
    for x in r["organic"]:
        rows.append({
            "title":x.get("title",""),
            "text":x.get("snippet",""),
            "url":x.get("url",""),
            "position":x.get("position"),
            "date":x.get("date"),
            "posted_at":x.get("date") or "",
            "source":"wongnai",
            "data_type":data_type,
            "method":"serper-snippet-fallback"
        })
    return _dedupe(rows,limit)

def crawl(url,business_name,data_type="reviews",limit=20):
    limit=max(1,min(int(limit),30))
    direct=[];direct_error=None
    try: direct=_direct_extract(url,data_type,limit)
    except Exception as e: direct_error=f"{type(e).__name__}: {e}"
    fallback=[]
    if len(direct)<min(5,limit):
        try:fallback=_search_fallback(business_name,data_type,limit)
        except Exception as e:
            if not direct_error:direct_error=f"Search fallback: {type(e).__name__}: {e}"
    records=_dedupe(direct+fallback,limit)
    return {
        "adapter":"wongnai-quick-v1",
        "url":url,
        "businessName":business_name,
        "dataType":data_type,
        "recordCount":len(records),
        "records":records,
        "status":"sample-retrieved" if records else "no-sample-retrieved",
        "directRecordCount":len(direct),
        "fallbackRecordCount":len(fallback),
        "warning":"Quick exploratory sample. Search snippets/direct public HTML can be incomplete and are not a substitute for a supported production data feed.",
        "error":direct_error
    }
