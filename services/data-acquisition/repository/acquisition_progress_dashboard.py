from __future__ import annotations
import json
from collections import Counter,defaultdict
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]

TABLE_GROUPS={
 "Commerce / Retail":{
   "tables":["business","canonical_product","listing","price_version","promotion","promotion_offer","marketplace_signal","evidence"],
   "labels":{"business":"Businesses","canonical_product":"Canonical Products","listing":"Listings","price_version":"Price Versions",
             "promotion":"Promotions","promotion_offer":"Promotion Offers","marketplace_signal":"Marketplace Signals","evidence":"Commerce Evidence"}
 },
 "Knowledge / Q":{
   "tables":["content_item","content_segment","topic","opinion","claim","knowledge_entity","entity_mention","learning_journey_step","content_journey_link"],
   "labels":{"content_item":"Content Items","content_segment":"Content Segments","topic":"Topics","opinion":"Opinions","claim":"Claims",
             "knowledge_entity":"Knowledge Entities","entity_mention":"Entity Mentions","learning_journey_step":"Journey Steps","content_journey_link":"Journey Links"}
 },
 "Evidence Verification":{
   "tables":["verification_claim","claim_evidence_link","evidence_cluster","evidence_passage","evidence_search_run","evidence_candidate_url"],
   "labels":{"verification_claim":"Verification Claims","claim_evidence_link":"Claim-Evidence Links","evidence_cluster":"Evidence Clusters",
             "evidence_passage":"Evidence Passages","evidence_search_run":"Discovery Runs","evidence_candidate_url":"Candidate URLs"}
 },
 "Unified Acquisition":{
   "tables":["acquisition_job","acquired_document"],
   "labels":{"acquisition_job":"Acquisition Jobs","acquired_document":"Acquired Documents"}
 }
}

def _load_json(name):
    p=ROOT/"config"/name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def _channel(url,source_type=None,group=None,sector=None):
    host=urlparse(url or "").netloc.lower()
    st=(source_type or "").lower();g=(group or "").lower();sec=(sector or "").lower()
    if "youtube.com" in host or st=="youtube":return "Video"
    if "pantip.com" in host or st in {"pantip","forum","community"} or "community" in g:return "Community / Forum"
    if "shopee." in host or "lazada." in host or "tiktok" in host or sec=="marketplace":return "Marketplace"
    if "blog" in host or "blog" in (url or "").lower() or "reference" in g:return "Blog / Reference"
    return "Official / Brand Website"

def monitor_registry_summary():
    rows=[]
    commerce=_load_json("source_registry.json").get("sources",[])
    for x in commerce:
        rows.append({"registry":"Commerce / Retail","source_id":x.get("source_id"),"domain":x.get("sector") or "Retail",
          "name":x.get("business"),"url":x.get("url"),"channel":_channel(x.get("url"),sector=x.get("sector")),
          "source_type":x.get("adapter") or "web","enabled":bool(x.get("enabled",True)),"cadence":x.get("cadence"),
          "max_pages":x.get("max_pages")})
    q=_load_json("q_diving_source_registry.json").get("sources",[])
    for x in q:
        rows.append({"registry":"Knowledge / Q Diving","source_id":x.get("source_id"),"domain":"Diving",
          "name":x.get("name"),"url":x.get("url"),"channel":_channel(x.get("url"),x.get("source_type"),x.get("group")),
          "source_type":x.get("source_type"),"enabled":bool(x.get("enabled",True)),"cadence":x.get("cadence"),"max_pages":None})
    by_domain=Counter(x["domain"] for x in rows if x["enabled"])
    by_channel=Counter(x["channel"] for x in rows if x["enabled"])
    by_registry=Counter(x["registry"] for x in rows if x["enabled"])
    return {"total_sources":len(rows),"enabled_sources":sum(x["enabled"] for x in rows),
            "disabled_sources":sum(not x["enabled"] for x in rows),
            "by_domain":dict(sorted(by_domain.items())),"by_channel":dict(sorted(by_channel.items())),
            "by_registry":dict(sorted(by_registry.items())),"sources":rows}

def _table_exists(con,t):
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone())

def _count(con,t):
    if not _table_exists(con,t):return None
    return int(con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])

def repository_group_counts(con):
    groups=[];grand=0
    for group,cfg in TABLE_GROUPS.items():
        items=[];subtotal=0;available=0
        for t in cfg["tables"]:
            c=_count(con,t)
            if c is not None:
                available+=1;subtotal+=c;grand+=c
            items.append({"table":t,"label":cfg["labels"].get(t,t),"count":c,"available":c is not None})
        groups.append({"group":group,"subtotal":subtotal,"available_tables":available,"items":items})
    return {"grand_total_records":grand,"groups":groups}

def profile_progress(profile_id,con):
    counts=repository_group_counts(con)
    # Additional progress indicators, not arbitrary completion percentages.
    nonempty=sum(1 for g in counts["groups"] for x in g["items"] if x["available"] and x["count"]>0)
    available=sum(1 for g in counts["groups"] for x in g["items"] if x["available"])
    return {"profile_id":profile_id,"populated_data_types":nonempty,"available_data_types":available,
            "coverage_ratio":round(nonempty/max(1,available),3),**counts}

def combined_progress(profile_connections):
    profiles=[];totals=defaultdict(int)
    for pid,con in profile_connections:
        p=profile_progress(pid,con);profiles.append(p)
        for g in p["groups"]:
            totals[g["group"]]+=g["subtotal"]
    return {"profiles":profiles,"combined_group_totals":dict(totals),
            "combined_records":sum(totals.values()),
            "note":"Progress is shown as observed record/data-type coverage, not a claimed percentage of all knowledge in the world."}
