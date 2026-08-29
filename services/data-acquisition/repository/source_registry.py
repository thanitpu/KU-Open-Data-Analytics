from pathlib import Path
from datetime import datetime
import json,uuid

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"config/source_registry.json"

def _load():
    if not REGISTRY.exists():
        return {"schema":"ku2d.source-registry.v1","version":1,"sources":[]}
    return json.loads(REGISTRY.read_text(encoding="utf-8"))

def _save(x):
    REGISTRY.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")

def list_sources():
    return _load()

def add_source(source):
    x=_load()
    item=dict(source)
    item.setdefault("source_id","SRC-"+uuid.uuid4().hex[:8].upper())
    item.setdefault("enabled",True)
    item.setdefault("cadence","daily")
    item.setdefault("max_pages",8)
    item.setdefault("store_to_repository",False)
    item.setdefault("notes","")
    item["updated_at"]=datetime.now().isoformat()
    x["sources"].append(item);_save(x);return item

def update_source(source_id,changes):
    x=_load()
    for item in x["sources"]:
        if item.get("source_id")==source_id:
            item.update({k:v for k,v in changes.items() if k!="source_id"})
            item["updated_at"]=datetime.now().isoformat()
            _save(x);return item
    raise KeyError(source_id)

def remove_source(source_id):
    x=_load();before=len(x["sources"])
    x["sources"]=[s for s in x["sources"] if s.get("source_id")!=source_id]
    if len(x["sources"])==before:raise KeyError(source_id)
    _save(x);return {"removed":source_id}

def enabled_sources():
    return [x for x in _load()["sources"] if x.get("enabled")]

def replace_registry(payload):
    if payload.get("schema")!="ku2d.source-registry.v1":raise ValueError("Unsupported registry schema.")
    if not isinstance(payload.get("sources"),list):raise ValueError("sources must be a list.")
    _save(payload);return payload


def selected_sources(sector=None,source_ids=None,enabled_only=True):
    xs=_load()["sources"]
    if enabled_only:xs=[x for x in xs if x.get("enabled")]
    if sector:xs=[x for x in xs if x.get("sector")==sector]
    if source_ids:
        wanted=set(source_ids);xs=[x for x in xs if x.get("source_id") in wanted]
    return xs
