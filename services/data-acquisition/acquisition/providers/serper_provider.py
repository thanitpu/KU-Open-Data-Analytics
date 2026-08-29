from __future__ import annotations
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json, os

ENDPOINT="https://google.serper.dev/search"

def _key_paths():
    here=Path(__file__).resolve()
    app=here.parents[2]
    return [
        app/"config"/"serper_api_key.txt",
    ]

def get_serper_key():
    env=os.getenv("SERPER_API_KEY","").strip()
    if env:return env
    for p in _key_paths():
        try:
            v=p.read_text(encoding="utf-8").strip()
            if v:return v
        except Exception:pass
    return ""

def key_status():
    key=get_serper_key()
    return {"configured":bool(key),"source":"environment" if os.getenv("SERPER_API_KEY","").strip() else ("local-config" if key else None)}

def search(query,num=10,gl="th",hl="th",timeout=25):
    key=get_serper_key()
    if not key:
        raise RuntimeError("SERPER_API_KEY is not configured.")
    payload=json.dumps({"q":query,"num":int(num),"gl":gl,"hl":hl}).encode("utf-8")
    req=Request(ENDPOINT,data=payload,headers={
        "X-API-KEY":key,
        "Content-Type":"application/json",
        "User-Agent":"KU-Open-DA/2.0"
    },method="POST")
    try:
        with urlopen(req,timeout=timeout) as r:
            body=json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        raw=e.read().decode("utf-8","ignore")
        raise RuntimeError(f"Serper HTTP {e.code}: {raw[:300]}")
    organic=[]
    for x in body.get("organic") or []:
        link=x.get("link")
        if not link:continue
        organic.append({
            "title":x.get("title") or link,
            "url":link,
            "snippet":x.get("snippet") or "",
            "position":x.get("position"),
            "date":x.get("date")
        })
    return {
        "provider":"serper",
        "query":query,
        "organic":organic,
        "credits":body.get("credits"),
        "searchParameters":body.get("searchParameters") or {}
    }

def test_connection():
    status=key_status()
    if not status["configured"]:
        return {**status,"ok":False,"message":"Serper API key is not configured."}
    try:
        r=search("Kasetsart University",num=1)
        return {**status,"ok":True,"message":"Serper connection successful.","organicCount":len(r["organic"])}
    except Exception as e:
        return {**status,"ok":False,"message":str(e)}
