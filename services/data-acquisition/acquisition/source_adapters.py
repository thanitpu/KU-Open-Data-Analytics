from __future__ import annotations
from urllib.parse import urlparse
import re,json

THB_PAT=re.compile(r"(?:฿|THB|บาท)?\s*([0-9]{1,6}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)\s*(?:บาท|THB|฿)?",re.I)
SIZE_PAT=re.compile(r"\b(\d+(?:\.\d+)?)\s*(ml|มล\.?|l|ลิตร|g|กรัม|kg|กก\.?|ชิ้น|pcs|pack|แพ็ค)\b",re.I)
DATE_PAT=re.compile(r"\b(\d{1,2})[\s/\-](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.|\d{1,2})[\s/\-](20\d{2}|25\d{2})\b",re.I)

def clean(s):return re.sub(r"\s+"," ",str(s or "")).strip()

def money(s):
    if s is None:return None
    m=re.search(r"([0-9]{1,6}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)",str(s))
    return float(m.group(1).replace(",","")) if m else None

def domain(url):
    return urlparse(url or "").netloc.lower().replace("www.","")

class BaseAdapter:
    key="generic";sector="Retail"
    domains=()
    def matches(self,url):return any(d in domain(url) for d in self.domains)
    def navigation_targets(self):
        return ["product","products","promotion","promotions","campaign","catalog","menu","offers","sale"]
    def classify_page(self,url,title="",text=""):
        x=(url+" "+title).lower()
        if any(k in x for k in ("promotion","campaign","offer","sale","catalog")):return "promotion"
        if any(k in x for k in ("product","p/","item","sku")):return "product"
        if "menu" in x:return "menu"
        return "general"
    def normalize_product(self,p,source_url="",posted_at=""):
        name=clean(p.get("name") or p.get("title") or p.get("product_name"))
        if not name:return None
        price=money(p.get("price") or p.get("current_price"))
        regular=money(p.get("regular_price") or p.get("original_price") or p.get("compare_at_price"))
        promo=money(p.get("promo_price") or p.get("sale_price"))
        return {"record_type":"ProductCandidate","product_name":name,"brand":clean(p.get("brand")),
          "category":clean(p.get("category")),"price":price,"regular_price":regular,"promo_price":promo,
          "currency":p.get("currency") or "THB","sku":clean(p.get("sku")),"source_url":source_url or p.get("url",""),
          "posted_at":posted_at or p.get("posted_at",""),"source_tag":"Marketing","provenance":p.get("provenance","adapter")}
    def normalize_promotion(self,p,source_url="",posted_at=""):
        title=clean(p.get("title") or p.get("promotion_title") or p.get("name"))
        if not title:return None
        return {"record_type":"PromotionCandidate","promotion_title":title,"promotion_type":clean(p.get("promotion_type")),
          "offer":clean(p.get("offer") or p.get("description")),"start_date":clean(p.get("start_date")),
          "end_date":clean(p.get("end_date")),"valid_time":clean(p.get("valid_time")),
          "participating_branch":clean(p.get("participating_branch") or p.get("location")),
          "terms":clean(p.get("terms")),"posted_at":posted_at or p.get("posted_at",""),
          "source_url":source_url or p.get("url",""),"source_image":p.get("image",""),
          "source_tag":"Marketing","provenance":p.get("provenance","adapter")}
    def extract_from_jsonld(self,obj,source_url=""):
        out=[]
        stack=obj if isinstance(obj,list) else [obj]
        while stack:
            x=stack.pop()
            if isinstance(x,list):stack.extend(x);continue
            if not isinstance(x,dict):continue
            typ=x.get("@type")
            types=set(typ if isinstance(typ,list) else [typ])
            if "Product" in types:
                offers=x.get("offers") or {}
                if isinstance(offers,list):offers=offers[0] if offers else {}
                brand=x.get("brand");brand=brand.get("name","") if isinstance(brand,dict) else brand
                r=self.normalize_product({"name":x.get("name"),"brand":brand,"sku":x.get("sku"),
                    "price":offers.get("price") or offers.get("lowPrice"),"currency":offers.get("priceCurrency"),
                    "url":x.get("url"),"provenance":"json-ld"},source_url)
                if r:out.append(r)
            if "@graph" in x:stack.append(x["@graph"])
            for k,v in x.items():
                if k not in ("@graph",) and isinstance(v,(dict,list)):stack.append(v)
        return out
    def extract_text_candidates(self,text,source_url=""):
        # Conservative fallback: lines containing a currency/price and a plausible product phrase.
        out=[]
        lines=[clean(x) for x in str(text or "").splitlines()]
        for line in lines:
            if len(line)<5 or len(line)>260:continue
            nums=list(THB_PAT.finditer(line))
            if not nums:continue
            if not (re.search(r"(บาท|฿|THB)",line,re.I) or SIZE_PAT.search(line)):continue
            price=money(nums[-1].group(0))
            name=clean(line[:nums[-1].start()]).strip("-:| ")
            if len(name)<3:continue
            out.append(self.normalize_product({"name":name,"price":price,"provenance":"text-pattern"},source_url))
        return [x for x in out if x]

class TopsAdapter(BaseAdapter):
    key="tops";sector="Supermarket";domains=("tops.co.th",)
    def navigation_targets(self):return ["campaign","promotions","product","fresh-food-bakery","grocery","catalog"]

class LotusAdapter(BaseAdapter):
    key="lotuss";sector="Supermarket";domains=("lotuss.com",)

class BigCAdapter(BaseAdapter):
    key="bigc";sector="Supermarket";domains=("bigc.co.th",)

class MakroAdapter(BaseAdapter):
    key="makro";sector="Supermarket";domains=("makro.co.th",)
    def navigation_targets(self):return ["promotion","catalog","makro-pro","product","offers"]

class GourmetAdapter(BaseAdapter):
    key="gourmetmarket";sector="Supermarket";domains=("gourmetmarketthailand.com",)

class CafeAdapter(BaseAdapter):
    sector="Cafe"
    def navigation_targets(self):return ["menu","promotion","campaign","offers","products"]

class DeanDelucaAdapter(CafeAdapter):
    key="dean-deluca";domains=("deandeluca.co.th",)

class StarbucksAdapter(CafeAdapter):
    key="starbucks-th";domains=("starbucks.co.th",)

class BeautyAdapter(BaseAdapter):
    sector="Beauty"
    def navigation_targets(self):return ["promotion","campaign","product","brands","new-arrivals","sale"]

class ITAdapter(BaseAdapter):
    sector="IT Retail"
    def navigation_targets(self):return ["product","promotion","campaign","computer-set","notebook","mobile","sale"]

ADAPTERS=[
 TopsAdapter(),LotusAdapter(),BigCAdapter(),MakroAdapter(),GourmetAdapter(),
 DeanDelucaAdapter(),StarbucksAdapter()
]
BEAUTY_DOMAINS={"watsons.co.th":"watsons","konvy.com":"konvy","eveandboy.com":"eveandboy",
 "thebeautrium.com":"beautrium","boots.co.th":"boots"}
IT_DOMAINS={"jib.co.th":"jib","advice.co.th":"advice","itcity.in.th":"it-city",
 "ihavecpu.com":"ihavecpu","banana.co.th":"banana"}

def adapter_for(url):
    for a in ADAPTERS:
        if a.matches(url):return a
    d=domain(url)
    for dom,key in BEAUTY_DOMAINS.items():
        if dom in d:
            a=BeautyAdapter();a.key=key;a.domains=(dom,);return a
    for dom,key in IT_DOMAINS.items():
        if dom in d:
            a=ITAdapter();a.key=key;a.domains=(dom,);return a
    return BaseAdapter()

def normalize_acquisition(url,payload):
    a=adapter_for(url);records=[]
    for obj in payload.get("jsonld",[]):records.extend(a.extract_from_jsonld(obj,url))
    for p in payload.get("products",[]):
        r=a.normalize_product(p,url,payload.get("posted_at",""))
        if r:records.append(r)
    for p in payload.get("promotions",[]):
        r=a.normalize_promotion(p,url,payload.get("posted_at",""))
        if r:records.append(r)
    if payload.get("text"):records.extend(a.extract_text_candidates(payload["text"],url))
    # dedup normalized candidates before Repository evidence hashing/entity resolution.
    seen=set();unique=[]
    for r in records:
        k=(r.get("record_type"),r.get("product_name") or r.get("promotion_title"),r.get("price"),r.get("source_url"))
        if k not in seen:seen.add(k);unique.append(r)
    return {"adapter":a.key,"sector":a.sector,"page_type":a.classify_page(url,payload.get("title",""),payload.get("text","")),
            "navigation_targets":a.navigation_targets(),"records":unique}
