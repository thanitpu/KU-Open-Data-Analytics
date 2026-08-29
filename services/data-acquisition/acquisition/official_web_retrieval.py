from __future__ import annotations
from urllib.request import Request, urlopen
from urllib.parse import urlparse, urljoin
from urllib.error import HTTPError, URLError
from html.parser import HTMLParser
from datetime import datetime, timezone
import json, re, xml.etree.ElementTree as ET

UA="Mozilla/5.0 KU-Open-DA-Official-Retrieval/2.10"

def _get(url,timeout=20,max_bytes=3_000_000):
    req=Request(url,headers={"User-Agent":UA,"Accept-Language":"th-TH,th;q=0.9,en;q=0.8"})
    with urlopen(req,timeout=timeout) as r:
        raw=r.read(max_bytes)
        return {
            "url":url,"final_url":r.geturl(),"status":getattr(r,"status",200),
            "content_type":r.headers.get("Content-Type",""),
            "body":raw.decode("utf-8","ignore")
        }

class InspectorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title=[]; self.in_title=False
        self.meta=[]; self.links=[]; self.images=[]; self.jsonld=[]
        self._jsonld=False; self._buf=[]
        self.text=[]; self._skip=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="title": self.in_title=True
        if tag in ("script","style","noscript"): self._skip+=1
        if tag=="script" and "ld+json" in a.get("type","").lower():
            self._jsonld=True; self._buf=[]
        if tag=="meta": self.meta.append(a)
        if tag=="link": self.links.append(a)
        if tag=="a" and a.get("href"):
            self.links.append({"href":a.get("href",""),"text":"","rel":a.get("rel",""),"class":a.get("class","")})
        if tag=="img" and (a.get("src") or a.get("data-src")):
            self.images.append({
                "src":a.get("src") or a.get("data-src"),
                "alt":a.get("alt",""),
                "title":a.get("title",""),
                "width":a.get("width",""),
                "height":a.get("height","")
            })
    def handle_endtag(self,tag):
        if tag=="title": self.in_title=False
        if tag=="script" and self._jsonld:
            self.jsonld.append("".join(self._buf)); self._jsonld=False; self._buf=[]
        if tag in ("script","style","noscript") and self._skip: self._skip-=1
    def handle_data(self,data):
        if self.in_title:self.title.append(data)
        if self._jsonld:self._buf.append(data)
        if not self._skip:
            x=" ".join(data.split())
            if x:self.text.append(x)

def _parse_jsonld(raws):
    out=[]
    for raw in raws:
        try:
            obj=json.loads(raw)
            if isinstance(obj,list): out.extend(obj)
            else: out.append(obj)
        except Exception:
            continue
    return out

def _find_meta(meta,key):
    for m in meta:
        if m.get("property")==key or m.get("name")==key:
            return m.get("content","")
    return ""

def _safe_get(url):
    try:return _get(url)
    except Exception as e:return {"url":url,"error":f"{type(e).__name__}: {e}"}

def _robots(base):
    p=urlparse(base); url=f"{p.scheme}://{p.netloc}/robots.txt"
    r=_safe_get(url)
    if "error" in r:return {"url":url,"available":False,"error":r["error"],"sitemaps":[]}
    sitemaps=re.findall(r"(?im)^\s*Sitemap:\s*(\S+)",r["body"])
    return {"url":url,"available":True,"status":r["status"],"sitemaps":sitemaps[:20]}

def _candidate_sitemaps(base,robots):
    p=urlparse(base); root=f"{p.scheme}://{p.netloc}"
    urls=list(robots.get("sitemaps") or [])
    urls += [root+"/sitemap.xml",root+"/sitemap_index.xml"]
    out=[]
    for u in urls:
        if u not in out:out.append(u)
    return out[:10]

def _inspect_sitemap(url):
    r=_safe_get(url)
    if "error" in r:return {"url":url,"available":False,"error":r["error"],"sample_urls":[]}
    body=r["body"]
    locs=re.findall(r"<loc>\s*(.*?)\s*</loc>",body,re.I|re.S)
    return {"url":url,"available":bool(locs),"status":r["status"],"url_count_estimate":len(locs),"sample_urls":locs[:20]}

def _feeds(base,links):
    found=[]
    for l in links:
        typ=(l.get("type") or "").lower()
        rel=(l.get("rel") or "").lower()
        href=l.get("href")
        if href and ("alternate" in rel) and ("rss" in typ or "atom" in typ):
            found.append(urljoin(base,href))
    return list(dict.fromkeys(found))[:10]


def _classify_section(label,url):
    x=(str(label)+" "+str(url)).lower()
    rules=[
        ("Promotion","Marketing",["promotion","promo","offer","campaign","deal"]),
        ("Menu","Product",["menu","food","drink","espresso","cafe-menu","restaurant-menu","bakery"]),
        ("Locations","About",["location","store","branch"]),
        ("Careers","Employment",["career","job","vacancy"]),
        ("Catering","Service",["catering"]),
        ("Contact","About",["contact"]),
        ("About","About",["about"]),
        ("Shopping","Product",["shop","shopping","product"])
    ]
    for section,tag,keys in rules:
        if any(k in x for k in keys): return section,tag
    return "Other","General"

def _internal_links(base,links):
    root=urlparse(base)
    out=[]; seen=set()
    for l in links:
        href=l.get("href") if isinstance(l,dict) else None
        if not href or href.startswith(("#","javascript:","mailto:","tel:")): continue
        u=urljoin(base,href)
        p=urlparse(u)
        if p.netloc != root.netloc: continue
        u=u.split("#")[0]
        if u in seen: continue
        seen.add(u)
        label=(l.get("text") or l.get("title") or "").strip()
        section,tag=_classify_section(label,u)
        out.append({"url":u,"label":label,"section":section,"tag":tag})
    return out

def _page_images(base,images):
    out=[]; seen=set()
    for im in images:
        u=urljoin(base,im.get("src",""))
        if not u or u in seen: continue
        seen.add(u)
        low=u.lower()
        likely=not any(x in low for x in ["logo","icon","sprite","favicon"])
        out.append({
            "url":u,"alt":im.get("alt",""),"title":im.get("title",""),
            "width":im.get("width",""),"height":im.get("height",""),
            "likely_content_image":likely
        })
    return out

def _inspect_child(url):
    try:
        page=_get(url)
        p=InspectorParser();p.feed(page["body"])
        imgs=_page_images(page["final_url"],p.images)
        text=" ".join(p.text)
        return {
            "url":page["final_url"],"title":" ".join(p.title).strip(),
            "image_count":len(imgs),
            "content_images":[x for x in imgs if x["likely_content_image"]][:12],
            "text_length":len(text),
            "date_candidates":list(dict.fromkeys(re.findall(
                r"\b(?:\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|"
                r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|"
                r"\d{1,2}\s+[A-Za-z]+\s*-\s*\d{1,2}\s+[A-Za-z]+\s+\d{4})\b",text,re.I)))[:10]
        }
    except Exception as e:
        return {"url":url,"error":f"{type(e).__name__}: {e}"}

def _purpose_profile(section):
    profiles={
        "Promotion":{
            "record_type":"PromotionCandidate","tag":"Marketing",
            "expected_fields":["title","description","promotion_start","promotion_end","terms","branch","image_url"],
            "visual_schema":["promotion_title","offer","start_date","end_date","terms","participating_branch"]
        },
        "Menu":{
            "record_type":"MenuCandidate","tag":"Product",
            "expected_fields":["category","item_name","description","variant","price","currency","image_url"],
            "visual_schema":["category","item_name","description","variant","price","currency"]
        }
    }
    return profiles.get(section,{
        "record_type":"OfficialSection","tag":"General",
        "expected_fields":["title","description"],"visual_schema":[]
    })

def _visual_readiness(section,images):
    if section not in ("Promotion","Menu"): return "not-targeted"
    return "vision-ready" if images else "no-content-image"

def _target_records(section_info):
    section=section_info.get("section","Other")
    profile=_purpose_profile(section)
    records=[]
    for url in section_info.get("urls",[])[:12]:
        info=_inspect_child(url)
        if info.get("error"): continue
        images=info.get("content_images") or []
        rec={
            "record_type":profile["record_type"],
            "section":section,
            "source_tag":section_info.get("tag") or profile["tag"],
            "title":info.get("title",""),
            "text":f"{section} official page",
            "posted_at":(info.get("date_candidates") or [""])[0],
            "date_candidates":info.get("date_candidates",[]),
            "url":info.get("url",url),"source_url":info.get("url",url),
            "image_count":info.get("image_count",0),
            "content_images":images,
            "visual_readiness":_visual_readiness(section,images),
            "expected_fields":profile["expected_fields"],
            "visual_extraction_schema":profile["visual_schema"],
            "provenance":"official-section-target"
        }
        records.append(rec)
    return records

def configure(url):
    page=_get(url)
    p=InspectorParser(); p.feed(page["body"])
    robots=_robots(page["final_url"])
    sitemap_infos=[]
    for u in _candidate_sitemaps(page["final_url"],robots):
        info=_inspect_sitemap(u)
        if info.get("available"):sitemap_infos.append(info)
    jsonld=_parse_jsonld(p.jsonld)
    types=[]
    for obj in jsonld:
        if isinstance(obj,dict):
            t=obj.get("@type")
            if isinstance(t,list):types.extend(map(str,t))
            elif t:types.append(str(t))
    feeds=_feeds(page["final_url"],p.links)

    links=_internal_links(page["final_url"],p.links)
    sections={}
    for x in links:
        if x["section"]=="Other": continue
        sections.setdefault(x["section"],{"section":x["section"],"tag":x["tag"],"urls":[]})
        if len(sections[x["section"]]["urls"])<12:
            sections[x["section"]]["urls"].append(x["url"])
    useful_sections=list(sections.values())

    home_images=_page_images(page["final_url"],p.images)
    high_value=[x for x in useful_sections if x["section"] in ("Promotion","Menu","Locations","Careers")]
    page_samples=[]
    for sec in high_value[:4]:
        if sec["urls"]:
            sample=_inspect_child(sec["urls"][0])
            sample["section"]=sec["section"]; sample["tag"]=sec["tag"]
            sample["visual_readiness"]=_visual_readiness(sec["section"],sample.get("content_images") or [])
            sample["expected_fields"]=_purpose_profile(sec["section"])["expected_fields"]
            page_samples.append(sample)

    targeted_candidates=[]
    for sec in useful_sections:
        if sec["section"] in ("Promotion","Menu"):
            targeted_candidates.extend(_target_records(sec))

    methods=[]
    if jsonld: methods.append({"priority":1,"method":"json-ld","reason":"Structured Schema.org data detected"})
    if useful_sections: methods.append({"priority":2,"method":"section-targeted","reason":"Useful official sections discovered from internal navigation"})
    if sitemap_infos: methods.append({"priority":3,"method":"sitemap-targeted","reason":"Sitemap detected"})
    if feeds: methods.append({"priority":4,"method":"rss-atom","reason":"RSS/Atom feed detected"})
    if any(x.get("content_images") for x in page_samples):
        methods.append({"priority":5,"method":"visual-candidate","reason":"Content images detected; suitable for later Vision extraction"})
    methods.append({"priority":9,"method":"main-content","reason":"Official-page semantic text extraction fallback"})

    return {
        "schema":"ku2d.official-retrieval-config.v2",
        "url":url,"final_url":page["final_url"],"http_status":page["status"],
        "page_title":" ".join(p.title).strip(),
        "robots":robots,"sitemaps":sitemap_infos,"feeds":feeds,
        "jsonld_count":len(jsonld),"schema_types":sorted(set(types)),
        "internal_link_count":len(links),
        "home_image_count":len(home_images),
        "useful_sections":useful_sections,
        "section_samples":page_samples,
        "targeted_candidates":targeted_candidates,
        "vision_candidate_count":sum(1 for x in targeted_candidates if x.get("visual_readiness")=="vision-ready"),
        "recommended_methods":methods,
        "recommended_method":methods[0]["method"],
        "configured_at":datetime.now(timezone.utc).isoformat()
    }

def _flatten_jsonld(obj,source_url):
    records=[]
    items=obj if isinstance(obj,list) else [obj]
    for x in items:
        if not isinstance(x,dict):continue
        graph=x.get("@graph")
        if isinstance(graph,list):
            records.extend(_flatten_jsonld(graph,source_url)); continue
        typ=x.get("@type")
        if isinstance(typ,list):typ="|".join(map(str,typ))
        text=x.get("description") or x.get("headline") or x.get("name") or ""
        rec={
            "record_type":str(typ or "StructuredData"),
            "name":x.get("name",""),
            "title":x.get("headline",""),
            "text":text,
            "posted_at":x.get("datePublished") or x.get("dateCreated") or x.get("startDate") or "",
            "modified_at":x.get("dateModified") or "",
            "telephone":x.get("telephone",""),
            "address":x.get("address",""),
            "url":x.get("url") or source_url,
            "source_url":source_url,
            "source_tag":"About" if str(typ) in ("Organization","LocalBusiness","Restaurant") else "General",
            "provenance":"official-json-ld"
        }
        records.append(rec)
    return records

def retrieve(url,method="auto"):
    page=_get(url)
    p=InspectorParser();p.feed(page["body"])
    jsonld=_parse_jsonld(p.jsonld)
    selected=method
    if method=="auto":
        selected="json-ld" if jsonld else "section-targeted"

    records=[]
    if selected=="section-targeted":
        links=_internal_links(page["final_url"],p.links)
        useful=[x for x in links if x["section"]!="Other"]
        grouped={}
        for x in useful:
            grouped.setdefault((x["section"],x["tag"]),{"section":x["section"],"tag":x["tag"],"urls":[]})
            if x["url"] not in grouped[(x["section"],x["tag"])]["urls"]:
                grouped[(x["section"],x["tag"])]["urls"].append(x["url"])
        for sec in list(grouped.values())[:20]:
            if sec["section"] in ("Promotion","Menu"):
                records.extend(_target_records(sec))
            else:
                for xurl in sec["urls"][:5]:
                    info=_inspect_child(xurl)
                    if info.get("error"): continue
                    records.append({
                        "record_type":"OfficialSection","section":sec["section"],
                        "name":sec["section"],"title":info.get("title",""),
                        "text":f"{sec['section']} official page",
                        "posted_at":(info.get("date_candidates") or [""])[0],
                        "modified_at":"","telephone":"","address":"",
                        "url":xurl,"source_url":xurl,"source_tag":sec["tag"],
                        "provenance":"official-navigation",
                        "image_count":info.get("image_count",0),
                        "content_images":info.get("content_images",[]),
                        "date_candidates":info.get("date_candidates",[])
                    })
        if not records:selected="main-content"

    if selected=="json-ld":
        for obj in jsonld:records.extend(_flatten_jsonld(obj,page["final_url"]))
        if not records:selected="main-content"

    if selected=="main-content":
        text=" ".join(p.text)
        # paragraph-like sentences; retain meaningful chunks only
        chunks=re.split(r'(?<=[.!?。])\s+|\s{2,}',text)
        seen=set()
        for c in chunks:
            c=" ".join(c.split())
            if len(c)<60 or c in seen:continue
            seen.add(c)
            low=c.lower()
            if any(x in low for x in ["privacy policy","cookie policy","all rights reserved","sign up","log in"]):continue
            tag="Marketing" if any(x in low for x in ["promotion","โปรโมชั่น","offer","campaign","ส่วนลด"]) else \
                "Employment" if any(x in low for x in ["career","job","สมัครงาน","ตำแหน่งงาน"]) else \
                "About" if any(x in low for x in ["address","ที่อยู่","contact","ติดต่อ","branch","สาขา","telephone","โทร"]) else "General"
            records.append({
                "record_type":"OfficialPageText","name":"","title":"","text":c[:2000],
                "posted_at":"","modified_at":"","telephone":"","address":"",
                "url":page["final_url"],"source_url":page["final_url"],
                "source_tag":tag,"provenance":"official-main-content"
            })
            if len(records)>=50:break

    collected=datetime.now(timezone.utc).isoformat()
    for r in records:r["collected_at"]=collected
    return {
        "schema":"ku2d.official-retrieval-result.v1",
        "url":url,"final_url":page["final_url"],"method":selected,
        "record_count":len(records),"records":records,
        "collected_at":collected,
        "quality_tier":"A" if selected=="json-ld" else ("B" if selected=="section-targeted" else "C")
    }
