from __future__ import annotations
from urllib.request import Request,urlopen
from urllib.parse import urlparse
from html.parser import HTMLParser
import re, json, hashlib, datetime

class Extractor(HTMLParser):
    def __init__(self):
        super().__init__();self.blocks=[];self.current=[];self.tag=None
    def handle_starttag(self,tag,attrs):
        if tag in ("p","li","article","blockquote","h1","h2","h3","div"):self.current=[];self.tag=tag
    def handle_data(self,data):
        if self.tag:self.current.append(data)
    def handle_endtag(self,tag):
        if self.tag==tag:
            t=" ".join(" ".join(self.current).split())
            if len(t)>=30:self.blocks.append(t)
            self.current=[];self.tag=None

def _host(u):return (urlparse(u).netloc or "").lower().removeprefix("www.")
def retrieve(url,data_type="generic",limit=20,timeout=20):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 KU-Open-DA-Quick-Sample/2.1","Accept-Language":"th-TH,th;q=0.9,en;q=0.8"})
    try:
        with urlopen(req,timeout=timeout) as r:
            raw=r.read(2_000_000); final=r.geturl();status=getattr(r,"status",200)
        html=raw.decode("utf-8","ignore");p=Extractor();p.feed(html)
        seen=set();records=[]
        for t in p.blocks:
            key=hashlib.sha1(t.encode("utf-8","ignore")).hexdigest()
            if key in seen:continue
            seen.add(key)
            records.append({"record_id":key[:12],"text":t,"source_url":final,"source_domain":_host(final),"requested_data_type":data_type})
            if len(records)>=max(1,min(int(limit),30)):break
        return {"ok":bool(records),"url":url,"finalUrl":final,"httpStatus":status,"dataType":data_type,
                "recordCount":len(records),"records":records,
                "retrievalStatus":"sample-retrieved" if records else "no-records-extracted",
                "method":"generic-public-html-text-blocks",
                "limitations":"Quick sample is generic page extraction. Platform-specific APIs/adapters are recommended for scale, completeness and stable fields."}
    except Exception as e:
        return {"ok":False,"url":url,"dataType":data_type,"recordCount":0,"records":[],
                "retrievalStatus":"retrieval-failed","error":f"{type(e).__name__}: {e}"}

def access_recommendation(domain,data_type,status):
    social=any(x in domain for x in ("facebook.com","instagram.com","tiktok.com","x.com","twitter.com"))
    if social:
        return {"quick":"Public-page sample where accessible","standard":"Official platform API/OAuth or authorized connector",
                "recommendation":"standard-for-scale" if status=="sample-retrieved" else "standard-access-needed"}
    return {"quick":"Public HTML sample / source-specific adapter","standard":"Official API, feed, export, licensed dataset, or source-specific adapter where available",
            "recommendation":"quick-then-standard" if status=="sample-retrieved" else "source-adapter-needed"}
