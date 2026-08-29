from __future__ import annotations
import re, json, math
from difflib import SequenceMatcher

UNIT_MAP={
 "ml":"ml","มล":"ml","มล.":"ml","milliliter":"ml","milliliters":"ml",
 "l":"l","liter":"l","litre":"l","ลิตร":"l",
 "g":"g","กรัม":"g","kg":"kg","กก":"kg","กก.":"kg",
 "gb":"gb","tb":"tb","oz":"oz","pcs":"pcs","pc":"pcs","ชิ้น":"pcs"
}

STOPWORDS={"the","and","with","for","of","new","pack","แพ็ค","ชุด","สินค้า","ของ","พร้อม","แบบ"}

def normalize_text(text):
    s=str(text or "").lower()
    # Common Thai/English retail equivalents. This is deliberately conservative:
    # it standardizes descriptive terms, not brands/models.
    synonyms={
      "นมยูเอชที":"uht milk","ยูเอชที":"uht","รสจืด":"plain",
      "มิลลิลิตร":"ml","มล.":"ml","มล":"ml","ลิตร":"l",
      "กรัม":"g","กิโลกรัม":"kg","แพ็ค":"pack","ชิ้น":"pcs",
      "ซื้อ 1 แถม 1":"buy 1 get 1","ซื้อ1แถม1":"buy 1 get 1"
    }
    for a,b in synonyms.items(): s=s.replace(a,b)
    s=s.replace("dutchmill","dutch mill")
    s=s.replace("×","x").replace("–","-").replace("—","-")
    s=re.sub(r"(?<=\d),(?=\d)","",s)
    s=re.sub(r"([0-9])([a-zA-Zก-๙])",r"\1 \2",s)
    s=re.sub(r"([a-zA-Zก-๙])([0-9])",r"\1 \2",s)
    s=re.sub(r"[()\[\]{}:/,_+]+"," ",s)
    s=re.sub(r"\s+"," ",s).strip()
    return s

def _num(x):
    try:return float(str(x).replace(",",""))
    except:return None

def extract_attributes(text):
    s=normalize_text(text)
    out={}
    # storage / memory first
    m=re.search(r"\b(\d+(?:\.\d+)?)\s*(tb|gb)\b",s)
    if m:
        out["storage_value"]=_num(m.group(1));out["storage_unit"]=m.group(2)
    # volume/weight
    vals=[]
    for m in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(ml|มล\.?|l|ลิตร|g|กรัม|kg|กก\.?|oz)\b",s):
        unit=UNIT_MAP.get(m.group(2),m.group(2))
        vals.append((_num(m.group(1)),unit))
    if vals:
        out["measure_value"],out["measure_unit"]=vals[-1]
    # pack counts: x6, 6 pack, pack 6, 6 pcs
    pats=[
      r"\bx\s*(\d+)\b",r"\b(\d+)\s*x\b",
      r"\bpack\s*(\d+)\b",r"\b(\d+)\s*pack\b",
      r"\bแพ็ค\s*(\d+)\b",r"\b(\d+)\s*แพ็ค\b",
      r"\b(\d+)\s*(?:pcs|pc|ชิ้น)\b"
    ]
    for p in pats:
        m=re.search(p,s)
        if m:
            out["pack_count"]=int(m.group(1));break
    # color/shade/model-ish signals
    m=re.search(r"(?:#|shade\s*|สี\s*)([a-z0-9\-]+)",s)
    if m:out["shade_or_color"]=m.group(1)
    # model tokens containing digits/letters e.g. iphone 17 pro, rtx 5070, sm-s938
    model_tokens=re.findall(r"\b[a-z]{1,8}[- ]?\d{2,5}[a-z0-9\-]*\b",s)
    if model_tokens:out["model_tokens"]=model_tokens[:5]
    return out

def normalize_units(attrs):
    x=dict(attrs or {})
    if x.get("measure_unit")=="l":
        x["measure_value"]=round(float(x["measure_value"])*1000,6);x["measure_unit"]="ml"
    elif x.get("measure_unit")=="kg":
        x["measure_value"]=round(float(x["measure_value"])*1000,6);x["measure_unit"]="g"
    elif x.get("storage_unit")=="tb":
        x["storage_value"]=round(float(x["storage_value"])*1024,6);x["storage_unit"]="gb"
    return x

def tokens(text):
    s=normalize_text(text)
    arr=[x for x in re.findall(r"[a-zA-Zก-๙0-9]+",s) if x not in STOPWORDS and len(x)>1]
    return arr

def token_jaccard(a,b):
    A=set(tokens(a));B=set(tokens(b))
    if not A or not B:return 0.0
    return len(A&B)/len(A|B)

def sequence_similarity(a,b):
    return SequenceMatcher(None,normalize_text(a),normalize_text(b)).ratio()

def attribute_conflicts(a,b):
    a=normalize_units(a);b=normalize_units(b);conf=[]
    for value_key,unit_key,label,tol in [
      ("measure_value","measure_unit","measure",0.01),
      ("storage_value","storage_unit","storage",0.01)
    ]:
        if value_key in a and value_key in b:
            if a.get(unit_key)==b.get(unit_key) and abs(float(a[value_key])-float(b[value_key]))>tol:
                conf.append(f"{label}-conflict:{a[value_key]}{a.get(unit_key)}!={b[value_key]}{b.get(unit_key)}")
    if "pack_count" in a and "pack_count" in b and int(a["pack_count"])!=int(b["pack_count"]):
        conf.append(f"pack-conflict:{a['pack_count']}!={b['pack_count']}")
    if a.get("shade_or_color") and b.get("shade_or_color") and a["shade_or_color"]!=b["shade_or_color"]:
        conf.append(f"shade-color-conflict:{a['shade_or_color']}!={b['shade_or_color']}")
    # model-token conflict only when both have a clear model token and no overlap.
    am=set(a.get("model_tokens") or []);bm=set(b.get("model_tokens") or [])
    if am and bm and not (am&bm):
        conf.append("model-conflict")
    return conf

def similarity(raw_name,canonical_name,raw_attrs=None,canonical_attrs=None):
    ra=raw_attrs or extract_attributes(raw_name)
    ca=canonical_attrs or extract_attributes(canonical_name)
    conflicts=attribute_conflicts(ra,ca)
    tj=token_jaccard(raw_name,canonical_name)
    seq=sequence_similarity(raw_name,canonical_name)
    # Weight lexical evidence while allowing multilingual/format differences.
    base=.58*tj+.42*seq
    # Matching structured attributes increase confidence.
    bonus=0.0
    for k in ["measure_value","pack_count","storage_value","shade_or_color"]:
        if k in normalize_units(ra) and k in normalize_units(ca) and normalize_units(ra)[k]==normalize_units(ca)[k]:
            bonus+=.045
    score=min(1.0,base+bonus)
    if conflicts:score=min(score,.49)
    return {"score":round(score,4),"token_jaccard":round(tj,4),"sequence_similarity":round(seq,4),
            "conflicts":conflicts,"raw_attributes":ra,"canonical_attributes":ca}

def classify(score,conflicts):
    if conflicts:return "do-not-match"
    if score>=.90:return "auto-match"
    if score>=.72:return "review"
    return "new-candidate"

def resolve_against_candidates(raw_name,candidates,raw_attrs=None,top_n=5):
    out=[]
    for c in candidates:
        r=similarity(raw_name,c.get("canonical_name",""),raw_attrs,c.get("attributes") or {})
        r.update({"canonical_product_id":c.get("canonical_product_id"),"canonical_name":c.get("canonical_name"),
                  "brand":c.get("brand"),"category":c.get("category")})
        r["decision"]=classify(r["score"],r["conflicts"])
        out.append(r)
    out.sort(key=lambda x:x["score"],reverse=True)
    return out[:top_n]
