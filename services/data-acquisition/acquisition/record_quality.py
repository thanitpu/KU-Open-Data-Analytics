from __future__ import annotations
import re

BOILERPLATE=[
    "all rights reserved","privacy policy","terms of use","cookie policy","log in","sign up",
    "สมัครสมาชิก","เข้าสู่ระบบ","copyright","© 20","การอัพโหลดผู้ติดต่อ",
    "javascript","enable cookies","access denied"
]
MARKETING=["promotion","โปรโมชั่น","ส่วนลด","offer","deal","campaign","โปรโม","สิทธิพิเศษ","เมนูใหม่"]
REVIEW=["review","รีวิว","rating","คะแนน","บริการ","service","อาหาร","food","กาแฟ","coffee","อร่อย","ประทับใจ"]
ABOUT=["address","ที่อยู่","phone","โทร","branch","สาขา","opening","เวลาเปิด","contact","ติดต่อ"]
EMPLOYMENT=["job","career","สมัครงาน","ตำแหน่งงาน","vacancy","เงินเดือน"]
NEIGHBORHOOD=["แถว","ละแวก","ใกล้","neighborhood","community","ย่าน"]
COMPETITIVE=["similar","recommended","ร้านคล้าย","ร้านแนะนำ","ใกล้เคียง"]
OFFERING=["menu","เมนู","product","สินค้า","อาหาร","เครื่องดื่ม","bakery"]

def _norm(x):
    return re.sub(r"\s+"," ",str(x or "")).strip()

def score_record(record,business_name=""):
    text=_norm(record.get("text") or record.get("title"))
    low=text.lower()
    n=len(text)
    quality=0.0
    reasons=[]

    if n>=220: quality+=0.45
    elif n>=100: quality+=0.35
    elif n>=45: quality+=0.22
    else: reasons.append("short")

    if any(x in low for x in BOILERPLATE):
        quality-=0.55; reasons.append("boilerplate")

    meaningful_hits=sum(1 for vocab in (MARKETING,REVIEW,ABOUT,EMPLOYMENT,NEIGHBORHOOD,COMPETITIVE,OFFERING)
                        if any(x in low for x in vocab))
    quality+=min(0.30,meaningful_hits*0.08)

    # Business relevance is separate from generic content quality.
    toks=[x.lower() for x in re.findall(r"[A-Za-z0-9\u0E00-\u0E7F]+",business_name or "") if len(x)>=3]
    hit=sum(1 for x in toks if x in low)
    relevance=hit/max(1,len(toks)) if toks else 0.5
    if relevance>0: quality+=0.18
    elif toks: reasons.append("business-name-not-found")

    # Search snippets are useful for discovery, but lower confidence than direct source records.
    method=str(record.get("method") or "").lower()
    if "snippet" in method:
        quality-=0.08; reasons.append("search-snippet")

    quality=max(0.0,min(1.0,quality))
    if quality>=0.68 and relevance>=0.34:
        readiness="analysis-ready"
    elif quality>=0.42:
        readiness="usable-with-review"
    else:
        readiness="low-value"

    return {
        "quality_score":round(quality,3),
        "business_relevance_score":round(relevance,3),
        "data_readiness":readiness,
        "quality_reasons":reasons
    }

def enrich_quality(record,business_name=""):
    out=dict(record)
    out.update(score_record(out,business_name))
    return out
