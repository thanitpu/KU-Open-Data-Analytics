from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def purposes():
    return json.loads((ROOT/"config"/"acquisition_purposes.json").read_text(encoding="utf-8"))["purposes"]

def route(domain,purpose,source_type="web"):
    # One acquisition platform, multiple downstream interpretations.
    downstream=[]
    if purpose=="retail_market_intelligence":
        downstream=["commerce_entity_resolution","listing_price_promotion","marketplace_signal"]
    elif purpose=="knowledge_learning":
        downstream=["knowledge_content","topic_entity_opinion","journey_mapping"]
    elif purpose=="voice_of_customer":
        downstream=["text_analytics","opinion_painpoint_question","claim_extraction"]
    elif purpose=="evidence_verification":
        downstream=["passage_retrieval","stance_verification","evidence_weighting"]
    elif purpose=="competitive_intelligence":
        downstream=["business_offering","price_promotion","claim_extraction"]
    elif purpose=="destination_service_intelligence":
        downstream=["place_service","experience","price_availability","claim_extraction"]
    else:downstream=["document_archive","claim_extraction"]
    return {"domain":domain,"purpose":purpose,"source_type":source_type,"downstream":downstream}

def compatible_purposes(domain):
    return [x for x in purposes() if domain in x["domains"] or "general" in x["domains"]]
