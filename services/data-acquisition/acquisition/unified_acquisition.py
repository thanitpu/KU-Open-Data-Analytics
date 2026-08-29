from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT/"repository") not in sys.path:sys.path.insert(0,str(ROOT/"repository"))
from repository_engine import hid,now

def fetch_public_url(url,timeout=20):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 KU2D-Acquisition/1.0"})
    try:
        with urlopen(req,timeout=timeout) as r:
            raw=r.read(2_500_000);ctype=r.headers.get("content-type","")
            enc="utf-8"
            try: text=raw.decode(enc,errors="replace")
            except:text=str(raw)
            return {"ok":True,"status":getattr(r,"status",200),"content_type":ctype,"html":text}
    except HTTPError as e:return {"ok":False,"status":e.code,"error":str(e),"html":""}
    except Exception as e:return {"ok":False,"status":None,"error":str(e),"html":""}

def html_to_text(html):
    x=re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>"," ",html or "")
    title=""
    m=re.search(r"(?is)<title[^>]*>(.*?)</title>",x)
    if m:title=re.sub(r"<[^>]+>"," ",m.group(1))
    x=re.sub(r"(?is)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>","\n",x)
    x=re.sub(r"(?s)<[^>]+>"," ",x)
    import html as H
    x=H.unescape(x);x=re.sub(r"[ \t]+"," ",x);x=re.sub(r"\n\s*\n+","\n",x)
    return re.sub(r"\s+"," ",title).strip(),x.strip()

def acquire(url,domain="general",purpose="research_evidence",source_type="web"):
    f=fetch_public_url(url)
    if not f["ok"]:return {**f,"source_url":url,"domain":domain,"purpose":purpose}
    title,text=html_to_text(f["html"])
    return {"ok":True,"source_url":url,"canonical_url":url,"title":title,"raw_text":text,
            "source_type":source_type,"domain":domain,"purpose":purpose,"http_status":f["status"],
            "parser_method":"html-baseline-v1","content_hash":hashlib.sha256(text.encode("utf-8")).hexdigest()}

def store_document(con,result,profile_id="q-diving",discovered_from=None):
    ts=now();url=result["source_url"];purpose=result.get("purpose","research_evidence");domain=result.get("domain","general")
    jid=hid("acquisition-job",profile_id,purpose,url,ts)
    con.execute("""INSERT INTO acquisition_job(acquisition_job_id,profile_id,domain,purpose,source_url,source_type,status,
      discovered_from,metadata_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
      (jid,profile_id,domain,purpose,url,result.get("source_type"),"fetched",discovered_from,json.dumps({},ensure_ascii=False),ts,ts))
    did=hid("acquired-document",url,result.get("content_hash"),ts)
    con.execute("""INSERT INTO acquired_document(acquired_document_id,acquisition_job_id,source_url,canonical_url,title,source_type,
      domain,purpose,raw_text,content_hash,fetched_at,http_status,parser_method,metadata_json)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (did,jid,url,result.get("canonical_url"),result.get("title"),result.get("source_type"),domain,purpose,
       result.get("raw_text"),result.get("content_hash"),ts,result.get("http_status"),result.get("parser_method"),
       json.dumps({},ensure_ascii=False)))
    con.commit();return {"acquisition_job_id":jid,"acquired_document_id":did}
