from __future__ import annotations
from urllib.parse import urlparse
import re, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/"providers"))
from serper_provider import search as serper_search, key_status

SOCIAL_HOSTS=("facebook.com","instagram.com","tiktok.com","x.com","twitter.com")

def host(url):
    return (urlparse(url).netloc or "").lower().removeprefix("www.")

def relevance(name,item):
    toks=[x.lower() for x in re.findall(r"[A-Za-z0-9\u0E00-\u0E7F]+",name) if len(x)>=3]
    hay=(item.get("title","")+" "+item.get("snippet","")+" "+item.get("url","")).lower()
    return sum(1 for t in toks if t in hay)/max(1,len(toks))

def _group_rows(name,gid,items):
    rows=[]
    for item in items:
        d=host(item["url"])
        if gid=="official":
            ok=not any(s in d for s in SOCIAL_HOSTS) and "wongnai.com" not in d and "tripadvisor." not in d
        elif gid=="x":
            ok=("x.com" in d or "twitter.com" in d)
        else:
            expected={"facebook":"facebook.com","instagram":"instagram.com","tiktok":"tiktok.com"}[gid]
            ok=expected in d
        if not ok: continue
        rows.append({**item,"domain":d,"relevance":relevance(name,item),"status":"serper-organic-found","provider":"serper"})
    rows.sort(key=lambda x:(x["relevance"], -(x.get("position") or 999)), reverse=True)
    return rows

def resolve(name,context="",seed_url=""):
    name=(name or "").strip()
    context=(context or "").strip()
    if not name: raise ValueError("Business name is required.")

    base=f'{name} {context}'.strip()
    exact=f'"{name}" {context}'.strip()
    out={}
    diagnostics=[]
    represented=set()

    queries=[
        ("official","Official website",f'{exact} official website'),
        ("facebook","Facebook",f'site:facebook.com {exact}'),
        ("instagram","Instagram",f'site:instagram.com {exact}'),
        ("tiktok","TikTok",f'site:tiktok.com {exact}'),
        ("x","X",f'(site:x.com OR site:twitter.com) {exact}')
    ]

    for gid,label,q in queries:
        try:
            r=serper_search(q,num=8)
            rows=_group_rows(name,gid,r["organic"])
            selected=rows[0] if rows else None
            if selected: represented.add(selected["domain"])
            out[gid]={"label":label,"query":q,"selected":selected,"candidates":rows[:3],"providerUsed":"serper"}
            diagnostics.append({"group":gid,"provider":"serper","status":"ok","organicCount":len(r["organic"]),"matchingCount":len(rows)})
        except Exception as e:
            out[gid]={"label":label,"query":q,"selected":None,"candidates":[],"providerUsed":"serper"}
            diagnostics.append({"group":gid,"provider":"serper","status":"provider-error","error":str(e)})

    # Free-plan-safe discovery for five additional unique domains.
    # Avoid the exact-only broad query that produced "Query pattern not allowed for free accounts".
    other_queries=[
        f"{base}",
        f"{base} reviews",
        f"{base} restaurant reviews",
        f"{base} Wongnai",
        f"{base} promotion"
    ]
    other=[]
    seen=set(represented)
    qdiag=[]
    for oq in other_queries:
        if len(other)>=5: break
        try:
            r=serper_search(oq,num=10)
            accepted=0
            for item in r["organic"]:
                d=host(item["url"])
                if not d or d in seen or any(x in d for x in SOCIAL_HOSTS): continue
                rel=relevance(name,item)
                if rel<=0: continue
                other.append({
                    **item,"domain":d,"relevance":rel,"status":"serper-organic-found",
                    "provider":"serper","discoveryQuery":oq
                })
                seen.add(d); accepted+=1
                if len(other)>=5: break
            qdiag.append({"query":oq,"status":"ok","organicCount":len(r["organic"]),"accepted":accepted})
        except Exception as e:
            qdiag.append({"query":oq,"status":"provider-error","error":str(e)})

    diagnostics.append({
        "group":"other","provider":"serper",
        "status":"ok" if other else "no-matching-result",
        "matchingCount":len(other),"queries":qdiag
    })
    out["other"]={
        "label":"Other Google organic (Top 5 unique domains)",
        "query":"multi-query free-plan-safe discovery",
        "queries":other_queries,
        "results":other,
        "providerUsed":"serper"
    }

    seed=None
    if seed_url:
        seed={"url":seed_url.strip(),"status":"user-supplied-seed"}

    return {
        "schema":"ku2d.structured-platform-url-resolution.v1",
        "business":{"name":name,"context":context},
        "stage":"platform-url-resolution",
        "provider":"serper",
        "providerStatus":key_status(),
        "groups":out,
        "seed":seed,
        "diagnostics":diagnostics
    }
