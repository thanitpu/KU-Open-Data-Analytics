from __future__ import annotations
from urllib.request import Request,urlopen
from urllib.parse import urlparse
from html.parser import HTMLParser
import re, json

class ProbeHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.title=[];self.in_title=False;self.text=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="title":self.in_title=True
        if tag=="a" and a.get("href"):self.links.append({"href":a["href"],"label":a.get("aria-label","")})
    def handle_endtag(self,tag):
        if tag=="title":self.in_title=False
    def handle_data(self,data):
        if self.in_title:self.title.append(data)
        x=" ".join(data.split())
        if x:self.text.append(x)

PATTERNS={
 "reviews":["review","reviews","รีวิว","rating","ratings","คะแนน","ความคิดเห็น"],
 "promotions":["promotion","promotions","โปรโมชั่น","privilege","deal","offer","ส่วนลด","สิทธิพิเศษ"],
 "posts":["post","posts","โพสต์","timeline","reel","reels"],
 "menu_offering":["menu","เมนู","สินค้า","product","products","อาหาร","เครื่องดื่ม"],
 "business_profile":["address","ที่อยู่","opening hours","เวลาเปิด","phone","โทร","location","สาขา"],
 "similar_businesses":["similar","recommended","ร้านคล้าย","ร้านแนะนำ","you may also like","ใกล้เคียง"]
}
def _host(u):return (urlparse(u).netloc or "").lower().removeprefix("www.")

def probe(url,timeout=20):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 KU-Open-DA-Source-Probe/2.1","Accept-Language":"th-TH,th;q=0.9,en;q=0.8"})
    try:
        with urlopen(req,timeout=timeout) as r:
            raw=r.read(1_500_000); status=getattr(r,"status",200); final=r.geturl()
            ctype=r.headers.get("Content-Type","")
        body=raw.decode("utf-8","ignore")
        p=ProbeHTML();p.feed(body)
        text=(" ".join(p.text)).lower()
        found={}
        for kind,terms in PATTERNS.items():
            hits=[t for t in terms if t in text]
            found[kind]={"status":"detected" if hits else "not-detected","evidenceTerms":hits[:8]}
        host=_host(final)
        restricted=any(x in text for x in ["log in to continue","login to continue","เข้าสู่ระบบเพื่อ","captcha","access denied"])
        return {"url":url,"finalUrl":final,"domain":host,"httpStatus":status,"contentType":ctype,
                "pageTitle":" ".join(p.title).strip() or final,
                "accessStatus":"access-restricted" if restricted else "public-page-fetched",
                "opportunities":found,"linkCount":len(p.links),
                "note":"Detection is page-evidence screening, not proof that records can be extracted."}
    except Exception as e:
        return {"url":url,"domain":_host(url),"accessStatus":"probe-failed","error":f"{type(e).__name__}: {e}",
                "opportunities":{k:{"status":"unknown","evidenceTerms":[]} for k in PATTERNS}}
