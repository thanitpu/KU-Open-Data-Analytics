from __future__ import annotations
import json,uuid
from pathlib import Path
from datetime import datetime,timezone,timedelta

ROOT=Path(__file__).resolve().parents[1]
COMMERCE=ROOT/"config/source_registry.json"
Q=ROOT/"config/q_diving_source_registry.json"
GENERAL=ROOT/"config/general_source_registry.json"

def _load(p,default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
def _save(p,obj): p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")

def normalized_sources():
    rows=[]
    for x in _load(COMMERCE,{"sources":[]}).get("sources",[]):
        rows.append({"registry":"commerce","source_id":x.get("source_id"),"name":x.get("business"),
          "domain":x.get("sector") or "Retail","url":x.get("url"),"source_type":x.get("adapter") or "web",
          "enabled":bool(x.get("enabled",True)),"cadence":x.get("cadence","daily"),
          "max_pages":int(x.get("max_pages",8)),"store_to_repository":bool(x.get("store_to_repository",False)),
          "purpose":"retail_market_intelligence","raw":x})
    for x in _load(Q,{"sources":[]}).get("sources",[]):
        rows.append({"registry":"q-diving","source_id":x.get("source_id"),"name":x.get("name"),
          "domain":"Diving","url":x.get("url"),"source_type":x.get("source_type") or "web",
          "enabled":bool(x.get("enabled",True)),"cadence":x.get("cadence","weekly"),"max_pages":3,
          "store_to_repository":True,"purpose":"knowledge_learning","raw":x})
    for x in _load(GENERAL,{"sources":[]}).get("sources",[]):
        rows.append({"registry":"general","source_id":x.get("source_id"),"name":x.get("name"),
          "domain":x.get("domain") or "General","url":x.get("url"),"source_type":x.get("source_type") or "web",
          "enabled":bool(x.get("enabled",True)),"cadence":x.get("cadence","weekly"),
          "max_pages":int(x.get("max_pages",3)),"store_to_repository":bool(x.get("store_to_repository",True)),
          "purpose":x.get("purpose") or "research_evidence","profile_id":x.get("profile_id") or "q-diving","raw":x})
    return rows

def add_general_source(item):
    x=_load(GENERAL,{"schema":"ku2d.general-source-registry.v1","version":1,"sources":[]})
    url=(item.get("url") or "").strip()
    if not url: raise ValueError("url is required")
    for s in normalized_sources():
        if (s.get("url") or "").rstrip("/").lower()==url.rstrip("/").lower():
            raise ValueError(f"URL already monitored as {s.get('source_id')}")
    out=dict(item)
    out.setdefault("source_id","GEN-"+uuid.uuid4().hex[:8].upper())
    out.setdefault("name",url)
    out.setdefault("domain","General")
    out.setdefault("source_type","web")
    out.setdefault("purpose","research_evidence")
    out.setdefault("profile_id","q-diving")
    out.setdefault("enabled",True)
    out.setdefault("cadence","weekly")
    out.setdefault("max_pages",3)
    out.setdefault("store_to_repository",True)
    out["created_at"]=datetime.now(timezone.utc).isoformat()
    x["sources"].append(out);_save(GENERAL,x);return out

def update_source(source_id,changes):
    for p in (COMMERCE,Q,GENERAL):
        x=_load(p,{"sources":[]})
        for s in x.get("sources",[]):
            if s.get("source_id")==source_id:
                for k,v in changes.items():
                    if k!="source_id":s[k]=v
                s["updated_at"]=datetime.now(timezone.utc).isoformat()
                _save(p,x);return s
    raise KeyError(source_id)

def cadence_due(last_success_at,cadence,now=None):
    if not last_success_at:return True
    now=now or datetime.now(timezone.utc)
    try:d=datetime.fromisoformat(str(last_success_at).replace("Z","+00:00"))
    except:return True
    if not d.tzinfo:d=d.replace(tzinfo=timezone.utc)
    delta={"hourly":timedelta(hours=1),"daily":timedelta(days=1),"weekly":timedelta(days=7),
           "monthly":timedelta(days=30)}.get((cadence or "weekly").lower(),timedelta(days=7))
    return now>=d+delta


def approve_source(item):
    purpose=item.get("purpose") or "research_evidence"
    domain=item.get("domain") or "General"
    url=(item.get("url") or "").strip()
    if not url:raise ValueError("url is required")
    # Prevent duplicate monitoring across all registries.
    for x in normalized_sources():
        if (x.get("url") or "").rstrip("/").lower()==url.rstrip("/").lower():
            raise ValueError(f"URL already monitored as {x.get('source_id')}")
    if purpose in {"retail_market_intelligence","competitive_intelligence"}:
        x=_load(COMMERCE,{"schema":"ku2d.source-registry.v1","version":1,"sources":[]})
        out={"source_id":"SRC-"+uuid.uuid4().hex[:8].upper(),"sector":domain,
             "business":item.get("name") or item.get("business") or urlparse_name(url),
             "url":url,"adapter":item.get("adapter") or "generic","enabled":True,
             "cadence":item.get("cadence") or "daily","max_pages":int(item.get("max_pages") or 8),
             "store_to_repository":True,"notes":item.get("notes") or "Approved from Explore/Discover"}
        x["sources"].append(out);_save(COMMERCE,x);return {"registry":"commerce",**out}
    if str(domain).lower()=="diving" and purpose=="knowledge_learning":
        x=_load(Q,{"schema":"q-diving.source-registry.v1","version":1,"sources":[]})
        out={"source_id":"Q-"+uuid.uuid4().hex[:8].upper(),"group":item.get("group") or "Explored Source",
             "name":item.get("name") or urlparse_name(url),"source_type":item.get("source_type") or "web",
             "url":url,"enabled":True,"cadence":item.get("cadence") or "weekly"}
        x["sources"].append(out);_save(Q,x);return {"registry":"q-diving",**out}
    return {"registry":"general",**add_general_source(item)}

def urlparse_name(url):
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.removeprefix("www.") or url
    except:return url
