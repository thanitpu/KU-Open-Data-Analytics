from urllib.parse import quote_plus,urlparse,parse_qs,unquote
from urllib.request import Request,urlopen
from html.parser import HTMLParser
import html,re,time

DDG_HTML="https://html.duckduckgo.com/html/?q={query}"

class DDGParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.results=[]; self.in_title=False; self.href=None; self.buf=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="a" and "result__a" in a.get("class",""):
            self.in_title=True; self.href=a.get("href"); self.buf=[]
    def handle_data(self,data):
        if self.in_title:self.buf.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.in_title:
            title=" ".join("".join(self.buf).split())
            if title and self.href:self.results.append((title,self.href))
            self.in_title=False; self.href=None; self.buf=[]

def unwrap(url):
    try:
        p=urlparse(url)
        if "duckduckgo.com" in p.netloc and p.path.startswith("/l/"):
            q=parse_qs(p.query)
            if q.get("uddg"): return unquote(q["uddg"][0])
    except Exception: pass
    return url

def search_web(query,limit=8,timeout=20):
    req=Request(DDG_HTML.format(query=quote_plus(query)),headers={"User-Agent":"Mozilla/5.0 KU-Open-DA-Discovery/1.5"})
    with urlopen(req,timeout=timeout) as r: body=r.read().decode("utf-8","ignore")
    p=DDGParser();p.feed(body);out=[]
    for title,href in p.results:
        href=unwrap(html.unescape(href))
        if href.startswith("http"):out.append({"title":html.unescape(title),"url":href})
        if len(out)>=limit:break
    return out

def classify(url,title,intent):
    host=(urlparse(url).netloc or "").lower().removeprefix("www.")
    text=(title+" "+url).lower()
    label=host or "Web"
    for needle,name in [("wongnai.com","Wongnai"),("onebangkok.com","One Bangkok"),("facebook.com","Facebook"),("instagram.com","Instagram"),("tripadvisor.","Tripadvisor")]:
        if needle in host: label=name
    dtype=intent
    if any(x in text for x in ["review","reviews","รีวิว"]):dtype="reviews"
    elif any(x in text for x in ["promotion","promotions","โปรโม","offer","privilege"]):dtype="promotions"
    elif any(x in text for x in ["menu","เมนู"]):dtype="offering"
    elif any(x in text for x in ["similar","recommended","ร้านคล้าย","ใกล้"]):dtype="similar"
    elif any(x in text for x in ["facebook","instagram","post"]):dtype="posts"
    return label,host,dtype

def standard_route(host,dtype):
    if "facebook.com" in host or "instagram.com" in host:return "Official platform API / OAuth or authorized connector"
    if dtype=="reviews":return "Source-supported API/export if available; otherwise configured domain adapter"
    return "Official API/feed/export where available; otherwise configured domain adapter"

def discover_business(name,context="",max_per_query=6):
    name=(name or "").strip();context=(context or "").strip()
    if not name:raise ValueError("Business name is required.")
    base=f'"{name}" {context}'.strip()
    intents=[("reviews",f"{base} reviews รีวิว"),("promotions",f"{base} promotion โปรโมชั่น"),("offering",f"{base} menu เมนู"),("similar",f"{base} similar recommended ร้านคล้าย"),("posts",f"{base} Facebook Instagram"),("profile",f"{base} official website")]
    found=[];seen=set();errors=[]
    for intent,q in intents:
        try:
            for r in search_web(q,max_per_query):
                url=r["url"];key=url.split("#")[0]
                if key in seen:continue
                seen.add(key);label,host,dtype=classify(url,r["title"],intent)
                found.append({"sourceLabel":label,"domain":host,"dataType":dtype,"title":r["title"],"url":url,"discoveredBy":"public-web-search","discoveryQuery":q,"quickMethod":"Public page test / limited extraction where accessible","standardMethod":standard_route(host,dtype),"verificationStatus":"search-result-found"})
        except Exception as e:errors.append({"intent":intent,"error":f"{type(e).__name__}: {e}"})
        time.sleep(.25)
    words=[w.lower() for w in re.findall(r"[A-Za-z0-9\u0E00-\u0E7F]+",name) if len(w)>2]
    for x in found:
        hay=(x["title"]+" "+x["url"]).lower()
        x["relevanceScore"]=sum(1 for w in words if w in hay)/max(1,len(words))
    found.sort(key=lambda x:(x["relevanceScore"],x["dataType"] in ("reviews","promotions","similar")),reverse=True)
    return {"business":{"name":name,"context":context},"discoveryMethod":"Quick workaround: public web search HTML","warning":"Search discovery is exploratory and can be incomplete. A result is a discovered public URL, not proof that KU Open DA can retrieve underlying records.","results":found[:30],"errors":errors}

def normalize_seed_url(raw):
    raw=(raw or "").strip()
    if not raw:return ""
    # Accept pasted prose containing a URL.
    m=re.search(r"https?://[^\s<>\"']+",raw)
    if m: raw=m.group(0)
    raw=raw.rstrip(".,);]")
    return raw

class PageProbeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title=[];self.in_title=False;self.links=[];self.text=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="title":self.in_title=True
        if tag=="a" and a.get("href"):self.links.append((a.get("href"),a.get("aria-label","")))
    def handle_endtag(self,tag):
        if tag=="title":self.in_title=False
    def handle_data(self,data):
        if self.in_title:self.title.append(data)
        if data.strip():self.text.append(data.strip())

def probe_public_url(url,timeout=20):
    url=normalize_seed_url(url)
    if not url:raise ValueError("Seed URL is empty.")
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 KU-Open-DA-Discovery/1.6"})
    with urlopen(req,timeout=timeout) as r:
        ctype=r.headers.get("Content-Type","")
        body=r.read(2_000_000).decode("utf-8","ignore")
        final_url=r.geturl()
        status=getattr(r,"status",200)
    p=PageProbeParser();p.feed(body)
    title=" ".join(" ".join(p.title).split()) or final_url
    text=" ".join(p.text[:500]).lower()
    opportunities=[]
    checks=[
        ("reviews",["review","reviews","รีวิว","rating","คะแนน"]),
        ("promotions",["promotion","promotions","โปรโมชั่น","offer","privilege","deal"]),
        ("offering",["menu","เมนู","product","สินค้า"]),
        ("similar",["similar","recommended","ร้านคล้าย","แนะนำ","ใกล้เคียง"]),
        ("posts",["post","facebook","instagram"])
    ]
    for dtype,needles in checks:
        hits=[x for x in needles if x in text]
        if hits: opportunities.append({"dataType":dtype,"evidenceTerms":hits[:5]})
    label,host,_=classify(final_url,title,"profile")
    return {
        "sourceLabel":label,"domain":host,"dataType":"profile",
        "title":title,"url":final_url,"httpStatus":status,"contentType":ctype,
        "discoveredBy":"direct-seed-url","verificationStatus":"public-url-fetched",
        "quickMethod":"Direct public-page probe / limited extraction where accessible",
        "standardMethod":standard_route(host,"profile"),
        "detectedOpportunities":opportunities
    }

def discover_business_with_seed(name,context="",seed_url=""):
    base=discover_business(name,context)
    seed=normalize_seed_url(seed_url)
    if seed:
        try:
            probed=probe_public_url(seed)
            # Add a base page row plus explicit detected opportunity rows.
            rows=[probed]
            for op in probed.get("detectedOpportunities",[]):
                r=dict(probed);r["dataType"]=op["dataType"];r["evidenceTerms"]=op["evidenceTerms"]
                r["standardMethod"]=standard_route(probed["domain"],op["dataType"])
                rows.append(r)
            existing={x["url"]+"|"+x["dataType"] for x in base["results"]}
            for r in reversed(rows):
                key=r["url"]+"|"+r["dataType"]
                if key not in existing:
                    base["results"].insert(0,r);existing.add(key)
            base["seedProbe"]={"ok":True,"url":seed,"status":probed["verificationStatus"]}
        except Exception as e:
            base["seedProbe"]={"ok":False,"url":seed,"error":f"{type(e).__name__}: {e}"}
    return base


SOCIAL_GROUPS = [
    ("official","Official website",None),
    ("facebook","Facebook","facebook.com"),
    ("instagram","Instagram","instagram.com"),
    ("tiktok","TikTok","tiktok.com"),
    ("x","X","x.com"),
]

def _google_public_search(query, limit=10, timeout=20):
    """Quick workaround: fetch Google public search HTML; extract organic destination URLs only."""
    url="https://www.google.com/search?q="+quote_plus(query)+"&num="+str(max(10,limit))+"&filter=1"
    req=Request(url,headers={
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36",
        "Accept-Language":"th-TH,th;q=0.9,en;q=0.8"
    })
    with urlopen(req,timeout=timeout) as r:
        body=r.read().decode("utf-8","ignore")
    # Google organic links commonly occur as /url?q=<destination>; ignore Google-owned navigation/ad URLs.
    candidates=[]
    for m in re.finditer(r'href=["\'](/url\?[^"\']+|https?://[^"\']+)["\']',body,re.I):
        href=html.unescape(m.group(1))
        if href.startswith("/url?"):
            q=parse_qs(urlparse(href).query)
            href=q.get("q",q.get("url",[""]))[0]
        if not href.startswith("http"): continue
        host=(urlparse(href).netloc or "").lower()
        if not host or "google." in host or "googleusercontent." in host or "gstatic." in host: continue
        # Exclude known ad/tracking destinations and obvious sponsored redirect parameters.
        if "googleadservices." in host or "doubleclick." in host: continue
        href=href.split("&ved=")[0]
        if href not in candidates:candidates.append(href)
        if len(candidates)>=limit:break
    return candidates

def _title_from_url(url):
    host=(urlparse(url).netloc or "").removeprefix("www.")
    path=urlparse(url).path.strip("/")
    return host + ((" — "+path[:80]) if path else "")

def google_grouped_discovery(name,context="",seed_url=""):
    name=(name or "").strip(); context=(context or "").strip()
    if not name: raise ValueError("Business name is required.")
    base=f'"{name}" {context}'.strip()
    groups={}; all_seen=set(); errors=[]

    # Explicit groups.
    queries=[
        ("official","Official website",f'{base} official'),
        ("facebook","Facebook",f'site:facebook.com {base}'),
        ("instagram","Instagram",f'site:instagram.com {base}'),
        ("tiktok","TikTok",f'site:tiktok.com {base}'),
        ("x","X",f'(site:x.com OR site:twitter.com) {base}')
    ]
    for gid,label,q in queries:
        try:
            urls=_google_public_search(q,5)
            # For social groups enforce expected host. Official excludes major social hosts.
            if gid=="official":
                social=("facebook.com","instagram.com","tiktok.com","x.com","twitter.com")
                urls=[u for u in urls if not any(x in (urlparse(u).netloc or "").lower() for x in social)]
            else:
                expected={"facebook":"facebook.com","instagram":"instagram.com","tiktok":"tiktok.com","x":("x.com","twitter.com")}[gid]
                if isinstance(expected,tuple): urls=[u for u in urls if any(x in (urlparse(u).netloc or "").lower() for x in expected)]
                else: urls=[u for u in urls if expected in (urlparse(u).netloc or "").lower()]
            rows=[]
            for rank,u in enumerate(urls[:1],1):
                all_seen.add(u); rows.append({"group":gid,"groupLabel":label,"organicRank":rank,"url":u,"domain":(urlparse(u).netloc or "").removeprefix("www."),"title":_title_from_url(u),"status":"google-organic-found","sponsored":False})
            groups[gid]={"label":label,"query":q,"results":rows}
        except Exception as e:
            groups[gid]={"label":label,"query":q,"results":[]};errors.append({"group":gid,"error":f"{type(e).__name__}: {e}"})

    # Other top 5 organic, excluding URLs/domains already represented above.
    try:
        urls=_google_public_search(base,20)
        used_domains={(urlparse(u).netloc or "").lower().removeprefix("www.") for u in all_seen}
        other=[]
        for u in urls:
            d=(urlparse(u).netloc or "").lower().removeprefix("www.")
            if u in all_seen or d in used_domains: continue
            if any(x in d for x in ("facebook.com","instagram.com","tiktok.com","x.com","twitter.com")): continue
            other.append({"group":"other","groupLabel":"Other Google organic","organicRank":len(other)+1,"url":u,"domain":d,"title":_title_from_url(u),"status":"google-organic-found","sponsored":False})
            used_domains.add(d)
            if len(other)>=5:break
        groups["other"]={"label":"Other Google organic (Top 5 unique sources)","query":base,"results":other}
    except Exception as e:
        groups["other"]={"label":"Other Google organic (Top 5 unique sources)","query":base,"results":[]};errors.append({"group":"other","error":f"{type(e).__name__}: {e}"})

    # Keep v1.6 seed URL as verified fallback/augmentation.
    seed_result=None
    seed=normalize_seed_url(seed_url)
    if seed:
        try:
            p=probe_public_url(seed); seed_result=p
        except Exception as e:
            seed_result={"url":seed,"verificationStatus":"seed-probe-failed","error":f"{type(e).__name__}: {e}"}

    return {
        "business":{"name":name,"context":context},
        "engine":"Google public Search HTML (Quick workaround)",
        "mode":"quick-discovery",
        "warning":"Google public-search HTML is used only as an exploratory workaround and can be blocked or change without notice. Results shown are organic destination URLs extracted by the prototype; sponsored/ad destinations are excluded. Standard deployment should use a configured supported search service/API.",
        "groups":groups,"seedResult":seed_result,"errors":errors
    }


# ---------------------------------------------------------------------
# v1.8 Platform URL Resolver
# Stage 1 is URL discovery + verification. Data opportunity probing comes later.
# ---------------------------------------------------------------------

class BingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results=[]; self.in_h2=False; self.in_a=False; self.href=None; self.buf=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="h2": self.in_h2=True
        elif tag=="a" and self.in_h2:
            self.in_a=True; self.href=a.get("href"); self.buf=[]
    def handle_data(self,data):
        if self.in_a:self.buf.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.in_a:
            title=" ".join("".join(self.buf).split())
            if self.href and self.href.startswith("http") and title:
                self.results.append((title,self.href))
            self.in_a=False; self.href=None; self.buf=[]
        elif tag=="h2": self.in_h2=False

def _bing_search(query,limit=10,timeout=20):
    url="https://www.bing.com/search?q="+quote_plus(query)+"&count="+str(max(limit,10))
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 KU-Open-DA-Discovery/1.8","Accept-Language":"th-TH,th;q=0.9,en;q=0.8"})
    with urlopen(req,timeout=timeout) as r: body=r.read().decode("utf-8","ignore")
    p=BingParser();p.feed(body);out=[]
    for title,u in p.results:
        host=(urlparse(u).netloc or "").lower()
        if "bing.com" in host or "microsoft.com" in host:continue
        if u not in [x["url"] for x in out]:out.append({"title":title,"url":u})
        if len(out)>=limit:break
    return out

def _ddg_search_structured(query,limit=10,timeout=20):
    return search_web(query,limit,timeout)

def _provider_search(provider,query,limit=10):
    if provider=="google":
        return [{"title":_title_from_url(u),"url":u} for u in _google_public_search(query,limit)]
    if provider=="bing":
        return _bing_search(query,limit)
    if provider=="duckduckgo":
        return _ddg_search_structured(query,limit)
    raise ValueError("Unknown provider")

PLATFORM_RULES=[
    {"id":"official","label":"Official website","query":lambda b,c:f'"{b}" {c} official website',
     "allow":lambda host: not any(x in host for x in ("facebook.com","instagram.com","tiktok.com","x.com","twitter.com","wongnai.com","tripadvisor.","google.","youtube.com"))},
    {"id":"facebook","label":"Facebook","query":lambda b,c:f'site:facebook.com "{b}" {c}',"allow":lambda h:"facebook.com" in h},
    {"id":"instagram","label":"Instagram","query":lambda b,c:f'site:instagram.com "{b}" {c}',"allow":lambda h:"instagram.com" in h},
    {"id":"tiktok","label":"TikTok","query":lambda b,c:f'site:tiktok.com "{b}" {c}',"allow":lambda h:"tiktok.com" in h},
    {"id":"x","label":"X","query":lambda b,c:f'(site:x.com OR site:twitter.com) "{b}" {c}',"allow":lambda h:"x.com" in h or "twitter.com" in h},
]

def _business_tokens(name):
    return [w.lower() for w in re.findall(r"[A-Za-z0-9\u0E00-\u0E7F]+",name or "") if len(w)>=3]

def _candidate_relevance(name,title,url):
    toks=_business_tokens(name);hay=(str(title)+" "+str(url)).lower()
    return sum(1 for t in toks if t in hay)/max(1,len(toks))

def verify_business_url(url,business_name,timeout=15):
    """Public GET verification; no auth bypass. Confirms reachability and weak business-name evidence."""
    try:
        req=Request(url,headers={"User-Agent":"Mozilla/5.0 KU-Open-DA-URL-Verify/1.8","Accept-Language":"th-TH,th;q=0.9,en;q=0.8"})
        with urlopen(req,timeout=timeout) as r:
            body=r.read(700_000).decode("utf-8","ignore")
            final=r.geturl(); status=getattr(r,"status",200)
        low=re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",body)).lower()
        toks=_business_tokens(business_name)
        hits=[t for t in toks if t in low]
        return {"reachable":True,"httpStatus":status,"finalUrl":final,"businessTokenHits":hits,
                "businessMatchScore":len(hits)/max(1,len(toks)),
                "verificationStatus":"url-verified" if hits else "url-reachable-unconfirmed"}
    except Exception as e:
        return {"reachable":False,"verificationStatus":"url-verification-failed","error":f"{type(e).__name__}: {e}"}

def resolve_platform_urls(name,context="",seed_url=""):
    name=(name or "").strip();context=(context or "").strip()
    if not name:raise ValueError("Business name is required.")
    providers=["google","bing","duckduckgo"]
    groups={};diagnostics=[]
    for rule in PLATFORM_RULES:
        query=rule["query"](name,context)
        candidates=[]
        provider_used=None
        for provider in providers:
            try:
                raw=_provider_search(provider,query,8)
                filtered=[]
                for r in raw:
                    host=(urlparse(r["url"]).netloc or "").lower().removeprefix("www.")
                    if rule["allow"](host):
                        filtered.append({**r,"domain":host,"provider":provider,"relevance":_candidate_relevance(name,r["title"],r["url"])})
                if filtered:
                    candidates=sorted(filtered,key=lambda x:x["relevance"],reverse=True)[:3];provider_used=provider;break
                diagnostics.append({"group":rule["id"],"provider":provider,"status":"no-matching-result"})
            except Exception as e:
                diagnostics.append({"group":rule["id"],"provider":provider,"status":"provider-error","error":f"{type(e).__name__}: {e}"})
        selected=None
        for c in candidates:
            v=verify_business_url(c["url"],name)
            c["verification"]=v
            if v.get("reachable") and (v.get("businessMatchScore",0)>0 or c["relevance"]>0):
                selected=c;break
        groups[rule["id"]]={"label":rule["label"],"query":query,"providerUsed":provider_used,"selected":selected,"candidates":candidates}

    # Other 5: provider chain on a broad business query, unique domains, exclude platform groups.
    broad=f'"{name}" {context}'.strip()
    other=[];provider_used=None
    represented=set()
    for g in groups.values():
        if g.get("selected"):represented.add(g["selected"]["domain"])
    for provider in providers:
        try:
            raw=_provider_search(provider,broad,20)
            rows=[]
            for r in raw:
                host=(urlparse(r["url"]).netloc or "").lower().removeprefix("www.")
                if not host or host in represented:continue
                if any(x in host for x in ("facebook.com","instagram.com","tiktok.com","x.com","twitter.com")):continue
                if any(x["domain"]==host for x in rows):continue
                rel=_candidate_relevance(name,r["title"],r["url"])
                if rel<=0:continue
                v=verify_business_url(r["url"],name)
                rows.append({**r,"domain":host,"provider":provider,"relevance":rel,"verification":v})
                if len(rows)>=5:break
            if rows:
                other=rows;provider_used=provider;break
            diagnostics.append({"group":"other","provider":provider,"status":"no-matching-result"})
        except Exception as e:
            diagnostics.append({"group":"other","provider":provider,"status":"provider-error","error":f"{type(e).__name__}: {e}"})
    groups["other"]={"label":"Other public sources (Top 5 unique domains)","query":broad,"providerUsed":provider_used,"results":other}

    seed=None
    seed_url=normalize_seed_url(seed_url)
    if seed_url:
        seed={"url":seed_url,"verification":verify_business_url(seed_url,name)}

    return {
        "schema":"ku2d.platform-url-resolution.v1",
        "business":{"name":name,"context":context},
        "stage":"platform-url-resolution",
        "providerChain":providers,
        "groups":groups,
        "seed":seed,
        "diagnostics":diagnostics,
        "statusMeaning":{
            "url-verified":"Public URL fetched and business-name evidence found",
            "url-reachable-unconfirmed":"URL fetched but business identity not confirmed from page text",
            "url-verification-failed":"Public GET failed; no bypass attempted",
            "no-matching-result":"Search provider responded but no platform-matching candidate was parsed",
            "provider-error":"Search provider could not be used"
        }
    }
