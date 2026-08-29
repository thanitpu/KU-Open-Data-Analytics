from __future__ import annotations
import re,hashlib
from collections import Counter,defaultdict

ENTITY_RULES={
 "DiveSite":[
   ("Koh Tao",[r"เกาะเต่า",r"\bkoh tao\b"]),("Sail Rock",[r"\bsail rock\b"]),
   ("Chumphon Pinnacle",[r"ชุมพรพินนาเคิล",r"chumphon pinnacle"]),
   ("Similan Islands",[r"สิมิลัน",r"similan"]),("Koh Lipe",[r"หลีเป๊ะ",r"koh lipe"]),
   ("Richelieu Rock",[r"richelieu rock",r"ริเชลิว"])
 ],
 "Equipment":[
   ("Mask",[r"หน้ากาก",r"\bmask\b"]),("Fins",[r"ตีนกบ",r"\bfins?\b"]),
   ("BCD",[r"\bbcd\b",r"buoyancy control device"]),("Regulator",[r"\bregulator\b",r"เรกูเลเตอร์"]),
   ("Dive Computer",[r"dive computer",r"คอมพิวเตอร์ดำน้ำ"]),("Wetsuit",[r"\bwetsuit\b",r"เว็ทสูท"]),
   ("SMB",[r"\bsmb\b",r"surface marker buoy"]),("Weights",[r"weight belt",r"ตุ้มถ่วง"])
 ],
 "Certification":[
   ("PADI Open Water",[r"padi.{0,15}open water",r"open water diver"]),
   ("SSI Open Water",[r"ssi.{0,15}open water"]),("Advanced Open Water",[r"advanced open water",r"\baow\b"]),
   ("Rescue Diver",[r"rescue diver"]),("Divemaster",[r"divemaster"])
 ],
 "Organization":[("PADI",[r"\bpadi\b"]),("SSI",[r"\bssi\b"])],
}
CLAIM_CUES=[
 ("recommendation",r"แนะนำ|ควร|recommend|best for|เหมาะ"),
 ("safety",r"ปลอดภัย|safety|อันตราย|danger|buddy check|safety stop"),
 ("cost",r"ราคา|บาท|cost|price|แพง|ถูก"),
 ("process",r"ขั้นตอน|process|briefing|debrief|ก่อนลงน้ำ|หลังดำน้ำ"),
 ("requirement",r"ต้อง|จำเป็น|required|must|prerequisite"),
]
STOP=set("the a an and or to of in for is are was were this that it you i we they กับ และ หรือ ที่ ใน เป็น มี ของ ให้ ได้ จะ จาก".split())

def clean(x):return re.sub(r"\s+"," ",str(x or "")).strip()
def units(text):
    return [clean(x) for x in re.split(r"(?<=[.!?])\s+|\n+",str(text or "")) if len(clean(x))>=12]

def extract_entities(text):
    out=[]
    for etype,defs in ENTITY_RULES.items():
        for canonical,pats in defs:
            hits=[]
            for p in pats:
                hits += [m.group(0) for m in re.finditer(p,text,re.I)]
            if hits:
                out.append({"entity_type":etype,"canonical_name":canonical,"mentions":hits[:10],
                            "count":len(hits),"confidence":round(min(.72+.05*len(hits),.97),2)})
    return sorted(out,key=lambda x:(-x["count"],x["entity_type"],x["canonical_name"]))

def extract_claims(text,authority_class="unclassified"):
    out=[]
    for u in units(text):
        types=[t for t,p in CLAIM_CUES if re.search(p,u,re.I)]
        if not types:continue
        ents=extract_entities(u)
        out.append({"statement":u,"claim_types":types,"entities":ents,
                    "authority_class":authority_class,"confidence":.62 if authority_class=="community-experience" else .76})
    return out

def emerging_terms(texts,min_docs=2,top_n=30):
    df=Counter();examples=defaultdict(list)
    for text in texts:
        toks=set(re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}|[ก-๙]{4,}",str(text).lower()))
        toks={t for t in toks if t not in STOP and not t.isdigit()}
        for t in toks:
            df[t]+=1
            if len(examples[t])<3:examples[t].append(clean(str(text))[:180])
    return [{"term":t,"document_frequency":n,"examples":examples[t]} for t,n in df.most_common()
            if n>=min_docs][:top_n]

def agreement_key(statement):
    s=re.sub(r"\d+(?:\.\d+)?","<n>",statement.lower())
    s=re.sub(r"[^\wก-๙]+"," ",s)
    words=[w for w in s.split() if w not in STOP]
    return " ".join(words[:14])

def source_agreement(items):
    groups=defaultdict(list)
    for x in items:
        key=agreement_key(x.get("statement",""))
        if key:groups[key].append(x)
    out=[]
    for k,xs in groups.items():
        src={x.get("source_type","unknown") for x in xs}
        auth={x.get("authority_class","unclassified") for x in xs}
        if len(xs)>=2:
            out.append({"normalized_claim":k,"evidence_count":len(xs),"source_types":sorted(src),
                        "authority_classes":sorted(auth),"cross_source":len(src)>1,
                        "examples":[x.get("statement","") for x in xs[:4]]})
    return sorted(out,key=lambda x:(-x["cross_source"],-x["evidence_count"],x["normalized_claim"]))
