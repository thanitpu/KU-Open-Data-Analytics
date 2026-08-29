from __future__ import annotations
import hashlib,re
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode

PAGE_KEYS=("page","p","page_no","pageNumber","page_number","pg")
PATH_PATTERNS=(re.compile(r"(?i)(/page/)(\d+)(?:/|$)"),re.compile(r"(?i)(/p/)(\d+)(?:/|$)"))

def normalized_text_hash(text):
    x=re.sub(r"\s+"," ",str(text or "")).strip()
    return hashlib.sha256(x.encode("utf-8","ignore")).hexdigest() if x else None

def pagination_identity(url):
    """Return (group,page_number) only when URL carries an explicit page identity."""
    try:
        x=urlsplit(url);q=parse_qsl(x.query,keep_blank_values=True);page=None;kept=[]
        for k,v in q:
            if k.lower() in {z.lower() for z in PAGE_KEYS} and str(v).isdigit():
                page=int(v)
            else:kept.append((k,v))
        path=x.path
        if page is None:
            for pat in PATH_PATTERNS:
                m=pat.search(path)
                if m:
                    page=int(m.group(2));path=path[:m.start(2)]+"{page}"+path[m.end(2):];break
        if page is None:return None,None
        group=urlunsplit((x.scheme.lower(),x.netloc.lower(),path.rstrip("/") or "/",urlencode(sorted(kept)),""))
        return group,page
    except:return None,None

def discover_pagination(page_url,links):
    """Conservative pagination discovery from explicit page-number URLs and labels."""
    items=[];groups={}
    # Include current URL if it is itself a numbered page.
    candidates=[{"url":page_url,"label":""}]+list(links or [])
    for item in candidates:
        u=item.get("url") if isinstance(item,dict) else str(item)
        label=str(item.get("label") or "") if isinstance(item,dict) else ""
        group,num=pagination_identity(u)
        if not group or not num:continue
        # Numeric/next/page labels strengthen confidence, but explicit URL parameter is sufficient.
        groups.setdefault(group,set()).add(num)
        items.append({"url":u,"pagination_group":group,"page_number":num,
                      "pagination_signal":"explicit-numbered-url","label":label})
    for group,nums in groups.items():
        total=max(nums) if nums else 0
        for item in items:
            if item["pagination_group"]==group:item["detected_total_pages"]=total
    return items

def pagination_summary_from_pages(pages):
    groups={}
    for p in pages or []:
        for x in p.get("pagination_links") or []:
            g=groups.setdefault(x["pagination_group"],set());g.add(int(x["page_number"]))
    return [{"pagination_group":g,"detected_total_pages":max(nums),"known_page_numbers":sorted(nums)}
            for g,nums in groups.items() if nums]
