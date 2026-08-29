from __future__ import annotations
import re,hashlib,math
from collections import defaultdict
from datetime import datetime,timezone
from repository_engine import hid,now

# Authority is contextual: source type x claim type, not a permanent truth score.
AUTHORITY={
 "safety":{"padi":1.0,"ssi":1.0,"official-tourism":.65,"pantip":.35,"youtube":.4,"dive-shop":.45,"web":.4},
 "requirement":{"padi":1.0,"ssi":1.0,"pantip":.3,"youtube":.4,"dive-shop":.5,"web":.4},
 "process":{"padi":.95,"ssi":.95,"pantip":.45,"youtube":.55,"dive-shop":.55,"web":.45},
 "cost":{"padi":.35,"ssi":.35,"pantip":.6,"youtube":.55,"dive-shop":.9,"web":.55},
 "recommendation":{"padi":.75,"ssi":.75,"pantip":.7,"youtube":.65,"dive-shop":.5,"web":.5},
 "experience":{"padi":.35,"ssi":.35,"pantip":.9,"youtube":.75,"dive-shop":.45,"web":.45},
 "popularity":{"padi":.25,"ssi":.25,"pantip":.75,"youtube":.8,"dive-shop":.4,"web":.5},
 "general":{"padi":.85,"ssi":.85,"official-tourism":.8,"pantip":.55,"youtube":.55,"dive-shop":.5,"web":.45},
}
NEG_CUES=[r"\bnot\b",r"\bno\b",r"\bnever\b",r"ไม่",r"ไม่ควร",r"ไม่จำเป็น",r"อันตราย",r"ผิด"]
SUPPORT_CUES=[r"แนะนำ",r"ควร",r"จำเป็น",r"ต้อง",r"recommended",r"should",r"required",r"must",r"important"]

def norm(s):
    s=str(s or "").lower()
    s=re.sub(r"\d+(?:\.\d+)?","<num>",s)
    s=re.sub(r"[^\wก-๙<>]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def tokens(s):return set(norm(s).split())
def similarity(a,b):
    A=tokens(a);B=tokens(b)
    return len(A&B)/max(1,len(A|B))

def register_claim(con,claim_text,claim_type="general",domain="Diving",entity_type=None,entity_name=None):
    n=norm(claim_text);cid=hid("verification-claim",domain,n);ts=now()
    con.execute("""INSERT INTO verification_claim(verification_claim_id,domain,claim_text,normalized_claim,claim_type,
      subject_entity_type,subject_entity_name,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(domain,normalized_claim) DO UPDATE SET updated_at=excluded.updated_at""",
      (cid,domain,claim_text,n,claim_type,entity_type,entity_name,"active",ts,ts))
    con.commit();return cid

def authority(source_type,claim_type):
    return AUTHORITY.get(claim_type,AUTHORITY["general"]).get(source_type,AUTHORITY["general"].get(source_type,.4))

def classify_stance(target,evidence):
    # Baseline only. Semantic/LLM stance may later coexist as another method.
    sim=similarity(target,evidence)
    if sim<.08:return "neutral",round(sim,3)
    neg=sum(bool(re.search(x,evidence,re.I)) for x in NEG_CUES)
    sup=sum(bool(re.search(x,evidence,re.I)) for x in SUPPORT_CUES)
    target_neg=sum(bool(re.search(x,target,re.I)) for x in NEG_CUES)
    if neg and not target_neg:return "against",round(min(.55+sim,.92),3)
    if target_neg and not neg:return "against",round(min(.5+sim,.88),3)
    if sup or sim>=.28:return "support",round(min(.5+sim,.94),3)
    return "neutral",round(sim,3)

def fingerprint(statement):
    n=norm(statement)
    # Drop weak boilerplate and retain a stable lexical fingerprint.
    stop={"the","a","an","is","are","to","of","and","or","ที่","และ","เป็น","มี","ให้","ได้"}
    w=sorted(x for x in set(n.split()) if x not in stop)
    return hashlib.sha1(" ".join(w).encode("utf-8")).hexdigest()[:18]

def evidence_quality(row):
    q=.45
    if row.get("source_url"):q+=.12
    if row.get("published_at"):q+=.08
    if len(row.get("statement",""))>=40:q+=.08
    if row.get("confidence") is not None:q+=.08*float(row["confidence"])
    return round(min(q,.9),3)

def recency_weight(published_at):
    if not published_at:return .9
    try:
        dt=datetime.fromisoformat(str(published_at).replace("Z","+00:00"))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        days=max(0,(datetime.now(timezone.utc)-dt).days)
        return round(max(.55,math.exp(-days/(365*5))),3)
    except:return .9

def candidate_evidence(con,target_claim,entity_type=None,entity_name=None,limit=500):
    wh=[];args=[]
    if entity_type:wh.append("ke.entity_type=?");args.append(entity_type)
    if entity_name:wh.append("ke.normalized_name=?");args.append(entity_name.lower().strip())
    where=(" WHERE "+" AND ".join(wh)) if wh else ""
    sql="""SELECT DISTINCT c.claim_id,c.statement,c.claim_type,c.confidence,ci.source_type,ci.source_url,
      ci.title,ci.published_at,c.authority_class FROM claim c JOIN content_item ci ON ci.content_id=c.content_id
      LEFT JOIN claim_entity ce ON ce.claim_id=c.claim_id LEFT JOIN knowledge_entity ke ON ke.entity_id=ce.entity_id"""
    rows=[dict(x) for x in con.execute(sql+where+" LIMIT ?",(*args,limit)).fetchall()]
    return sorted(rows,key=lambda x:similarity(target_claim,x["statement"]),reverse=True)

def verify(con,claim_text,claim_type="general",entity_type=None,entity_name=None):
    vcid=register_claim(con,claim_text,claim_type,"Diving",entity_type,entity_name)
    rows=candidate_evidence(con,claim_text,entity_type,entity_name)
    # Cluster near-identical evidence before scoring independence.
    cluster_members=defaultdict(list)
    for x in rows:
        stance,sc=classify_stance(claim_text,x["statement"])
        if stance=="neutral" and sc<.08:continue
        fp=fingerprint(x["statement"]);cluster_members[fp].append((x,stance,sc))
    results=[]
    for fp,members in cluster_members.items():
        domains={re.sub(r"^www\.","",re.sub(r"^https?://","",x[0].get("source_url","")).split("/")[0]) for x in members}
        independent=max(1,len({d for d in domains if d}))
        cluster_id=hid("evidence-cluster",vcid,fp)
        con.execute("""INSERT OR REPLACE INTO evidence_cluster(cluster_id,verification_claim_id,fingerprint,representative_claim_id,
          member_count,independent_source_count,created_at) VALUES(?,?,?,?,?,?,?)""",
          (cluster_id,vcid,fp,members[0][0]["claim_id"],len(members),independent,now()))
        # Copy/near-duplicate records share one unit of influence.
        iw=round(independent/max(1,len(members)),3)
        for x,stance,sc in members:
            aw=authority(x["source_type"],claim_type);rq=recency_weight(x.get("published_at"));eq=evidence_quality(x)
            relevance=max(.15,similarity(claim_text,x["statement"]))
            weighted=round(sc*relevance*aw*iw*rq*eq,4)
            lid=hid("claim-evidence-link",vcid,x["claim_id"])
            con.execute("""INSERT OR REPLACE INTO claim_evidence_link(link_id,verification_claim_id,evidence_claim_id,stance,
              stance_confidence,relevance,authority_weight,independence_weight,recency_weight,evidence_quality,weighted_score,
              cluster_id,method,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (lid,vcid,x["claim_id"],stance,sc,relevance,aw,iw,rq,eq,weighted,cluster_id,"lexical-baseline-v1",now()))
            results.append({**x,"stance":stance,"stance_confidence":sc,"relevance":round(relevance,3),
              "authority_weight":aw,"independence_weight":iw,"recency_weight":rq,"evidence_quality":eq,
              "weighted_score":weighted,"cluster_id":cluster_id})
    con.commit()
    return summarize(claim_text,claim_type,results)

def summarize(claim_text,claim_type,rows):
    counts=defaultdict(int);weights=defaultdict(float);clusters=defaultdict(set);sources=defaultdict(set)
    for x in rows:
        st=x["stance"];counts[st]+=1;weights[st]+=x["weighted_score"];clusters[st].add(x["cluster_id"])
        if x.get("source_url"):sources[st].add(x["source_url"])
    sw=weights["support"];aw=weights["against"];decisive=sw+aw
    balance=(sw-aw)/decisive if decisive else 0
    independent=len(clusters["support"]|clusters["against"])
    if decisive<.08 or independent<2:state="insufficient-evidence"
    elif balance>=.6:state="strongly-supported"
    elif balance>=.2:state="supported"
    elif balance<=-.6:state="strongly-challenged"
    elif balance<=-.2:state="challenged"
    else:state="mixed-evidence"
    return {"claim":claim_text,"claim_type":claim_type,"state":state,
      "record_counts":dict(counts),
      "independent_evidence_clusters":{"support":len(clusters["support"]),"against":len(clusters["against"]),"neutral":len(clusters["neutral"])},
      "weighted_evidence":{"support":round(sw,4),"against":round(aw,4),"neutral":round(weights["neutral"],4),
                           "balance":round(balance,3)},
      "source_counts":{k:len(v) for k,v in sources.items()},
      "evidence":sorted(rows,key=lambda x:-x["weighted_score"]),
      "guardrail":"Evidence state, not absolute truth. Review high-stakes claims and conflicting primary sources."}
