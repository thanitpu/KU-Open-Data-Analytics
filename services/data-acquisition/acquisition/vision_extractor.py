from __future__ import annotations
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
import base64, json, mimetypes, os, re

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/"config"
DEFAULT_MODEL="gpt-4.1-mini"

def _read_key():
    env=os.getenv("OPENAI_API_KEY","").strip()
    if env:return env,"environment"
    p=CONFIG/"openai_api_key.txt"
    if p.exists():
        key=p.read_text(encoding="utf-8").strip()
        if key:return key,"config/openai_api_key.txt"
    return "","missing"

def key_status():
    key,source=_read_key()
    return {"configured":bool(key),"source":source,"model":DEFAULT_MODEL}

def _download_image(url,timeout=25,max_bytes=8_000_000):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 KU2D-Vision/2.13"})
    with urlopen(req,timeout=timeout) as r:
        raw=r.read(max_bytes)
        ctype=(r.headers.get("Content-Type") or "").split(";")[0].strip()
        if not ctype.startswith("image/"):
            ext=Path(urlparse(url).path).suffix.lower()
            ctype=mimetypes.types_map.get(ext,"image/jpeg")
        return raw,ctype

def _data_url(url):
    raw,ctype=_download_image(url)
    return f"data:{ctype};base64,{base64.b64encode(raw).decode('ascii')}"

def _schema(kind):
    if kind=="menu":
        return {
          "name":"menu_extraction",
          "schema":{"type":"object","additionalProperties":False,"properties":{
            "page_title":{"type":["string","null"]},
            "items":{"type":"array","items":{"type":"object","additionalProperties":False,"properties":{
              "category":{"type":["string","null"]},"item_name":{"type":"string"},
              "description":{"type":["string","null"]},"variant":{"type":["string","null"]},
              "price":{"type":["number","null"]},"currency":{"type":["string","null"]},
              "evidence_text":{"type":["string","null"]},"confidence":{"type":"number"}
            },"required":["category","item_name","description","variant","price","currency","evidence_text","confidence"]}},
            "notes":{"type":["string","null"]}
          },"required":["page_title","items","notes"]}
        }
    return {
      "name":"promotion_extraction",
      "schema":{"type":"object","additionalProperties":False,"properties":{
        "promotion_title":{"type":["string","null"]},"offer":{"type":["string","null"]},
        "start_date":{"type":["string","null"]},"end_date":{"type":["string","null"]},
        "terms":{"type":["string","null"]},"participating_branch":{"type":["string","null"]},
        "evidence_text":{"type":["string","null"]},"confidence":{"type":"number"},
        "notes":{"type":["string","null"]}
      },"required":["promotion_title","offer","start_date","end_date","terms","participating_branch","evidence_text","confidence","notes"]}
    }

def extract_image(image_url,kind,source_page="",model=DEFAULT_MODEL):
    key,source=_read_key()
    if not key:
        return {"ok":False,"status":"not-configured","message":"OpenAI API key is not configured.","key_source":source}
    if kind not in ("menu","promotion"):
        raise ValueError("kind must be menu or promotion")

    data_url=_data_url(image_url)
    instructions=(
      "Extract only information visibly supported by this official-source image. "
      "Never guess missing text, prices, dates, branches, or terms. Use null when unreadable or absent. "
      "Confidence must be between 0 and 1. Preserve the displayed currency. "
      + ("Return each menu item separately and pair prices only with the item/variant they visibly belong to."
         if kind=="menu" else
         "Identify the promotion mechanism, dates, branches and terms only when visible.")
    )
    schema=_schema(kind)
    payload={
      "model":model,
      "input":[{"role":"user","content":[
        {"type":"input_text","text":instructions+f"\nSource page: {source_page}"},
        {"type":"input_image","image_url":data_url}
      ]}],
      "text":{"format":{"type":"json_schema","name":schema["name"],"strict":True,"schema":schema["schema"]}},
      "temperature":0
    }
    req=Request("https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
    try:
        with urlopen(req,timeout=90) as r:
            result=json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        body=e.read().decode("utf-8","ignore")
        return {"ok":False,"status":"openai-http-error","http_status":e.code,
                "message":body[:2000] or str(e),"provider":"openai"}
    except URLError as e:
        return {"ok":False,"status":"openai-network-error",
                "message":str(e.reason or e),"provider":"openai"}
    except Exception as e:
        return {"ok":False,"status":"openai-call-error",
                "message":f"{type(e).__name__}: {e}","provider":"openai"}
    text=result.get("output_text")
    if not text:
        for out in result.get("output",[]):
            for c in out.get("content",[]):
                if c.get("type")=="output_text": text=c.get("text"); break
            if text:break
    parsed=json.loads(text) if isinstance(text,str) else text
    return {"ok":True,"status":"completed","provider":"openai","model":model,
            "kind":kind,"image_url":image_url,"source_page":source_page,"data":parsed}


def test_connection(model=DEFAULT_MODEL):
    key,source=_read_key()
    if not key:
        return {"ok":False,"status":"not-configured","message":"OpenAI API key is not configured.","key_source":source}
    payload={
      "model":model,
      "input":"Reply with the single word OK.",
      "max_output_tokens":16
    }
    req=Request("https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
    try:
        with urlopen(req,timeout=30) as r:
            result=json.loads(r.read().decode("utf-8"))
        return {"ok":True,"status":"connected","provider":"openai","model":model,
                "key_source":source,"response_id":result.get("id","")}
    except HTTPError as e:
        body=e.read().decode("utf-8","ignore")
        return {"ok":False,"status":"openai-http-error","http_status":e.code,
                "message":body[:2000] or str(e),"provider":"openai","key_source":source}
    except URLError as e:
        return {"ok":False,"status":"openai-network-error",
                "message":str(e.reason or e),"provider":"openai","key_source":source}
    except Exception as e:
        return {"ok":False,"status":"openai-call-error",
                "message":f"{type(e).__name__}: {e}","provider":"openai","key_source":source}
