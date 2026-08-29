from __future__ import annotations
from urllib.request import Request,urlopen
from urllib.parse import urljoin,urlparse
from urllib.error import HTTPError,URLError
from html.parser import HTMLParser
import json,re,time
from source_adapters import adapter_for,normalize_acquisition
from optimized_adapters import optimized_records
from promotion_terms import enrich_promotion_record
from pagination_monitor import normalized_text_hash,discover_pagination,pagination_summary_from_pages

UA="Mozilla/5.0 (compatible; KU2D-Research/1.0; +public-data-acquisition)"
MAX_BYTES=3_000_000

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.images=[];self.scripts=[];self.title="";self._title=False
        self._script=False;self._stype="";self._buf=[];self.text=[];self.meta={}
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=="a" and d.get("href"):self.links.append((d.get("href"),d.get("title","")))
        elif tag=="img" and (d.get("src") or d.get("data-src")):
            self.images.append({"src":d.get("src") or d.get("data-src"),"alt":d.get("alt",""),
                                "width":d.get("width"),"height":d.get("height")})
        elif tag=="title":self._title=True
        elif tag=="script":
            self._script=True;self._stype=(d.get("type") or "").lower();self._buf=[]
        elif tag=="meta":
            key=d.get("property") or d.get("name")
            if key and d.get("content"):self.meta[key.lower()]=d["content"]
    def handle_endtag(self,tag):
        if tag=="title":self._title=False
        elif tag=="script" and self._script:
            if "ld+json" in self._stype:self.scripts.append("".join(self._buf))
            self._script=False;self._buf=[]
    def handle_data(self,data):
        if self._title:self.title+=data
        if self._script:self._buf.append(data)
        elif data.strip():self.text.append(data.strip())

def fetch(url,timeout=15):
    req=Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
    try:
        with urlopen(req,timeout=timeout) as r:
            ct=r.headers.get("Content-Type","")
            raw=r.read(MAX_BYTES)
            enc=r.headers.get_content_charset() or "utf-8"
            return {"ok":True,"status":getattr(r,"status",200),"content_type":ct,
                    "final_url":r.geturl(),"text":raw.decode(enc,"replace")}
    except HTTPError as e:return {"ok":False,"status":e.code,"error":f"HTTP {e.code}"}
    except (URLError,TimeoutError,OSError) as e:return {"ok":False,"status":0,"error":type(e).__name__+": "+str(e)}

def same_domain(a,b):
    da=urlparse(a).netloc.lower().replace("www.","");db=urlparse(b).netloc.lower().replace("www.","")
    return da==db or da.endswith("."+db) or db.endswith("."+da)

def image_score(img):
    s=(img.get("src","")+" "+img.get("alt","")).lower();score=0
    good=("menu","promotion","promo","campaign","catalog","offer","price","deal","product","banner")
    bad=("logo","icon","sprite","favicon","payment","footer","header","social","facebook","instagram","tiktok")
    score+=sum(2 for x in good if x in s);score-=sum(3 for x in bad if x in s)
    try:
        w=int(re.sub(r"\D","",str(img.get("width") or "0")) or 0);h=int(re.sub(r"\D","",str(img.get("height") or "0")) or 0)
        if w>=500 or h>=500:score+=2
        if 0<w<120 and 0<h<120:score-=3
    except:pass
    return score

def parse_page(url,html):
    p=PageParser();p.feed(html)
    jsonld=[]
    for raw in p.scripts:
        try:jsonld.append(json.loads(raw))
        except:pass
    links=[]
    for href,label in p.links:
        u=urljoin(url,href)
        if u.startswith(("http://","https://")) and same_domain(url,u):
            links.append({"url":u.split("#")[0],"label":re.sub(r"\s+"," ",label).strip()})
    images=[]
    for im in p.images:
        x=dict(im);x["src"]=urljoin(url,x["src"]);x["score"]=image_score(x);images.append(x)
    images.sort(key=lambda x:x["score"],reverse=True)
    return {"title":re.sub(r"\s+"," ","".join(p.title)).strip(),"text":"\n".join(p.text),
            "jsonld":jsonld,"links":links,"images":images,"meta":p.meta}

def discover(url,max_pages=8,delay_seconds=0,progress=None):
    adapter=adapter_for(url);targets=adapter.navigation_targets()
    queue=[url];seen=set();pages=[];diagnostics=[]
    while queue and len(pages)<max_pages:
        u=queue.pop(0)
        if u in seen:continue
        seen.add(u)
        if pages and delay_seconds:time.sleep(max(0,float(delay_seconds)))
        r=fetch(u)
        if not r["ok"]:
            diagnostics.append({"url":u,"status":"fetch-failed","detail":r.get("error")});continue
        if "html" not in r.get("content_type","").lower():
            diagnostics.append({"url":u,"status":"non-html","content_type":r.get("content_type")});continue
        parsed=parse_page(r["final_url"],r["text"])
        norm=normalize_acquisition(r["final_url"],{"title":parsed["title"],"text":parsed["text"],
                                                    "jsonld":parsed["jsonld"]})
        optimized=optimized_records(adapter.key,parsed["text"],parsed["images"],r["final_url"],parsed["title"])
        merged=norm["records"]+optimized
        seen=set();records=[]
        for z in merged:
            k=(z.get("record_type"),z.get("product_name") or z.get("title") or z.get("promotion_title"),
               z.get("price"),z.get("source_url"),z.get("source_image"))
            if k not in seen:seen.add(k);records.append(enrich_promotion_record(z))
        pagination_links=discover_pagination(r["final_url"],parsed["links"])
        pages.append({"url":r["final_url"],"title":parsed["title"],"page_type":norm["page_type"],
                      "records":records,"images":parsed["images"][:20],"meta":parsed["meta"],"links":parsed["links"][:500],
                      "content_hash":normalized_text_hash(parsed["text"]),"pagination_links":pagination_links})
        if progress:
            try:
                progress({"pages_done":len(pages),"records_found":sum(len(p["records"]) for p in pages),
                          "current_url":r["final_url"],
                          "message":f"Acquired {len(pages)} of {max_pages} pages"})
            except Exception:
                pass
        ranked=[]
        for x in parsed["links"]:
            lu=x["url"].lower();score=sum(2 for t in targets if t in lu)
            if score and x["url"] not in seen:ranked.append((score,x["url"]))
        for _,v in sorted(ranked,reverse=True):
            if v not in queue:queue.append(v)
    records=[];images=[]
    for p in pages:
        records.extend(p["records"])
        for im in p["images"]:
            if im["score"]>0:images.append({"page_url":p["url"],**im})
    # final record dedup
    uniq=[];keys=set()
    for r in records:
        k=(r.get("record_type"),r.get("product_name") or r.get("promotion_title"),r.get("price"),r.get("source_url"))
        if k not in keys:keys.add(k);uniq.append(r)
    return {"adapter":adapter.key,"sector":adapter.sector,"start_url":url,"pages":pages,
            "records":uniq,"vision_candidates":sorted(images,key=lambda x:x["score"],reverse=True)[:30],
            "pagination_groups":pagination_summary_from_pages(pages),"diagnostics":diagnostics}
