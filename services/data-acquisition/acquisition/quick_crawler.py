from __future__ import annotations
from urllib.parse import urlparse
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/"adapters"))
sys.path.insert(0,str(HERE))
from wongnai_adapter import crawl as crawl_wongnai
from quick_sample_retriever import retrieve as generic_retrieve, access_recommendation
from record_metadata import enrich_record
from record_quality import enrich_quality

def crawl(url,business_name="",data_type="generic",limit=20):
    domain=(urlparse(url).netloc or "").lower().removeprefix("www.")
    if "wongnai.com" in domain:
        mapped="similar_businesses" if data_type=="similar_businesses" else data_type
        r=crawl_wongnai(url,business_name,mapped,limit)
    else:
        r=generic_retrieve(url,data_type,limit)
        r["adapter"]="generic-public-html-v1"
        r["accessRecommendation"]=access_recommendation(domain,data_type,r["retrievalStatus"])
    r["records"]=[
        enrich_quality(enrich_record(x,domain=domain,data_type=data_type),business_name)
        for x in r.get("records",[])
    ]
    return r
