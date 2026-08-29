from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PROV=ROOT/"acquisition"/"providers"
if str(PROV) not in sys.path:sys.path.insert(0,str(PROV))
if str(ROOT/"repository") not in sys.path:sys.path.insert(0,str(ROOT/"repository"))
from serper_provider import search as serper_search
from evidence_retrieval_planner import query_plan,confirmation_bias_check

def discover(claim_text,claim_type="general",entity_name=None,max_queries=12,num_per_query=5):
    plan=query_plan(claim_text,claim_type,entity_name)[:max(2,min(max_queries,30))]
    rows=[];diagnostics=[]
    for p in plan:
        try:
            r=serper_search(p["query"],num=max(1,min(num_per_query,10)))
            organic=r.get("organic",[])
            diagnostics.append({"query":p["query"],"stance_target":p["stance_target"],"status":"ok","count":len(organic)})
            for x in organic:
                rows.append({"title":x.get("title"),"link":x.get("link"),"snippet":x.get("snippet"),
                             "position":x.get("position"),"stance_target":p["stance_target"],
                             "source_family":p["source_family"],"query":p["query"]})
        except Exception as e:
            diagnostics.append({"query":p["query"],"stance_target":p["stance_target"],
                                "status":"provider-error","error":str(e)})
    # URL dedupe, preserving all search intents that found it.
    merged={}
    for x in rows:
        u=x.get("link")
        if not u:continue
        if u not in merged:merged[u]={**x,"found_by_stances":[x["stance_target"]],"found_by_queries":[x["query"]]}
        else:
            if x["stance_target"] not in merged[u]["found_by_stances"]:merged[u]["found_by_stances"].append(x["stance_target"])
            if x["query"] not in merged[u]["found_by_queries"]:merged[u]["found_by_queries"].append(x["query"])
    candidates=list(merged.values())
    return {"plan":plan,"candidates":candidates,"diagnostics":diagnostics,
            "bias_check":confirmation_bias_check(plan,rows),
            "note":"Search intent is not evidence stance. Retrieved pages must be acquired and stance-classified before verification."}
