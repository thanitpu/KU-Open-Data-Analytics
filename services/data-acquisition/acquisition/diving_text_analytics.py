from __future__ import annotations
import re,math
from collections import Counter

TOPIC_RULES={
"Beginner":[r"มือใหม่",r"beginner",r"first dive",r"ครั้งแรก",r"เริ่มดำน้ำ"],
"Process":[r"ขั้นตอน",r"process",r"ก่อนลง",r"หลังดำน้ำ",r"brief",r"debrief"],
"Training":[r"เรียน",r"training",r"course",r"open water",r"confined",r"skill"],
"Safety":[r"ปลอดภัย",r"safety",r"buddy check",r"safety stop",r"emergency",r"อันตราย"],
"Equipment":[r"อุปกรณ์",r"equipment",r"gear",r"mask",r"fins?",r"bcd",r"regulator",r"wetsuit",r"computer"],
"Dive Site":[r"เกาะเต่า",r"koh tao",r"dive site",r"จุดดำน้ำ",r"ชุมพรพินนาเคิล",r"sail rock"],
"Travel":[r"เดินทาง",r"ferry",r"เรือ",r"ที่พัก",r"travel",r"hotel"],
"Cost":[r"ราคา",r"บาท",r"ค่าใช้จ่าย",r"cost",r"price",r"แพง",r"ถูก"],
"Certification":[r"padi",r"ssi",r"certif",r"ใบรับรอง",r"license"],
"Recommendation":[r"แนะนำ",r"ควร",r"recommend",r"worth",r"เหมาะ"],
"Problem":[r"ปัญหา",r"กังวล",r"กลัว",r"เจ็บ",r"problem",r"issue",r"anxiety",r"difficult"],
"Equalization":[r"equaliz",r"เคลียร์หู",r"หูอื้อ",r"เจ็บหู"],
"Mask Fogging":[r"fog",r"ฝ้า",r"หน้ากาก.*มัว"],
"Seasickness":[r"เมาเรือ",r"seasick",r"motion sickness"],
"Buoyancy":[r"buoyancy",r"ลอยตัว",r"การทรงตัว"],
"Air Consumption":[r"air consumption",r"อากาศหมด",r"กินอากาศ",r"ถัง.*หมด"],
}
JOURNEY_RULES={
"Interest":[r"สนใจ",r"อยากลอง",r"interested"],
"Snorkeling Experience":[r"snorkel"],
"Discover Scuba":[r"discover scuba",r"try dive",r"ทดลองดำน้ำ"],
"Choose Certification":[r"padi|ssi|certif"],
"Choose Dive School":[r"dive school|ร้านดำน้ำ|โรงเรียนดำน้ำ|เลือก.*ร้าน"],
"Medical / Prerequisites":[r"medical|สุขภาพ|ว่ายน้ำ|prerequisite"],
"Theory":[r"theory|ทฤษฎี|e-learning"],
"Equipment Orientation":[r"equipment|gear|อุปกรณ์|mask|bcd|regulator"],
"Confined-water Training":[r"confined|สระ|pool session"],
"Open-water Dive":[r"open water|ทะเลจริง"],
"Dive Briefing":[r"briefing|บรีฟ"],
"Buddy Check":[r"buddy check|bwraf|เช็ค.*บัดดี้"],
"Entry":[r"entry|ลงน้ำ|giant stride|back roll"],
"Dive":[r"ระหว่างดำน้ำ|underwater|ใต้น้ำ"],
"Safety Stop":[r"safety stop|หยุดนิรภัย"],
"Exit":[r"exit|ขึ้นเรือ|ขึ้นจากน้ำ"],
"Debrief":[r"debrief|สรุปหลัง"],
"Certification":[r"certified|certification|สอบผ่าน|ใบรับรอง"],
"Buy / Rent Equipment":[r"ซื้อ|เช่า|rent|buy|ราคา|shop"],
"Choose Next Dive Destination":[r"next dive|ทริปต่อไป|จุดดำน้ำ|dive site|เกาะเต่า|sail rock"],
}
POS=[r"ดี",r"ชอบ",r"สนุก",r"สวย",r"ง่าย",r"แนะนำ",r"great",r"good",r"love",r"amazing",r"recommend"]
NEG=[r"แย่",r"กลัว",r"เจ็บ",r"แพง",r"ยาก",r"อันตราย",r"bad",r"scared",r"pain",r"expensive",r"difficult",r"danger"]
QUESTION=[r"\?",r"ไหม",r"มั้ย",r"อย่างไร",r"ยังไง",r"ที่ไหน",r"เท่าไร",r"ควร.*ไหม",r"\bhow\b",r"\bwhat\b",r"\bwhere\b",r"\bwhich\b"]

def clean(x):return re.sub(r"\s+"," ",str(x or "")).strip()

def split_units(text):
    x=str(text or "").replace("\r","\n")
    units=[]
    for para in re.split(r"\n+",x):
        para=clean(para)
        if not para:continue
        parts=re.split(r"(?<=[.!?])\s+|(?<=ครับ)\s+|(?<=ค่ะ)\s+",para)
        units.extend([clean(z) for z in parts if len(clean(z))>=8])
    return units

def score_rules(text,rules):
    low=text.lower();out=[]
    for label,pats in rules.items():
        hits=sum(1 for p in pats if re.search(p,low,re.I))
        if hits:out.append({"label":label,"hits":hits,"confidence":round(min(.55+.12*hits,.95),2)})
    return sorted(out,key=lambda z:(-z["hits"],z["label"]))

def sentiment(text):
    p=sum(bool(re.search(x,text,re.I)) for x in POS);n=sum(bool(re.search(x,text,re.I)) for x in NEG)
    if p>n:return "positive"
    if n>p:return "negative"
    return "neutral"

def opinion_type(text):
    if any(re.search(x,text,re.I) for x in QUESTION):return "question"
    if re.search(r"แนะนำ|ควร|recommend|worth",text,re.I):return "recommendation"
    if re.search(r"เตือน|ระวัง|อันตราย|warning|danger",text,re.I):return "warning"
    if re.search(r"ปัญหา|กังวล|กลัว|เจ็บ|problem|issue|difficult",text,re.I):return "pain-point"
    return "experience"

def analyze(text,max_units=250):
    units=split_units(text)[:max_units];opinions=[];topic_counts=Counter();journey_counts=Counter()
    for u in units:
        topics=score_rules(u,TOPIC_RULES);journey=score_rules(u,JOURNEY_RULES)
        for x in topics:topic_counts[x["label"]]+=1
        for x in journey:journey_counts[x["label"]]+=1
        typ=opinion_type(u)
        if topics or typ!="experience":
            opinions.append({"statement":u,"sentiment":sentiment(u),"opinion_type":typ,
              "topics":topics,"journey_steps":journey,
              "confidence":round(max([x["confidence"] for x in topics] or [.5]),2)})
    return {"units":len(units),"opinions":opinions,
      "topic_counts":[{"topic":k,"count":v} for k,v in topic_counts.most_common()],
      "journey_counts":[{"step":k,"count":v} for k,v in journey_counts.most_common()],
      "questions":[x for x in opinions if x["opinion_type"]=="question"],
      "pain_points":[x for x in opinions if x["opinion_type"]=="pain-point"],
      "recommendations":[x for x in opinions if x["opinion_type"]=="recommendation"]}
