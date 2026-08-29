from __future__ import annotations
import re,sys
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]
PROV=ROOT/"acquisition"/"providers"
for p in (ROOT/"acquisition",ROOT/"repository",PROV):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from unified_acquisition import acquire as generic_acquire
from actual_acquisition import discover as commerce_discover
from acquisition_quality import quality_report
from source_adapters import adapter_for
from serper_provider import search as serper_search, key_status as serper_key_status
from source_discovery import search_web as public_search_web
from technique_strategy import explore_with_strategy
from track_selection import select_track_profile
from control_plane.domain_playbooks import recommended_sequence


def explain_failure(result,url):
    err=str((result or {}).get("error") or "")
    low=err.lower()
    if "certificate_verify_failed" in low or "certificate verify failed" in low:
        return {"reason_code":"ssl-certificate-verification",
          "reason":"KU2D could not verify the site's TLS/SSL certificate chain from this Python environment.",
          "blocked":False,
          "next_step":"This does not by itself mean the website blocked KU2D. Fix/update the local CA certificate bundle or use a trusted HTTP client configuration; do not disable certificate verification as the default."}
    if "403" in low or "forbidden" in low:
        return {"reason_code":"http-403","reason":"The server refused this request (HTTP 403).",
          "blocked":True,"next_step":"The site may require browser headers, cookies, authentication, anti-bot handling, or an official API."}
    if "429" in low:
        return {"reason_code":"http-429","reason":"The source rate-limited the request (HTTP 429).",
          "blocked":True,"next_step":"Reduce acquisition frequency/back off and prefer an official API/feed when available."}
    if "401" in low:
        return {"reason_code":"http-401","reason":"Authentication is required (HTTP 401).","blocked":True,
          "next_step":"Use an authorized API/session rather than public-page acquisition."}
    if "timed out" in low or "timeout" in low:
        return {"reason_code":"timeout","reason":"The source did not respond before the acquisition timeout.","blocked":None,
          "next_step":"Retry later or use a source-specific adapter/browser/API if the site is JavaScript-heavy."}
    return {"reason_code":"fetch-failed","reason":err or "The source could not be fetched.","blocked":None,
      "next_step":"Inspect HTTP/network diagnostics and try a source-specific adapter or alternate public URL."}

def content_quality(text,title=""):
    t=(text or "").strip();low=t.lower()
    nav_terms=["sign in","sign up","privacy","cookie","support","contact","forum rules","view new content","all activity",
               "facebook","instagram","tiktok","youtube"]
    nav_hits=sum(low.count(x) for x in nav_terms)
    words=re.findall(r"[A-Za-z\u0E00-\u0E7F]+",t)
    unique=len(set(w.lower() for w in words));n=len(words)
    substantive=max(0,n-nav_hits*3)
    score=0
    if len(t)>=500:score+=20
    if len(t)>=2000:score+=15
    if n>=100:score+=15
    if unique>=60:score+=15
    if title:score+=10
    nav_ratio=min(1,(nav_hits*3)/max(1,n))
    score+=max(0,25-round(nav_ratio*50))
    label="good" if score>=75 else ("usable" if score>=50 else "weak")
    warnings=[]
    if nav_ratio>.12:warnings.append("High navigation/chrome content; page extraction may include menus rather than the target article.")
    if n<80:warnings.append("Very little substantive text was extracted.")
    return {"score":min(100,score),"label":label,"word_count":n,"unique_words":unique,
            "navigation_ratio":round(nav_ratio,3),"warnings":warnings}

def _host(url):
    try:return urlparse(url).netloc.lower().removeprefix("www.")
    except:return ""
def _tags(text,limit=20):
    words=re.findall(r"[A-Za-z][A-Za-z0-9+-]{2,}|[\u0E00-\u0E7F]{3,}",text or "")
    stop={"https","www","com","the","and","for","with","this","that","จาก","และ","ของ","ที่","ใน","เป็น"}
    freq={}
    for w in words:
        k=w.lower()
        if k in stop:continue
        freq[k]=freq.get(k,0)+1
    return [{"tag":k,"count":v} for k,v in sorted(freq.items(),key=lambda kv:(-kv[1],kv[0]))[:limit]]


def _pattern_clues(strategy_result):
    """Infer generic domain-playbook clues from observed technique evidence.

    Technique-level 403s are marked as partial surface blocking only. Whole-source
    cloud blocking is an execution-environment conclusion and must come from the
    environment probe, not from one failed subrequest inside Explore.
    """
    clues=set()
    for tr in strategy_result.get("technique_results") or []:
        tech=str(tr.get("technique") or "").lower()
        label=str(tr.get("label") or "").lower()
        potential=tr.get("potential") or {}
        diag=" ".join(str(x) for x in (tr.get("diagnostics") or [])).lower()
        text=" ".join([tech,label,diag,str(potential).lower()])
        if "sitemap" in text:
            clues.update(["sitemap","sitemap_index"])
            if "product" in text:clues.add("product_sitemap")
        if "graphql" in text:
            clues.update(["graphql","graphql_endpoint","api_candidate"])
        if "api" in text or "endpoint" in text:
            clues.update(["json_api","api_candidate"])
        if "product" in text and ("api" in text or "endpoint" in text):
            clues.add("product_endpoint")
        if "rendered" in text or "product card" in text or "product_cards" in text:
            clues.update(["product_cards","ssr_listing"])
        if "next" in text or "rsc" in text or "hydration" in text:
            clues.update(["next_data","rsc","hydration_state"])
        if "promotion" in text or "campaign" in text or "catalogue" in text:
            clues.update(["promotion","campaign"])
        if potential.get("reported_total") or potential.get("reported_products") or potential.get("reported_pages"):
            clues.add("catalog_endpoint")
        if "403" in text or "forbidden" in text:
            clues.add("partial_surface_blocking")
    return sorted(clues)


def explore_url(url,domain="General",purpose="research_evidence",max_pages=3,techniques=None,progress_callback=None):
    m=explore_with_strategy(url,domain,purpose,max(1,min(max_pages,8)),techniques,progress_callback=progress_callback)
    total=m.get("record_count",0); unique=m.get("unique_sample_record_count",0)
    useful=sum(1 for x in m.get("technique_results") or [] if x.get("record_count",0)>0)
    q={"label":"good" if useful>=2 and total>0 else ("usable" if useful else "weak"),
       "score":min(95,30+useful*10+min(25,total)) if useful else 20,
       "technique_count":len(m.get("technique_results") or []),"techniques_with_evidence":useful}
    text=" ".join(str(r) for r in (m.get("sample_records") or [])[:30])
    clues=_pattern_clues(m)
    guidance=recommended_sequence(domain,clues=clues)

    # Source-specific supermarket selectors already own their validated track logic.
    # Generic retail domains use conservative output-based track inference so a
    # promotion-heavy or document-heavy method cannot win Product & Price merely by
    # returning many rows.
    original_best=m.get("recommended_techniques") or []
    track_selection={}
    if purpose in {"retail_market_intelligence","competitive_intelligence"} and guidance.get("required_tracks") and not (m.get("track_recommendations") or {}):
        picked,tracks,selection=select_track_profile(
            m.get("technique_results") or [],
            required_tracks=guidance.get("required_tracks") or [],
            optional_tracks=guidance.get("optional_tracks") or [],
            quality_gates=guidance.get("quality_gates") or {},
        )
        best=picked
        m["recommended_techniques"]=picked
        m["assigned_techniques"]=[x.get("technique") for x in picked if x.get("technique")]
        m["track_recommendations"]=tracks
        track_selection={**selection,"global_recommendations_before_track_selection":original_best}
    else:
        best=original_best
        track_selection={"required_track_gaps":{},"candidates":{}}

    return {"status":"completed","mode":"adaptive-technique-explore","url":url,"domain":domain,
      "purpose":purpose,"adapter":"adaptive-technique-bench",
      "pages_checked":sum(x.get("pages_checked",0) for x in m.get("technique_results") or []),
      "record_count":total,"unique_sample_record_count":unique,"record_types":m.get("record_types"),"quality":q,"tags":_tags(text),
      "sample_records":m.get("sample_records") or [],"diagnostics":[],
      "techniques_available":m.get("techniques_available"),"techniques_selected":m.get("techniques_selected"),
      "technique_results":m.get("technique_results"),"recommended_techniques":best,"assigned_techniques":m.get("assigned_techniques") or [],
      "track_recommendations":m.get("track_recommendations") or {},"track_selection":track_selection,
      "potential_coverage":m.get("potential_coverage") or [],
      "pattern_clues":clues,"learned_pattern_guidance":guidance,
      "recommendation":"add-to-monitoring" if best and not (track_selection.get("required_track_gaps") or {}) else "review-required-track-gaps" if (track_selection.get("required_track_gaps") or {}) else "review-source"}

def discovery_queries(query_text,query_type="topic",domain="General"):
    q=(query_text or "").strip()
    base=[
      f'{q} official',
      f'{q} Thailand',
      f'{q} review experience',
      f'{q} price promotion' if query_type in {"product","domain","source"} else f'{q} guide reference',
    ]
    if query_type=="product":base += [f'{q} retailer Thailand',f'{q} marketplace Thailand']
    if query_type=="topic":base += [f'{q} forum discussion',f'{q} expert guidance']
    if query_type=="domain":base += [f'best {q} websites Thailand',f'{q} brands retailers']
    seen=[]
    for x in base:
        if x not in seen:seen.append(x)
    return seen

def discover_sources(query_text,query_type="topic",domain="General",num_per_query=5,max_candidates=20):
    queries=discovery_queries(query_text,query_type,domain);merged={};diag=[]
    serper_ready=bool(serper_key_status().get("configured")); provider="serper" if serper_ready else "public-web-fallback"
    effective_queries=queries if serper_ready else queries[:4]
    for q in effective_queries:
        try:
            if serper_ready:
                raw=(serper_search(q,num=max(1,min(num_per_query,10))).get("organic") or [])
            else:
                raw=public_search_web(q,limit=max(1,min(num_per_query,6)),timeout=15)
            diag.append({"query":q,"status":"ok","count":len(raw),"provider":provider})
            for i,x in enumerate(raw,1):
                u=x.get("url")
                if not u:continue
                host=_host(u); pos=x.get("position") or i
                if u not in merged:
                    merged[u]={"url":u,"host":host,"title":x.get("title") or u,"snippet":x.get("snippet") or "",
                               "found_by_queries":[q],"position":pos,"provider":provider}
                else:merged[u]["found_by_queries"].append(q)
        except Exception as e:diag.append({"query":q,"status":"error","error":str(e),"provider":provider})
    rows=list(merged.values()); rows.sort(key=lambda x:(x.get("position") or 99,x["host"],x["url"]))
    chosen=[];perhost={}
    for x in rows:
        if perhost.get(x["host"],0)>=3:continue
        chosen.append(x);perhost[x["host"]]=perhost.get(x["host"],0)+1
        if len(chosen)>=max_candidates:break
    return {"status":"completed","query_text":query_text,"query_type":query_type,"domain":domain,
      "queries":effective_queries,"candidate_count":len(chosen),"candidates":chosen,"diagnostics":diag,"provider":provider,
      "provider_note":"Serper configured." if serper_ready else "Serper key is not configured; using bounded public-web discovery fallback.",
      "note":"Discovery results are candidates only. Explore/sample a URL before adding it to recurring monitoring."}
