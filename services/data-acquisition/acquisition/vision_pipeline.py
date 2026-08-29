from vision_extractor import extract_image
from promotion_terms import enrich_promotion_record

def candidate_kind(x):
    s=(x.get("src","")+" "+x.get("alt","")+" "+x.get("page_url","")).lower()
    if "menu" in s or "espresso" in s:return "menu"
    if any(k in s for k in ("promo","promotion","campaign","catalog","catalogue","offer")):return "promotion"
    return "product"

def extract_ranked(candidates,max_images=3,min_score=2):
    chosen=[x for x in candidates if int(x.get("score") or 0)>=min_score][:max(0,min(int(max_images),10))]
    results=[];records=[]
    for c in chosen:
        kind=candidate_kind(c)
        r=extract_image(c["src"],kind=kind,source_url=c.get("page_url") or c["src"])
        results.append({"candidate":c,"result":r})
        if r.get("ok"):
            payload=r.get("data") or r.get("extracted") or {}
            xs=payload.get("records") if isinstance(payload,dict) else None
            if not xs and isinstance(payload,dict):xs=[payload]
            for z in xs or []:
                if isinstance(z,dict):
                    z.setdefault("source_image",c["src"]);z.setdefault("source_url",c.get("page_url") or c["src"])
                    records.append(enrich_promotion_record(z))
    return {"selected":len(chosen),"results":results,"records":records}
