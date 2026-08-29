from __future__ import annotations
from collections import Counter,defaultdict
import re

AUTH_WEIGHT={
 "official-training-reference":1.00,
 "official-destination-reference":.92,
 "community-experience":.62,
 "creator-content":.52,
 "commercial-operator":.42,
 "unclassified":.35,
}
AUTH_BUCKET={
 "official-training-reference":"official_guidance",
 "official-destination-reference":"official_guidance",
 "community-experience":"community_experience",
 "creator-content":"community_experience",
 "commercial-operator":"commercial_information",
 "unclassified":"other_evidence",
}

def _norm(x):return re.sub(r"\s+"," ",str(x or "")).strip()
def _rowdict(r):return dict(r)

def evidence_rows(con,entity_type=None,entity_name=None,claim_type=None,limit=300):
    wh=[];args=[]
    if entity_type:wh.append("ke.entity_type=?");args.append(entity_type)
    if entity_name:wh.append("ke.normalized_name=?");args.append(entity_name.lower().strip())
    if claim_type:wh.append("c.claim_type LIKE ?");args.append("%"+claim_type+"%")
    where=(" WHERE "+" AND ".join(wh)) if wh else ""
    sql="""SELECT c.claim_id,c.statement,c.claim_type,c.authority_class,c.confidence,
      ci.content_id,ci.source_type,ci.source_url,ci.title,ci.published_at,
      ke.entity_type,ke.canonical_name
      FROM claim c JOIN content_item ci ON ci.content_id=c.content_id
      LEFT JOIN claim_entity ce ON ce.claim_id=c.claim_id
      LEFT JOIN knowledge_entity ke ON ke.entity_id=ce.entity_id"""
    rows=[_rowdict(x) for x in con.execute(sql+where+" ORDER BY c.confidence DESC LIMIT ?",(*args,limit)).fetchall()]
    # Avoid duplicate claim rows if a claim links to multiple entities and no filter is supplied.
    seen=set();out=[]
    for x in rows:
        k=(x["claim_id"],x.get("entity_type"),x.get("canonical_name"))
        if k not in seen:seen.add(k);out.append(x)
    return out

def evidence_score(row):
    return round(AUTH_WEIGHT.get(row.get("authority_class") or "unclassified",.35) *
                 float(row.get("confidence") or .5),3)

def bucket_evidence(rows):
    out=defaultdict(list)
    for x in rows:
        y=dict(x);y["evidence_score"]=evidence_score(y)
        out[AUTH_BUCKET.get(y.get("authority_class"),"other_evidence")].append(y)
    for k in out:out[k].sort(key=lambda z:-z["evidence_score"])
    return dict(out)

def coverage(rows):
    sources={x.get("source_url") for x in rows if x.get("source_url")}
    types={x.get("source_type") for x in rows if x.get("source_type")}
    official=sum(AUTH_BUCKET.get(x.get("authority_class"))=="official_guidance" for x in rows)
    community=sum(AUTH_BUCKET.get(x.get("authority_class"))=="community_experience" for x in rows)
    commercial=sum(AUTH_BUCKET.get(x.get("authority_class"))=="commercial_information" for x in rows)
    score=min(100, len(sources)*10 + min(30,official*10)+min(20,community*5)+min(10,commercial*3))
    if score>=70:label="strong"
    elif score>=40:label="moderate"
    elif score>0:label="limited"
    else:label="none"
    return {"score":score,"label":label,"unique_sources":len(sources),"source_types":sorted(types),
            "official_claims":official,"community_claims":community,"commercial_claims":commercial}

def conflict_candidates(rows):
    # Conservative: flag possible conflicts for review; never declare contradiction automatically.
    grouped=defaultdict(list)
    for x in rows:
        entity=x.get("canonical_name") or "general"
        ctype=(x.get("claim_type") or "general").split(",")[0]
        grouped[(entity,ctype)].append(x)
    out=[]
    antonyms=[("ควร","ไม่ควร"),("safe","danger"),("ปลอดภัย","อันตราย"),("cheap","expensive"),("ถูก","แพง"),
              ("buy","rent"),("ซื้อ","เช่า")]
    for (entity,ctype),xs in grouped.items():
        if len(xs)<2:continue
        joined=" ".join(x["statement"].lower() for x in xs)
        cues=[]
        for a,b in antonyms:
            if a in joined and b in joined:cues.append(f"{a} <> {b}")
        nums=set(re.findall(r"\b\d+(?:\.\d+)?\b",joined))
        if cues or (ctype in ("cost","requirement") and len(nums)>=3):
            out.append({"entity":entity,"claim_type":ctype,"review_status":"possible-conflict",
                        "cues":cues,"evidence_count":len(xs),
                        "statements":[{"statement":x["statement"],"source_url":x["source_url"],
                                       "authority_class":x["authority_class"]} for x in xs[:8]]})
    return out

def decision_brief(con,entity_type=None,entity_name=None,claim_type=None):
    rows=evidence_rows(con,entity_type,entity_name,claim_type)
    buckets=bucket_evidence(rows);cov=coverage(rows);conflicts=conflict_candidates(rows)
    return {
      "query":{"entity_type":entity_type,"entity_name":entity_name,"claim_type":claim_type},
      "coverage":cov,
      "official_guidance":buckets.get("official_guidance",[])[:20],
      "community_experience":buckets.get("community_experience",[])[:20],
      "commercial_information":buckets.get("commercial_information",[])[:20],
      "other_evidence":buckets.get("other_evidence",[])[:10],
      "possible_conflicts":conflicts,
      "unknown_or_insufficient": cov["label"] in ("none","limited"),
      "guardrail":"Evidence brief only. Absence of evidence is not evidence of absence; possible conflicts require review."
    }

QUESTION_TEMPLATES={
 "beginner":{"label":"What should a beginner know?","claim_type":None},
 "safety":{"label":"What safety guidance is available?","claim_type":"safety"},
 "cost":{"label":"What cost/price evidence is available?","claim_type":"cost"},
 "process":{"label":"What process guidance is available?","claim_type":"process"},
 "requirement":{"label":"What is required?","claim_type":"requirement"},
 "recommendation":{"label":"What is recommended?","claim_type":"recommendation"},
}

def answer_template(con,question_key,entity_type=None,entity_name=None):
    q=QUESTION_TEMPLATES.get(question_key)
    if not q:raise KeyError(question_key)
    brief=decision_brief(con,entity_type,entity_name,q["claim_type"])
    brief["question"]={"key":question_key,"label":q["label"]}
    return brief

def knowledge_gaps(con):
    # Journey coverage identifies what Q still lacks evidence for.
    journey=[dict(r) for r in con.execute("""SELECT j.sequence_no,j.name,
      COUNT(DISTINCT l.content_id) content_count
      FROM learning_journey_step j LEFT JOIN content_journey_link l ON l.step_id=j.step_id
      WHERE j.domain='Diving' GROUP BY j.step_id ORDER BY j.sequence_no""").fetchall()]
    gaps=[]
    for x in journey:
        if x["content_count"]==0:priority="high"
        elif x["content_count"]<3:priority="medium"
        else:priority="covered"
        gaps.append({**x,"priority":priority})
    entities=[dict(r) for r in con.execute("""SELECT ke.entity_type,ke.canonical_name,
      COUNT(DISTINCT em.content_id) content_count
      FROM knowledge_entity ke LEFT JOIN entity_mention em ON em.entity_id=ke.entity_id
      GROUP BY ke.entity_id ORDER BY content_count ASC,ke.entity_type,ke.canonical_name""").fetchall()]
    return {"journey_gaps":gaps,"thin_entities":[x for x in entities if x["content_count"]<3]}
