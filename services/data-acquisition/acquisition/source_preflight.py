from __future__ import annotations
import re,time,ssl
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from urllib.parse import urlparse
from source_explorer import content_quality,_tags,explain_failure

def _host(url):
    try:return urlparse(url).netloc.lower().removeprefix("www.")
    except:return ""

def preflight_url(url,timeout=8,max_bytes=350_000):
    started=time.time();req=Request(url,headers={
      "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
      "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    try:
        with urlopen(req,timeout=timeout) as r:
            raw=r.read(max_bytes);status=getattr(r,"status",200);ctype=r.headers.get("content-type","")
            final_url=r.geturl()
            text=raw.decode("utf-8",errors="replace")
            title=""
            m=re.search(r"(?is)<title[^>]*>(.*?)</title>",text)
            if m:title=re.sub(r"<[^>]+>"," ",m.group(1)).strip()
            stripped=re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>"," ",text)
            stripped=re.sub(r"(?s)<[^>]+>"," ",stripped)
            stripped=re.sub(r"\s+"," ",stripped).strip()
            q=content_quality(stripped,title)
            js_signals=sum(1 for x in ("__NEXT_DATA__","webpack","application/ld+json","react","data-reactroot") if x.lower() in text.lower())
            return {"status":"accessible","url":url,"final_url":final_url,"host":_host(url),"http_status":status,
              "content_type":ctype,"bytes_sampled":len(raw),"text_length":len(stripped),"title":title,
              "elapsed_seconds":round(time.time()-started,2),"quality":q,"tags":_tags(stripped,10),
              "likely_js_heavy":js_signals>=2 and len(stripped)<1200,
              "access_assessment":"direct-public-html" if len(stripped)>=500 else "thin-public-html",
              "recommendation":"full-explore" if len(stripped)>=300 else "review-access"}
    except Exception as e:
        why=explain_failure({"error":f"{type(e).__name__}: {e}"},url)
        return {"status":"inaccessible","url":url,"host":_host(url),"elapsed_seconds":round(time.time()-started,2),
          "http_status":getattr(e,"code",None),"failure":why,"recommendation":"review-access"}

def preflight_candidates(candidates,max_candidates=20,max_workers=4):
    items=list((candidates or [])[:max_candidates]);results=[None]*len(items)
    # Bounded concurrency: one request per candidate, maximum four sites at once.
    with ThreadPoolExecutor(max_workers=max(1,min(int(max_workers),4))) as ex:
        futs={ex.submit(preflight_url,x.get("url")):i for i,x in enumerate(items)}
        for fut in as_completed(futs):
            i=futs[fut]
            try:p=fut.result()
            except Exception as e:p={"status":"inaccessible","url":items[i].get("url"),"failure":{"reason":str(e)}}
            results[i]={**items[i],"preflight":p}
    return results
