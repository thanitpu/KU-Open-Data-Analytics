from __future__ import annotations
import re
from urllib.parse import urlparse
from evidence_verification_engine import norm

SOURCE_FAMILIES={
 "official_training":{
   "domains":["padi.com","blog.padi.com","divessi.com"],
   "best_for":["safety","requirement","process","recommendation"],
   "authority_role":"official-guidance"
 },
 "community":{
   "domains":["pantip.com","scubaboard.com","reddit.com"],
   "best_for":["experience","popularity","recommendation","cost"],
   "authority_role":"community-experience"
 },
 "video_creator":{
   "domains":["youtube.com"],
   "best_for":["experience","process","recommendation","popularity"],
   "authority_role":"creator/community"
 },
 "commercial":{
   "domains":[],
   "best_for":["cost","availability","recommendation"],
   "authority_role":"commercial-information"
 }
}
STANCE_EXPANSIONS={
 "support":["evidence","recommended","benefits","why","ควร","แนะนำ","ข้อดี","ประโยชน์"],
 "against":["not recommended","risks","disadvantages","problems","ไม่ควร","ข้อเสีย","ปัญหา","ไม่จำเป็น"],
 "neutral":["guide","discussion","experience","review","ข้อมูล","ประสบการณ์","รีวิว"]
}

def clean_claim(x):return re.sub(r"\s+"," ",str(x or "")).strip()

def query_plan(claim_text,claim_type="general",entity_name=None):
    base=clean_claim(claim_text)
    entity=clean_claim(entity_name)
    plans=[]
    # Balanced generic searches: never only seek confirmation.
    for stance in ("support","against","neutral"):
        terms=STANCE_EXPANSIONS[stance]
        q=f'"{entity}" {base} {terms[0]}' if entity else f'{base} {terms[0]}'
        plans.append({"stance_target":stance,"source_family":"open_web","query":q,
                      "purpose":f"Seek {stance} or contextual evidence without domain restriction."})
    # Domain-directed searches according to claim type.
    for fam,cfg in SOURCE_FAMILIES.items():
        if not cfg["domains"]:continue
        if claim_type not in cfg["best_for"] and claim_type!="general":continue
        for domain in cfg["domains"]:
            for stance in ("support","against"):
                cue=STANCE_EXPANSIONS[stance][1]
                q=f'site:{domain} "{entity}" {base} {cue}' if entity else f'site:{domain} {base} {cue}'
                plans.append({"stance_target":stance,"source_family":fam,"domain":domain,"query":q,
                              "purpose":f"{cfg['authority_role']} counter-balanced retrieval."})
    # Deduplicate query strings.
    seen=set();out=[]
    for p in plans:
        k=p["query"].lower()
        if k not in seen:seen.add(k);out.append(p)
    return out

def domain_of(url):
    try:return urlparse(url).netloc.lower().removeprefix("www.")
    except:return ""

def discovery_summary(results):
    by_stance={};by_domain={};unique=set()
    for x in results:
        st=x.get("stance_target","unknown");by_stance[st]=by_stance.get(st,0)+1
        d=domain_of(x.get("link") or x.get("url") or "")
        if d:by_domain[d]=by_domain.get(d,0)+1
        u=x.get("link") or x.get("url")
        if u:unique.add(u)
    return {"candidate_records":len(results),"unique_urls":len(unique),
            "by_search_intent":by_stance,"by_domain":by_domain}

def confirmation_bias_check(plan,results=None):
    pcounts={s:sum(x.get("stance_target")==s for x in plan) for s in ("support","against","neutral")}
    warnings=[]
    if pcounts["support"] and not pcounts["against"]:warnings.append("No counter-evidence query is planned.")
    if pcounts["against"] < max(1,pcounts["support"]//2):warnings.append("Counter-evidence search coverage is thin.")
    domains={x.get("domain") for x in plan if x.get("domain")}
    if len(domains)<2:warnings.append("Low planned source diversity.")
    result_summary=discovery_summary(results or [])
    return {"planned_queries":pcounts,"planned_domains":sorted(domains),
            "warnings":warnings,"result_summary":result_summary,
            "bias_guard_pass":not warnings}
